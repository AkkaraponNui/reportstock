"""Find any listed company in the world and pull it into the system."""
from __future__ import annotations

import streamlit as st

from shared import (
    fmt_money,
    render_pipeline_result,
    run_pipeline,
    search_global,
    tickers_on_disk,
    verify_symbol,
)

EXAMPLES = [
    ("Nvidia", "ชิปประมวลผล AI"),
    ("Toyota", "รถยนต์ ญี่ปุ่น"),
    ("Tencent", "อินเทอร์เน็ต จีน"),
    ("Nestle", "อาหาร สวิตเซอร์แลนด์"),
    ("PTT", "พลังงาน ไทย"),
    ("Samsung Electronics", "อิเล็กทรอนิกส์ เกาหลี"),
    ("ASML", "เครื่องผลิตชิป เนเธอร์แลนด์"),
    ("Reliance Industries", "กลุ่มธุรกิจ อินเดีย"),
]


def render():
    st.title("ค้นหาหุ้น")
    st.caption(
        "ค้นได้ทุกบริษัทที่จดทะเบียนในตลาดหลักทรัพย์ทั่วโลก พิมพ์ชื่อบริษัทหรือสัญลักษณ์ก็ได้ "
        "รายการหุ้นใน config/universe.yaml เป็นแค่ทางลัดสำหรับหุ้นที่ติดตามประจำ ไม่ใช่ขอบเขตของระบบ"
    )

    query = st.text_input(
        "ชื่อบริษัทหรือสัญลักษณ์",
        placeholder="เช่น Nvidia, โตโยต้าใช้ Toyota, PTT, 7203.T",
        key="search_query",
    ).strip()

    st.markdown("**ลองค้นดู**")
    cols = st.columns(4)
    for i, (name, desc) in enumerate(EXAMPLES):
        if cols[i % 4].button(name, key="ex_" + name, width="stretch", help=desc):
            st.session_state["search_query"] = name
            st.rerun()

    if not query:
        return

    with st.spinner("กำลังค้นหา..."):
        hits = search_global(query, limit=12)

    if not hits:
        st.warning(
            "ไม่พบผลลัพธ์สำหรับ {!r} ลองใช้ชื่อภาษาอังกฤษ หรือใส่สัญลักษณ์ตรงๆ พร้อมรหัสตลาด "
            "เช่น .BK สำหรับไทย .T สำหรับโตเกียว .HK สำหรับฮ่องกง".format(query)
        )
        return

    st.divider()
    st.subheader("ผลการค้นหา {} รายการ".format(len(hits)))
    st.caption(
        "บริษัทเดียวกันมักจดทะเบียนหลายตลาด และแต่ละรายการไม่เท่ากัน "
        "ตลาดบ้านเกิดมีสภาพคล่องดีที่สุดและรายงานงบเป็นสกุลเงินของตัวเอง "
        "ส่วน ADR ในสหรัฐซื้อขายเป็นดอลลาร์แต่รายงานงบเป็นสกุลเงินบ้านเกิด"
    )

    known = set(tickers_on_disk())

    for h in hits:
        sym = h.get("symbol") or "?"
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 3, 2])
            c1.markdown("**{}** · {}".format(sym, h.get("name") or "ไม่ทราบชื่อ"))
            c1.caption("{} · {}".format(h.get("region") or "?", h.get("quote_type") or "?"))

            if sym in known:
                c2.success("มีข้อมูลในระบบแล้ว", icon=":material/check:")
            else:
                c2.caption("ยังไม่มีข้อมูลในระบบ")

            if c3.button("เปิดรายงาน", key="open_" + sym, width="stretch"):
                st.session_state["selected_ticker"] = sym
                st.session_state["goto_page"] = "report"
                st.rerun()

            with c2.popover("ตรวจสอบข้อมูล", width="stretch"):
                v = verify_symbol(sym)
                if not v.get("ok"):
                    st.error("สัญลักษณ์นี้ไม่มีข้อมูล: {}".format(v.get("error")))
                else:
                    st.write("ชื่อเต็ม:", v.get("name") or "-")
                    st.write("ราคา:", "{} {}".format(v.get("price"), v.get("currency") or ""))
                    st.write("มูลค่าตลาด:", fmt_money(v.get("market_cap"), v.get("currency") or ""))
                    st.write("กลุ่ม:", v.get("sector") or "-")
                    st.write("ประเทศ:", v.get("country") or "-")
                    if v.get("currency_mismatch"):
                        st.warning(
                            "ซื้อขายเป็น {} แต่รายงานงบเป็น {} โมเดลคะแนนแก้จุดนี้ให้แล้ว".format(
                                v.get("currency"), v.get("financial_currency")
                            )
                        )

    st.divider()
    with st.expander("ดึงข้อมูลหุ้นหลายตัวพร้อมกัน"):
        st.caption(
            "ใส่สัญลักษณ์คั่นด้วยเว้นวรรคหรือจุลภาค ระบบจะดึงงบ ข่าว เอกสาร และคำนวณคะแนนให้ทีละตัว "
            "การเก็บข่าวใช้เวลาราวหนึ่งถึงสองนาทีต่อหุ้นหนึ่งตัว"
        )
        raw = st.text_area("รายการสัญลักษณ์", placeholder="NVDA MSFT 7203.T", height=80)
        c1, c2 = st.columns([1, 3])
        days = c1.slider("ย้อนหลังข่าว (วัน)", 14, 365, 60, step=7, key="batch_days")
        if c2.button("เริ่มดึงข้อมูล", type="primary"):
            syms = [s.strip().upper() for s in raw.replace(",", " ").split() if s.strip()]
            if not syms:
                st.warning("ยังไม่ได้ใส่สัญลักษณ์")
            else:
                bar = st.progress(0.0, text="เริ่ม...")
                for i, sym in enumerate(syms):
                    st.markdown("**{}**".format(sym))
                    steps = run_pipeline(
                        sym, news_days=days, with_filings=True,
                        progress=lambda p, msg, i=i: bar.progress(
                            (i + p) / len(syms), text="{} · {}".format(sym, msg)
                        ),
                    )
                    render_pipeline_result(steps)
                bar.empty()
                st.cache_data.clear()
                st.success("ดึงข้อมูลครบ {} ตัว".format(len(syms)))
