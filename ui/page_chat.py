"""Chat with the analyst agent, which answers from the data stored on disk."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from shared import tickers_on_disk

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import chat_agent  # noqa: E402

TOOL_LABELS = {
    "list_stocks": "ดูรายชื่อหุ้นในระบบ",
    "get_fundamentals": "อ่านงบการเงิน",
    "get_score": "อ่านคะแนนและฉากทัศน์",
    "get_prediction": "อ่านผลโมเดลจำลอง",
    "get_news": "อ่านข่าว",
    "get_risk_factors": "อ่านความเสี่ยงจากเอกสาร SEC",
    "get_macro_news": "อ่านข่าวมหภาค",
    "get_peer_comparison": "เทียบกับคู่แข่งในกลุ่ม",
    "get_sector_medians": "ดูค่ากลางรายกลุ่ม",
    "list_funds": "ดูรายชื่อกองทุน",
    "get_fund": "อ่านข้อมูลกองทุน",
    "get_fund_overlap": "ตรวจความซ้ำซ้อนของกองทุน",
    "search_ticker": "ค้นหาสัญลักษณ์หุ้น",
    "fetch_stock_data": "ดึงข้อมูลหุ้นใหม่",
    "compare_stocks": "เปรียบเทียบหุ้น",
    "read_report": "อ่านรายงานที่บันทึกไว้",
}

STARTERS = [
    "หุ้นตัวไหนในระบบน่าถือ 5 ปีที่สุด เพราะอะไร",
    "NVDA ตอนนี้เติบโตเท่าไหร่ และแพงไปหรือยัง",
    "เทียบ ASML กับ TSM ให้หน่อย",
    "ความเสี่ยงที่ใหญ่ที่สุดของ LLY คืออะไร",
    "มีข่าวอะไรที่กระทบการลงทุนระยะยาวบ้างในเดือนนี้",
    "อธิบายว่าทำไม ASML ได้คะแนนความถูกแพงต่ำ",
    "ถ้าถือ NVDA อยู่แล้ว ซื้อ QQQ เพิ่มจะซ้ำซ้อนไหม",
    "กองทุนไหนในระบบคุ้มค่าธรรมเนียมที่สุด",
]


def _api_key():
    """A key from Streamlit secrets or the environment, else None for SDK default."""
    try:
        v = st.secrets.get("ANTHROPIC_API_KEY")
        if v:
            return str(v)
    except Exception:
        pass
    return None


def _credentials_ok():
    return bool(_api_key()) or chat_agent.credentials_available()


def _setup_help():
    st.warning("ยังไม่ได้ตั้งค่ากุญแจ API ของ Anthropic จึงยังใช้ช่องแชทไม่ได้",
               icon=":material/key_off:")
    st.markdown(
        "ช่องแชทนี้เรียกโมเดล Claude ผ่าน API ของ Anthropic ซึ่งมีค่าใช้จ่ายตามปริมาณการใช้งาน "
        "ส่วนหน้าอื่นทั้งหมดในแอปนี้ทำงานได้โดยไม่ต้องใช้กุญแจ"
    )
    st.markdown("**ตั้งค่าบนเครื่องตัวเอง**")
    st.code('export ANTHROPIC_API_KEY="sk-ant-..."\nuv run python -m streamlit run app.py', language="bash")
    st.markdown("**ตั้งค่าเมื่อ deploy ขึ้นออนไลน์** ใส่ในช่อง Secrets ของแพลตฟอร์ม")
    st.code('ANTHROPIC_API_KEY = "sk-ant-..."', language="toml")
    st.caption("ขอกุญแจได้ที่ console.anthropic.com หรือถ้าเคยรัน `ant auth login` ไว้ ระบบจะหาโปรไฟล์เจอเอง")


def _render_history():
    for turn in st.session_state.get("chat_display", []):
        with st.chat_message(turn["role"]):
            if turn.get("tools"):
                names = [TOOL_LABELS.get(t["name"], t["name"]) for t in turn["tools"]]
                seen, ordered = set(), []
                for n in names:
                    if n not in seen:
                        seen.add(n)
                        ordered.append(n)
                st.caption("ใช้เครื่องมือ: " + " · ".join(ordered))
            st.markdown(turn["content"])


def render():
    st.title("คุยกับนักวิเคราะห์")
    st.caption(
        "ถามได้ทุกเรื่องเกี่ยวกับหุ้นในระบบ ตัวแทนจะอ่านงบการเงิน คะแนน ผลโมเดลจำลอง ข่าว "
        "และเอกสารความเสี่ยงจริงก่อนตอบ ไม่ตอบตัวเลขจากความจำ"
    )

    if not _credentials_ok():
        _setup_help()
        return

    known = tickers_on_disk()
    with st.sidebar:
        st.divider()
        st.caption("ตัวแทนอ่านข้อมูลของหุ้น {} ตัวที่มีในเครื่อง".format(len(known)))
        effort = st.select_slider(
            "ความละเอียดในการคิด",
            ["low", "medium", "high", "xhigh"],
            value="high",
            help="สูงขึ้นหมายถึงคิดละเอียดขึ้น ตอบช้าลง และมีค่าใช้จ่ายมากขึ้น",
        )
        if st.button("ล้างบทสนทนา", width="stretch"):
            st.session_state.pop("chat_messages", None)
            st.session_state.pop("chat_display", None)
            st.rerun()

    st.session_state.setdefault("chat_messages", [])
    st.session_state.setdefault("chat_display", [])

    if not st.session_state["chat_display"]:
        st.markdown("**ลองถามดู**")
        cols = st.columns(2)
        for i, s in enumerate(STARTERS):
            if cols[i % 2].button(s, key="starter_{}".format(i), width="stretch"):
                st.session_state["pending_prompt"] = s
                st.rerun()

    _render_history()

    prompt = st.chat_input("พิมพ์คำถามเกี่ยวกับหุ้น...")
    if not prompt:
        prompt = st.session_state.pop("pending_prompt", None)
    if not prompt:
        _footer(known)
        return

    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state["chat_display"].append({"role": "user", "content": prompt})
    st.session_state["chat_messages"].append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        status = st.empty()
        placeholder = st.empty()
        chunks = []
        used = []

        def on_text(t):
            chunks.append(t)
            placeholder.markdown("".join(chunks))

        def on_tool_start(name, tool_input):
            label = TOOL_LABELS.get(name, name)
            detail = tool_input.get("ticker") or tool_input.get("query") or ""
            if isinstance(tool_input.get("tickers"), list):
                detail = ", ".join(tool_input["tickers"])
            status.info("{} {}".format(label, detail).strip(), icon=":material/build:")

        def on_tool_end(name, _result):
            used.append(name)

        try:
            client = chat_agent.make_client(api_key=_api_key())
            result = chat_agent.run_turn(
                client,
                st.session_state["chat_messages"],
                on_text=on_text,
                on_tool_start=on_tool_start,
                on_tool_end=on_tool_end,
                effort=effort,
            )
            status.empty()
            text = result["text"] or "".join(chunks)
            placeholder.markdown(text)
            st.session_state["chat_display"].append(
                {"role": "assistant", "content": text, "tools": result["tools"]}
            )
        except Exception as e:
            status.empty()
            _handle_error(e)
            # Drop the unanswered user turn so the history stays valid for the API.
            st.session_state["chat_messages"] = [
                m for m in st.session_state["chat_messages"][:-1]
            ]
            st.session_state["chat_display"].pop()

    _footer(known)


def _handle_error(e):
    name = type(e).__name__
    msg = str(e)
    if "authentication" in msg.lower() or name == "AuthenticationError":
        st.error("กุญแจ API ไม่ถูกต้องหรือหมดอายุ ตรวจสอบค่า ANTHROPIC_API_KEY อีกครั้ง")
    elif name == "RateLimitError":
        st.error("ถูกจำกัดอัตราการเรียกใช้ รอสักครู่แล้วลองใหม่")
    elif name == "APIConnectionError":
        st.error("เชื่อมต่อ API ไม่ได้ ตรวจสอบอินเทอร์เน็ตแล้วลองใหม่")
    elif name == "NotFoundError":
        st.error("ไม่พบโมเดลที่ระบุ บัญชีของคุณอาจยังไม่มีสิทธิ์เข้าถึงโมเดลนี้")
    else:
        st.error("เกิดข้อผิดพลาด {}: {}".format(name, msg[:300]))


def _footer(known):
    st.divider()
    with st.expander("ตัวแทนนี้เห็นอะไรบ้าง และเชื่อได้แค่ไหน"):
        st.markdown(
            "ตัวแทนอ่านจากไฟล์ที่ระบบนี้เก็บไว้ ไม่ใช่จากความจำของโมเดล "
            "ทุกคำตอบจึงย้อนกลับไปหาไฟล์และวันที่ได้\n\n"
            "- งบการเงินย้อนหลังและอัตราส่วนทางการเงิน\n"
            "- คะแนนห้าเสาและฉากทัศน์ 5 ปี พร้อมสมมติฐานทุกตัว\n"
            "- ผลจากโมเดลจำลองและการวิเคราะห์ความอ่อนไหว\n"
            "- ข่าวที่เก็บมาพร้อมแท็กประเภทเหตุการณ์\n"
            "- ความเสี่ยงที่บริษัทระบุเองในเอกสาร SEC เฉพาะหุ้นสหรัฐ\n"
            "- รายงานที่เคยสร้างไว้ในโฟลเดอร์ reports\n\n"
            "ถ้าถามถึงหุ้นที่ยังไม่มีในระบบ ตัวแทนจะค้นหาสัญลักษณ์ให้ก่อน "
            "แล้วถามว่าจะให้ดึงข้อมูลไหม การดึงใช้เวลาหนึ่งถึงสองนาที\n\n"
            "ข้อจำกัดยังเป็นข้อจำกัดเดิมของข้อมูล ข้อมูลดีเลย์และมีการแก้ย้อนหลัง "
            "หุ้นนอกสหรัฐไม่มีเอกสาร SEC และตัวเลขผลตอบแทนทุกตัวเป็นผลของสมมติฐาน ไม่ใช่การพยากรณ์"
        )
        st.caption("หุ้นที่มีข้อมูลตอนนี้: " + (", ".join(known) if known else "ยังไม่มี"))
    st.caption("เครื่องมือวิจัย ไม่ใช่คำแนะนำการลงทุน การตัดสินใจและความเสี่ยงเป็นของผู้ใช้")
