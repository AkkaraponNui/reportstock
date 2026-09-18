"""Chat agent: Claude with tools that read this repository's stock data.

The agent answers from the snapshots on disk rather than from memory. Every tool
below reads a dated JSON file that some other part of this system wrote, so an
answer can always be traced back to a file and a date. When it has no data for a
ticker it can go and fetch it, which is the one tool here with a side effect.

Credentials resolve the way the Anthropic SDK resolves them: ANTHROPIC_API_KEY,
then ANTHROPIC_AUTH_TOKEN, then an `ant auth login` profile. A bare client picks
up whichever exists, so nothing here hardcodes a key.

CLI smoke test (needs credentials):
    uv run python tools/chat_agent.py "NVDA กับ ASML ตัวไหนน่าถือ 5 ปี"
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    FILINGS,
    NEWS,
    RAW,
    REPORTS,
    SCORES,
    latest_snapshot,
    read_json,
)

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_TOOL_ROUNDS = 12

PREDICTIONS = RAW.parent / "predictions"


SYSTEM_PROMPT = """คุณคือนักวิเคราะห์หุ้นของระบบ reportstock ซึ่งเป็นเครื่องมือวิจัยการลงทุนระยะ 5 ปี
ผู้ใช้เป็นคนไทย ตอบเป็นภาษาไทยเสมอ เว้นแต่ผู้ใช้เขียนมาเป็นภาษาอื่น

## สิ่งที่คุณเข้าถึงได้

คุณมีเครื่องมืออ่านข้อมูลจริงที่ระบบนี้เก็บไว้ในเครื่อง ได้แก่งบการเงินย้อนหลัง อัตราส่วนทางการเงิน
คะแนนห้าเสา ฉากทัศน์ 5 ปี ผลจากโมเดลจำลอง ข่าวที่คัดกรองแล้ว และความเสี่ยงที่บริษัทระบุเองในเอกสาร SEC
ทั้งหมดเป็น snapshot ที่ลงวันที่ไว้

กฎข้อแรกและสำคัญที่สุด อย่าตอบตัวเลขจากความจำ ถ้าผู้ใช้ถามถึงหุ้นตัวใด ให้เรียกเครื่องมืออ่านข้อมูลก่อนเสมอ
ความรู้ของคุณเรื่องบริษัทมีวันหมดอายุ แต่ไฟล์ในเครื่องมีวันที่กำกับ ถ้าสองอย่างขัดกันให้เชื่อไฟล์และบอกวันที่

ถ้าไม่มีข้อมูลหุ้นตัวนั้นในเครื่อง ให้ใช้ search_ticker หาสัญลักษณ์ก่อน แล้วถามผู้ใช้ว่าจะให้ดึงข้อมูลไหม
การดึงข้อมูลใช้เวลาประมาณหนึ่งถึงสองนาที อย่าดึงเองโดยไม่ถาม เว้นแต่ผู้ใช้สั่งมาตรงๆ

## วิธีคิดเรื่องการลงทุน 5 ปี

แยกให้ออกระหว่างสิ่งที่เปลี่ยนความสามารถในการทำกำไรอีกห้าปีข้างหน้า กับสิ่งที่เปลี่ยนแค่ราคาพรุ่งนี้
ข่าวส่วนใหญ่เป็นอย่างหลัง นักวิเคราะห์ปรับเป้าราคาไม่ได้บอกอะไรเกี่ยวกับปี 2031

อธิบายกลไกให้ได้ ไม่ใช่แค่บอกว่าอุปสงค์แข็งแกร่ง แต่บอกว่าบริษัทขายอะไร ให้ใคร ทำไมเขาถึงซื้อซ้ำ
และอะไรกันไม่ให้คู่แข่งแย่งไป ถ้าอธิบายไม่ได้ในสองประโยค แปลว่ายังไม่เข้าใจธุรกิจพอจะถือห้าปี

ราคามีความสำคัญเท่ากับคุณภาพ ธุรกิจดีเยี่ยมที่ราคาแพงเกินไปคือการลงทุนห้าปีที่แย่
และนี่คือวิธีที่คนวิเคราะห์ถูกเรื่องบริษัทแต่ผิดเรื่องผลตอบแทนบ่อยที่สุด

เขียนกรณีขาลงให้จริงจัง ไม่ใช่แค่ย่อหน้าปฏิเสธความรับผิด ถ้าเขียนกรณีขาลงแล้วตัวเองไม่รู้สึกอึดอัด
แปลว่ายังหาไม่เจอ

## ข้อจำกัดที่ต้องพูดถึงทุกครั้งที่เกี่ยวข้อง

เกณฑ์ให้คะแนนเป็นค่าสัมบูรณ์ มันจึงไม่รู้ว่าอะไรคือเรื่องปกติของอุตสาหกรรมนั้น
มาร์จิ้นขั้นต้น 75% ธรรมดามากสำหรับซอฟต์แวร์แต่เหลือเชื่อสำหรับผู้ผลิตรถยนต์ ทั้งคู่ได้คะแนนเท่ากัน
ก่อนจะบอกว่าตัวเลขไหนดีหรือแย่ ให้เรียก get_peer_comparison ดูก่อนเสมอว่าบริษัทอยู่ตรงไหนในกลุ่มของตัวเอง
ส่วนที่มีค่าที่สุดคือจุดที่เกณฑ์กลางกับกลุ่มไม่ตรงกัน เพราะมันแยกได้ว่าคะแนนมาจากตัวบริษัทหรือมาจากอุตสาหกรรม
และต้องดูค่า reliable ด้วย กลุ่มที่มีไม่ถึงสี่บริษัทในเครื่องทำให้เปอร์เซ็นไทล์ไม่มีความหมาย

ผลตอบแทนที่รายงานเป็นผลตอบแทนรวมซึ่งนับปันผลแล้ว ในฉากทัศน์จะแยกให้เห็นสองส่วนคือ
price_return_annualized กับ dividend_contribution เวลาเทียบหุ้นโตช้าที่จ่ายปันผลกับหุ้นโตเร็วที่ไม่จ่าย
ให้พูดถึงทั้งสองส่วน เพราะการดูแต่ส่วนต่างราคาจะเอียงเข้าข้างหุ้นที่ไม่จ่ายเสมอ

คะแนนรวมอ่านจากอดีตแล้วสมมติว่ารูปแบบเดิมดำเนินต่อ มันมองไม่เห็นธุรกิจที่กำลังเปลี่ยนรูป
ซึ่งในช่วงห้าปีมักเป็นสิ่งที่ตัดสินผลจริง คะแนนสูงเป็นเหตุผลให้ไปดูให้ละเอียด ไม่ใช่ข้อสรุป
ถ้าคุณไม่เห็นด้วยกับคะแนน ให้บอกและอธิบายว่าทำไม นั่นมีประโยชน์กว่าการท่องคะแนนซ้ำ

ตัวเลขผลตอบแทนจากฉากทัศน์และจากโมเดลจำลองเป็นผลทางคณิตศาสตร์ของสมมติฐาน ไม่ใช่การพยากรณ์
ห้ามนำเสนอเป็นผลตอบแทนที่คาดหวัง ให้โจมตีสมมติฐานแทน ถ้าคิดว่าสมมติฐานไหนผิดให้บอกว่าค่าที่ถูกควรเป็นเท่าไหร่

หุ้นนอกสหรัฐไม่มีเอกสาร SEC หลักฐานฝั่งความเสี่ยงจึงไม่เท่ากันระหว่างหุ้นอเมริกากับหุ้นประเทศอื่น
หุ้นกลุ่มธนาคารและประกันทำให้อัตราส่วนอย่างหนี้สุทธิและ EV/EBITDA ไม่มีความหมาย
ข้อมูลจาก Yahoo Finance เป็นข้อมูลดีเลย์และมีการแก้ย้อนหลัง
การติดแท็กข่าวใช้การจับคำ จึงผิดพลาดได้เป็นปกติ

## วิธีเขียนคำตอบ

ตอบคำถามก่อน แล้วค่อยให้เหตุผล คนที่อ่านแค่ย่อหน้าแรกควรได้คำตอบแล้ว
บอกเมื่อไม่รู้ ช่องว่างในข้อมูลเป็นส่วนหนึ่งของการวิเคราะห์ คำตอบที่มั่นใจแต่ตั้งอยู่บนช่องว่างแย่กว่าการบอกว่าข้อมูลไม่พอ
แยกให้ชัดว่าอันไหนคือสิ่งที่ข้อมูลบอก อันไหนคือสิ่งที่คุณอนุมาน
อย่าเลี่ยงจนไร้ประโยชน์ คำว่าขึ้นก็ได้ลงก็ได้ไม่ใช่การวิเคราะห์ ให้เลือกข้างและบอกเงื่อนไขที่ทำให้ผิด

ระบบนี้เป็นเครื่องมือวิจัย ไม่ใช่คำแนะนำการลงทุน ถ้าผู้ใช้ถามตรงๆ ว่าควรซื้อไหม
ให้วิเคราะห์อย่างเต็มที่และบอกว่าการตัดสินใจและความเสี่ยงเป็นของเขา โดยไม่ต้องเทศนา"""


# ---------------------------------------------------------------------------
# tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_stocks",
        "description": (
            "List every ticker that already has data stored locally, with the company "
            "name, sector, composite score, and the date of the newest snapshot. Call "
            "this first when the user asks a broad question such as which stock looks "
            "best, so you know what you actually have."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_fundamentals",
        "description": (
            "Financial statements and derived metrics for one ticker: revenue and profit "
            "history, growth rates, margins and their trend, returns on capital, balance "
            "sheet, and valuation multiples. This is the primary source for any question "
            "about how a company is performing or how fast it is growing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Symbol, e.g. NVDA, 7203.T, PTT.BK"}
            },
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_score",
        "description": (
            "The five-pillar scorecard and the three five-year scenarios for one ticker, "
            "including every assumption behind each scenario and the warnings the numbers "
            "raise. Use it to see how a company compares on the shared yardstick, and to "
            "get the assumptions you are expected to argue with."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_prediction",
        "description": (
            "Monte Carlo simulation results for one ticker: the distribution of modelled "
            "five-year annualized returns with percentiles, the probability of losing "
            "money, and a sensitivity ranking of which assumption moves the answer most. "
            "Also returns the fitted growth-fade curve and its statistics. Remember this "
            "simulates the spread of assumptions, not a probability of anything real."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_news",
        "description": (
            "Recent collected headlines for one ticker with event tags, publisher, date "
            "and link. Tagging is keyword-based and mislabels articles regularly, so read "
            "the headlines rather than trusting the tags."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "limit": {"type": "integer", "description": "How many headlines, default 25"},
            },
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_risk_factors",
        "description": (
            "Risk factors the company itself disclosed in its annual SEC filing, as "
            "headings plus filing metadata. This is the company writing under legal "
            "liability, which carries more weight than journalism. US filers only; "
            "returns nothing for a listing with no SEC presence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_macro_news",
        "description": (
            "Recent macro and thematic headlines affecting the whole portfolio: rates, "
            "inflation, trade policy, capital cycles. Use it when the question is about "
            "the environment rather than one company."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "search_ticker",
        "description": (
            "Find the ticker symbol for a company anywhere in the world, by name or "
            "partial symbol. Returns every listing found with its exchange. Use this "
            "before assuming a symbol, and tell the user which listing you picked: a "
            "home listing and its US ADR are different instruments in different "
            "currencies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Company name or symbol"}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fetch_stock_data",
        "description": (
            "Download fresh data for a ticker and compute its score: statements, news, "
            "SEC filings where available. This is the only tool with a side effect and "
            "it takes one to two minutes. Ask the user before calling it unless they "
            "explicitly asked you to add or refresh a stock."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "news_days": {"type": "integer", "description": "News lookback, default 90"},
            },
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_peer_comparison",
        "description": (
            "Where a company sits among the others in its sector: its value, the peer "
            "median, and its percentile for growth, margins, returns on capital, "
            "valuation and yield. Also returns the places where the absolute scorecard "
            "and the peer group disagree, which is the most useful part: a metric that "
            "scores well on the fixed band but sits at the sector median means the "
            "company is riding an industry rather than beating one. Use this whenever "
            "you are about to call a margin or a multiple good or bad, because the fixed "
            "bands cannot know what is normal for that industry. Check `reliable` first; "
            "a small group makes every percentile meaningless."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_sector_medians",
        "description": (
            "Median growth, margins, returns and valuation for every sector that has "
            "data on disk, with the number of companies behind each. Use it for "
            "questions about what is normal in an industry, or to check whether a "
            "sector has enough members for its medians to mean anything."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "compare_stocks",
        "description": (
            "Side-by-side comparison of several tickers on the shared yardstick: composite "
            "and pillar scores, growth, margin, valuation, and modelled return. Use it for "
            "any 'which is better' question, since a ranking forces the trade-off into the "
            "open in a way separate write-ups never do."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tickers"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_report",
        "description": (
            "List generated reports, or read one by filename. Data packs contain facts "
            "only; files named thesis contain analysis written earlier by an agent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Omit to list what exists; pass a filename to read it.",
                }
            },
            "additionalProperties": False,
        },
    },
]


# ---------------------------------------------------------------------------
# tool implementations
# ---------------------------------------------------------------------------

def _snap(folder, ticker):
    p = latest_snapshot(folder / ticker.upper())
    if not p:
        return None, None
    return read_json(p), p.stem


def _tool_list_stocks():
    if not RAW.exists():
        return {"stocks": [], "note": "No data stored yet."}
    rows = []
    for d in sorted(RAW.iterdir()):
        if not d.is_dir():
            continue
        f, date = _snap(RAW, d.name)
        if not f:
            continue
        s, _ = _snap(SCORES, d.name)
        prof = f.get("profile") or {}
        rows.append(
            {
                "ticker": d.name,
                "company": prof.get("name"),
                "sector": prof.get("sector"),
                "country": prof.get("country"),
                "composite_score": (s or {}).get("composite_score"),
                "snapshot_date": date,
            }
        )
    return {"stocks": rows, "count": len(rows)}


def _tool_get_fundamentals(ticker):
    f, date = _snap(RAW, ticker)
    if not f:
        return {
            "error": "No local data for {}.".format(ticker.upper()),
            "hint": "Use search_ticker to confirm the symbol, then ask the user before calling fetch_stock_data.",
        }
    return {
        "ticker": f.get("ticker"),
        "snapshot_date": date,
        "profile": f.get("profile"),
        "market": f.get("market"),
        "analyst": f.get("analyst"),
        "metrics": f.get("metrics"),
        "annual": f.get("annual"),
    }


def _tool_get_score(ticker):
    s, date = _snap(SCORES, ticker)
    if not s:
        return {"error": "No score for {}. Fundamentals may exist; the score has not been computed.".format(ticker.upper())}
    s = dict(s)
    s["snapshot_date"] = date
    return s


def _tool_get_prediction(ticker):
    p, date = _snap(PREDICTIONS, ticker)
    if not p:
        return {"error": "No simulation stored for {}. The user can run it from the prediction page.".format(ticker.upper())}
    out = dict(p)
    out["snapshot_date"] = date
    sim = out.get("simulation") or {}
    # The raw distribution is thousands of numbers and adds nothing to a reply.
    if "distribution" in sim:
        sim = dict(sim)
        sim.pop("distribution", None)
        out["simulation"] = sim
    return out


def _tool_get_news(ticker, limit=25):
    n, date = _snap(NEWS, ticker)
    if not n:
        return {"error": "No news collected for {}.".format(ticker.upper())}
    arts = (n.get("articles") or [])[: max(1, int(limit or 25))]
    return {
        "ticker": n.get("ticker"),
        "snapshot_date": date,
        "lookback_days": n.get("lookback_days"),
        "summary": n.get("summary"),
        "articles": [
            {
                "title": a.get("title"),
                "published": a.get("published"),
                "publisher": a.get("publisher"),
                "tags": a.get("tags"),
                "lean": a.get("lean"),
                "url": a.get("url"),
            }
            for a in arts
        ],
        "caveat": "Tags are keyword matches and mislabel articles regularly.",
    }


def _tool_get_risk_factors(ticker):
    fl, date = _snap(FILINGS, ticker)
    if not fl:
        return {
            "error": "No SEC filings for {}.".format(ticker.upper()),
            "note": "Listings outside the US have no EDGAR presence. This is a limit of the data source, not a statement about the company.",
        }
    rf = fl.get("risk_factors") or {}
    return {
        "ticker": fl.get("ticker"),
        "snapshot_date": date,
        "company": fl.get("company"),
        "recent_filings": (fl.get("filings") or [])[:8],
        "risk_factor_headings": rf.get("candidate_risk_headings", [])[:30],
        "from_filing": rf.get("from_filing"),
        "extraction_error": rf.get("error"),
        "source_url": rf.get("source_url"),
    }


def _tool_get_macro_news(limit=25):
    m = read_json(latest_snapshot(NEWS / "_macro") or Path("/nonexistent"))
    if not m:
        return {"error": "No macro sweep collected yet."}
    return {
        "as_of": m.get("as_of"),
        "lookback_days": m.get("lookback_days"),
        "summary": m.get("summary"),
        "articles": [
            {
                "title": a.get("title"),
                "published": a.get("published"),
                "publisher": a.get("publisher"),
                "url": a.get("url"),
            }
            for a in (m.get("articles") or [])[: max(1, int(limit or 25))]
        ],
    }


def _tool_search_ticker(query):
    from search_tickers import search

    hits = search(query, limit=10)
    if not hits:
        return {"error": "No listing found for {!r}.".format(query)}
    return {"query": query, "results": hits}


def _tool_fetch_stock_data(ticker, news_days=90):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ui"))
    from shared import run_pipeline

    steps = run_pipeline(ticker, news_days=int(news_days or 90), with_filings=True)
    return {
        "ticker": ticker.upper(),
        "steps": [{"stage": s, "status": st, "detail": d} for s, st, d in steps],
    }


def _tool_get_peer_comparison(ticker):
    from peers import absolute_vs_relative

    ctx = absolute_vs_relative(ticker)
    if not ctx.get("ok"):
        return {"error": ctx.get("reason", "เทียบไม่ได้")}
    return ctx


def _tool_get_sector_medians():
    from peers import load_universe_metrics, sector_table

    table = sector_table(load_universe_metrics())
    # Strip metrics with no coverage so the payload stays readable.
    for d in table.values():
        d["medians"] = {
            k: v for k, v in d["medians"].items() if v.get("median") is not None
        }
    return {
        "sectors": table,
        "note": "A sector with fewer than 4 companies on disk cannot support a percentile.",
    }


def _tool_compare_stocks(tickers):
    rows = []
    for tk in tickers or []:
        f, fdate = _snap(RAW, tk)
        s, _ = _snap(SCORES, tk)
        if not f:
            rows.append({"ticker": tk.upper(), "error": "no local data"})
            continue
        m = f.get("metrics") or {}
        prof = f.get("profile") or {}
        pil = (s or {}).get("pillars") or {}
        base = ((s or {}).get("projection_5y") or {}).get("base") or {}
        rows.append(
            {
                "ticker": tk.upper(),
                "company": prof.get("name"),
                "sector": prof.get("sector"),
                "snapshot_date": fdate,
                "composite_score": (s or {}).get("composite_score"),
                "pillars": {k: (v or {}).get("score") for k, v in pil.items()},
                "revenue_growth_ttm": m.get("revenue_growth_ttm"),
                "revenue_cagr": m.get("revenue_cagr"),
                "operating_margin": m.get("operating_margin_latest"),
                "roic_est": m.get("roic_est"),
                "forward_pe": m.get("forward_pe"),
                "modelled_base_return": base.get("annualized_return"),
                "currency_mismatch": m.get("currency_mismatch"),
                "flags": (s or {}).get("flags"),
            }
        )
    return {"comparison": rows}


def _tool_read_report(filename=None):
    if not REPORTS.exists():
        return {"error": "No reports directory yet."}
    files = sorted(REPORTS.glob("*.md"), reverse=True)
    if not filename:
        return {
            "reports": [
                {"filename": p.name, "size_kb": round(p.stat().st_size / 1024)} for p in files[:30]
            ]
        }
    target = REPORTS / Path(filename).name  # never escape the reports directory
    if not target.exists():
        return {"error": "No report named {}.".format(filename)}
    text = target.read_text(encoding="utf-8")
    truncated = len(text) > 60000
    return {"filename": target.name, "truncated": truncated, "content": text[:60000]}


DISPATCH = {
    "list_stocks": lambda i: _tool_list_stocks(),
    "get_fundamentals": lambda i: _tool_get_fundamentals(i["ticker"]),
    "get_score": lambda i: _tool_get_score(i["ticker"]),
    "get_prediction": lambda i: _tool_get_prediction(i["ticker"]),
    "get_news": lambda i: _tool_get_news(i["ticker"], i.get("limit", 25)),
    "get_risk_factors": lambda i: _tool_get_risk_factors(i["ticker"]),
    "get_macro_news": lambda i: _tool_get_macro_news(i.get("limit", 25)),
    "search_ticker": lambda i: _tool_search_ticker(i["query"]),
    "fetch_stock_data": lambda i: _tool_fetch_stock_data(i["ticker"], i.get("news_days", 90)),
    "get_peer_comparison": lambda i: _tool_get_peer_comparison(i["ticker"]),
    "get_sector_medians": lambda i: _tool_get_sector_medians(),
    "compare_stocks": lambda i: _tool_compare_stocks(i["tickers"]),
    "read_report": lambda i: _tool_read_report(i.get("filename")),
}

SIDE_EFFECT_TOOLS = {"fetch_stock_data"}


def execute_tool(name, tool_input):
    """Run one tool. Errors come back as data so the model can recover."""
    fn = DISPATCH.get(name)
    if not fn:
        return {"error": "Unknown tool {!r}.".format(name)}
    try:
        return fn(tool_input or {})
    except Exception as e:
        return {"error": "{}: {}".format(type(e).__name__, e)}


# ---------------------------------------------------------------------------
# credentials and client
# ---------------------------------------------------------------------------

def credentials_available():
    """Whether the SDK will find a credential without being handed one."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    # An `ant auth login` profile lives here and the SDK reads it automatically.
    profile_dir = Path.home() / ".config" / "anthropic"
    return profile_dir.exists() and any(profile_dir.iterdir())


def make_client(api_key=None):
    import anthropic

    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


# ---------------------------------------------------------------------------
# the agentic loop
# ---------------------------------------------------------------------------

def run_turn(client, messages, on_text=None, on_tool_start=None, on_tool_end=None,
             model=MODEL, max_rounds=MAX_TOOL_ROUNDS, effort="high"):
    """One user turn: stream text, run tools, loop until Claude stops calling them.

    `messages` is mutated in place so the caller keeps the full history, including
    thinking blocks, which must be echoed back unchanged on the same model.

    Returns a dict with the final text and the tool calls that ran.
    """
    tool_log = []

    for _round in range(max_rounds):
        with client.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for event in stream:
                if (
                    on_text
                    and event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    on_text(event.delta.text)
            response = stream.get_final_message()

        # Echo the assistant turn back whole. Stripping thinking blocks here
        # would break the next request on this model.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            detail = getattr(response, "stop_details", None)
            return {
                "text": "คำขอนี้ถูกปฏิเสธโดยระบบความปลอดภัย{}".format(
                    " (หมวด {})".format(detail.category) if detail and detail.category else ""
                ),
                "tools": tool_log,
                "refused": True,
            }

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text")
            return {"text": text, "tools": tool_log, "refused": False}

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        results = []
        for block in tool_uses:
            if on_tool_start:
                on_tool_start(block.name, block.input)
            result = execute_tool(block.name, block.input)
            is_error = isinstance(result, dict) and "error" in result
            if on_tool_end:
                on_tool_end(block.name, result)
            tool_log.append({"name": block.name, "input": block.input, "error": is_error})
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str)[:180000],
                    "is_error": is_error,
                }
            )
        # All results from one assistant turn go back in a single user message.
        messages.append({"role": "user", "content": results})

    return {
        "text": "หยุดหลังเรียกเครื่องมือครบ {} รอบโดยยังไม่ได้ข้อสรุป ลองถามให้เฉพาะเจาะจงขึ้น".format(max_rounds),
        "tools": tool_log,
        "refused": False,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    if not credentials_available():
        print("No Anthropic credentials found. Set ANTHROPIC_API_KEY or run `ant auth login`.",
              file=sys.stderr)
        return 1

    question = " ".join(sys.argv[1:])
    client = make_client()
    messages = [{"role": "user", "content": question}]

    result = run_turn(
        client,
        messages,
        on_text=lambda t: print(t, end="", flush=True),
        on_tool_start=lambda n, i: print("\n[tool] {} {}\n".format(n, i), file=sys.stderr),
    )
    print()
    if result["tools"]:
        print("\ntools used: " + ", ".join(t["name"] for t in result["tools"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
