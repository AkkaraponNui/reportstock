"""Optional password gate, for when the app is served on a public URL.

No password configured means no gate, which is the right default for running on
your own machine. Set `APP_PASSWORD` in the host's secrets panel and the gate
turns itself on.

This is a shared-secret door, not an identity system. It keeps strangers and
crawlers from burning your data-source rate limits on a public URL. It does not
give per-user accounts, and it is not a substitute for keeping anything genuinely
sensitive off a public host in the first place.
"""
from __future__ import annotations

import hmac
import os

import streamlit as st


def _configured_password():
    """Password from Streamlit secrets, else the environment. None means no gate."""
    try:
        value = st.secrets.get("APP_PASSWORD")
        if value:
            return str(value)
    except Exception:
        # No secrets.toml present, which is normal locally.
        pass
    return os.environ.get("APP_PASSWORD") or None


def require_password() -> bool:
    """Return True when the app may render. Draws the login form when it may not."""
    expected = _configured_password()
    if not expected:
        return True

    if st.session_state.get("_authenticated"):
        return True

    st.title("reportstock")
    st.caption("ใส่รหัสผ่านเพื่อเข้าใช้งาน")

    with st.form("login", border=True):
        entered = st.text_input("รหัสผ่าน", type="password")
        submitted = st.form_submit_button("เข้าใช้งาน", type="primary")

    if submitted:
        # Constant-time comparison, so response timing reveals nothing.
        if hmac.compare_digest(entered.encode("utf-8"), expected.encode("utf-8")):
            st.session_state["_authenticated"] = True
            st.rerun()
        else:
            st.error("รหัสผ่านไม่ถูกต้อง")

    st.caption(
        "หน้านี้เป็นเครื่องมือวิจัยส่วนตัว ข้อมูลทั้งหมดมาจากแหล่งสาธารณะ "
        "และไม่ใช่คำแนะนำการลงทุน"
    )
    return False
