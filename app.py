"""reportstock - Streamlit front end for the five-year equity research system.

Run it with:
    uv run streamlit run app.py

The app is a window onto the same files the agents use. Fetching from here writes
the identical dated snapshots under data/, so anything pulled in the browser is
immediately available to the agents on the command line, and the other way round.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
for sub in ("tools", "ui"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

st.set_page_config(
    page_title="reportstock",
    page_icon=":material/trending_up:",
    layout="wide",
    initial_sidebar_state="expanded",
)

import page_chat  # noqa: E402
import page_funds  # noqa: E402
import page_macro  # noqa: E402
import page_predict  # noqa: E402
import page_ranking  # noqa: E402
import page_report  # noqa: E402
import page_search  # noqa: E402
from auth import require_password  # noqa: E402
from shared import tickers_on_disk  # noqa: E402

PAGES = {
    "chat": ("คุยกับนักวิเคราะห์", ":material/forum:", page_chat.render),
    "search": ("ค้นหาหุ้น", ":material/search:", page_search.render),
    "report": ("รายงานหุ้นรายตัว", ":material/monitoring:", page_report.render),
    "predict": ("โมเดลพยากรณ์การเติบโต", ":material/insights:", page_predict.render),
    "funds": ("กองทุนและ ETF", ":material/donut_large:", page_funds.render),
    "ranking": ("จัดอันดับ", ":material/leaderboard:", page_ranking.render),
    "macro": ("ภาพรวมมหภาค", ":material/public:", page_macro.render_macro),
    "reports": ("รายงานที่สร้างไว้", ":material/description:", page_macro.render_reports),
}

DEFAULT_PAGE = "report"


def main():
    # No-op unless APP_PASSWORD is configured, which is how a public deployment
    # keeps strangers from spending its data-source rate limits.
    if not require_password():
        return

    # A page button elsewhere in the app can request a jump.
    if "goto_page" in st.session_state:
        st.session_state["nav"] = st.session_state.pop("goto_page")

    with st.sidebar:
        st.markdown("### reportstock")
        st.caption("วิจัยหุ้นต่างประเทศสำหรับการลงทุนระยะ 5 ปี")

        choice = st.radio(
            "เมนู",
            list(PAGES),
            format_func=lambda k: PAGES[k][0],
            key="nav",
            label_visibility="collapsed",
        )

        st.divider()
        known = tickers_on_disk()
        st.caption("หุ้นที่มีข้อมูลในเครื่อง: {} ตัว".format(len(known)))
        if known:
            with st.expander("ดูรายชื่อ"):
                st.write(", ".join(known))

        st.divider()
        st.caption(
            "ระบบนี้ค้นและวิเคราะห์หุ้นได้ทุกตัวที่ Yahoo Finance มีข้อมูล "
            "ครอบคลุมตลาดหลักทั่วโลกรวมถึงตลาดหุ้นไทย"
        )
        with st.expander("ข้อจำกัดที่ควรรู้"):
            st.markdown(
                "- ข้อมูลราคาและงบเป็นข้อมูลดีเลย์และมีการแก้ย้อนหลัง\n"
                "- หุ้นนอกสหรัฐไม่มีเอกสาร SEC หลักฐานฝั่งความเสี่ยงจึงไม่เท่ากัน\n"
                "- หุ้นกลุ่มธนาคารทำให้อัตราส่วนหลายตัวไม่มีความหมาย\n"
                "- ตัวเลขผลตอบแทน 5 ปีเป็นผลของสมมติฐาน ไม่ใช่การพยากรณ์\n"
                "- โมเดลอ่านอดีต มันมองไม่เห็นธุรกิจที่กำลังเปลี่ยนรูป"
            )
        st.caption("เครื่องมือวิจัย ไม่ใช่คำแนะนำการลงทุน")

    PAGES[choice or DEFAULT_PAGE][2]()


if __name__ == "__main__":
    main()
