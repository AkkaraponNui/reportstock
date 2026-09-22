"""Score a stock's 5-year growth case from the fundamentals snapshot.

Usage:
    uv run python tools/score.py NVDA MSFT
    uv run python tools/score.py ai_infra
    uv run python tools/score.py --all --rank

Reads the newest data/raw/<TICKER>/*.json and writes data/scores/<TICKER>/<date>.json.

What this is: a transparent, rules-based scorecard plus a scenario projection.
What this is not: a forecast. Every number is an arithmetic consequence of the
inputs and the assumptions printed alongside it. The bands and weights live in
BANDS and PILLARS below; edit them and every output moves with them. Read it as a
way to compare names on the same yardstick, not as a prediction of price.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    RAW,
    safe_div,
    SCORES,
    latest_snapshot,
    read_json,
    resolve_tickers,
    today,
    utc_now,
    write_json,
)

# Each band is an ordered list of (metric value, score out of 100) breakpoints.
# Scores interpolate between breakpoints and clamp outside them. Bands ordered
# high-to-low mean "lower is better" (valuation, leverage).
BANDS = {
    # --- growth ---
    "revenue_cagr": [(-0.10, 0), (0.0, 20), (0.05, 40), (0.10, 60), (0.20, 80), (0.35, 95), (0.60, 100)],
    "revenue_growth_ttm": [(-0.10, 0), (0.0, 20), (0.05, 40), (0.12, 62), (0.25, 82), (0.45, 96), (0.70, 100)],
    "net_income_cagr": [(-0.15, 0), (0.0, 25), (0.08, 45), (0.15, 65), (0.28, 85), (0.50, 100)],
    "forward_eps_growth": [(-0.20, 0), (0.0, 25), (0.08, 45), (0.15, 65), (0.30, 88), (0.50, 100)],
    # --- quality and moat ---
    "gross_margin_latest": [(0.10, 0), (0.25, 30), (0.40, 55), (0.55, 75), (0.70, 92), (0.85, 100)],
    "operating_margin_latest": [(-0.05, 0), (0.05, 25), (0.12, 45), (0.20, 65), (0.32, 85), (0.50, 100)],
    "operating_margin_trend": [(-0.04, 0), (-0.01, 30), (0.0, 50), (0.01, 68), (0.03, 88), (0.06, 100)],
    "roic_est": [(0.0, 0), (0.05, 25), (0.10, 45), (0.15, 62), (0.25, 82), (0.40, 100)],
    "roe": [(0.0, 0), (0.05, 22), (0.12, 45), (0.20, 65), (0.32, 85), (0.50, 100)],
    # --- cash generation ---
    "fcf_margin_latest": [(-0.05, 0), (0.0, 22), (0.08, 45), (0.15, 65), (0.25, 85), (0.40, 100)],
    "fcf_cagr": [(-0.15, 0), (0.0, 28), (0.08, 48), (0.18, 70), (0.30, 90), (0.50, 100)],
    "fcf_yield": [(0.0, 10), (0.01, 28), (0.025, 48), (0.04, 65), (0.07, 88), (0.10, 100)],
    # --- balance sheet (lower is better) ---
    "net_debt_to_ebitda": [(-1.0, 100), (0.0, 92), (1.0, 78), (2.0, 60), (3.0, 40), (4.5, 18), (6.0, 0)],
    "debt_to_equity": [(0.0, 100), (25.0, 85), (60.0, 66), (100.0, 50), (180.0, 28), (300.0, 0)],
    "current_ratio": [(0.6, 0), (1.0, 35), (1.3, 55), (1.8, 75), (2.5, 92), (3.5, 100)],
    # --- valuation (lower is better) ---
    "forward_pe": [(6.0, 100), (12.0, 84), (18.0, 68), (25.0, 52), (35.0, 34), (50.0, 15), (80.0, 0)],
    "peg_est": [(0.4, 100), (0.8, 85), (1.2, 68), (1.6, 50), (2.2, 30), (3.5, 8), (5.0, 0)],
    "ev_to_ebitda": [(4.0, 100), (9.0, 82), (14.0, 64), (20.0, 46), (30.0, 25), (45.0, 0)],
    "price_to_sales": [(0.5, 100), (2.0, 82), (4.0, 64), (7.0, 46), (12.0, 26), (20.0, 5), (30.0, 0)],
}

PILLARS = {
    "growth": {
        "weight": 0.30,
        "metrics": {
            "revenue_cagr": 0.35,
            "revenue_growth_ttm": 0.30,
            "net_income_cagr": 0.20,
            "forward_eps_growth": 0.15,
        },
    },
    "quality": {
        "weight": 0.25,
        "metrics": {
            "roic_est": 0.30,
            "operating_margin_latest": 0.25,
            "gross_margin_latest": 0.20,
            "operating_margin_trend": 0.15,
            "roe": 0.10,
        },
    },
    "cash": {
        "weight": 0.15,
        "metrics": {
            "fcf_margin_latest": 0.45,
            "fcf_cagr": 0.35,
            "fcf_yield": 0.20,
        },
    },
    "balance_sheet": {
        "weight": 0.15,
        "metrics": {
            "net_debt_to_ebitda": 0.45,
            "debt_to_equity": 0.30,
            "current_ratio": 0.25,
        },
    },
    "valuation": {
        "weight": 0.15,
        "metrics": {
            "forward_pe": 0.30,
            "peg_est": 0.30,
            "ev_to_ebitda": 0.20,
            "price_to_sales": 0.20,
        },
    },
}

GRADES = [
    (80, "A  strong 5y compounder case"),
    (70, "B+ solid, watch the entry price"),
    (60, "B  decent but with a real weak pillar"),
    (50, "C  mixed, needs a specific catalyst"),
    (40, "D  weak on the numbers"),
    (0, "E  the numbers argue against it"),
]


def band_score(metric, value):
    """Map a raw metric to 0-100 by linear interpolation across its band.

    Every band is ordered by ascending metric value. A band whose scores fall as
    the value rises (valuation, leverage) encodes "lower is better" on its own.
    Values outside the band clamp to the nearest endpoint.
    """
    if value is None or metric not in BANDS:
        return None
    pts = BANDS[metric]
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


# Metrics that divide a market number by a statement number. When a company
# trades in one currency and reports in another, as every ADR does, the two
# sides are in different units and the ratio is wrong by the exchange rate.
# It stays plausible-looking, which is what makes it dangerous: TSM came back
# with a price-to-sales of 0.51 and a free cash flow yield of 44%, scoring 99.9
# and 100, because its statements are in TWD and its market cap is in USD.
# ASML failed the other way with an EV/EBITDA of 2657 and scored 0.
#
# `project()` already guards itself through `_sales_multiple`. These are the
# graded metrics, which were still reading the raw fields.
CURRENCY_SENSITIVE = ("price_to_sales", "ev_to_ebitda", "fcf_yield")


def drop_currency_contaminated(metrics):
    """Blank the metrics a currency mismatch makes meaningless.

    Dropping rather than converting is deliberate. A conversion needs a rate at
    the statement date, which this data source does not carry, so an estimate
    would replace a visibly wrong number with an invisibly wrong one. A blank
    metric renormalizes its pillar over what remains and shows up in coverage.
    """
    if not metrics.get("currency_mismatch"):
        return metrics, []
    out = dict(metrics)
    dropped = []
    for k in CURRENCY_SENSITIVE:
        if out.get(k) is not None:
            dropped.append(k)
            out[k] = None
    return out, dropped


def score_pillars(metrics):
    """Weighted pillar scores, renormalized over whatever metrics are available."""
    metrics, dropped_for_currency = drop_currency_contaminated(metrics)
    detail = {}
    for pname, pdef in PILLARS.items():
        parts, wsum, acc = {}, 0.0, 0.0
        for m, w in pdef["metrics"].items():
            s = band_score(m, metrics.get(m))
            parts[m] = {"value": metrics.get(m), "score": None if s is None else round(s, 1), "weight": w}
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
    composite = (
        round(sum(v["score"] * v["weight"] for v in live.values()) / total_w, 1)
        if total_w
        else None
    )
    return composite, detail, round(total_w, 2)


def grade_for(score):
    if score is None:
        return "n/a  not enough data"
    for cut, label in GRADES:
        if score >= cut:
            return label
    return GRADES[-1][1]


def blended_growth(m):
    """Starting revenue growth rate: history, current run-rate, and the forward view.

    Forward EPS growth is only a proxy for revenue growth, and a poor one for a
    cyclical whose earnings rebound off a trough while revenue barely moves. When
    a direct revenue measure exists the EPS term is capped at 1.5 times the higher
    of them, so a margin-recovery spike cannot drive a revenue projection.
    """
    rev_signals = [v for v in (m.get("revenue_cagr"), m.get("revenue_growth_ttm")) if v is not None]
    eps = m.get("forward_eps_growth")
    if eps is not None and rev_signals:
        ceiling = max(rev_signals) * 1.5
        if ceiling > 0:
            eps = min(eps, ceiling)

    parts = [
        (m.get("revenue_cagr"), 0.35),
        (m.get("revenue_growth_ttm"), 0.40),
        (eps, 0.25),
    ]
    live = [(v, w) for v, w in parts if v is not None]
    if not live:
        return None
    wsum = sum(w for _, w in live)
    g = sum(v * w for v, w in live) / wsum
    return max(-0.25, min(g, 0.60))  # cap: 60% sustained growth is already heroic


def dividend_component(m, scenario="base"):
    """The yield to add to the price return, as a fraction. Zero when unknown.

    `dividend_yield` is stored as a fraction by the fetcher, which normalizes
    Yahoo's percentage field. The cap is a guard against a bad upstream value
    rather than a view: a sustained yield above 15% is a distressed price or a
    data error, and either way it should not drive a five-year projection.

    A payout the company cannot fund gets cut, so a payout ratio above 100% is
    treated as only partly durable. The bear case haircuts the yield for the same
    reason; the bull case does not raise it, because a rising yield on a rising
    price implies a dividend growing faster than the business.
    """
    y = m.get("dividend_yield")
    if not y or y <= 0:
        return 0.0
    y = min(float(y), 0.15)

    payout = m.get("payout_ratio")
    if payout is not None and payout > 1.0:
        y *= 0.6  # paying out more than it earns; assume much of this is cut

    if scenario == "bear":
        y *= 0.5
    return y


def sales_multiple_and_margin(m):
    """Today's market cap per unit of revenue, with the margin that matches it.

    These two have to be returned together, because `project` divides one by the
    other to recover the entry P/E and then values the exit on the same basis.
    Pairing multiples from different periods is what this function exists to
    prevent.

    Two routes, in order of preference:

    `price_to_sales` is market cap over trailing-twelve-month revenue, which is
    the honest answer when it can be trusted. The margin that belongs with it is
    the one the market is implying right now, `price_to_sales / trailing_pe`, not
    last fiscal year's. For a company whose trailing year does not resemble its
    last annual report those differ enormously: Micron's TTM revenue grew 346%,
    so the implied margin is 55.4% where the last annual close was 22.8%.

    `trailing_pe x net_margin` is the fallback, and its only merit is that price
    and earnings per share are both quoted in the trading currency, so it
    survives an ADR's currency mismatch. It mixes a trailing price multiple with
    an annual margin, so it is used only when the clean route is unavailable.

    Returns (multiple, margin, basis). The margin is None when the caller should
    fall back to the reported annual figure.
    """
    ps = m.get("price_to_sales")
    pe = m.get("trailing_pe")
    mismatch = bool(m.get("currency_mismatch"))

    if ps and ps > 0 and not mismatch:
        implied = safe_div(ps, pe) if pe and pe > 0 else None
        if implied is not None and 0 < implied < 0.95:
            return ps, implied, "reported price_to_sales, margin implied by trailing_pe"
        # No usable P/E: the multiple is still right, the margin is not derivable.
        return ps, None, "reported price_to_sales"

    margin = m.get("net_margin_latest")
    if pe and pe > 0 and margin and margin > 0:
        why = ("trailing_pe x net_margin (currency-safe route; mixes a trailing "
               "price multiple with an annual margin)")
        return pe * margin, margin, why

    if ps and ps > 0 and mismatch:
        # Only path left is the one the mismatch corrupts, so decline to guess.
        return None, None, "unavailable: market cap and statements use different currencies"
    return None, None, "unavailable: no usable sales multiple"


def _sales_multiple(m):
    """Backwards-compatible view of `sales_multiple_and_margin`."""
    ps, _margin, basis = sales_multiple_and_margin(m)
    return ps, basis


def project(m, years=5, terminal_growth=0.04, scenario="base"):
    """Fade today's growth to a terminal rate, then value the result on an exit multiple.

    Returns None when the inputs needed for the arithmetic are missing.
    """
    mcap = m.get("market_cap")
    g0 = blended_growth(m)
    net_margin = m.get("net_margin_latest")
    reported_margin = net_margin
    if g0 is None or not mcap:
        return None
    if net_margin is None or net_margin <= 0:
        net_margin = 0.08  # fallback for a loss-maker: assume it reaches a modest margin

    # Everything below is an index, never a currency amount. Market cap over a
    # statement line item is unit-inconsistent whenever a company trades in one
    # currency and reports in another, which is true of every ADR. Working in
    # ratios makes the arithmetic identical in any currency.
    ps_effective, matched_margin, ps_basis = sales_multiple_and_margin(m)
    # The margin has to come from the same period as the multiple; see
    # sales_multiple_and_margin. Only fall back to the annual figure when the
    # clean route could not supply one.
    if matched_margin is not None and matched_margin > 0:
        net_margin = matched_margin
    if ps_effective is None:
        return None

    tweak = {"bear": (0.55, 0.70), "base": (1.0, 1.0), "bull": (1.30, 1.25)}[scenario]
    g_mult, mult_mult = tweak

    g_start = g0 * g_mult
    revenue_index = 1.0
    path = []
    for i in range(years):
        # Linear fade from the starting rate to the terminal rate.
        g = g_start + (terminal_growth - g_start) * ((i + 1) / years)
        revenue_index *= 1.0 + g
        path.append({"year": i + 1, "growth": round(g, 4), "revenue_index": round(revenue_index, 3)})

    # Margin drifts along its recent trend at half weight. The ceiling is 45%, or
    # today's margin if it is already above that: the cap blocks assumed expansion
    # into rare territory, it never forces a decline the trend does not support.
    trend = m.get("operating_margin_trend") or 0.0
    ceiling = max(0.45, net_margin)
    margin_end = max(0.01, min(net_margin + trend * years * 0.5, ceiling))
    if scenario == "bear":
        margin_end = max(0.01, margin_end * 0.75)
    elif scenario == "bull":
        # The bull ceiling scales with today's margin so it can never land below base.
        margin_end = min(margin_end * 1.15, max(0.50, net_margin * 1.15))

    # Exit multiple: today's multiple pulled toward a growth-justified one.
    #
    # The anchor has to be the same multiple that sets the entry price, or the
    # model hands out a free lunch. Anchoring the exit on forward P/E while the
    # entry comes from trailing P/E means raising the forward multiple lifts the
    # terminal value without raising what you pay today, so an expensive stock
    # scores better than a cheap one. Deriving the anchor from ps_effective keeps
    # both sides on one basis: paying a higher multiple and selling at a higher
    # multiple cancel, and only the pull toward the justified multiple remains,
    # which is the mean reversion that should penalise a demanding price.
    entry_pe = safe_div(ps_effective, net_margin)
    justified = 10.0 + 55.0 * max(0.0, min(terminal_growth + g_start * 0.25, 0.30))
    exit_pe = (0.5 * entry_pe + 0.5 * justified) if entry_pe else justified
    exit_pe = max(6.0, min(exit_pe * mult_mult, 60.0))

    # Market cap today is revenue times the sales multiple; market cap in five
    # years is the grown revenue times the end margin times the exit P/E. Dividing
    # one by the other leaves a pure ratio, so revenue itself never appears.
    exit_sales_multiple = margin_end * exit_pe
    value_ratio = revenue_index * exit_sales_multiple / ps_effective

    price_annualized = value_ratio ** (1.0 / years) - 1.0

    # Dividends are part of the return, and leaving them out biases the whole
    # ranking in one direction: against mature payers, toward companies that
    # retain everything. Assume the yield holds and is reinvested at the same
    # total rate, which is the standard total-return convention.
    div_yield = dividend_component(m, scenario)
    annualized = (1.0 + price_annualized) * (1.0 + div_yield) - 1.0
    total_return = (1.0 + annualized) ** years - 1.0

    return {
        "scenario": scenario,
        "assumptions": {
            "start_growth": round(g_start, 4),
            "terminal_growth": terminal_growth,
            # The margin the projection actually starts from, which is the one
            # paired with the multiple. It is the trailing-twelve-month figure
            # on the clean route and the last annual one on the fallback, and
            # those differ a lot for a company mid-cycle, so both are reported.
            "start_net_margin": round(net_margin, 4),
            "reported_annual_net_margin": (
                None if reported_margin is None else round(reported_margin, 4)),
            "margin_basis": ps_basis,
            "end_net_margin": round(margin_end, 4),
            "exit_pe": round(exit_pe, 1),
            "current_sales_multiple": round(ps_effective, 3),
            "sales_multiple_basis": ps_basis,
            "dividend_yield": round(div_yield, 4),
            "years": years,
        },
        "revenue_path": path,
        "revenue_index_end": round(revenue_index, 3),
        "exit_sales_multiple": round(exit_sales_multiple, 3),
        "implied_market_cap": round(mcap * value_ratio, 0),
        "current_market_cap": mcap,
        "price_return_annualized": round(price_annualized, 4),
        "dividend_contribution": round(div_yield, 4),
        "total_return": round(total_return, 4),
        "annualized_return": round(annualized, 4),
    }


def flags(m, composite, detail):
    """Plain-language warnings worth reading before the score."""
    out = []
    if m.get("currency_mismatch"):
        _, dropped = drop_currency_contaminated(m)
        if dropped:
            out.append(
                "Trades in {} but reports in {}, so {} were excluded from the score: "
                "each divides a market number by a statement number in a different "
                "currency. The affected pillars renormalize over the metrics that "
                "remain, so read the coverage figure alongside the score.".format(
                    m.get("trading_currency") or "one currency",
                    m.get("financial_currency") or "another",
                    ", ".join(dropped),
                )
            )
    nd = m.get("net_debt_to_ebitda")
    if nd is not None and nd > 3.0:
        out.append("Leverage is high at {:.1f}x net debt to EBITDA, which limits room to invest through a downturn.".format(nd))
    if (m.get("fcf_margin_latest") or 0) < 0:
        out.append("Free cash flow is negative, so growth is being funded by the balance sheet or by issuing shares.")
    pe = m.get("forward_pe")
    if pe and pe > 40:
        out.append("A forward P/E of {:.0f} prices in years of execution, leaving little margin for a stumble.".format(pe))
    peg = m.get("peg_est")
    if peg and peg > 2.5:
        out.append("The PEG of {:.1f} says you are paying well above the growth you are buying.".format(peg))
    if (m.get("operating_margin_trend") or 0) < -0.01:
        out.append("Operating margin is trending down, which usually means pricing pressure or cost inflation.")
    if (m.get("years_of_data") or 0) < 3:
        out.append("Fewer than three years of financials are available, so the growth rates are fragile.")
    val = detail.get("valuation", {}).get("score")
    gro = detail.get("growth", {}).get("score")
    if val is not None and gro is not None and gro > 70 and val < 35:
        out.append("Strong growth is paired with a demanding valuation: the thesis depends on the multiple holding up.")
    if composite is not None and composite >= 70 and not out:
        out.append("No structural red flags in the numbers. The remaining risk is competitive and regulatory, which the news agent covers.")
    return out


def score_ticker(ticker, years=5, terminal_growth=0.04):
    snap_path = latest_snapshot(RAW / ticker.upper())
    if not snap_path:
        raise FileNotFoundError(
            "No fundamentals for {}. Run: uv run python tools/fetch_fundamentals.py {}".format(ticker, ticker)
        )
    snap = read_json(snap_path) or {}
    m = snap.get("metrics") or {}
    profile = snap.get("profile") or {}
    composite, detail, coverage = score_pillars(m)

    scenarios = {}
    for sc in ("bear", "base", "bull"):
        p = project(m, years=years, terminal_growth=terminal_growth, scenario=sc)
        if p:
            scenarios[sc] = p

    return {
        "ticker": ticker.upper(),
        "company": profile.get("name"),
        "sector": profile.get("sector"),
        "as_of": utc_now(),
        "source_snapshot": str(snap_path.relative_to(RAW.parent.parent)),
        "composite_score": composite,
        "grade": grade_for(composite),
        "pillar_weight_coverage": coverage,
        "pillars": detail,
        "projection_5y": scenarios,
        "flags": flags(m, composite, detail),
        "disclaimer": (
            "Rules-based scorecard over public financial data. Not investment advice "
            "and not a price forecast. Assumptions are listed with every projection."
        ),
    }


def _fmt_pct(v):
    return "   n/a" if v is None else "{:6.1f}%".format(v * 100)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--all", action="store_true", help="score every ticker with a snapshot on disk")
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--terminal-growth", type=float, default=0.04)
    ap.add_argument("--rank", action="store_true", help="print a table sorted by composite score")
    ap.add_argument("--out-date", default=today())
    args = ap.parse_args()

    if args.all:
        tickers = sorted(p.name for p in RAW.iterdir() if p.is_dir())
    else:
        tickers = resolve_tickers(args.tickers)
    if not tickers:
        print("No tickers with data. Run tools/fetch_fundamentals.py first.", file=sys.stderr)
        return 2

    rows = []
    for tk in tickers:
        try:
            res = score_ticker(tk, years=args.years, terminal_growth=args.terminal_growth)
            write_json(SCORES / tk.upper() / "{}.json".format(args.out_date), res)
            base = (res.get("projection_5y") or {}).get("base") or {}
            rows.append(
                {
                    "ticker": res["ticker"],
                    "company": (res.get("company") or "?")[:26],
                    "score": res["composite_score"],
                    "growth": res["pillars"]["growth"]["score"],
                    "quality": res["pillars"]["quality"]["score"],
                    "value": res["pillars"]["valuation"]["score"],
                    "cagr5y": base.get("annualized_return"),
                    "grade": res["grade"],
                }
            )
        except Exception as e:
            print("{:<8} FAILED: {}: {}".format(tk.upper(), type(e).__name__, e), file=sys.stderr)

    if not rows:
        return 1

    if args.rank:
        rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))

    header = "{:<7} {:<26} {:>6} {:>7} {:>7} {:>7} {:>8}  {}".format(
        "TICKER", "COMPANY", "SCORE", "GROWTH", "QUALITY", "VALUE", "5Y/YR", "GRADE"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            "{:<7} {:<26} {:>6} {:>7} {:>7} {:>7} {:>8}  {}".format(
                r["ticker"],
                r["company"],
                "n/a" if r["score"] is None else "{:.1f}".format(r["score"]),
                "n/a" if r["growth"] is None else "{:.0f}".format(r["growth"]),
                "n/a" if r["quality"] is None else "{:.0f}".format(r["quality"]),
                "n/a" if r["value"] is None else "{:.0f}".format(r["value"]),
                _fmt_pct(r["cagr5y"]).strip(),
                r["grade"],
            )
        )
    print("\nScores written to data/scores/<TICKER>/{}.json".format(args.out_date))
    print("5Y/YR is a modelled annualized return under base-case assumptions, not a forecast.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
