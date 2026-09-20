"""Fetch and normalize data for funds and ETFs.

Usage:
    uv run python tools/fetch_funds.py QQQ VOO
    uv run python tools/fetch_funds.py core          # a group from universe.yaml
    uv run python tools/fetch_funds.py               # every fund in the universe

Writes data/funds/<TICKER>/<YYYY-MM-DD>.json.

A fund is not a company. It has no income statement, so revenue growth, margins
and return on capital simply do not exist for it, and running one through the
equity scorecard would produce either nulls or nonsense. What a fund does have is
a cost, a risk profile, a composition, and a size, and those are what this
collects.

Unit warning. Yahoo mixes three conventions inside one payload for the same fund:
`netExpenseRatio` is a percentage number (0.18 means 0.18%), `yield` is a plain
fraction (0.0042 means 0.42%), `ytdReturn` is a percentage number while
`threeYearAverageReturn` is a fraction, and `fund_operations` reports the expense
ratio as a fraction again. Every field below is normalized to a fraction on the
way in, and the expense ratio is cross-checked between its two sources.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DATA,
    clean,
    resolve_funds,
    safe_div,
    today,
    utc_now,
    with_retry,
    write_json,
)

FUNDS = DATA / "funds"
FUNDS.mkdir(parents=True, exist_ok=True)

# Used only to turn a return into a risk-adjusted one. Stated in the output so a
# reader can redo the arithmetic with their own assumption.
DEFAULT_RISK_FREE = 0.04

FUND_QUOTE_TYPES = {"ETF", "MUTUALFUND", "MONEYMARKET"}


def _as_fraction_from_percent(v):
    """A field Yahoo reports as a percentage number: 0.18 means 0.18%."""
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v / 100.0


def _as_fraction(v, cap=2.0):
    """A field Yahoo already reports as a fraction. Cap guards a bad value."""
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if abs(v) <= cap else None


def expense_ratio(info, operations):
    """Expense ratio as a fraction, cross-checked between its two sources.

    `info.netExpenseRatio` is a percentage number and `fund_operations` gives the
    same figure as a fraction. When both exist and agree, confidence is high;
    when they disagree the lower one is reported, since the net ratio after
    waivers is what an investor actually pays.
    """
    from_info = _as_fraction_from_percent(info.get("netExpenseRatio"))
    if from_info is None:
        from_info = _as_fraction_from_percent(info.get("annualReportExpenseRatio"))

    from_ops = None
    if operations is not None:
        try:
            row = operations.loc["Annual Report Expense Ratio"]
            from_ops = _as_fraction(row.iloc[0], cap=0.5)
        except Exception:
            from_ops = None

    candidates = [v for v in (from_info, from_ops) if v is not None and 0 <= v < 0.5]
    if not candidates:
        return None, "unavailable"
    if len(candidates) == 2:
        agree = abs(candidates[0] - candidates[1]) < 0.0005
        return min(candidates), "cross-checked, sources {}".format("agree" if agree else "differ")
    return candidates[0], "single source"


def price_risk(ticker, years=5):
    """Volatility, drawdown and realized return, computed from monthly closes.

    Yahoo's own return fields cover fixed windows and say nothing about the ride.
    A fund that returned 14% a year after falling 74% on the way is a different
    proposition from one that returned 13% after falling 16%.
    """
    import yfinance as yf

    try:
        hist = with_retry(
            lambda: yf.Ticker(ticker).history(period="{}y".format(years), interval="1mo"),
            label="history {}".format(ticker),
        )
    except Exception as e:
        return {"error": "{}: {}".format(type(e).__name__, e)}

    if hist is None or hist.empty or "Close" not in hist:
        return {"error": "No price history returned."}

    close = hist["Close"].dropna()
    if len(close) < 13:
        return {"error": "Only {} monthly closes; too short to measure risk.".format(len(close))}

    rets = close.pct_change().dropna()
    months = len(close) - 1
    vol = float(rets.std()) * math.sqrt(12)

    first, last = float(close.iloc[0]), float(close.iloc[-1])
    span_years = months / 12.0
    cagr = (last / first) ** (1.0 / span_years) - 1.0 if first > 0 and span_years > 0 else None

    peak = close.cummax()
    drawdown = float((close / peak - 1.0).min())

    worst = float(rets.min())
    best = float(rets.max())
    negative_months = int((rets < 0).sum())

    return {
        "months_observed": months,
        "span_years": round(span_years, 2),
        "price_cagr": None if cagr is None else round(cagr, 4),
        "volatility_annual": round(vol, 4),
        "max_drawdown": round(drawdown, 4),
        "worst_month": round(worst, 4),
        "best_month": round(best, 4),
        "share_of_negative_months": round(negative_months / len(rets), 4),
        "note": "Price return only; distributions are reported separately as yield.",
    }


def concentration(top_holdings):
    """How much of the fund sits in its largest positions.

    A fund can be called diversified and still be a bet on ten companies. Only
    the top ten are published, so this is a floor on concentration, not a
    complete picture.
    """
    if top_holdings is None or getattr(top_holdings, "empty", True):
        return {"available": False}
    try:
        weights = [float(w) for w in top_holdings["Holding Percent"].tolist() if w == w]
        names = list(top_holdings.index)
        labels = top_holdings["Name"].tolist() if "Name" in top_holdings else names
    except Exception:
        return {"available": False}

    if not weights:
        return {"available": False}

    return {
        "available": True,
        "top_10_weight": round(sum(weights), 4),
        "largest_weight": round(max(weights), 4),
        "holdings": [
            {"symbol": str(s), "name": str(n), "weight": round(float(w), 4)}
            for s, n, w in zip(names, labels, weights)
        ],
        "note": "Only the ten largest positions are published, so the true tail is unknown.",
    }


def _herfindahl(weights):
    """Concentration index over sector weights: 1.0 is a single sector."""
    vals = [float(v) for v in weights if v is not None]
    total = sum(vals)
    if total <= 0:
        return None
    return round(sum((v / total) ** 2 for v in vals), 4)


def fetch_one(fund, years=5, risk_free=DEFAULT_RISK_FREE):
    import yfinance as yf

    t = yf.Ticker(fund)
    try:
        info = with_retry(lambda: t.info, label="info {}".format(fund)) or {}
    except Exception:
        info = {}

    quote_type = (info.get("quoteType") or "").upper()

    operations = sectors = assets = holdings = None
    description = None
    try:
        fd = t.funds_data
        operations = fd.fund_operations
        sectors = fd.sector_weightings or {}
        assets = fd.asset_classes or {}
        holdings = fd.top_holdings
        description = (fd.description or "")[:1200] or None
    except Exception:
        pass

    expense, expense_basis = expense_ratio(info, operations)
    risk = price_risk(fund, years=years)

    vol = risk.get("volatility_annual")
    cagr = risk.get("price_cagr")
    dist_yield = _as_fraction(info.get("yield"), cap=0.5)
    total_cagr = None if cagr is None else cagr + (dist_yield or 0.0)

    # Return per unit of risk. Named for what it is: the excess over a stated
    # risk-free rate divided by volatility. The rate is an assumption, so it
    # travels with the number.
    sharpe = None
    if total_cagr is not None and vol:
        sharpe = round((total_cagr - risk_free) / vol, 3)

    turnover = None
    if operations is not None:
        try:
            turnover = _as_fraction(operations.loc["Annual Holdings Turnover"].iloc[0], cap=20.0)
        except Exception:
            turnover = None

    return {
        "ticker": fund.upper(),
        "as_of": utc_now(),
        "source": "yfinance",
        "is_fund": quote_type in FUND_QUOTE_TYPES,
        "quote_type": quote_type or None,
        "profile": {
            "name": info.get("longName") or info.get("shortName"),
            "family": info.get("fundFamily"),
            "category": info.get("category"),
            "legal_type": info.get("legalType"),
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
            "inception": info.get("fundInceptionDate"),
            "description": description,
        },
        "market": {
            "price": info.get("previousClose") or info.get("regularMarketPrice"),
            "nav": info.get("navPrice"),
            "total_assets": info.get("totalAssets"),
            "avg_volume": info.get("averageVolume"),
            "week52_high": info.get("fiftyTwoWeekHigh"),
            "week52_low": info.get("fiftyTwoWeekLow"),
        },
        "costs": {
            "expense_ratio": None if expense is None else round(expense, 5),
            "expense_ratio_basis": expense_basis,
            "turnover": turnover,
            "cost_per_100k_per_year": None if expense is None else round(expense * 100000, 0),
        },
        "returns": {
            # Yahoo's own windows, normalized. ytdReturn is a percentage number,
            # the multi-year averages are already fractions.
            "ytd": _as_fraction_from_percent(info.get("ytdReturn")),
            "three_year_avg": _as_fraction(info.get("threeYearAverageReturn")),
            "five_year_avg": _as_fraction(info.get("fiveYearAverageReturn")),
            "distribution_yield": dist_yield,
            "price_cagr_measured": cagr,
            "total_cagr_estimate": None if total_cagr is None else round(total_cagr, 4),
        },
        "risk": {
            **risk,
            "beta_3y": info.get("beta3Year"),
            "return_per_unit_of_risk": sharpe,
            "risk_free_assumed": risk_free,
        },
        "composition": {
            "concentration": concentration(holdings),
            "sector_weights": {k: round(float(v), 4) for k, v in (sectors or {}).items() if v},
            "sector_concentration_hhi": _herfindahl(list((sectors or {}).values())),
            "asset_classes": {k: round(float(v), 4) for k, v in (assets or {}).items() if v},
        },
    }


def _pct(v, digits=2):
    return "   n/a" if v is None else "{:.{d}f}%".format(v * 100, d=digits)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("funds", nargs="*", help="symbols, a fund group, or blank for all funds")
    ap.add_argument("--years", type=int, default=5, help="price history window for risk metrics")
    ap.add_argument("--risk-free", type=float, default=DEFAULT_RISK_FREE)
    ap.add_argument("--out-date", default=today())
    args = ap.parse_args()

    funds = resolve_funds(args.funds)
    if not funds:
        print("No funds. Pass symbols or fill the `funds` list in config/universe.yaml.",
              file=sys.stderr)
        return 2

    header = "{:<7} {:<30} {:>8} {:>8} {:>8} {:>8} {:>7}".format(
        "FUND", "NAME", "EXPENSE", "YIELD", "VOL", "MAXDD", "AUM")
    print(header)
    print("-" * len(header))

    ok = failed = 0
    not_funds = []
    for f in funds:
        try:
            payload = fetch_one(f, years=args.years, risk_free=args.risk_free)
            write_json(FUNDS / f.upper() / "{}.json".format(args.out_date), clean(payload))
            if not payload["is_fund"]:
                not_funds.append((f.upper(), payload.get("quote_type")))
            aum = (payload["market"] or {}).get("total_assets")
            print("{:<7} {:<30} {:>8} {:>8} {:>8} {:>8} {:>7}".format(
                f.upper(),
                str((payload["profile"] or {}).get("name") or "?")[:30],
                _pct(payload["costs"]["expense_ratio"]),
                _pct(payload["returns"]["distribution_yield"]),
                _pct(payload["risk"].get("volatility_annual"), 1),
                _pct(payload["risk"].get("max_drawdown"), 0),
                "-" if not aum else "{:.0f}B".format(aum / 1e9),
            ))
            ok += 1
        except Exception as e:
            failed += 1
            print("{:<7} FAILED: {}: {}".format(f.upper(), type(e).__name__, e), file=sys.stderr)

    print("\ndone: {} ok, {} failed".format(ok, failed))
    if not_funds:
        print("\nNot funds, so the fund metrics above are meaningless for them:")
        for sym, qt in not_funds:
            print("  {} is a {}. Use tools/fetch_fundamentals.py instead.".format(sym, qt or "?"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
