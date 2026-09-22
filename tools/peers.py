"""Compare a company against the others in its sector, not against a fixed band.

The scorecard in `score.py` grades every metric on an absolute scale, which is
what makes companies comparable across the whole universe. The cost is that the
scale cannot know what is normal for an industry. A 75% gross margin is ordinary
for enterprise software and extraordinary for a carmaker, yet both land in the
same band and collect the same points. The quality pillar therefore measures
which sector a company is in about as much as it measures how good the company is.

This module supplies the missing half: where a company sits among its actual
peers. Read the two together. An absolute score says whether the business is good
in general; a peer percentile says whether it is good at being what it is.

Usage:
    uv run python tools/peers.py NVDA
    uv run python tools/peers.py --sectors        # the sector table
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import RAW, latest_snapshot, read_json, resolve_tickers  # noqa: E402
from score import drop_currency_contaminated  # noqa: E402

# Metrics worth a peer comparison, with the direction that counts as better.
# Valuation and leverage are "lower is better", so their percentile is inverted.
PEER_METRICS = {
    "revenue_cagr": ("การเติบโตเฉลี่ย", "revenue CAGR", True),
    "revenue_growth_ttm": ("การเติบโตปีล่าสุด", "revenue growth TTM", True),
    "gross_margin_latest": ("มาร์จิ้นขั้นต้น", "gross margin", True),
    "operating_margin_latest": ("มาร์จิ้นดำเนินงาน", "operating margin", True),
    "net_margin_latest": ("มาร์จิ้นสุทธิ", "net margin", True),
    "fcf_margin_latest": ("มาร์จิ้นเงินสดอิสระ", "FCF margin", True),
    "roic_est": ("ROIC", "ROIC", True),
    "roe": ("ROE", "ROE", True),
    "forward_pe": ("P/E ข้างหน้า", "forward P/E", False),
    "ev_to_ebitda": ("EV/EBITDA", "EV/EBITDA", False),
    "price_to_sales": ("P/S", "price to sales", False),
    "net_debt_to_ebitda": ("หนี้สุทธิ/EBITDA", "net debt / EBITDA", False),
    "dividend_yield": ("ปันผล", "dividend yield", True),
}

# Below this many companies a percentile is arithmetic without meaning. The
# threshold counts the company itself, so 4 means three real peers.
MIN_PEERS = 4


def _median(vals):
    s = sorted(v for v in vals if v is not None)
    if not s:
        return None
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def _percentile_rank(value, population, higher_is_better=True):
    """Share of peers this value beats, 0 to 1. None when it cannot be computed."""
    vals = [v for v in population if v is not None]
    if value is None or len(vals) < 2:
        return None
    if higher_is_better:
        beaten = sum(1 for v in vals if value > v)
    else:
        beaten = sum(1 for v in vals if value < v)
    return beaten / (len(vals) - 1) if len(vals) > 1 else None


def load_universe_metrics(tickers=None):
    """Every ticker on disk as (ticker, sector, industry, metrics)."""
    if tickers is None:
        tickers = [p.name for p in RAW.iterdir() if p.is_dir()] if RAW.exists() else []
    rows = []
    for tk in tickers:
        snap = latest_snapshot(RAW / tk.upper())
        if not snap:
            continue
        f = read_json(snap) or {}
        prof = f.get("profile") or {}
        rows.append(
            {
                "ticker": tk.upper(),
                "company": prof.get("name"),
                "sector": prof.get("sector") or "ไม่ระบุ",
                "industry": prof.get("industry") or "ไม่ระบุ",
                # Cleaned at the door. An ADR's price_to_sales, ev_to_ebitda and
                # fcf_yield divide a market number by a statement number in another
                # currency, and leaving them in corrupts more than that company's
                # own percentile: the contaminated value goes into the sector
                # median, which every other member is then ranked against. TSM sat
                # at the 100th percentile on a price-to-sales of 0.5.
                "metrics": drop_currency_contaminated(f.get("metrics") or {})[0],
                "snapshot": snap.stem,
            }
        )
    return rows


def group_sizes(rows, key="sector"):
    out = {}
    for r in rows:
        out.setdefault(r[key], []).append(r["ticker"])
    return out


def sector_table(rows):
    """Median of each peer metric per sector, plus how many companies back it."""
    groups = {}
    for r in rows:
        groups.setdefault(r["sector"], []).append(r)

    out = {}
    for sector, members in sorted(groups.items()):
        stats = {}
        for key in PEER_METRICS:
            vals = [m["metrics"].get(key) for m in members]
            stats[key] = {
                "median": _median(vals),
                "coverage": sum(1 for v in vals if v is not None),
            }
        out[sector] = {
            "n": len(members),
            "tickers": sorted(m["ticker"] for m in members),
            "reliable": len(members) >= MIN_PEERS,
            "medians": stats,
        }
    return out


def peer_context(ticker, rows=None, level="sector"):
    """Where one company sits among its peers, metric by metric."""
    rows = rows if rows is not None else load_universe_metrics()
    me = next((r for r in rows if r["ticker"] == ticker.upper()), None)
    if not me:
        return {"ok": False, "reason": "ไม่มีข้อมูลของ {} ในเครื่อง".format(ticker.upper())}

    group_key = me[level]
    peers = [r for r in rows if r[level] == group_key]
    n = len(peers)

    comparisons = []
    for key, (label_th, label_en, higher_better) in PEER_METRICS.items():
        mine = me["metrics"].get(key)
        population = [r["metrics"].get(key) for r in peers if r["ticker"] != me["ticker"]]
        med = _median([r["metrics"].get(key) for r in peers])
        pct = _percentile_rank(mine, [r["metrics"].get(key) for r in peers], higher_better)
        if mine is None and med is None:
            continue
        comparisons.append(
            {
                "key": key,
                "label": label_th,
                "label_en": label_en,
                "higher_is_better": higher_better,
                "value": mine,
                "peer_median": med,
                "percentile": pct,
                "peers_with_data": sum(1 for v in population if v is not None),
            }
        )

    ranked = [c for c in comparisons if c["percentile"] is not None]
    ranked.sort(key=lambda c: -(c["percentile"] or 0))

    return {
        "ok": True,
        "ticker": me["ticker"],
        "company": me["company"],
        "level": level,
        "group": group_key,
        "peers": sorted(r["ticker"] for r in peers if r["ticker"] != me["ticker"]),
        "n_in_group": n,
        "reliable": n >= MIN_PEERS,
        "min_peers_needed": MIN_PEERS,
        # Size is necessary but nowhere near sufficient. Consumer Cyclical here
        # holds Amazon, Toyota, LVMH, Alibaba and Tesla: five companies, five
        # industries, one label. It clears MIN_PEERS and is still not a peer
        # group, so report the spread rather than letting `reliable` imply more
        # than a count can support.
        "distinct_industries": len({r.get("industry") for r in peers}),
        "homogeneous": len({r.get("industry") for r in peers}) <= max(1, n // 2),
        "comparisons": comparisons,
        "strongest": ranked[:3],
        "weakest": ranked[-3:][::-1] if len(ranked) >= 3 else [],
        "snapshot": me["snapshot"],
        "caveat": (
            "เปรียบเทียบกับหุ้นที่มีข้อมูลในเครื่องเท่านั้น ไม่ใช่กับทั้งอุตสาหกรรมจริง "
            "ยิ่งกลุ่มเล็ก เปอร์เซ็นไทล์ยิ่งไม่มีความหมาย"
        ),
    }


def absolute_vs_relative(ticker, rows=None):
    """Where the absolute band and the peer group disagree.

    This is the finding worth reading. A metric that scores well on the fixed
    scale but sits below its sector's median means the company is riding an
    industry, not beating one. The reverse means a good operator in a poor
    industry, which the composite score understates.
    """
    from score import band_score

    ctx = peer_context(ticker, rows=rows)
    if not ctx.get("ok"):
        return ctx

    findings = []
    for c in ctx["comparisons"]:
        if c["value"] is None or c["percentile"] is None:
            continue
        abs_score = band_score(c["key"], c["value"])
        if abs_score is None:
            continue
        rel_score = c["percentile"] * 100
        gap = abs_score - rel_score
        if abs(gap) < 25:
            continue
        findings.append(
            {
                "key": c["key"],
                "label": c["label"],
                "label_en": c["label_en"],
                "value": c["value"],
                "peer_median": c["peer_median"],
                "absolute_score": round(abs_score, 1),
                "peer_percentile": round(rel_score, 1),
                "gap": round(gap, 1),
                "reading": (
                    "ดูดีบนเกณฑ์กลาง แต่อยู่กลางหรือท้ายกลุ่มของตัวเอง เป็นการได้อานิสงส์จากอุตสาหกรรม "
                    "มากกว่าการเอาชนะคู่แข่ง"
                    if gap > 0
                    else "ดูไม่เด่นบนเกณฑ์กลาง แต่อยู่ต้นกลุ่มของตัวเอง คะแนนรวมจึงประเมินต่ำกว่าความจริง"
                ),
            }
        )
    findings.sort(key=lambda f: -abs(f["gap"]))
    ctx["disagreements"] = findings
    return ctx


def _fmt(key, v):
    if v is None:
        return "n/a"
    if key in ("forward_pe", "ev_to_ebitda", "price_to_sales", "net_debt_to_ebitda"):
        return "{:.1f}".format(v)
    return "{:.1%}".format(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--sectors", action="store_true", help="print the sector medians and stop")
    ap.add_argument("--level", default="sector", choices=["sector", "industry"])
    args = ap.parse_args()

    rows = load_universe_metrics()
    if not rows:
        print("No data on disk. Run tools/fetch_fundamentals.py first.", file=sys.stderr)
        return 2

    if args.sectors:
        table = sector_table(rows)
        print("{:<26} {:>4} {:>9} {:>9} {:>9} {:>8}".format(
            "SECTOR", "N", "revCAGR", "opMgn", "ROIC", "fwdPE"))
        print("-" * 70)
        for sector, d in sorted(table.items(), key=lambda kv: -kv[1]["n"]):
            med = d["medians"]
            flag = "" if d["reliable"] else "  (too few to compare)"
            print("{:<26} {:>4} {:>9} {:>9} {:>9} {:>8}{}".format(
                sector[:26], d["n"],
                _fmt("revenue_cagr", med["revenue_cagr"]["median"]),
                _fmt("operating_margin_latest", med["operating_margin_latest"]["median"]),
                _fmt("roic_est", med["roic_est"]["median"]),
                _fmt("forward_pe", med["forward_pe"]["median"]), flag))
        print("\nA percentile needs at least {} companies in the group to mean anything.".format(MIN_PEERS))
        return 0

    tickers = resolve_tickers(args.tickers)
    if not tickers:
        print("Pass tickers, or --sectors for the group table.", file=sys.stderr)
        return 2

    for tk in tickers:
        ctx = absolute_vs_relative(tk, rows=rows)
        if not ctx.get("ok"):
            print("{:<10} {}".format(tk.upper(), ctx.get("reason")), file=sys.stderr)
            continue

        print("\n{} {} — {} ({} companies in group)".format(
            ctx["ticker"], ctx.get("company") or "", ctx["group"], ctx["n_in_group"]))
        if not ctx["reliable"]:
            print("  Warning: only {} companies here, so percentiles are close to meaningless.".format(
                ctx["n_in_group"]))
        elif not ctx.get("homogeneous"):
            print("  Warning: {} companies spanning {} different industries. The group clears the "
                  "size threshold but is not an economic peer set, so read these percentiles as "
                  "'versus this sector label', not 'versus comparable businesses'.".format(
                      ctx["n_in_group"], ctx["distinct_industries"]))
        print("  {:<24} {:>10} {:>12} {:>12}".format("METRIC", "VALUE", "PEER MEDIAN", "PERCENTILE"))
        for c in ctx["comparisons"]:
            pct = "n/a" if c["percentile"] is None else "{:.0f}th".format(c["percentile"] * 100)
            print("  {:<24} {:>10} {:>12} {:>12}".format(
                c["label_en"][:24], _fmt(c["key"], c["value"]),
                _fmt(c["key"], c["peer_median"]), pct))

        if ctx.get("disagreements"):
            print("\n  Where the absolute band and the peer group disagree:")
            for d in ctx["disagreements"][:4]:
                print("    {:<22} band {:>5.0f} vs peers {:>5.0f}  ({:+.0f})".format(
                    d["label_en"][:22], d["absolute_score"], d["peer_percentile"], d["gap"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
