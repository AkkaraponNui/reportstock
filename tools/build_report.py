"""Assemble every collected source for a set of tickers into one markdown data pack.

Usage:
    uv run python tools/build_report.py NVDA MSFT --name ai-leaders
    uv run python tools/build_report.py ai_infra
    uv run python tools/build_report.py --all --name full-universe

Writes data/reports/<YYYY-MM-DD>-<name>-datapack.md.

This file is deliberately facts-only: numbers, headlines, filing references, and
the assumptions behind each projection. It carries no judgement and no
recommendation. The analyst agent reads it and writes the thesis; keeping the two
apart means the narrative can always be checked against the pack it came from.
"""
from __future__ import annotations

import argparse
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
    resolve_tickers,
    today,
)


def _money(v):
    if v is None:
        return "n/a"
    a = abs(v)
    for cut, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= cut:
            return "{:.2f}{}".format(v / cut, suf)
    return "{:.0f}".format(v)


def _pct(v, digits=1):
    return "n/a" if v is None else "{:.{d}f}%".format(v * 100, d=digits)


def _num(v, digits=1):
    return "n/a" if v is None else "{:.{d}f}".format(v, d=digits)


PREDICTIONS = RAW.parent / "predictions"


def _load(ticker):
    tk = ticker.upper()
    return {
        "fundamentals": read_json(latest_snapshot(RAW / tk) or Path("/nonexistent")),
        "score": read_json(latest_snapshot(SCORES / tk) or Path("/nonexistent")),
        "news": read_json(latest_snapshot(NEWS / tk) or Path("/nonexistent")),
        "filings": read_json(latest_snapshot(FILINGS / tk) or Path("/nonexistent")),
        "prediction": read_json(latest_snapshot(PREDICTIONS / tk) or Path("/nonexistent")),
    }


def ranking_table(bundles):
    lines = [
        "| Ticker | Company | Sector | Score | Growth | Quality | Cash | Balance | Value | Base 5y/yr | Grade |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    rows = []
    for tk, b in bundles.items():
        s = b.get("score")
        if not s:
            continue
        p = s.get("pillars", {})
        base = (s.get("projection_5y") or {}).get("base") or {}
        rows.append(
            {
                "tk": tk,
                "score": s.get("composite_score"),
                "line": "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                    tk,
                    (s.get("company") or "?")[:28],
                    s.get("sector") or "?",
                    _num(s.get("composite_score")),
                    _num(p.get("growth", {}).get("score"), 0),
                    _num(p.get("quality", {}).get("score"), 0),
                    _num(p.get("cash", {}).get("score"), 0),
                    _num(p.get("balance_sheet", {}).get("score"), 0),
                    _num(p.get("valuation", {}).get("score"), 0),
                    _pct(base.get("annualized_return")),
                    (s.get("grade") or "")[:2],
                ),
            }
        )
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    lines.extend(r["line"] for r in rows)
    return "\n".join(lines)


def metrics_table(m):
    rows = [
        ("Revenue CAGR ({}y)".format(m.get("revenue_cagr_years") or "?"), _pct(m.get("revenue_cagr"))),
        ("Revenue growth TTM", _pct(m.get("revenue_growth_ttm"))),
        ("Net income CAGR", _pct(m.get("net_income_cagr"))),
        ("FCF CAGR", _pct(m.get("fcf_cagr"))),
        ("Gross margin", _pct(m.get("gross_margin_latest"))),
        ("Operating margin", _pct(m.get("operating_margin_latest"))),
        ("Operating margin trend / yr", _pct(m.get("operating_margin_trend"), 2)),
        ("Net margin", _pct(m.get("net_margin_latest"))),
        ("FCF margin", _pct(m.get("fcf_margin_latest"))),
        ("ROIC (est.)", _pct(m.get("roic_est"))),
        ("ROE", _pct(m.get("roe"))),
        ("R&D intensity", _pct(m.get("rnd_intensity_latest"))),
        ("Net debt", _money(m.get("net_debt"))),
        ("Net debt / EBITDA", _num(m.get("net_debt_to_ebitda"), 2) + "x"),
        ("Current ratio", _num(m.get("current_ratio"), 2)),
        ("Market cap", _money(m.get("market_cap"))),
        ("Forward P/E", _num(m.get("forward_pe"))),
        ("Trailing P/E", _num(m.get("trailing_pe"))),
        ("PEG (est.)", _num(m.get("peg_est"), 2)),
        ("EV / EBITDA", _num(m.get("ev_to_ebitda"), 1)),
        ("Price / sales", _num(m.get("price_to_sales"), 1)),
        ("FCF yield", _pct(m.get("fcf_yield"), 2)),
        ("Beta", _num(m.get("beta"), 2)),
    ]
    out = ["| Metric | Value |", "|---|---:|"]
    out += ["| {} | {} |".format(k, v) for k, v in rows]
    return "\n".join(out)


def history_table(f):
    a = (f or {}).get("annual") or {}
    periods = a.get("periods") or []
    if not periods:
        return "_No annual statements retrieved._"
    series = [
        ("Revenue", a.get("revenue") or []),
        ("Gross profit", a.get("gross_profit") or []),
        ("Operating income", a.get("operating_income") or []),
        ("Net income", a.get("net_income") or []),
        ("Free cash flow", a.get("free_cash_flow") or []),
        ("R&D", a.get("rnd") or []),
        ("Total debt", a.get("total_debt") or []),
        ("Cash", a.get("cash") or []),
    ]
    header = "| Line item | " + " | ".join(periods) + " |"
    divider = "|---|" + "---:|" * len(periods)
    lines = [header, divider]
    for label, vals in series:
        vals = list(vals) + [None] * (len(periods) - len(vals))
        lines.append("| {} | ".format(label) + " | ".join(_money(v) for v in vals[: len(periods)]) + " |")
    return "\n".join(lines)


def scenario_table(s):
    scen = (s or {}).get("projection_5y") or {}
    if not scen:
        return "_No projection: the inputs it needs are missing._"
    lines = [
        "| Scenario | Start growth | End net margin | Exit P/E | Implied mkt cap | Total return | Annualized |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("bear", "base", "bull"):
        v = scen.get(name)
        if not v:
            continue
        a = v["assumptions"]
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} |".format(
                name,
                _pct(a["start_growth"]),
                _pct(a["end_net_margin"]),
                _num(a["exit_pe"]),
                _money(v["implied_market_cap"]),
                _pct(v["total_return"], 0),
                _pct(v["annualized_return"]),
            )
        )
    return "\n".join(lines)


def prediction_table(pred):
    """The simulated range, when a Monte Carlo run exists for this ticker."""
    sim = (pred or {}).get("simulation") or {}
    if not sim.get("ok"):
        return None
    r = sim["annualized_return"]
    p = sim["probabilities"]
    sens = (pred or {}).get("sensitivity") or {}

    lines = [
        "Simulated over {:,} runs on {}. This is the spread of the assumptions, not a "
        "forecast, and it has never been validated out of sample.".format(
            sim.get("runs", 0), (pred.get("as_of") or "")[:10]
        ),
        "",
        "| p05 | p25 | median | p75 | p95 | P(loss) | P(doubles) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        "| {} | {} | **{}** | {} | {} | {} | {} |".format(
            _pct(r["p05"]), _pct(r["p25"]), _pct(r["p50"]), _pct(r["p75"]), _pct(r["p95"]),
            _pct(p["loses_money"], 0), _pct(p["doubles_in_5y"], 0),
        ),
        "",
    ]
    if sens.get("ok") and sens.get("levers"):
        top = sens["levers"][0]
        lines += [
            "The assumption carrying the answer is **{}**, worth {} percentage points "
            "of annualized return between its low and high case.".format(
                top.get("lever_en") or top["lever"], _num(top["swing"] * 100, 1)
            ),
            "",
            "| Assumption | Low case | High case | Swing |",
            "|---|---:|---:|---:|",
        ]
        for x in sens["levers"]:
            lines.append(
                "| {} | {} | {} | {} pts |".format(
                    x.get("lever_en") or x["lever"],
                    _pct(x["low_median"]), _pct(x["high_median"]),
                    _num(x["swing"] * 100, 1),
                )
            )
        lines.append("")
    return "\n".join(lines)


def pillar_detail(s):
    p = (s or {}).get("pillars") or {}
    lines = ["| Pillar | Score | Weight | Coverage | Weakest input |", "|---|---:|---:|---:|---|"]
    for name, d in p.items():
        mets = d.get("metrics") or {}
        scored = [(k, v) for k, v in mets.items() if v.get("score") is not None]
        weakest = min(scored, key=lambda kv: kv[1]["score"])[0] if scored else "-"
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                name,
                _num(d.get("score")),
                _pct(d.get("weight"), 0),
                _pct(d.get("coverage"), 0),
                weakest,
            )
        )
    return "\n".join(lines)


def news_section(n, limit=20):
    if not n:
        return "_No news collected. Run tools/fetch_news.py for this ticker._"
    s = n.get("summary") or {}
    tags = s.get("by_event_tag") or {}
    lean = s.get("headline_lean") or {}
    out = [
        "Collected {} articles over the last {} days. "
        "Headline lean: {} positive, {} negative, {} neutral.".format(
            s.get("total", 0),
            n.get("lookback_days", "?"),
            lean.get("positive", 0),
            lean.get("negative", 0),
            lean.get("neutral", 0),
        ),
        "",
        "Event mix: " + (", ".join("{} {}".format(v, k) for k, v in tags.items()) or "none tagged"),
        "",
        "| Date | Publisher | Tags | Headline |",
        "|---|---|---|---|",
    ]
    for a in (n.get("articles") or [])[:limit]:
        title = (a.get("title") or "").replace("|", "/")
        url = a.get("url")
        headline = "[{}]({})".format(title[:120], url) if url else title[:120]
        out.append(
            "| {} | {} | {} | {} |".format(
                (a.get("published") or "")[:10],
                (a.get("publisher") or "?")[:20],
                ",".join(a.get("tags") or []) or "-",
                headline,
            )
        )
    return "\n".join(out)


def filings_section(f, heading_limit=18):
    if not f:
        return "_No filings collected. US listings only; run tools/fetch_filings.py._"
    out = []
    rows = (f.get("filings") or [])[:10]
    if rows:
        out += ["| Form | Filed | Period | Document |", "|---|---|---|---|"]
        for r in rows:
            out.append(
                "| {} | {} | {} | [link]({}) |".format(
                    r.get("form"), r.get("filed"), r.get("period") or "-", r.get("url")
                )
            )
    rf = f.get("risk_factors") or {}
    if rf.get("error"):
        out += ["", "Risk factors: {}".format(rf["error"])]
    elif rf.get("candidate_risk_headings"):
        out += [
            "",
            "Risk factors from the {} filed {} ({} characters captured):".format(
                (rf.get("from_filing") or {}).get("form", "annual report"),
                (rf.get("from_filing") or {}).get("filed", "?"),
                rf.get("chars"),
            ),
            "",
        ]
        out += ["- {}".format(h) for h in rf["candidate_risk_headings"][:heading_limit]]
        out += ["", "Full text: `{}`".format(rf.get("source_url"))]
    return "\n".join(out)


def macro_section():
    m = read_json(latest_snapshot(NEWS / "_macro") or Path("/nonexistent"))
    if not m:
        return "_No macro sweep collected. Run: uv run python tools/fetch_news.py --macro_"
    out = ["| Date | Publisher | Headline |", "|---|---|---|"]
    for a in (m.get("articles") or [])[:25]:
        title = (a.get("title") or "").replace("|", "/")
        url = a.get("url")
        out.append(
            "| {} | {} | {} |".format(
                (a.get("published") or "")[:10],
                (a.get("publisher") or "?")[:20],
                "[{}]({})".format(title[:120], url) if url else title[:120],
            )
        )
    return "\n".join(out)


def build(tickers, name):
    bundles = {tk.upper(): _load(tk) for tk in tickers}
    stamp = today()

    doc = [
        "# Data pack: {}".format(name),
        "",
        "Generated {} covering {} tickers. Facts only, no recommendation.".format(stamp, len(bundles)),
        "",
        "Sources: Yahoo Finance for financial statements and market data, Google News "
        "and optional news APIs for headlines, SEC EDGAR for filings and risk factors. "
        "Every score and projection is produced by `tools/score.py` from the numbers "
        "shown here, under the assumptions printed with each scenario.",
        "",
        "## Ranking",
        "",
        ranking_table(bundles),
        "",
        "Scores are 0-100 per pillar. `Base 5y/yr` is the modelled annualized return "
        "under base-case assumptions. It is arithmetic, not a forecast.",
        "",
        "## Macro backdrop",
        "",
        macro_section(),
        "",
    ]

    for tk, b in bundles.items():
        f, s, n, fl = b["fundamentals"], b["score"], b["news"], b["filings"]
        pred = b.get("prediction")
        if not f:
            doc += ["## {}".format(tk), "", "_No fundamentals on disk. Run tools/fetch_fundamentals.py {}_".format(tk), ""]
            continue
        prof = f.get("profile") or {}
        mkt = f.get("market") or {}
        ana = f.get("analyst") or {}
        m = f.get("metrics") or {}

        doc += [
            "---",
            "",
            "## {} - {}".format(tk, prof.get("name") or "?"),
            "",
            "{} | {} | {} | listed {}".format(
                prof.get("sector") or "?",
                prof.get("industry") or "?",
                prof.get("country") or "?",
                prof.get("exchange") or "?",
            ),
            "",
            "Price {} {} | market cap {} | {} off the 52-week high | analyst target {} ({} analysts, {})".format(
                _num(mkt.get("price"), 2),
                prof.get("currency") or "",
                _money(mkt.get("market_cap")),
                _pct(mkt.get("off_52w_high")),
                _num(ana.get("target_mean"), 2),
                ana.get("n_analysts") or "?",
                ana.get("recommendation") or "?",
            ),
            "",
        ]
        if prof.get("summary"):
            doc += ["> " + prof["summary"][:700].replace("\n", " "), ""]

        if s:
            doc += [
                "### Scorecard: {} ({})".format(_num(s.get("composite_score")), s.get("grade")),
                "",
                pillar_detail(s),
                "",
                "### Five-year scenarios",
                "",
                scenario_table(s),
                "",
            ]
            pt = prediction_table(pred)
            if pt:
                doc += ["### Simulated range", "", pt]
            if s.get("flags"):
                doc += ["**What the numbers warn about**", ""]
                doc += ["- {}".format(x) for x in s["flags"]]
                doc += [""]
        else:
            doc += ["_No score yet. Run tools/score.py {}_".format(tk), ""]

        doc += [
            "### Key metrics",
            "",
            metrics_table(m),
            "",
            "### Reported history",
            "",
            history_table(f),
            "",
            "### News flow",
            "",
            news_section(n),
            "",
            "### Filings and disclosed risks",
            "",
            filings_section(fl),
            "",
        ]

    doc += [
        "---",
        "",
        "## How to read this",
        "",
        "The scorecard compares companies on one fixed yardstick so that differences "
        "come from the businesses rather than from how each was analysed. The scenario "
        "table is a fade model: today's growth rate decays to a terminal rate over five "
        "years, margins drift along their recent trend, and the result is valued on an "
        "exit multiple blended between today's forward P/E and one justified by terminal "
        "growth. Change any assumption and the output moves with it.",
        "",
        "Known limits: Yahoo Finance data is delayed and occasionally revises; headline "
        "tagging is keyword-based and will mislabel some articles; risk-factor extraction "
        "covers US filers only; and no model here accounts for a business changing shape, "
        "which over five years is the thing most likely to matter.",
        "",
        "Not investment advice.",
        "",
    ]

    out_path = REPORTS / "{}-{}-datapack.md".format(stamp, name)
    out_path.write_text("\n".join(doc), encoding="utf-8")
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--all", action="store_true", help="every ticker with a fundamentals snapshot")
    ap.add_argument("--name", default="watchlist", help="slug used in the output filename")
    args = ap.parse_args()

    if args.all:
        tickers = sorted(p.name for p in RAW.iterdir() if p.is_dir())
    else:
        tickers = resolve_tickers(args.tickers)
    if not tickers:
        print("No tickers with data. Run tools/fetch_fundamentals.py first.", file=sys.stderr)
        return 2

    path = build(tickers, args.name)
    size_kb = path.stat().st_size / 1024
    print("Wrote {} ({:.0f} KB, {} tickers)".format(path, size_kb, len(tickers)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
