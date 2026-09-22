"""Stock report: how fast this company is growing now, and what that implies over five years."""
from __future__ import annotations

import streamlit as st

from shared import (
    C_ACCENT,
    C_MUTED,
    C_NEGATIVE,
    C_POSITIVE,
    C_PRIMARY,
    PILLAR_LABELS,
    SCENARIO_LABELS,
    currency_warning,
    data_quality_note,
    fmt_money,
    fmt_num,
    fmt_pct,
    fmt_x,
    growth_word,
    load_bundle,
    render_pipeline_result,
    run_pipeline,
    sector_caveats,
    snapshot_dates,
    tickers_on_disk,
)


def growth_headline(m, prof):
    """The question the page exists to answer: how fast is it growing right now."""
    st.subheader("ตอนนี้เติบโตเท่าไหร่")

    ttm = m.get("revenue_growth_ttm")
    cagr = m.get("revenue_cagr")
    yrs = m.get("revenue_cagr_years") or "?"
    earn = m.get("earnings_growth_ttm")
    fwd = m.get("forward_eps_growth")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("รายได้ เทียบปีก่อน", fmt_pct(ttm), growth_word(ttm), delta_color="off")
    c2.metric("รายได้ เฉลี่ยต่อปี {} ปี".format(yrs), fmt_pct(cagr), growth_word(cagr), delta_color="off")
    c3.metric("กำไร เทียบปีก่อน", fmt_pct(earn), growth_word(earn), delta_color="off")
    c4.metric("กำไรต่อหุ้น คาดการณ์ข้างหน้า", fmt_pct(fwd), growth_word(fwd), delta_color="off")

    if ttm is not None and cagr is not None:
        if ttm > cagr * 1.3:
            st.caption(
                "การเติบโตปีล่าสุดสูงกว่าค่าเฉลี่ยย้อนหลังอย่างชัดเจน "
                "ควรตรวจว่ามาจากฐานที่ต่ำผิดปกติ การเข้าซื้อกิจการ หรืออุปสงค์ที่เปลี่ยนไปจริง"
            )
        elif ttm < cagr * 0.6:
            st.caption(
                "การเติบโตปีล่าสุดต่ำกว่าค่าเฉลี่ยย้อนหลังชัดเจน "
                "เป็นสัญญาณว่าวงจรธุรกิจกำลังชะลอ หรือฐานเดิมใหญ่ขึ้นจนโตยาก"
            )

    st.caption(
        "ตัวเลขทั้งหมดมาจากงบการเงินที่บริษัทรายงาน สกุลเงิน {} "
        "การเติบโตของกำไรต่อหุ้นข้างหน้าเป็นค่าประมาณของนักวิเคราะห์ ไม่ใช่ตัวเลขที่เกิดขึ้นจริง".format(
            prof.get("financial_currency") or prof.get("currency") or "?"
        )
    )


def history_chart(f):
    import plotly.graph_objects as go

    a = (f or {}).get("annual") or {}
    periods = a.get("periods") or []
    if not periods:
        st.info("ไม่มีงบการเงินรายปีสำหรับหุ้นตัวนี้")
        return

    rev = a.get("revenue") or []
    gp = a.get("gross_profit") or []
    oi = a.get("operating_income") or []
    ni = a.get("net_income") or []
    fcf = a.get("free_cash_flow") or []

    def pad(x):
        return list(x) + [None] * (len(periods) - len(x))

    fig = go.Figure()
    fig.add_bar(x=periods, y=pad(rev), name="รายได้", marker_color=C_PRIMARY)
    fig.add_bar(x=periods, y=pad(gp), name="กำไรขั้นต้น", marker_color=C_ACCENT)
    fig.add_bar(x=periods, y=pad(oi), name="กำไรจากการดำเนินงาน", marker_color=C_POSITIVE)
    fig.add_scatter(
        x=periods, y=pad(ni), name="กำไรสุทธิ", mode="lines+markers",
        line=dict(color="#f59e0b", width=3),
    )
    fig.add_scatter(
        x=periods, y=pad(fcf), name="กระแสเงินสดอิสระ", mode="lines+markers",
        line=dict(color=C_MUTED, width=2, dash="dot"),
    )
    fig.update_layout(
        barmode="group",
        height=380,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
    )
    fig.update_yaxes(title=None)
    st.plotly_chart(fig, width="stretch")


def margin_chart(f):
    import plotly.graph_objects as go

    a = (f or {}).get("annual") or {}
    periods = a.get("periods") or []
    rev = a.get("revenue") or []
    if not periods or not any(rev):
        return

    def ratio(nums):
        nums = list(nums) + [None] * (len(periods) - len(nums))
        out = []
        for n, r in zip(nums, rev):
            out.append(None if (n is None or not r) else n / r * 100)
        return out

    fig = go.Figure()
    fig.add_scatter(x=periods, y=ratio(a.get("gross_profit") or []), name="ขั้นต้น",
                    mode="lines+markers", line=dict(color=C_ACCENT, width=3))
    fig.add_scatter(x=periods, y=ratio(a.get("operating_income") or []), name="ดำเนินงาน",
                    mode="lines+markers", line=dict(color=C_POSITIVE, width=3))
    fig.add_scatter(x=periods, y=ratio(a.get("net_income") or []), name="สุทธิ",
                    mode="lines+markers", line=dict(color="#f59e0b", width=3))
    fig.add_scatter(x=periods, y=ratio(a.get("free_cash_flow") or []), name="เงินสดอิสระ",
                    mode="lines+markers", line=dict(color=C_MUTED, width=2, dash="dot"))
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
        yaxis=dict(ticksuffix="%"),
    )
    st.plotly_chart(fig, width="stretch")


def scorecard(s):
    import plotly.graph_objects as go

    composite = s.get("composite_score")
    st.subheader("คะแนนรวม {} · {}".format(fmt_num(composite), s.get("grade") or ""))

    pillars = s.get("pillars") or {}
    names, vals, weights = [], [], []
    for key, d in pillars.items():
        if d.get("score") is None:
            continue
        names.append(PILLAR_LABELS.get(key, key))
        vals.append(d["score"])
        weights.append(d.get("weight", 0))

    if not names:
        st.info("คำนวณคะแนนไม่ได้ ข้อมูลไม่เพียงพอ")
        return

    colors = [C_POSITIVE if v >= 70 else (C_PRIMARY if v >= 50 else C_NEGATIVE) for v in vals]
    fig = go.Figure(
        go.Bar(
            x=vals, y=names, orientation="h", marker_color=colors,
            text=["{:.0f}".format(v) for v in vals], textposition="outside",
            hovertemplate="%{y}: %{x:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=250, margin=dict(l=10, r=40, t=10, b=10),
        xaxis=dict(range=[0, 108], title=None), yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, width="stretch")

    cols = st.columns(len(names))
    for col, key in zip(cols, [k for k, d in pillars.items() if d.get("score") is not None]):
        d = pillars[key]
        mets = d.get("metrics") or {}
        scored = [(k, v) for k, v in mets.items() if v.get("score") is not None]
        if scored:
            weakest = min(scored, key=lambda kv: kv[1]["score"])
            col.caption("{} · จุดอ่อนสุดคือ {}".format(PILLAR_LABELS.get(key, key), weakest[0]))

    if s.get("flags"):
        st.markdown("**สิ่งที่ตัวเลขเตือน**")
        for x in s["flags"]:
            st.markdown("- " + x)


def scenarios(s):
    import plotly.graph_objects as go

    scen = (s or {}).get("projection_5y") or {}
    if not scen:
        st.info("ฉายภาพ 5 ปีไม่ได้ ขาดข้อมูลที่จำเป็น")
        return

    st.subheader("ภาพ 5 ปีข้างหน้า")

    cols = st.columns(3)
    for col, key in zip(cols, ("bear", "base", "bull")):
        v = scen.get(key)
        if not v:
            continue
        ann = v["annualized_return"]
        col.metric(
            "กรณี{}".format(SCENARIO_LABELS[key]),
            "{:+.1f}% ต่อปี".format(ann * 100),
            "รวม {:+.0f}%".format(v["total_return"] * 100),
            delta_color="off",
        )

    base = scen.get("base")
    if base:
        fig = go.Figure()
        for key, color in (("bear", C_NEGATIVE), ("base", C_PRIMARY), ("bull", C_POSITIVE)):
            v = scen.get(key)
            if not v:
                continue
            years = [0] + [p["year"] for p in v["revenue_path"]]
            idx = [1.0] + [p["revenue_index"] for p in v["revenue_path"]]
            fig.add_scatter(
                x=years, y=idx, name="กรณี{}".format(SCENARIO_LABELS[key]),
                mode="lines+markers", line=dict(color=color, width=3),
            )
        fig.update_layout(
            height=300, margin=dict(l=10, r=10, t=30, b=10),
            xaxis=dict(title="ปีข้างหน้า", dtick=1),
            yaxis=dict(title="ดัชนีรายได้ (ปีนี้ = 1.0)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            hovermode="x unified",
        )
        st.plotly_chart(fig, width="stretch")

    rows = []
    for key in ("bear", "base", "bull"):
        v = scen.get(key)
        if not v:
            continue
        a = v["assumptions"]
        rows.append(
            {
                "กรณี": SCENARIO_LABELS[key],
                "โตเริ่มต้น": fmt_pct(a["start_growth"]),
                "โตปลายทาง": fmt_pct(a["terminal_growth"]),
                "มาร์จิ้นสุทธิปลายทาง": fmt_pct(a["end_net_margin"]),
                "P/E ตอนขาย": fmt_num(a["exit_pe"]),
                "รายได้โตรวม": "{:.2f} เท่า".format(v["revenue_index_end"]),
                "ผลตอบแทนต่อปี": "{:+.1f}%".format(v["annualized_return"] * 100),
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)

    basis = ((scen.get("base") or {}).get("assumptions") or {}).get("sales_multiple_basis")
    st.caption(
        "โมเดลนี้ให้อัตราการเติบโตปัจจุบันค่อยๆ ลดลงสู่อัตราปลายทาง มาร์จิ้นเคลื่อนตามเทรนด์ของตัวเอง "
        "แล้วตีมูลค่าด้วย P/E ตอนขาย ตัวเลขที่ได้เป็นผลทางคณิตศาสตร์ของสมมติฐานในตาราง "
        "ไม่ใช่การพยากรณ์ราคา เปลี่ยนสมมติฐานตัวเลขก็เปลี่ยน"
        + ("  ฐานที่ใช้คำนวณมูลค่าปัจจุบัน: {}".format(basis) if basis else "")
    )


def metrics_grid(m, prof):
    # An ADR trades in one currency and reports in another, so these three
    # divide a market number by a statement number in different units. Showing
    # TSM a 44% free cash flow yield is worse than showing nothing.
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent / "tools"))
    from score import drop_currency_contaminated  # noqa: E402

    m, _dropped = drop_currency_contaminated(m)
    st.subheader("ตัวเลขสำคัญ")
    cur = prof.get("financial_currency") or prof.get("currency") or ""

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**ความสามารถทำกำไร**")
        st.write("มาร์จิ้นขั้นต้น", fmt_pct(m.get("gross_margin_latest")))
        st.write("มาร์จิ้นดำเนินงาน", fmt_pct(m.get("operating_margin_latest")))
        st.write("มาร์จิ้นสุทธิ", fmt_pct(m.get("net_margin_latest")))
        st.write("มาร์จิ้นเงินสดอิสระ", fmt_pct(m.get("fcf_margin_latest")))
        trend = m.get("operating_margin_trend")
        st.write("ทิศทางมาร์จิ้นต่อปี", fmt_pct(trend, 2) if trend is not None else "n/a")
    with c2:
        st.markdown("**ผลตอบแทนและฐานะการเงิน**")
        st.write("ROIC ประมาณการ", fmt_pct(m.get("roic_est")))
        st.write("ROE", fmt_pct(m.get("roe")))
        st.write("หนี้สุทธิ", fmt_money(m.get("net_debt"), cur))
        st.write("หนี้สุทธิ / EBITDA", fmt_x(m.get("net_debt_to_ebitda")))
        st.write("current ratio", fmt_num(m.get("current_ratio"), 2))
    with c3:
        st.markdown("**ความถูกแพง**")
        st.write("P/E ล่าสุด", fmt_num(m.get("trailing_pe")))
        st.write("P/E ข้างหน้า", fmt_num(m.get("forward_pe")))
        st.write("PEG ประมาณการ", fmt_num(m.get("peg_est"), 2))
        st.write("EV / EBITDA", fmt_num(m.get("ev_to_ebitda")))
        st.write("FCF yield", fmt_pct(m.get("fcf_yield"), 2))
        if _dropped:
            st.caption(
                "ซื้อขายเป็น {} แต่รายงานงบเป็น {} ตัวเลข EV/EBITDA, P/S และ FCF yield "
                "จึงเอาค่าตลาดหารด้วยค่างบคนละสกุล ระบบตัดออกแทนที่จะแสดงค่าที่ผิด"
                "ตามอัตราแลกเปลี่ยน".format(
                    m.get("trading_currency") or "สกุลหนึ่ง",
                    m.get("financial_currency") or "อีกสกุลหนึ่ง")
            )


def peer_block(ticker):
    """Where this company sits among its sector, next to its absolute score."""
    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / "tools"))
    from peers import absolute_vs_relative

    try:
        ctx = absolute_vs_relative(ticker)
    except Exception as e:
        st.error("เทียบคู่แข่งไม่สำเร็จ {}: {}".format(type(e).__name__, e))
        return

    if not ctx.get("ok"):
        st.info(ctx.get("reason", "เทียบไม่ได้"))
        return

    st.subheader("เทียบกับกลุ่ม {}".format(ctx["group"]))
    st.caption(
        "คะแนนห้าเสาใช้เกณฑ์สัมบูรณ์ ซึ่งทำให้เทียบข้ามอุตสาหกรรมได้ แต่แลกมาด้วยการที่เกณฑ์ไม่รู้ว่า "
        "อะไรคือเรื่องปกติของอุตสาหกรรมนั้น มาร์จิ้นขั้นต้น 75% เป็นเรื่องธรรมดาของซอฟต์แวร์ "
        "แต่เหลือเชื่อสำหรับผู้ผลิตรถยนต์ หน้านี้เติมอีกครึ่งที่ขาดไป คือบริษัทนี้อยู่ตรงไหนในกลุ่มของตัวเอง"
    )

    if not ctx["reliable"]:
        st.warning(
            "กลุ่มนี้มีแค่ {} บริษัทในเครื่อง เปอร์เซ็นไทล์จึงแทบไม่มีความหมาย "
            "ต้องมีอย่างน้อย {} ตัวถึงจะเริ่มอ่านได้ ดึงหุ้นในกลุ่มเดียวกันเพิ่มก่อน".format(
                ctx["n_in_group"], ctx["min_peers_needed"]
            ),
            icon=":material/group_off:",
        )
    else:
        st.caption("เทียบกับ {} ตัว: {}".format(len(ctx["peers"]), ", ".join(ctx["peers"])))

    dis = ctx.get("disagreements") or []
    if dis:
        st.markdown("**จุดที่เกณฑ์กลางกับกลุ่มของตัวเองไม่ตรงกัน**")
        for d in dis[:4]:
            st.markdown("- **{}** · {} (เกณฑ์กลางให้ {:.0f} แต่ในกลุ่มอยู่เปอร์เซ็นไทล์ที่ {:.0f}) — {}".format(
                d["label"], _peer_fmt(d["key"], d["value"]),
                d["absolute_score"], d["peer_percentile"], d["reading"]))
        st.caption(
            "นี่คือส่วนที่ควรอ่านที่สุด เพราะมันบอกว่าคะแนนที่เห็นมาจากตัวบริษัทเองหรือมาจากอุตสาหกรรมที่มันอยู่"
        )

    _peer_chart(ctx)

    rows = []
    for c in ctx["comparisons"]:
        rows.append(
            {
                "ตัวชี้วัด": c["label"],
                "ค่าของบริษัท": _peer_fmt(c["key"], c["value"]),
                "ค่ากลางของกลุ่ม": _peer_fmt(c["key"], c["peer_median"]),
                "เปอร์เซ็นไทล์": None if c["percentile"] is None else c["percentile"],
                "ทิศทางที่ดี": "สูงกว่าดี" if c["higher_is_better"] else "ต่ำกว่าดี",
            }
        )
    st.dataframe(
        rows, width="stretch", hide_index=True,
        column_config={"เปอร์เซ็นไทล์": st.column_config.ProgressColumn(
            "เปอร์เซ็นไทล์ในกลุ่ม", min_value=0, max_value=1, format="%.0f%%")},
    )
    st.caption(ctx["caveat"] + " ข้อมูล ณ {}".format(ctx.get("snapshot", "?")))


def _peer_fmt(key, v):
    if v is None:
        return "n/a"
    if key in ("forward_pe", "ev_to_ebitda", "price_to_sales", "net_debt_to_ebitda"):
        return "{:.1f}".format(v)
    return fmt_pct(v)


def _peer_chart(ctx):
    import plotly.graph_objects as go

    pts = [c for c in ctx["comparisons"] if c["percentile"] is not None]
    if len(pts) < 3:
        return
    labels = [c["label"] for c in pts][::-1]
    vals = [c["percentile"] * 100 for c in pts][::-1]
    colors = [C_POSITIVE if v >= 66 else (C_PRIMARY if v >= 33 else C_NEGATIVE) for v in vals]

    fig = go.Figure(
        go.Bar(x=vals, y=labels, orientation="h", marker_color=colors,
               text=["{:.0f}".format(v) for v in vals], textposition="outside",
               hovertemplate="%{y}: เปอร์เซ็นไทล์ที่ %{x:.0f}<extra></extra>")
    )
    fig.add_vline(x=50, line=dict(color=C_MUTED, width=2, dash="dot"),
                  annotation_text="ค่ากลางของกลุ่ม", annotation_position="top")
    fig.update_layout(
        height=max(280, 26 * len(pts)), margin=dict(l=10, r=40, t=30, b=10),
        xaxis=dict(range=[0, 108], title="เปอร์เซ็นไทล์ในกลุ่มเดียวกัน"),
        yaxis=dict(title=None),
    )
    st.plotly_chart(fig, width="stretch")


def news_block(n):
    if not n:
        st.info("ยังไม่ได้เก็บข่าวของหุ้นตัวนี้ กดปุ่มอัปเดตข้อมูลด้านบน")
        return

    s = n.get("summary") or {}
    lean = s.get("headline_lean") or {}
    tags = s.get("by_event_tag") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ข่าวที่เก็บได้", s.get("total", 0))
    c2.metric("พาดหัวเชิงบวก", lean.get("positive", 0))
    c3.metric("พาดหัวเชิงลบ", lean.get("negative", 0))
    c4.metric("ช่วงที่เก็บ", "{} วัน".format(n.get("lookback_days", "?")))

    if tags:
        st.caption("ประเภทเหตุการณ์ที่พบ: " + ", ".join("{} ({})".format(k, v) for k, v in tags.items()))

    all_tags = sorted(tags)
    picked = st.multiselect("กรองตามประเภท", all_tags, default=[], key="news_tag_filter")

    articles = n.get("articles") or []
    if picked:
        articles = [a for a in articles if set(a.get("tags") or []) & set(picked)]

    st.caption("แสดง {} จาก {} ชิ้น".format(min(len(articles), 40), len(n.get("articles") or [])))
    for a in articles[:40]:
        lean_mark = {"positive": "▲", "negative": "▼"}.get(a.get("lean"), "·")
        title = a.get("title") or "(ไม่มีพาดหัว)"
        url = a.get("url")
        line = "{} **{}**".format(lean_mark, title)
        st.markdown("[{}]({})".format(line, url) if url else line)
        st.caption(
            "{} · {} · {}".format(
                (a.get("published") or "")[:10],
                a.get("publisher") or "ไม่ระบุแหล่ง",
                ", ".join(a.get("tags") or []) or "ไม่ได้ติดแท็ก",
            )
        )

    st.caption(
        "การติดแท็กใช้การจับคำ จึงผิดพลาดได้เป็นปกติ ใช้เป็นตัวกรองชั้นแรกเท่านั้น ไม่ใช่คำตัดสิน"
    )


def filings_block(fl):
    if not fl:
        st.info(
            "ไม่มีเอกสารจาก SEC สำหรับหุ้นตัวนี้ "
            "หุ้นที่ไม่ได้จดทะเบียนในสหรัฐจะไม่มีข้อมูลใน EDGAR ซึ่งเป็นข้อจำกัดของแหล่งข้อมูล ไม่ใช่ของบริษัท"
        )
        return

    rows = [
        {
            "แบบ": r.get("form"),
            "วันยื่น": r.get("filed"),
            "รอบบัญชี": r.get("period") or "-",
            "ลิงก์": r.get("url"),
        }
        for r in (fl.get("filings") or [])[:12]
    ]
    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        column_config={"ลิงก์": st.column_config.LinkColumn("เอกสาร", display_text="เปิด")},
    )

    rf = fl.get("risk_factors") or {}
    if rf.get("error"):
        st.warning("ดึงหัวข้อความเสี่ยงไม่สำเร็จ: {}".format(rf["error"]))
        return
    if not rf.get("candidate_risk_headings"):
        return

    src = rf.get("from_filing") or {}
    st.markdown(
        "**ความเสี่ยงที่บริษัทระบุเองในแบบ {} ยื่นวันที่ {}**".format(
            src.get("form", "?"), src.get("filed", "?")
        )
    )
    st.caption(
        "นี่คือถ้อยคำที่บริษัทเขียนเองภายใต้ความรับผิดทางกฎหมาย จึงมีน้ำหนักมากกว่าบทความทั่วไป "
        "แต่บางข้อเป็นข้อความมาตรฐานที่ปรากฏในทุกบริษัท"
    )
    for h in rf["candidate_risk_headings"][:20]:
        st.markdown("- " + h)

    with st.expander("อ่านเนื้อหาความเสี่ยงฉบับเต็ม ({:,} ตัวอักษร)".format(rf.get("chars", 0))):
        st.text(rf.get("text", "")[:60000])
        if rf.get("source_url"):
            st.markdown("[เปิดเอกสารต้นฉบับ]({})".format(rf["source_url"]))


def render():
    st.title("รายงานหุ้นรายตัว")

    known = tickers_on_disk()
    default_tk = st.session_state.get("selected_ticker")

    c1, c2 = st.columns([3, 2])
    with c1:
        typed = st.text_input(
            "สัญลักษณ์หุ้น",
            value=default_tk or "",
            placeholder="เช่น NVDA, 7203.T, 0700.HK, PTT.BK",
            help="ใส่ได้ทุกตลาดทั่วโลก ถ้าไม่รู้สัญลักษณ์ ไปที่หน้าค้นหาหุ้น",
        ).strip().upper()
    with c2:
        if known:
            picked = st.selectbox(
                "หรือเลือกจากที่มีข้อมูลแล้ว",
                ["—"] + known,
                index=(known.index(default_tk) + 1) if (default_tk and default_tk in known) else 0,
            )
            if picked != "—" and picked != default_tk:
                typed = picked

    if not typed:
        st.info(
            "ใส่สัญลักษณ์หุ้นเพื่อเริ่ม ระบบรองรับหุ้นทุกตัวที่ Yahoo Finance มีข้อมูล "
            "ครอบคลุมตลาดหลักทั่วโลกรวมถึงตลาดหุ้นไทย"
        )
        return

    st.session_state["selected_ticker"] = typed

    with st.expander("อัปเดตข้อมูล", expanded=typed not in known):
        cc1, cc2, cc3 = st.columns([2, 2, 3])
        news_days = cc1.slider("ย้อนหลังข่าว (วัน)", 14, 365, 90, step=7)
        want_filings = cc2.checkbox("ดึงเอกสาร SEC", value=True,
                                    help="ใช้ได้กับหุ้นที่จดทะเบียนในสหรัฐเท่านั้น")
        if cc3.button("ดึงข้อมูลใหม่ทั้งหมด", type="primary", width="stretch"):
            bar = st.progress(0.0, text="เริ่ม...")
            steps = run_pipeline(
                typed, news_days=news_days, with_filings=want_filings,
                progress=lambda p, msg: bar.progress(p, text=msg),
            )
            bar.empty()
            render_pipeline_result(steps)
            st.cache_data.clear()

    b = load_bundle(typed)
    f, s, n, fl = b["fundamentals"], b["score"], b["news"], b["filings"]

    if not f:
        st.warning(
            "ยังไม่มีข้อมูลของ {} ในเครื่อง กดปุ่มดึงข้อมูลใหม่ด้านบนเพื่อเริ่ม".format(typed)
        )
        return

    prof = f.get("profile") or {}
    mkt = f.get("market") or {}
    ana = f.get("analyst") or {}
    m = f.get("metrics") or {}

    st.header("{} · {}".format(typed, prof.get("name") or "ไม่ทราบชื่อ"))
    st.caption(
        "{} · {} · {} · ตลาด {}".format(
            prof.get("sector") or "?", prof.get("industry") or "?",
            prof.get("country") or "?", prof.get("exchange") or "?",
        )
    )

    dates = snapshot_dates(typed)
    st.caption("ข้อมูล ณ วันที่ " + " · ".join(
        "{} {}".format(k, v or "ยังไม่มี") for k, v in dates.items()
    ))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ราคา", fmt_num(mkt.get("price"), 2, " " + (prof.get("currency") or "")))
    c2.metric("มูลค่าตลาด", fmt_money(mkt.get("market_cap"), prof.get("currency") or ""))
    c3.metric("ห่างจากจุดสูงสุด 52 สัปดาห์", fmt_pct(mkt.get("off_52w_high")))
    upside = ana.get("upside_to_target")
    c4.metric(
        "เทียบเป้านักวิเคราะห์",
        fmt_pct(upside),
        "{} คน · {}".format(ana.get("n_analysts") or "?", ana.get("recommendation") or "?"),
        delta_color="off",
    )

    currency_warning(f)
    sector_caveats(f)
    data_quality_note(f, s)

    st.divider()
    growth_headline(m, prof)

    tabs = st.tabs(["งบและมาร์จิ้น", "คะแนนและภาพ 5 ปี", "เทียบคู่แข่ง", "ตัวเลขสำคัญ",
                    "ข่าว", "เอกสารและความเสี่ยง", "ธุรกิจ"])

    with tabs[0]:
        st.markdown("**รายได้และกำไรย้อนหลัง** หน่วยตามสกุลเงินในงบ")
        history_chart(f)
        st.markdown("**อัตรากำไรย้อนหลัง** ทิศทางของเส้นสำคัญกว่าระดับ")
        margin_chart(f)

    with tabs[1]:
        if s:
            scorecard(s)
            st.divider()
            scenarios(s)
        else:
            st.info("ยังไม่ได้คำนวณคะแนน กดปุ่มอัปเดตข้อมูลด้านบน")

    with tabs[2]:
        peer_block(typed)

    with tabs[3]:
        metrics_grid(m, prof)

    with tabs[4]:
        news_block(n)

    with tabs[5]:
        filings_block(fl)

    with tabs[6]:
        if prof.get("summary"):
            st.write(prof["summary"])
        else:
            st.info("ไม่มีคำอธิบายธุรกิจจากแหล่งข้อมูล")
        cc1, cc2 = st.columns(2)
        cc1.write("พนักงาน: {}".format(
            "{:,}".format(prof["employees"]) if prof.get("employees") else "ไม่ระบุ"))
        if prof.get("website"):
            cc2.markdown("[เว็บไซต์บริษัท]({})".format(prof["website"]))

    st.divider()
    st.caption(
        "ข้อมูลงบการเงินและราคามาจาก Yahoo Finance ซึ่งเป็นข้อมูลดีเลย์และมีการแก้ย้อนหลัง "
        "เพียงพอสำหรับเปรียบเทียบเชิงโครงสร้างระยะปี แต่ไม่เหมาะกับการตัดสินใจที่อ่อนไหวต่อเวลา "
        "หน้านี้เป็นเครื่องมือวิจัย ไม่ใช่คำแนะนำการลงทุน"
    )
