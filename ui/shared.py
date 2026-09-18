"""Shared helpers for the Streamlit app: data loading, formatting, and pipeline calls.

Every function that touches the network is cached, because Streamlit re-runs the
whole script on each interaction and an uncached fetch would hammer Yahoo Finance
on every click.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from common import (  # noqa: E402
    FILINGS,
    NEWS,
    RAW,
    REPORTS,
    SCORES,
    latest_snapshot,
    read_json,
    today,
)

PILLAR_LABELS = {
    "growth": "การเติบโต",
    "quality": "คุณภาพธุรกิจ",
    "cash": "กระแสเงินสด",
    "balance_sheet": "ฐานะการเงิน",
    "valuation": "ความถูกแพง",
}

SCENARIO_LABELS = {"bear": "แย่", "base": "ฐาน", "bull": "ดี"}

# Shared chart colours, readable in both Streamlit themes.
C_PRIMARY = "#2563eb"
C_POSITIVE = "#059669"
C_NEGATIVE = "#dc2626"
C_MUTED = "#94a3b8"
C_ACCENT = "#7c3aed"


# --------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------

def fmt_money(v, currency=""):
    if v is None:
        return "n/a"
    a = abs(v)
    for cut, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= cut:
            return "{:,.2f}{} {}".format(v / cut, suf, currency).strip()
    return "{:,.0f} {}".format(v, currency).strip()


def fmt_pct(v, digits=1):
    return "n/a" if v is None else "{:.{d}f}%".format(v * 100, d=digits)


def fmt_num(v, digits=1, suffix=""):
    if v is None:
        return "n/a"
    return "{:,.{d}f}{}".format(v, suffix, d=digits)


def fmt_x(v, digits=2):
    return "n/a" if v is None else "{:,.{d}f}x".format(v, d=digits)


def growth_word(v):
    """Plain Thai for a growth rate, so the number is never read without context."""
    if v is None:
        return "ไม่มีข้อมูล"
    if v >= 0.30:
        return "เติบโตสูงมาก"
    if v >= 0.15:
        return "เติบโตสูง"
    if v >= 0.07:
        return "เติบโตปานกลาง"
    if v >= 0.02:
        return "เติบโตช้า"
    if v >= -0.02:
        return "แทบไม่เติบโต"
    return "หดตัว"


# --------------------------------------------------------------------------
# reading what is already on disk
# --------------------------------------------------------------------------

def tickers_on_disk():
    if not RAW.exists():
        return []
    return sorted(p.name for p in RAW.iterdir() if p.is_dir() and any(p.glob("*.json")))


def load_bundle(ticker):
    """Newest snapshot of every source for one ticker. Missing pieces come back None."""
    tk = ticker.upper()
    missing = Path("/nonexistent")
    return {
        "ticker": tk,
        "fundamentals": read_json(latest_snapshot(RAW / tk) or missing),
        "score": read_json(latest_snapshot(SCORES / tk) or missing),
        "news": read_json(latest_snapshot(NEWS / tk) or missing),
        "filings": read_json(latest_snapshot(FILINGS / tk) or missing),
    }


def snapshot_dates(ticker):
    tk = ticker.upper()
    out = {}
    for label, folder in (("งบการเงิน", RAW), ("คะแนน", SCORES), ("ข่าว", NEWS), ("เอกสาร", FILINGS)):
        p = latest_snapshot(folder / tk)
        out[label] = p.stem if p else None
    return out


def load_macro():
    return read_json(latest_snapshot(NEWS / "_macro") or Path("/nonexistent"))


def list_reports():
    if not REPORTS.exists():
        return []
    return sorted(REPORTS.glob("*.md"), key=lambda p: p.name, reverse=True)


# --------------------------------------------------------------------------
# pipeline calls, cached
# --------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def search_global(query, limit=12):
    """Find a ticker anywhere Yahoo Finance indexes."""
    from search_tickers import search

    return search(query, limit=limit)


@st.cache_data(ttl=3600, show_spinner=False)
def verify_symbol(symbol):
    from search_tickers import verify

    return verify(symbol)


def fetch_fundamentals(ticker, years=5):
    """Fetch and persist a fundamentals snapshot. Returns the payload."""
    from common import write_json
    from fetch_fundamentals import fetch_one

    payload = fetch_one(ticker, years=years)
    write_json(RAW / ticker.upper() / "{}.json".format(today()), payload)
    return payload


def fetch_news(ticker, days=90, limit_per_query=10):
    from common import write_json, utc_now
    from fetch_news import DEFAULT_ANGLES, collect_for_ticker, summarize

    name, articles = collect_for_ticker(
        ticker.upper(), days, DEFAULT_ANGLES, [], limit_per_query, 0.4
    )
    payload = {
        "ticker": ticker.upper(),
        "company": name,
        "as_of": utc_now(),
        "lookback_days": days,
        "summary": summarize(articles),
        "articles": articles,
    }
    write_json(NEWS / ticker.upper() / "{}.json".format(today()), payload)
    return payload


def fetch_macro(days=30, limit_per_query=8):
    import time

    from common import write_json, utc_now
    from fetch_news import MACRO_ANGLES, dedupe, google_news, summarize

    articles = []
    for q in MACRO_ANGLES:
        articles.extend(google_news(q, days, limit=limit_per_query))
        time.sleep(0.3)
    articles = dedupe(articles)
    payload = {
        "scope": "macro",
        "as_of": utc_now(),
        "lookback_days": days,
        "summary": summarize(articles),
        "articles": articles,
    }
    write_json(NEWS / "_macro" / "{}.json".format(today()), payload)
    return payload


def fetch_filings(ticker, with_risk_factors=True):
    """SEC filings. Returns None for a listing with no EDGAR presence."""
    from common import utc_now, write_json
    from fetch_filings import DEFAULT_FORMS, recent_filings, risk_factors, ticker_to_cik

    cik = ticker_to_cik(ticker)
    if not cik:
        return None

    payload = recent_filings(cik, DEFAULT_FORMS, 25)
    payload.update({"ticker": ticker.upper(), "cik": cik, "as_of": utc_now(), "source": "sec_edgar"})

    if with_risk_factors:
        annual = next((f for f in payload["filings"] if f["form"] in ("10-K", "20-F")), None)
        if annual:
            rf = risk_factors(annual["url"])
            rf["from_filing"] = {"form": annual["form"], "filed": annual["filed"]}
            payload["risk_factors"] = rf
        else:
            payload["risk_factors"] = {"error": "ไม่พบแบบ 10-K หรือ 20-F ในช่วงที่ดึงมา"}

    write_json(FILINGS / ticker.upper() / "{}.json".format(today()), payload)
    return payload


def compute_score(ticker, years=5, terminal_growth=0.04):
    from common import write_json
    from score import score_ticker

    res = score_ticker(ticker, years=years, terminal_growth=terminal_growth)
    write_json(SCORES / ticker.upper() / "{}.json".format(today()), res)
    return res


def run_pipeline(ticker, news_days=90, with_filings=True, progress=None):
    """Full refresh for one ticker. Reports each stage so a failure is visible.

    Returns a list of (stage, status, detail) so the caller can show exactly what
    succeeded. A news failure must not hide a successful fundamentals fetch.
    """
    steps = []
    tk = ticker.upper()

    def note(stage, pct, msg):
        if progress:
            progress(pct, msg)
        return stage

    note("fundamentals", 0.05, "กำลังดึงงบการเงิน {} ...".format(tk))
    try:
        payload = fetch_fundamentals(tk)
        name = (payload.get("profile") or {}).get("name") or tk
        yrs = (payload.get("metrics") or {}).get("years_of_data") or 0
        steps.append(("งบการเงิน", "ok", "{} · ข้อมูลย้อนหลัง {} ปี".format(name, yrs)))
    except Exception as e:
        steps.append(("งบการเงิน", "error", "{}: {}".format(type(e).__name__, e)))
        return steps  # nothing downstream can work without this

    note("news", 0.35, "กำลังเก็บข่าว {} วันย้อนหลัง ...".format(news_days))
    try:
        n = fetch_news(tk, days=news_days)
        steps.append(("ข่าว", "ok", "เก็บได้ {} ชิ้น".format((n.get("summary") or {}).get("total", 0))))
    except Exception as e:
        steps.append(("ข่าว", "error", "{}: {}".format(type(e).__name__, e)))

    if with_filings:
        note("filings", 0.65, "กำลังดึงเอกสาร SEC ...")
        try:
            f = fetch_filings(tk)
            if f is None:
                steps.append(("เอกสาร SEC", "skip", "หุ้นนอกสหรัฐ ไม่มีข้อมูลใน EDGAR"))
            else:
                rf = f.get("risk_factors") or {}
                detail = "{} รายการ".format(len(f.get("filings") or []))
                if rf.get("chars"):
                    detail += " · Risk Factors {:,} ตัวอักษร".format(rf["chars"])
                elif rf.get("error"):
                    detail += " · ดึง Risk Factors ไม่สำเร็จ"
                steps.append(("เอกสาร SEC", "ok", detail))
        except Exception as e:
            steps.append(("เอกสาร SEC", "error", "{}: {}".format(type(e).__name__, e)))

    note("score", 0.9, "กำลังคำนวณคะแนน ...")
    try:
        s = compute_score(tk)
        steps.append(("คะแนน", "ok", "{} · {}".format(s.get("composite_score"), s.get("grade"))))
    except Exception as e:
        steps.append(("คะแนน", "error", "{}: {}".format(type(e).__name__, e)))

    note("done", 1.0, "เสร็จแล้ว")
    return steps


# --------------------------------------------------------------------------
# small shared UI pieces
# --------------------------------------------------------------------------

def render_pipeline_result(steps):
    for stage, status, detail in steps:
        if status == "ok":
            st.success("{} · {}".format(stage, detail), icon=":material/check_circle:")
        elif status == "skip":
            st.info("{} · {}".format(stage, detail), icon=":material/info:")
        else:
            st.error("{} · {}".format(stage, detail), icon=":material/error:")


def currency_warning(fundamentals):
    """Say it out loud when market cap and the statements use different currencies."""
    m = (fundamentals or {}).get("metrics") or {}
    if not m.get("currency_mismatch"):
        return
    st.warning(
        "หุ้นตัวนี้ซื้อขายเป็น {} แต่รายงานงบการเงินเป็น {} "
        "อัตราส่วนที่เอามูลค่าตลาดหารด้วยตัวเลขในงบ เช่น P/S ที่ Yahoo ให้มา จึงผิดหน่วยไปตามอัตราแลกเปลี่ยน "
        "โมเดลคะแนนแก้จุดนี้แล้วโดยคำนวณจาก P/E คูณมาร์จิ้นแทน".format(
            m.get("trading_currency") or "?", m.get("financial_currency") or "?"
        ),
        icon=":material/currency_exchange:",
    )


def sector_caveats(fundamentals):
    """Warn where the shared yardstick genuinely does not fit the business."""
    prof = (fundamentals or {}).get("profile") or {}
    sector = (prof.get("sector") or "").lower()
    if "financial" in sector:
        st.info(
            "หุ้นกลุ่มการเงิน อัตราส่วนอย่างหนี้สุทธิ EV และ EV/EBITDA แทบไม่มีความหมายสำหรับธนาคาร "
            "คะแนนรวมจึงเทียบกับหุ้นอุตสาหกรรมตรงๆ ไม่ได้",
            icon=":material/account_balance:",
        )
    if "real estate" in sector or "utilities" in sector:
        st.info(
            "ธุรกิจกลุ่มนี้ใช้หนี้สูงเป็นปกติของโมเดลธุรกิจ เสาฐานะการเงินจึงมักได้คะแนนต่ำโดยไม่ได้แปลว่าผิดปกติ",
            icon=":material/apartment:",
        )


def data_quality_note(fundamentals, score=None):
    m = (fundamentals or {}).get("metrics") or {}
    notes = []
    yrs = m.get("years_of_data") or 0
    if yrs < 3:
        notes.append("มีงบย้อนหลังเพียง {} ปี อัตราการเติบโตทุกตัวจึงเปราะบาง".format(yrs))
    if m.get("operating_margin_latest") is None:
        notes.append("ไม่มีข้อมูลกำไรจากการดำเนินงาน ทำให้ ROIC และมาร์จิ้นคำนวณไม่ได้")
    if score:
        cov = score.get("pillar_weight_coverage")
        if cov is not None and cov < 0.95:
            notes.append("คะแนนรวมคำนวณจากเสาที่มีข้อมูลเพียง {:.0f}% ของน้ำหนักทั้งหมด".format(cov * 100))
    if notes:
        st.warning("ข้อจำกัดของข้อมูลชุดนี้\n\n" + "\n".join("- " + n for n in notes), icon=":material/warning:")
