"""Funds and ETFs: cost, risk, what they hold, and what they duplicate."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from shared import C_MUTED, C_NEGATIVE, C_POSITIVE, C_PRIMARY, fmt_money, fmt_num, fmt_pct

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from common import latest_snapshot, read_json, today, write_json  # noqa: E402

FUNDS = ROOT / "data" / "funds"
FUND_SCORES = ROOT / "data" / "fund_scores"

PILLAR_LABELS = {
    "cost": "ค่าธรรมเนียม",
    "risk_adjusted_return": "ผลตอบแทนเทียบความเสี่ยง",
    "diversification": "การกระจายตัว",
    "size": "ขนาดกองทุน",
    "income": "เงินปันผล",
}


def funds_on_disk():
    if not FUNDS.exists():
        return []
    return sorted(p.name for p in FUNDS.iterdir() if p.is_dir() and any(p.glob("*.json")))


def load_fund_score(fund):
    from score_funds import score_fund

    return score_fund(fund)


def fetch_and_score(symbols, progress=None):
    """Pull fresh data for these symbols and rescore them."""
    from fetch_funds import fetch_one
    from score_funds import score_fund

    done, failed = [], []
    for i, sym in enumerate(symbols):
        if progress:
            progress(i / len(symbols), "กำลังดึง {} ...".format(sym))
        try:
            payload = fetch_one(sym)
            write_json(FUNDS / sym.upper() / "{}.json".format(today()), payload)
            res = score_fund(sym)
            write_json(FUND_SCORES / sym.upper() / "{}.json".format(today()), res)
            done.append((sym.upper(), payload.get("is_fund", False),
                         payload.get("quote_type")))
        except Exception as e:
            failed.append((sym.upper(), "{}: {}".format(type(e).__name__, e)))
    if progress:
        progress(1.0, "เสร็จแล้ว")
    return done, failed


# --------------------------------------------------------------------------
# panels
# --------------------------------------------------------------------------

def ranking_panel(known):
    st.subheader("จัดอันดับกองทุน")
    st.caption(
        "น้ำหนักในการให้คะแนนตั้งใจให้ค่าธรรมเนียมสำคัญกว่าผลตอบแทนย้อนหลัง "
        "เพราะค่าธรรมเนียมเป็นตัวเลขเดียวที่รู้ล่วงหน้าแน่นอน ส่วนผลตอบแทนในอดีตเป็นตัวชี้อนาคตที่อ่อนที่สุด"
    )

    rows, errors = [], []
    for f in known:
        try:
            r = load_fund_score(f)
        except Exception as e:
            errors.append("{}: {}".format(f, e))
            continue
        p = r["pillars"]
        ov = (r.get("overlap_with_tracked") or {})
        rows.append({
            "กองทุน": r["ticker"],
            "ชื่อ": (r.get("name") or "?")[:28],
            "ประเภท": (r.get("category") or "?")[:18],
            "คะแนนรวม": r["composite_score"],
            PILLAR_LABELS["cost"]: p["cost"]["score"],
            PILLAR_LABELS["risk_adjusted_return"]: p["risk_adjusted_return"]["score"],
            PILLAR_LABELS["diversification"]: p["diversification"]["score"],
            PILLAR_LABELS["income"]: p["income"]["score"],
            "ค่าธรรมเนียม": r["metrics"]["expense_ratio"],
            "ซ้ำกับหุ้นที่ติดตาม": ov.get("overlap_weight"),
        })
    for e in errors:
        st.warning(e)
    if not rows:
        return

    rows.sort(key=lambda r: (r["คะแนนรวม"] is None, -(r["คะแนนรวม"] or 0)))
    st.dataframe(
        rows, width="stretch", hide_index=True,
        column_config={
            "คะแนนรวม": st.column_config.ProgressColumn(
                "คะแนนรวม", min_value=0, max_value=100, format="%.1f"),
            "ค่าธรรมเนียม": st.column_config.NumberColumn(format="percent"),
            "ซ้ำกับหุ้นที่ติดตาม": st.column_config.NumberColumn(
                "ซ้ำกับหุ้นที่ติดตาม", format="percent",
                help="สัดส่วนของกองทุนที่อยู่ในหุ้นซึ่งระบบนี้ติดตามรายตัวอยู่แล้ว"),
        },
    )
    st.caption(
        "กองทุนตราสารหนี้กับกองทุนหุ้นเทียบกันตรงๆ บนแกนความเสี่ยงไม่ได้ "
        "ความผันผวน 6% เป็นเรื่องปกติของตราสารหนี้แต่ต่ำผิดปกติสำหรับหุ้น ให้ดูคอลัมน์ประเภทก่อน"
    )
    _risk_return_chart(known)


def _risk_return_chart(known):
    import plotly.graph_objects as go

    pts = []
    for f in known:
        snap = latest_snapshot(FUNDS / f)
        if not snap:
            continue
        d = read_json(snap) or {}
        vol = (d.get("risk") or {}).get("volatility_annual")
        ret = (d.get("returns") or {}).get("total_cagr_estimate")
        exp = (d.get("costs") or {}).get("expense_ratio")
        if vol is None or ret is None:
            continue
        pts.append((f, vol * 100, ret * 100, (exp or 0) * 100))
    if len(pts) < 3:
        return

    st.markdown("**ผลตอบแทนเทียบความผันผวน** ขนาดวงกลมคือค่าธรรมเนียม")
    fig = go.Figure(go.Scatter(
        x=[p[1] for p in pts], y=[p[2] for p in pts],
        mode="markers+text", text=[p[0] for p in pts], textposition="top center",
        marker=dict(
            size=[max(10, 10 + p[3] * 22) for p in pts],
            color=[p[2] / max(0.1, p[1]) for p in pts],
            colorscale=[[0, C_NEGATIVE], [0.5, C_PRIMARY], [1, C_POSITIVE]],
            showscale=True, colorbar=dict(title="ผลตอบแทน<br>ต่อความเสี่ยง"),
        ),
        hovertemplate="%{text}<br>ผันผวน %{x:.1f}%<br>ผลตอบแทน %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=20, b=10),
        xaxis=dict(title="ความผันผวนต่อปี", ticksuffix="%"),
        yaxis=dict(title="ผลตอบแทนรวมต่อปี ที่วัดได้", ticksuffix="%"),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "ผลตอบแทนเป็นค่าที่วัดจากราคาย้อนหลังบวกเงินปันผล ไม่ใช่การพยากรณ์ "
        "กองที่อยู่ซ้ายบนให้ผลตอบแทนต่อความเสี่ยงดีที่สุดในช่วงที่วัด ซึ่งไม่รับประกันว่าจะเป็นแบบนั้นต่อไป"
    )


def detail_panel(fund):
    try:
        r = load_fund_score(fund)
    except Exception as e:
        st.error("อ่านข้อมูลกองทุนไม่สำเร็จ {}: {}".format(type(e).__name__, e))
        return

    snap = latest_snapshot(FUNDS / fund.upper())
    raw = read_json(snap) if snap else {}
    raw = raw or {}

    st.subheader("{} · {}".format(r["ticker"], r.get("name") or ""))
    st.caption("{} · บริหารโดย {} · ข้อมูล ณ {}".format(
        r.get("category") or "?", r.get("family") or "?", r.get("source_snapshot") or "?"))

    if not r.get("is_fund"):
        st.error(
            "สัญลักษณ์นี้ไม่ใช่กองทุน ตัวเลขทุกตัวในหน้านี้จึงอ่านผิดประเภท "
            "ถ้าเป็นหุ้นรายตัวให้ไปที่หน้ารายงานหุ้นรายตัวแทน",
            icon=":material/error:",
        )

    m = r["metrics"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("คะแนนรวม", fmt_num(r["composite_score"]), r["grade"][:2], delta_color="off")
    c2.metric("ค่าธรรมเนียมต่อปี", fmt_pct(m.get("expense_ratio"), 2),
              "คิดเป็น {} ต่อเงินลงทุนแสนหนึ่ง".format(
                  fmt_num((raw.get("costs") or {}).get("cost_per_100k_per_year"), 0)),
              delta_color="off")
    c3.metric("เงินปันผล", fmt_pct(m.get("distribution_yield"), 2))
    c4.metric("ขนาดกองทุน", fmt_money(m.get("total_assets"),
                                      (raw.get("profile") or {}).get("currency") or ""))

    if r.get("flags"):
        st.markdown("**สิ่งที่ตัวเลขเตือน**")
        for x in r["flags"]:
            st.markdown("- " + x)

    tabs = st.tabs(["คะแนนรายด้าน", "ความเสี่ยง", "ถืออะไรบ้าง", "ความซ้ำซ้อน"])

    with tabs[0]:
        _pillar_chart(r)
    with tabs[1]:
        _risk_panel(raw)
    with tabs[2]:
        _composition_panel(raw)
    with tabs[3]:
        _overlap_panel(r, fund)

    st.caption(r["disclaimer"])


def _pillar_chart(r):
    import plotly.graph_objects as go

    pillars = r["pillars"]
    names, vals = [], []
    for key, d in pillars.items():
        if d.get("score") is None:
            continue
        names.append(PILLAR_LABELS.get(key, key))
        vals.append(d["score"])
    if not names:
        st.info("ข้อมูลไม่พอให้คะแนน")
        return

    colors = [C_POSITIVE if v >= 70 else (C_PRIMARY if v >= 50 else C_NEGATIVE) for v in vals]
    fig = go.Figure(go.Bar(
        x=vals, y=names, orientation="h", marker_color=colors,
        text=["{:.0f}".format(v) for v in vals], textposition="outside",
    ))
    fig.update_layout(height=260, margin=dict(l=10, r=40, t=10, b=10),
                      xaxis=dict(range=[0, 108], title=None),
                      yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")

    missing = [PILLAR_LABELS.get(k, k) for k, d in pillars.items() if d.get("score") is None]
    if missing:
        st.caption(
            "ไม่มีข้อมูลสำหรับด้าน {} คะแนนรวมจึงถ่วงน้ำหนักใหม่เฉพาะด้านที่มี "
            "ซึ่งเป็นเรื่องปกติของกองทุนตราสารหนี้และกองทุนทองคำที่ไม่มีการถือหุ้นรายตัว".format(
                ", ".join(missing)))

    st.markdown("**น้ำหนักที่ใช้**")
    st.dataframe(
        [{"ด้าน": PILLAR_LABELS.get(k, k), "คะแนน": d.get("score"),
          "น้ำหนัก": d.get("weight"), "ข้อมูลครบ": d.get("coverage")}
         for k, d in pillars.items()],
        width="stretch", hide_index=True,
        column_config={
            "น้ำหนัก": st.column_config.NumberColumn(format="percent"),
            "ข้อมูลครบ": st.column_config.NumberColumn(format="percent"),
        },
    )


def _risk_panel(raw):
    risk = raw.get("risk") or {}
    rets = raw.get("returns") or {}
    if risk.get("error"):
        st.warning("คำนวณความเสี่ยงไม่ได้: {}".format(risk["error"]))
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ความผันผวนต่อปี", fmt_pct(risk.get("volatility_annual")))
    c2.metric("ตกหนักสุดจากจุดสูงสุด", fmt_pct(risk.get("max_drawdown"), 0))
    c3.metric("เดือนที่แย่ที่สุด", fmt_pct(risk.get("worst_month")))
    c4.metric("beta 3 ปี", fmt_num(risk.get("beta_3y"), 2))

    st.markdown("**ผลตอบแทนตามช่วงเวลา**")
    st.dataframe(
        [
            {"ช่วง": "ตั้งแต่ต้นปี", "ผลตอบแทน": rets.get("ytd")},
            {"ช่วง": "เฉลี่ย 3 ปี", "ผลตอบแทน": rets.get("three_year_avg")},
            {"ช่วง": "เฉลี่ย 5 ปี", "ผลตอบแทน": rets.get("five_year_avg")},
            {"ช่วง": "วัดจากราคาเอง", "ผลตอบแทน": rets.get("price_cagr_measured")},
            {"ช่วง": "รวมปันผลแล้ว", "ผลตอบแทน": rets.get("total_cagr_estimate")},
        ],
        width="stretch", hide_index=True,
        column_config={"ผลตอบแทน": st.column_config.NumberColumn(format="percent")},
    )

    sharpe = risk.get("return_per_unit_of_risk")
    if sharpe is not None:
        st.metric("ผลตอบแทนส่วนเกินต่อหนึ่งหน่วยความเสี่ยง", fmt_num(sharpe, 2))
        st.caption(
            "คำนวณจากผลตอบแทนรวมลบอัตราปลอดความเสี่ยงที่สมมติไว้ {} แล้วหารด้วยความผันผวน "
            "อัตราปลอดความเสี่ยงเป็นสมมติฐาน ไม่ใช่ค่าที่วัดได้ เปลี่ยนค่านี้ตัวเลขก็เปลี่ยน".format(
                fmt_pct(risk.get("risk_free_assumed"))))

    st.caption(
        "ตัวเลขความเสี่ยงคำนวณจากราคาปิดรายเดือน {} เดือน ซึ่งครอบคลุมเฉพาะสิ่งที่เกิดขึ้นแล้ว "
        "ช่วงที่วัดไม่ได้รวมวิกฤตทุกรูปแบบ การตกหนักสุดในอดีตจึงเป็นพื้น ไม่ใช่เพดาน".format(
            risk.get("months_observed", "?")))


def _composition_panel(raw):
    import plotly.graph_objects as go

    comp = raw.get("composition") or {}
    conc = comp.get("concentration") or {}
    sectors = comp.get("sector_weights") or {}
    assets = comp.get("asset_classes") or {}

    if conc.get("available"):
        c1, c2 = st.columns(2)
        c1.metric("น้ำหนัก 10 อันดับแรก", fmt_pct(conc.get("top_10_weight"), 1))
        c2.metric("ตัวใหญ่ที่สุด", fmt_pct(conc.get("largest_weight"), 1))
        st.dataframe(
            [{"สัญลักษณ์": h["symbol"], "ชื่อ": h["name"], "น้ำหนัก": h["weight"]}
             for h in conc["holdings"]],
            width="stretch", hide_index=True,
            column_config={"น้ำหนัก": st.column_config.NumberColumn(format="percent")},
        )
        st.caption(conc.get("note", ""))
    else:
        st.info(
            "ไม่มีรายการหุ้นรายตัวที่เผยแพร่สำหรับกองนี้ ซึ่งเป็นเรื่องปกติของกองทุนตราสารหนี้และกองทุนสินค้าโภคภัณฑ์"
        )

    if sectors:
        st.markdown("**สัดส่วนรายกลุ่มอุตสาหกรรม**")
        items = sorted(sectors.items(), key=lambda kv: -kv[1])
        fig = go.Figure(go.Bar(
            x=[v * 100 for _, v in items],
            y=[k.replace("_", " ") for k, _ in items],
            orientation="h", marker_color=C_PRIMARY,
            text=["{:.1f}%".format(v * 100) for _, v in items], textposition="outside",
        ))
        fig.update_layout(height=max(260, 24 * len(items)),
                          margin=dict(l=10, r=40, t=10, b=10),
                          xaxis=dict(title=None, ticksuffix="%"),
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, width="stretch")
        hhi = comp.get("sector_concentration_hhi")
        if hhi is not None:
            st.caption(
                "ดัชนีการกระจุกตัวรายกลุ่มอยู่ที่ {:.2f} ค่าเข้าใกล้ 1 แปลว่าเกือบทั้งกองอยู่ในกลุ่มเดียว "
                "ค่าต่ำแปลว่ากระจายจริง".format(hhi))

    if assets:
        st.markdown("**ประเภทสินทรัพย์**")
        st.dataframe(
            [{"ประเภท": k, "สัดส่วน": v} for k, v in sorted(assets.items(), key=lambda kv: -kv[1])],
            width="stretch", hide_index=True,
            column_config={"สัดส่วน": st.column_config.NumberColumn(format="percent")},
        )


def _overlap_panel(r, fund):
    ov = r.get("overlap_with_tracked") or {}
    st.markdown("**ซ้ำกับหุ้นที่ระบบนี้ติดตามรายตัว**")
    if not ov.get("ok"):
        st.info(ov.get("reason", "ตรวจความซ้ำซ้อนไม่ได้"))
    else:
        c1, c2 = st.columns(2)
        c1.metric("สัดส่วนกองทุนที่ซ้ำ", fmt_pct(ov.get("overlap_weight"), 1))
        c2.metric("จำนวนหุ้นที่ซ้ำ", len(ov.get("already_tracked") or []))
        st.info(ov.get("reading", ""), icon=":material/join_inner:")
        if ov.get("already_tracked"):
            st.dataframe(
                [{"สัญลักษณ์": h["symbol"], "ชื่อ": h["name"], "น้ำหนักในกองทุน": h["weight_in_fund"]}
                 for h in ov["already_tracked"]],
                width="stretch", hide_index=True,
                column_config={"น้ำหนักในกองทุน": st.column_config.NumberColumn(format="percent")},
            )
        st.caption(ov.get("caveat", ""))

    st.divider()
    st.markdown("**เทียบกับกองทุนอีกกองหนึ่ง**")
    others = [f for f in funds_on_disk() if f != fund.upper()]
    if not others:
        return
    other = st.selectbox("เลือกกองทุนที่จะเทียบ", others, key="overlap_other_{}".format(fund))
    if st.button("ตรวจความซ้ำซ้อน", key="overlap_go_{}".format(fund)):
        from score_funds import overlap_between

        res = overlap_between(fund, other)
        if not res.get("ok"):
            st.warning(res.get("reason"))
            return
        st.info(res["reading"], icon=":material/compare_arrows:")
        if res["holdings"]:
            st.dataframe(
                [{"สัญลักษณ์": h["symbol"], "ชื่อ": h["name"],
                  fund.upper(): h["weight_a"], other: h["weight_b"]}
                 for h in res["holdings"]],
                width="stretch", hide_index=True,
                column_config={
                    fund.upper(): st.column_config.NumberColumn(format="percent"),
                    other: st.column_config.NumberColumn(format="percent"),
                },
            )
        st.caption(res["caveat"])


# --------------------------------------------------------------------------
# page
# --------------------------------------------------------------------------

def render():
    st.title("กองทุนและ ETF")
    st.caption(
        "กองทุนไม่ใช่บริษัท มันไม่มีงบกำไรขาดทุน จึงไม่มีรายได้ มาร์จิ้น หรือ ROIC ให้วัด "
        "หน้านี้จึงใช้เกณฑ์คนละชุดกับหน้าหุ้น คือค่าธรรมเนียม ผลตอบแทนเทียบความเสี่ยง "
        "การกระจายตัว ขนาด และเงินปันผล"
    )

    known = funds_on_disk()

    with st.expander("เพิ่มหรืออัปเดตกองทุน", expanded=not known):
        st.caption(
            "ใส่สัญลักษณ์ ETF คั่นด้วยเว้นวรรค เว้นว่างไว้เพื่อดึงทุกกองใน config/universe.yaml"
        )
        raw = st.text_area("สัญลักษณ์", placeholder="QQQ VOO VTI", height=70)
        if st.button("ดึงข้อมูลและคำนวณคะแนน", type="primary"):
            from common import load_universe

            syms = [s.strip().upper() for s in raw.replace(",", " ").split() if s.strip()]
            if not syms:
                uni = load_universe()
                syms = [f if isinstance(f, str) else f.get("ticker")
                        for f in (uni.get("funds") or [])]
            if not syms:
                st.warning("ไม่มีสัญลักษณ์ให้ดึง")
            else:
                bar = st.progress(0.0, text="เริ่ม...")
                done, failed = fetch_and_score(
                    syms, progress=lambda p, m: bar.progress(p, text=m))
                bar.empty()
                st.cache_data.clear()
                st.success("ดึงสำเร็จ {} กอง".format(len(done)))
                for sym, is_fund, qt in done:
                    if not is_fund:
                        st.warning("{} เป็น {} ไม่ใช่กองทุน ตัวเลขจะอ่านผิดประเภท".format(sym, qt))
                for sym, err in failed:
                    st.error("{}: {}".format(sym, err))
                known = funds_on_disk()

    if not known:
        st.info(
            "ยังไม่มีกองทุนในระบบ กดปุ่มด้านบนเพื่อดึงรายการตั้งต้น 13 กอง "
            "ครอบคลุมดัชนีหลัก ตลาดต่างประเทศ กลุ่มอุตสาหกรรม ตราสารหนี้ และทองคำ"
        )
        return

    ranking_panel(known)
    st.divider()

    default = st.session_state.get("selected_fund")
    pick = st.selectbox("ดูรายละเอียดกองทุน", known,
                        index=known.index(default) if default in known else 0)
    st.session_state["selected_fund"] = pick
    detail_panel(pick)

    st.divider()
    st.caption(
        "เครื่องมือวิจัย ไม่ใช่คำแนะนำการลงทุน ผลตอบแทนในอดีตไม่รับประกันอนาคต "
        "และเป็นตัวชี้ที่อ่อนที่สุดในบรรดาตัวเลขบนหน้านี้"
    )
