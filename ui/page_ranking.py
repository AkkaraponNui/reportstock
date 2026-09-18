"""Compare every stock that has data on the same yardstick."""
from __future__ import annotations

import streamlit as st

from shared import (
    C_NEGATIVE,
    C_POSITIVE,
    C_PRIMARY,
    PILLAR_LABELS,
    compute_score,
    load_bundle,
    tickers_on_disk,
)


def _rows(tickers):
    out = []
    for tk in tickers:
        b = load_bundle(tk)
        s, f = b["score"], b["fundamentals"]
        if not s:
            continue
        p = s.get("pillars") or {}
        base = (s.get("projection_5y") or {}).get("base") or {}
        m = (f or {}).get("metrics") or {}
        prof = (f or {}).get("profile") or {}

        def pillar(name):
            return (p.get(name) or {}).get("score")

        out.append(
            {
                "หุ้น": tk,
                "บริษัท": (s.get("company") or "?")[:30],
                "กลุ่ม": s.get("sector") or "?",
                "ประเทศ": prof.get("country") or "?",
                "คะแนนรวม": s.get("composite_score"),
                PILLAR_LABELS["growth"]: pillar("growth"),
                PILLAR_LABELS["quality"]: pillar("quality"),
                PILLAR_LABELS["cash"]: pillar("cash"),
                PILLAR_LABELS["balance_sheet"]: pillar("balance_sheet"),
                PILLAR_LABELS["valuation"]: pillar("valuation"),
                "รายได้โต TTM": m.get("revenue_growth_ttm"),
                "รายได้โตเฉลี่ย": m.get("revenue_cagr"),
                "มาร์จิ้นดำเนินงาน": m.get("operating_margin_latest"),
                "P/E ข้างหน้า": m.get("forward_pe"),
                "ผลตอบแทนกรณีฐาน": base.get("annualized_return"),
                "เกรด": (s.get("grade") or "")[:2].strip(),
            }
        )
    return out


def render():
    st.title("จัดอันดับและเปรียบเทียบ")

    known = tickers_on_disk()
    if not known:
        st.info(
            "ยังไม่มีหุ้นตัวใดในระบบ ไปที่หน้าค้นหาหุ้นเพื่อเพิ่มตัวแรก "
            "หรือรันคำสั่ง `uv run python tools/fetch_fundamentals.py NVDA MSFT` ในเทอร์มินัล"
        )
        return

    c1, c2 = st.columns([3, 1])
    picked = c1.multiselect("เลือกหุ้นที่จะเปรียบเทียบ", known, default=known)
    if c2.button("คำนวณคะแนนใหม่ทั้งหมด", width="stretch",
                 help="ใช้งบที่มีอยู่แล้วในเครื่อง ไม่ได้ดึงข้อมูลใหม่จากอินเทอร์เน็ต"):
        ok, fail = 0, []
        for tk in picked:
            try:
                compute_score(tk)
                ok += 1
            except Exception as e:
                fail.append("{}: {}".format(tk, e))
        st.cache_data.clear()
        st.success("คำนวณคะแนนสำเร็จ {} ตัว".format(ok))
        for msg in fail:
            st.error(msg)

    rows = _rows(picked)
    if not rows:
        st.warning(
            "หุ้นที่เลือกยังไม่มีคะแนน กดปุ่มคำนวณคะแนนใหม่ หรือดึงข้อมูลจากหน้ารายงานหุ้นรายตัวก่อน"
        )
        return

    rows.sort(key=lambda r: (r["คะแนนรวม"] is None, -(r["คะแนนรวม"] or 0)))

    st.caption(
        "คะแนนแต่ละเสาเต็ม 100 คะแนนรวมถ่วงน้ำหนัก การเติบโต 30% คุณภาพ 25% "
        "กระแสเงินสด 15% ฐานะการเงิน 15% ความถูกแพง 15% "
        "หุ้นกลุ่มการเงินเทียบกับหุ้นอุตสาหกรรมตรงๆ ไม่ได้ เพราะอัตราส่วนหลายตัวไม่มีความหมายกับธนาคาร"
    )

    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        column_config={
            "คะแนนรวม": st.column_config.ProgressColumn(
                "คะแนนรวม", min_value=0, max_value=100, format="%.1f"
            ),
            "รายได้โต TTM": st.column_config.NumberColumn(format="percent"),
            "รายได้โตเฉลี่ย": st.column_config.NumberColumn(format="percent"),
            "มาร์จิ้นดำเนินงาน": st.column_config.NumberColumn(format="percent"),
            "ผลตอบแทนกรณีฐาน": st.column_config.NumberColumn(format="percent"),
            "P/E ข้างหน้า": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    st.divider()
    _scatter(rows)
    _pillar_compare(rows)

    st.caption(
        "ผลตอบแทนกรณีฐานเป็นผลทางคณิตศาสตร์ของสมมติฐานในโมเดล ไม่ใช่การพยากรณ์ "
        "และคะแนนสูงเป็นเหตุผลให้ไปดูให้ละเอียด ไม่ใช่ข้อสรุป "
        "โมเดลอ่านอดีตแล้วสมมติว่ารูปแบบเดิมดำเนินต่อ มันมองไม่เห็นธุรกิจที่กำลังเปลี่ยนรูป"
    )


def _scatter(rows):
    import plotly.graph_objects as go

    st.subheader("การเติบโตเทียบกับความถูกแพง")
    st.caption(
        "แกนนอนคือคะแนนการเติบโต แกนตั้งคือคะแนนความถูกแพง ขนาดวงกลมคือคะแนนรวม "
        "มุมขวาบนคือโตดีและราคายังไม่แพง ซึ่งพบได้ยากและมักมีเหตุผลอยู่เบื้องหลัง"
    )

    pts = [r for r in rows if r[PILLAR_LABELS["growth"]] is not None
           and r[PILLAR_LABELS["valuation"]] is not None]
    if not pts:
        return

    fig = go.Figure(
        go.Scatter(
            x=[r[PILLAR_LABELS["growth"]] for r in pts],
            y=[r[PILLAR_LABELS["valuation"]] for r in pts],
            mode="markers+text",
            text=[r["หุ้น"] for r in pts],
            textposition="top center",
            marker=dict(
                size=[max(12, (r["คะแนนรวม"] or 0) / 2.2) for r in pts],
                color=[r["คะแนนรวม"] or 0 for r in pts],
                colorscale=[[0, C_NEGATIVE], [0.5, C_PRIMARY], [1, C_POSITIVE]],
                cmin=30, cmax=95, showscale=True,
                colorbar=dict(title="คะแนนรวม"),
            ),
            hovertemplate="%{text}<br>เติบโต %{x:.0f}<br>ถูกแพง %{y:.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=20, b=10),
        xaxis=dict(title="คะแนนการเติบโต", range=[0, 105]),
        yaxis=dict(title="คะแนนความถูกแพง", range=[0, 105]),
    )
    fig.add_hline(y=50, line=dict(color="#cbd5e1", dash="dot"))
    fig.add_vline(x=50, line=dict(color="#cbd5e1", dash="dot"))
    st.plotly_chart(fig, width="stretch")


def _pillar_compare(rows):
    import plotly.graph_objects as go

    st.subheader("เทียบรายเสา")
    top = rows[:10]
    if not top:
        return

    fig = go.Figure()
    for key in ("growth", "quality", "cash", "balance_sheet", "valuation"):
        label = PILLAR_LABELS[key]
        fig.add_bar(
            name=label,
            x=[r["หุ้น"] for r in top],
            y=[r.get(label) for r in top],
        )
    fig.update_layout(
        barmode="group", height=380, margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis=dict(title="คะแนน", range=[0, 105]),
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")
