"""Score funds on their own terms, and check what a fund duplicates.

Usage:
    uv run python tools/score_funds.py --rank
    uv run python tools/score_funds.py QQQ
    uv run python tools/score_funds.py --overlap QQQ        # vs the stocks tracked here
    uv run python tools/score_funds.py --overlap QQQ VGT    # two funds against each other

Writes data/fund_scores/<TICKER>/<YYYY-MM-DD>.json.

Why this is not the equity scorecard
------------------------------------
A fund has no revenue, no margin and no return on capital, so four of the five
equity pillars have nothing to measure. What decides a fund outcome is a
different list, and the weighting below reflects an uncomfortable finding: the
expense ratio predicts future relative performance more reliably than past
performance does. Cost is therefore weighted above return, and the return that
is counted is adjusted for how rough the ride was.

The scores compare funds against fixed bands, which means a bond fund and an
equity fund are not really comparable on risk: 6% volatility is unremarkable for
bonds and extraordinary for equities. Read `category` before reading the rank,
the same way the equity side needs peer context alongside its absolute bands.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DATA,
    RAW,
    latest_snapshot,
    read_json,
    resolve_funds,
    today,
    utc_now,
    write_json,
)

FUNDS = DATA / "funds"
FUND_SCORES = DATA / "fund_scores"
FUND_SCORES.mkdir(parents=True, exist_ok=True)

# Bands run from the metric value to a score out of 100, interpolated between
# breakpoints, ascending in the metric. A band whose scores fall as the value
# rises encodes "lower is better".
FUND_BANDS = {
    # --- cost: the one number known in advance ---
    "expense_ratio": [(0.0002, 100), (0.0005, 96), (0.001, 90), (0.002, 78),
                      (0.004, 58), (0.0075, 30), (0.015, 0)],
    "turnover": [(0.0, 100), (0.2, 85), (0.5, 68), (1.0, 45), (2.0, 15), (4.0, 0)],
    # --- risk-adjusted return ---
    "return_per_unit_of_risk": [(-0.5, 0), (0.0, 25), (0.25, 50), (0.5, 70),
                                (0.8, 88), (1.2, 100)],
    "total_cagr_estimate": [(-0.05, 0), (0.0, 20), (0.04, 40), (0.08, 60),
                            (0.12, 78), (0.18, 94), (0.25, 100)],
    "max_drawdown": [(-0.75, 0), (-0.55, 18), (-0.40, 40), (-0.30, 58),
                     (-0.20, 78), (-0.12, 92), (-0.05, 100)],
    # --- diversification: what the label hides ---
    "top_10_weight": [(0.05, 100), (0.15, 88), (0.25, 72), (0.40, 52),
                      (0.55, 30), (0.75, 8), (0.95, 0)],
    "sector_concentration_hhi": [(0.10, 100), (0.15, 85), (0.25, 66), (0.40, 42),
                                 (0.60, 18), (0.85, 0)],
    # --- size and liquidity ---
    "total_assets": [(1e8, 0), (5e8, 35), (2e9, 60), (1e10, 80), (5e10, 94), (2e11, 100)],
    # --- income ---
    "distribution_yield": [(0.0, 10), (0.005, 25), (0.015, 48), (0.025, 68),
                           (0.035, 85), (0.05, 100)],
}

FUND_PILLARS = {
    "cost": {
        "weight": 0.30,
        "metrics": {"expense_ratio": 0.80, "turnover": 0.20},
    },
    "risk_adjusted_return": {
        "weight": 0.25,
        "metrics": {
            "return_per_unit_of_risk": 0.45,
            "total_cagr_estimate": 0.30,
            "max_drawdown": 0.25,
        },
    },
    "diversification": {
        "weight": 0.20,
        "metrics": {"top_10_weight": 0.60, "sector_concentration_hhi": 0.40},
    },
    "size": {"weight": 0.10, "metrics": {"total_assets": 1.0}},
    "income": {"weight": 0.15, "metrics": {"distribution_yield": 1.0}},
}

FUND_GRADES = [
    (80, "A  a sound core holding on cost and risk"),
    (70, "B+ solid, check what it duplicates"),
    (60, "B  workable with one clear weakness"),
    (50, "C  narrow or expensive; hold it deliberately"),
    (40, "D  the costs or the risks are doing the work"),
    (0, "E  hard to justify against a cheap index"),
]


def band_score(metric, value):
    """Interpolate a metric onto its 0-100 band, clamping outside it."""
    if value is None or metric not in FUND_BANDS:
        return None
    pts = FUND_BANDS[metric]
    if value <= pts[0][0]:
        return float(pts[0][1])
    if value >= pts[-1][0]:
        return float(pts[-1][1])
    for (v1, s1), (v2, s2) in zip(pts, pts[1:]):
        if v1 <= value <= v2:
            if v2 == v1:
                return float(s2)
            return float(s1 + (value - v1) / (v2 - v1) * (s2 - s1))
    return float(pts[-1][1])


def flatten(payload):
    """Pull the scored metrics out of a fund snapshot into one flat dict."""
    costs = payload.get("costs") or {}
    returns = payload.get("returns") or {}
    risk = payload.get("risk") or {}
    comp = payload.get("composition") or {}
    conc = comp.get("concentration") or {}
    market = payload.get("market") or {}
    return {
        "expense_ratio": costs.get("expense_ratio"),
        "turnover": costs.get("turnover"),
        "return_per_unit_of_risk": risk.get("return_per_unit_of_risk"),
        "total_cagr_estimate": returns.get("total_cagr_estimate"),
        "max_drawdown": risk.get("max_drawdown"),
        "volatility_annual": risk.get("volatility_annual"),
        "top_10_weight": conc.get("top_10_weight"),
        "sector_concentration_hhi": comp.get("sector_concentration_hhi"),
        "total_assets": market.get("total_assets"),
        "distribution_yield": returns.get("distribution_yield"),
    }


def score_pillars(metrics):
    detail = {}
    for pname, pdef in FUND_PILLARS.items():
        parts, wsum, acc = {}, 0.0, 0.0
        for m, w in pdef["metrics"].items():
            s = band_score(m, metrics.get(m))
            parts[m] = {"value": metrics.get(m), "score": None if s is None else round(s, 1),
                        "weight": w}
            if s is not None:
                acc += s * w
                wsum += w
        detail[pname] = {
            "score": round(acc / wsum, 1) if wsum else None,
            "coverage": round(wsum / sum(pdef["metrics"].values()), 2),
            "weight": pdef["weight"],
            "metrics": parts,
        }
    live = {k: v for k, v in detail.items() if v["score"] is not None}
    total_w = sum(v["weight"] for v in live.values())
    composite = (round(sum(v["score"] * v["weight"] for v in live.values()) / total_w, 1)
                 if total_w else None)
    return composite, detail, round(total_w, 2)


def grade_for(score):
    if score is None:
        return "n/a  not enough data"
    for cut, label in FUND_GRADES:
        if score >= cut:
            return label
    return FUND_GRADES[-1][1]


def flags(payload, metrics, composite):
    """Plain warnings worth reading before the score."""
    out = []
    exp = metrics.get("expense_ratio")
    if exp is not None and exp > 0.005:
        out.append(
            "An expense ratio of {:.2f}% costs {:,.0f} per 100,000 invested every year, "
            "whatever the fund returns. Over five years that is roughly {:,.0f} before "
            "any compounding effect.".format(exp * 100, exp * 100000, exp * 100000 * 5)
        )
    top = metrics.get("top_10_weight")
    if top is not None and top > 0.45:
        out.append(
            "The ten largest positions are {:.0f}% of the fund. Whatever the name "
            "suggests, this is a concentrated bet.".format(top * 100)
        )
    hhi = metrics.get("sector_concentration_hhi")
    if hhi is not None and hhi > 0.30:
        sectors = (payload.get("composition") or {}).get("sector_weights") or {}
        biggest = max(sectors.items(), key=lambda kv: kv[1]) if sectors else None
        if biggest:
            out.append(
                "Sector exposure is concentrated: {:.0f}% sits in {}. This is a sector "
                "position wearing a fund's clothing.".format(biggest[1] * 100,
                                                             biggest[0].replace("_", " "))
            )
    dd = metrics.get("max_drawdown")
    if dd is not None and dd < -0.45:
        out.append(
            "It has fallen {:.0f}% from a peak within the measured window. Ask whether "
            "you would have held it through that, because the return only accrues to "
            "someone who did.".format(abs(dd) * 100)
        )
    aum = metrics.get("total_assets")
    if aum is not None and aum < 5e8:
        out.append(
            "Assets of {:.0f} million are small. Small funds carry wider spreads and a "
            "real chance of being closed and liquidated on someone else's schedule."
            .format(aum / 1e6)
        )
    if not payload.get("is_fund"):
        out.append(
            "This symbol is a {} rather than a fund, so every number here is being "
            "read off the wrong kind of instrument.".format(payload.get("quote_type") or "?")
        )
    if composite is not None and composite >= 75 and not out:
        out.append(
            "Nothing structural stands out. The remaining question is what it duplicates "
            "in the rest of the portfolio, which the overlap check answers."
        )
    return out


# ---------------------------------------------------------------------------
# overlap
# ---------------------------------------------------------------------------

def tracked_stocks():
    """Symbols that have an equity snapshot on disk, i.e. names being followed."""
    if not RAW.exists():
        return {}
    out = {}
    for d in sorted(RAW.iterdir()):
        if not d.is_dir():
            continue
        snap = latest_snapshot(d)
        if not snap:
            continue
        f = read_json(snap) or {}
        out[d.name.upper()] = (f.get("profile") or {}).get("name")
    return out


def load_fund(fund):
    snap = latest_snapshot(FUNDS / fund.upper())
    if not snap:
        return None, None
    return read_json(snap), snap.stem


def overlap_with_tracked(fund):
    """How much of a fund you already hold directly through individual stocks.

    Buying an index on top of the names inside it is the most common way a
    portfolio becomes concentrated while looking diversified. Only the ten
    largest positions are published, so this measures overlap within that slice
    and says nothing about the tail.
    """
    payload, date = load_fund(fund)
    if not payload:
        return {"ok": False, "reason": "No data for {}. Run tools/fetch_funds.py {}.".format(
            fund.upper(), fund.upper())}

    conc = ((payload.get("composition") or {}).get("concentration") or {})
    if not conc.get("available"):
        return {"ok": False, "reason": "No published holdings for {}.".format(fund.upper())}

    tracked = tracked_stocks()
    matches, misses = [], []
    for h in conc["holdings"]:
        sym = (h["symbol"] or "").upper()
        if sym in tracked:
            matches.append({"symbol": sym, "name": tracked[sym] or h["name"],
                            "weight_in_fund": h["weight"]})
        else:
            misses.append({"symbol": sym, "name": h["name"], "weight_in_fund": h["weight"]})

    overlap_weight = sum(m["weight_in_fund"] for m in matches)
    return {
        "ok": True,
        "fund": payload["ticker"],
        "fund_name": (payload.get("profile") or {}).get("name"),
        "snapshot": date,
        "tracked_count": len(tracked),
        "overlap_weight": round(overlap_weight, 4),
        "overlap_share_of_top10": round(
            overlap_weight / conc["top_10_weight"], 4) if conc.get("top_10_weight") else None,
        "already_tracked": sorted(matches, key=lambda m: -m["weight_in_fund"]),
        "not_tracked": sorted(misses, key=lambda m: -m["weight_in_fund"]),
        "reading": _overlap_words(overlap_weight, len(matches)),
        "caveat": (
            "Overlap is measured against the ten largest published positions only, and "
            "against the stocks followed here rather than a real portfolio. It is a "
            "floor on duplication, not a full picture."
        ),
    }


def _overlap_words(weight, n):
    if n == 0:
        return "None of this fund's largest positions are followed individually here, so it adds exposure rather than doubling it."
    if weight >= 0.30:
        return ("{:.0f}% of the fund sits in {} companies already followed individually. "
                "Buying both concentrates the same bet twice.".format(weight * 100, n))
    if weight >= 0.12:
        return ("{:.0f}% of the fund is in {} names already followed. Worth knowing before "
                "sizing a position.".format(weight * 100, n))
    return ("Only {:.0f}% sits in names already followed, across {} holdings, so duplication "
            "is minor.".format(weight * 100, n))


def overlap_between(fund_a, fund_b):
    """Shared positions between two funds, by published top-ten weight."""
    a, _ = load_fund(fund_a)
    b, _ = load_fund(fund_b)
    if not a or not b:
        missing = fund_a if not a else fund_b
        return {"ok": False, "reason": "No data for {}.".format(missing.upper())}

    def holdings(p):
        c = ((p.get("composition") or {}).get("concentration") or {})
        return {h["symbol"].upper(): h for h in (c.get("holdings") or [])}

    ha, hb = holdings(a), holdings(b)
    shared = sorted(set(ha) & set(hb))
    rows = [
        {
            "symbol": s,
            "name": ha[s]["name"],
            "weight_a": ha[s]["weight"],
            "weight_b": hb[s]["weight"],
            "shared_weight": round(min(ha[s]["weight"], hb[s]["weight"]), 4),
        }
        for s in shared
    ]
    rows.sort(key=lambda r: -r["shared_weight"])
    shared_weight = sum(r["shared_weight"] for r in rows)

    return {
        "ok": True,
        "fund_a": a["ticker"],
        "fund_b": b["ticker"],
        "shared_names": len(rows),
        "shared_weight_min": round(shared_weight, 4),
        "holdings": rows,
        "reading": (
            "{} of the ten largest positions are in both, worth at least {:.0f}% of each "
            "fund. Holding both buys that exposure twice.".format(len(rows), shared_weight * 100)
            if rows else
            "No overlap among the published top ten, so these two are genuinely different bets."
        ),
        "caveat": "Top ten only. Two broad index funds can overlap almost completely further down.",
    }


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def score_fund(fund):
    payload, date = load_fund(fund)
    if not payload:
        raise FileNotFoundError(
            "No fund data for {}. Run: uv run python tools/fetch_funds.py {}".format(
                fund.upper(), fund.upper())
        )
    metrics = flatten(payload)
    composite, detail, coverage = score_pillars(metrics)
    prof = payload.get("profile") or {}

    return {
        "ticker": payload["ticker"],
        "name": prof.get("name"),
        "category": prof.get("category"),
        "family": prof.get("family"),
        "is_fund": payload.get("is_fund"),
        "as_of": utc_now(),
        "source_snapshot": date,
        "composite_score": composite,
        "grade": grade_for(composite),
        "pillar_weight_coverage": coverage,
        "pillars": detail,
        "metrics": metrics,
        "flags": flags(payload, metrics, composite),
        "overlap_with_tracked": overlap_with_tracked(fund),
        "disclaimer": (
            "A rules-based comparison of funds on cost, risk-adjusted history, "
            "concentration, size and yield. Past return is the weakest of these as a "
            "guide to the future and cost is the strongest, which is why cost carries "
            "more weight. Not investment advice."
        ),
    }


def _pct(v, digits=2):
    return "  n/a" if v is None else "{:.{d}f}%".format(v * 100, d=digits)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("funds", nargs="*")
    ap.add_argument("--rank", action="store_true", help="table sorted by composite score")
    ap.add_argument("--overlap", nargs="+", metavar="FUND",
                    help="one fund against tracked stocks, or two funds against each other")
    ap.add_argument("--out-date", default=today())
    args = ap.parse_args()

    if args.overlap:
        if len(args.overlap) == 1:
            res = overlap_with_tracked(args.overlap[0])
            if not res.get("ok"):
                print(res["reason"], file=sys.stderr)
                return 1
            print("{} — {}".format(res["fund"], res["fund_name"] or ""))
            print("Overlap with the {} stocks followed here: {:.1f}% of the fund\n".format(
                res["tracked_count"], res["overlap_weight"] * 100))
            print(res["reading"], "\n")
            if res["already_tracked"]:
                print("  Already followed individually:")
                for m in res["already_tracked"]:
                    print("    {:<8} {:<30} {:>6}".format(
                        m["symbol"], (m["name"] or "")[:30], _pct(m["weight_in_fund"], 1)))
            if res["not_tracked"]:
                print("\n  In the fund but not followed here:")
                for m in res["not_tracked"]:
                    print("    {:<8} {:<30} {:>6}".format(
                        m["symbol"], (m["name"] or "")[:30], _pct(m["weight_in_fund"], 1)))
            print("\n" + res["caveat"])
            return 0

        res = overlap_between(args.overlap[0], args.overlap[1])
        if not res.get("ok"):
            print(res["reason"], file=sys.stderr)
            return 1
        print("{} vs {}\n".format(res["fund_a"], res["fund_b"]))
        print(res["reading"], "\n")
        for r in res["holdings"]:
            print("  {:<8} {:<28} {:>7} {:>7}".format(
                r["symbol"], (r["name"] or "")[:28],
                _pct(r["weight_a"], 1), _pct(r["weight_b"], 1)))
        print("\n" + res["caveat"])
        return 0

    funds = resolve_funds(args.funds)
    if not funds:
        print("No funds. Run tools/fetch_funds.py first.", file=sys.stderr)
        return 2

    rows = []
    for f in funds:
        try:
            res = score_fund(f)
            write_json(FUND_SCORES / f.upper() / "{}.json".format(args.out_date), res)
            p = res["pillars"]
            rows.append({
                "ticker": res["ticker"],
                "name": (res.get("name") or "?")[:26],
                "category": (res.get("category") or "?")[:16],
                "score": res["composite_score"],
                "cost": p["cost"]["score"],
                "risk": p["risk_adjusted_return"]["score"],
                "div": p["diversification"]["score"],
                "income": p["income"]["score"],
                "expense": res["metrics"]["expense_ratio"],
                "overlap": (res["overlap_with_tracked"] or {}).get("overlap_weight"),
                "grade": res["grade"],
            })
        except Exception as e:
            print("{:<7} FAILED: {}: {}".format(f.upper(), type(e).__name__, e), file=sys.stderr)

    if not rows:
        return 1
    if args.rank:
        rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))

    header = "{:<7} {:<26} {:<16} {:>6} {:>5} {:>5} {:>5} {:>6} {:>8} {:>8}".format(
        "FUND", "NAME", "CATEGORY", "SCORE", "COST", "RISK", "DIV", "INCOME", "EXPENSE", "OVERLAP")
    print(header)
    print("-" * len(header))
    for r in rows:
        print("{:<7} {:<26} {:<16} {:>6} {:>5} {:>5} {:>5} {:>6} {:>8} {:>8}".format(
            r["ticker"], r["name"], r["category"],
            "n/a" if r["score"] is None else "{:.1f}".format(r["score"]),
            "n/a" if r["cost"] is None else "{:.0f}".format(r["cost"]),
            "n/a" if r["risk"] is None else "{:.0f}".format(r["risk"]),
            "n/a" if r["div"] is None else "{:.0f}".format(r["div"]),
            "n/a" if r["income"] is None else "{:.0f}".format(r["income"]),
            _pct(r["expense"]), _pct(r["overlap"], 1)))

    print("\nScores written to data/fund_scores/<TICKER>/{}.json".format(args.out_date))
    print("OVERLAP is the share of the fund sitting in stocks already followed here.")
    print("Cost is weighted above past return on purpose: it is the more reliable guide.")
    print("A bond fund and an equity fund are not comparable on risk; read CATEGORY first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
