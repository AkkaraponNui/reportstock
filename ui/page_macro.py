"""Macro backdrop and the generated markdown reports."""
from __future__ import annotations

import streamlit as st

from shared import fetch_macro, list_reports, load_macro


def render_macro():
    st.title("ภาพรวมมหภาค")
    st.caption(
        "ข่าวระดับมหภาคที่กระทบทั้งพอร์ต ไม่ใช่หุ้นตัวใดตัวหนึ่ง เช่น ทิศทางดอกเบี้ย เงินเฟ้อ "
        "นโยบายการค้า และวัฏจักรการลงทุนขนาดใหญ่"
    )

    c1, c2 = st.columns([1, 3])
    days = c1.slider("ย้อนหลัง (วัน)", 7, 120, 30, step=7)
    if c2.button("อัปเดตข่าวมหภาค", type="primary"):
        with st.spinner("กำลังเก็บข่าว..."):
            try:
                payload = fetch_macro(days=days)
                st.success("เก็บข่าวได้ {} ชิ้น".format((payload.get("summary") or {}).get("total", 0)))
                st.cache_data.clear()
            except Exception as e:
                st.error("เก็บข่าวไม่สำเร็จ {}: {}".format(type(e).__name__, e))

    m = load_macro()
    if not m:
        st.info("ยังไม่มีข่าวมหภาคในระบบ กดปุ่มอัปเดตด้านบน")
        return

    s = m.get("summary") or {}
    lean = s.get("headline_lean") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ข่าวทั้งหมด", s.get("total", 0))
    c2.metric("พาดหัวเชิงบวก", lean.get("positive", 0))
    c3.metric("พาดหัวเชิงลบ", lean.get("negative", 0))
    c4.metric("ช่วงที่เก็บ", "{} วัน".format(m.get("lookback_days", "?")))

    st.caption("ข้อมูลชุดนี้เก็บเมื่อ {}".format((m.get("as_of") or "")[:16].replace("T", " ")))
    st.divider()

    for a in (m.get("articles") or [])[:50]:
        mark = {"positive": "▲", "negative": "▼"}.get(a.get("lean"), "·")
        title = a.get("title") or "(ไม่มีพาดหัว)"
        url = a.get("url")
        line = "{} **{}**".format(mark, title)
        st.markdown("[{}]({})".format(line, url) if url else line)
        st.caption("{} · {}".format((a.get("published") or "")[:10], a.get("publisher") or "ไม่ระบุแหล่ง"))

    st.divider()
    st.caption(
        "การจัดกลุ่มพาดหัวเป็นบวกหรือลบใช้การจับคำ จึงผิดพลาดได้เป็นปกติ "
        "ข่าวมหภาคส่วนใหญ่พูดถึงการประชุมครั้งหน้าหรือไตรมาสหน้า ซึ่งแทบไม่เปลี่ยนผลลัพธ์ในห้าปี "
        "สิ่งที่ควรโฟกัสคือทิศทางต้นทุนเงินทุน วัฏจักรการลงทุน และนโยบายที่ย้ายแหล่งกำไรระหว่างประเทศ"
    )


def render_reports():
    st.title("รายงานที่สร้างไว้")
    st.caption(
        "ไฟล์ทั้งหมดอยู่ใน data/reports สร้างโดยเครื่องมือหรือโดย agent "
        "ไฟล์ที่ลงท้ายด้วย datapack คือข้อเท็จจริงล้วนไม่มีความเห็นปน "
        "ส่วน thesis คือบทวิเคราะห์ที่เขียนโดย agent"
    )

    files = list_reports()
    if not files:
        st.info(
            "ยังไม่มีรายงาน สร้างได้ด้วยคำสั่ง "
            "`uv run python tools/build_report.py NVDA --name nvda` "
            "หรือให้ agent เขียนบทวิเคราะห์ผ่าน skill ชื่อ stock-research"
        )
        return

    labels = []
    for p in files:
        kind = "ข้อเท็จจริง" if "datapack" in p.name else (
            "บทวิเคราะห์" if "thesis" in p.name else "มหภาค" if "macro" in p.name else "อื่นๆ"
        )
        size = p.stat().st_size / 1024
        labels.append("{}  ·  {}  ·  {:.0f} KB".format(p.name, kind, size))

    idx = st.selectbox("เลือกรายงาน", range(len(files)), format_func=lambda i: labels[i])
    path = files[idx]

    c1, c2 = st.columns([1, 4])
    c2.caption("ไฟล์: {}".format(path))
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        st.error("อ่านไฟล์ไม่สำเร็จ: {}".format(e))
        return

    c1.download_button(
        "ดาวน์โหลด", text, file_name=path.name, mime="text/markdown", width="stretch"
    )

    st.divider()
    if len(text) > 300000:
        st.warning("รายงานยาวมาก แสดงเฉพาะ 300,000 ตัวอักษรแรก กดดาวน์โหลดเพื่ออ่านฉบับเต็ม")
        text = text[:300000]
    st.markdown(text)
