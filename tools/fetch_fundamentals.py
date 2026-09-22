"""Fetch fundamentals + derived growth metrics for tickers, one JSON per ticker.

Usage:
    uv run python tools/fetch_fundamentals.py NVDA MSFT
    uv run python tools/fetch_fundamentals.py ai_infra      # a group in universe.yaml
    uv run python tools/fetch_fundamentals.py               # whole watchlist

Writes data/raw/<TICKER>/<YYYY-MM-DD>.json and prints one summary line per ticker.
Source: Yahoo Finance via yfinance (delayed, free, best-effort).
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    get_logger,
    RAW,
    cagr,
    clean,
    pct_change,
    resolve_tickers,
    safe_div,
    with_retry,
    slope_per_year,
    today,
    utc_now,
    write_json,
)

# yfinance renames rows between versions, so try each alias in order.
INCOME_ROWS = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "Total Operating Income As Reported"],
    "net_income": [
        "Net Income",
        "Net Income Common Stockholders",
        "Net Income From Continuing Operation Net Minority Interest",
    ],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "rnd": ["Research And Development"],
    "eps_diluted": ["Diluted EPS"],
    "shares_diluted": ["Diluted Average Shares"],
}
BALANCE_ROWS = {
    "total_assets": ["Total Assets"],
    "equity": ["Stockholders Equity", "Total Equity Gross Minority Interest"],
    "total_debt": ["Total Debt"],
    "cash": [
        "Cash Cash Equivalents And Short Term Investments",
        "Cash And Cash Equivalents",
    ],
    "current_assets": ["Current Assets", "Total Current Assets"],
    "current_liabilities": ["Current Liabilities", "Total Current Liabilities"],
    "invested_capital": ["Invested Capital"],
}
CASHFLOW_ROWS = {
    "operating_cf": [
        "Operating Cash Flow",
        "Cash Flow From Continuing Operating Activities",
    ],
    "capex": ["Capital Expenditure"],
    "free_cash_flow": ["Free Cash Flow"],
    "buybacks": ["Repurchase Of Capital Stock"],
}


def _row(df, aliases, n_cols):
    """Pull one row as an oldest-to-newest list, padded to n_cols."""
    out = [None] * n_cols
    if df is None or getattr(df, "empty", True):
        return out
    for name in aliases:
        if name in df.index:
            vals = [clean(v) for v in df.loc[name].tolist()]
            vals = vals[::-1]  # yfinance returns newest-first
            if len(vals) < n_cols:
                vals = [None] * (n_cols - len(vals)) + vals
            return vals[-n_cols:]
    return out


def _periods(df):
    if df is None or getattr(df, "empty", True):
        return []
    return [str(c)[:10] for c in df.columns.tolist()][::-1]


def _extract(df, spec, periods):
    n = len(periods)
    return {k: _row(df, aliases, n) for k, aliases in spec.items()}


def _ratio_series(num, den):
    return [safe_div(a, b) for a, b in zip(num, den)]


def _last(series):
    return next((v for v in reversed(series or []) if v is not None), None)


def dividend_yield_fraction(info):
    """Dividend yield as a plain fraction, e.g. 0.008 for 0.8 percent.

    Yahoo's `dividendYield` is a percentage number, not a fraction: Microsoft
    comes back as 0.8 meaning 0.80%. Reading it as a fraction overstates every
    payer by 100x, which is the kind of error that survives all the way into a
    recommendation. `dividendRate / price` is unambiguous and matches the field
    exactly on every ticker checked, so prefer it and fall back to the field.
    """
    rate = info.get("dividendRate")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if rate and price:
        y = safe_div(rate, price)
        if y is not None and 0 <= y < 0.5:  # above 50% is a data error, not a payer
            return y

    raw = info.get("dividendYield")
    if raw is None:
        return None
    try:
        raw = float(raw)
    except (TypeError, ValueError):
        return None
    if raw <= 0:
        return None
    y = raw / 100.0
    return y if y < 0.5 else None


def _first_last(series):
    """Oldest and newest non-null values, plus the number of periods between them."""
    idx = [i for i, v in enumerate(series) if v is not None]
    if len(idx) < 2:
        return None, None, 0
    return series[idx[0]], series[idx[-1]], idx[-1] - idx[0]


def compute_metrics(annual, info):
    rev = annual.get("revenue", [])
    ni = annual.get("net_income", [])
    fcf = annual.get("free_cash_flow", [])
    ocf = annual.get("operating_cf", [])
    capex = annual.get("capex", [])
    gp = annual.get("gross_profit", [])
    oi = annual.get("operating_income", [])
    ebitda = annual.get("ebitda", [])
    equity = annual.get("equity", [])
    debt = annual.get("total_debt", [])
    cash = annual.get("cash", [])
    ca = annual.get("current_assets", [])
    cl = annual.get("current_liabilities", [])
    rnd = annual.get("rnd", [])

    # Derive FCF when the row is missing: OCF + capex, where capex is negative.
    if not any(v is not None for v in fcf) and any(v is not None for v in ocf):
        fcf = [None if (o is None or c is None) else o + c for o, c in zip(ocf, capex)]
        annual["free_cash_flow"] = fcf

    gross_margin = _ratio_series(gp, rev)
    op_margin = _ratio_series(oi, rev)
    net_margin = _ratio_series(ni, rev)
    fcf_margin = _ratio_series(fcf, rev)
    rnd_intensity = _ratio_series(rnd, rev)

    r0, r1, rn = _first_last(rev)
    n0, n1, nn = _first_last(ni)
    f0, f1, fn = _first_last(fcf)

    last_equity = _last(equity)
    last_debt = _last(debt)
    last_cash = _last(cash)
    last_ebitda = _last(ebitda)
    last_oi = _last(oi)
    last_ni = _last(ni)
    last_rev = _last(rev)
    last_fcf = _last(fcf)
    last_ic = _last(annual.get("invested_capital", []))

    net_debt = None if last_debt is None else last_debt - (last_cash or 0.0)

    if last_ic is None and last_equity is not None:
        last_ic = last_equity + (last_debt or 0.0) - (last_cash or 0.0)

    # ROIC using a 21% blended tax haircut on operating income.
    roic = safe_div(last_oi * 0.79, last_ic) if (last_oi is not None and last_ic) else None

    mcap = info.get("marketCap")
    ev = info.get("enterpriseValue")
    if ev is None and mcap is not None and net_debt is not None:
        ev = mcap + net_debt

    fwd_growth = pct_change(info.get("trailingEps"), info.get("forwardEps"))
    currency_mismatch = bool(
        info.get("currency")
        and info.get("financialCurrency")
        and info.get("currency") != info.get("financialCurrency")
    )

    peg = None
    fpe = info.get("forwardPE")
    growth_for_peg = info.get("earningsGrowth") or fwd_growth
    if fpe and growth_for_peg and growth_for_peg > 0:
        peg = fpe / (growth_for_peg * 100.0)

    return {
        "years_of_data": len(rev),
        # True when market cap and the statements are in different currencies, so
        # any market-cap-over-statement ratio below is unit-inconsistent.
        "currency_mismatch": currency_mismatch,
        "trading_currency": info.get("currency"),
        "financial_currency": info.get("financialCurrency"),
        "revenue_cagr": cagr(r0, r1, rn) if rn else None,
        "revenue_cagr_years": rn,
        "net_income_cagr": cagr(n0, n1, nn) if nn else None,
        "fcf_cagr": cagr(f0, f1, fn) if fn else None,
        "revenue_growth_ttm": info.get("revenueGrowth"),
        "earnings_growth_ttm": info.get("earningsGrowth"),
        "forward_eps_growth": fwd_growth,
        "gross_margin_latest": _last(gross_margin),
        "gross_margin_trend": slope_per_year(gross_margin),
        "operating_margin_latest": _last(op_margin),
        "operating_margin_trend": slope_per_year(op_margin),
        "net_margin_latest": _last(net_margin),
        "fcf_margin_latest": _last(fcf_margin),
        "fcf_margin_trend": slope_per_year(fcf_margin),
        "rnd_intensity_latest": _last(rnd_intensity),
        "roe": info.get("returnOnEquity") or safe_div(last_ni, last_equity),
        "roa": info.get("returnOnAssets"),
        "roic_est": roic,
        "current_ratio": info.get("currentRatio") or safe_div(_last(ca), _last(cl)),
        "debt_to_equity": info.get("debtToEquity"),
        "net_debt": net_debt,
        "net_debt_to_ebitda": (
            safe_div(net_debt, last_ebitda) if net_debt is not None else None
        ),
        "market_cap": mcap,
        "enterprise_value": ev,
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": fpe,
        "peg_est": peg,
        "price_to_sales": info.get("priceToSalesTrailing12Months")
        or safe_div(mcap, last_rev),
        "ev_to_ebitda": info.get("enterpriseToEbitda") or safe_div(ev, last_ebitda),
        "ev_to_revenue": info.get("enterpriseToRevenue") or safe_div(ev, last_rev),
        "fcf_yield": safe_div(last_fcf, mcap),
        # A fraction, normalized from Yahoo's percentage field. See the helper.
        "dividend_yield": dividend_yield_fraction(info),
        "dividend_rate": info.get("dividendRate"),
        "payout_ratio": info.get("payoutRatio"),
        "beta": info.get("beta"),
    }


def fetch_one(ticker, years=5):
    import yfinance as yf

    t = yf.Ticker(ticker)
    try:
        # Rate limits are the normal failure here, and a silent empty `info`
        # would look like a company with no data rather than a throttled request.
        info = with_retry(lambda: t.info, label="info {}".format(ticker)) or {}
    except Exception:
        info = {}

    inc = getattr(t, "income_stmt", None)
    bal = getattr(t, "balance_sheet", None)
    cfs = getattr(t, "cashflow", None)

    periods = _periods(inc) or _periods(bal) or _periods(cfs)
    periods = periods[-years:] if periods else []

    annual = {}
    annual.update(_extract(inc, INCOME_ROWS, periods))
    annual.update(_extract(bal, BALANCE_ROWS, periods))
    annual.update(_extract(cfs, CASHFLOW_ROWS, periods))

    metrics = compute_metrics(annual, info)
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    target = info.get("targetMeanPrice")

    return {
        "ticker": ticker.upper(),
        "as_of": utc_now(),
        "source": "yfinance",
        "profile": {
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "exchange": info.get("exchange"),
            "currency": info.get("currency"),
            # The currency the statements are reported in. For an ADR such as NVO
            # this differs from the trading currency, which makes any ratio built
            # from market cap over a statement line item meaningless.
            "financial_currency": info.get("financialCurrency"),
            "employees": info.get("fullTimeEmployees"),
            "website": info.get("website"),
            "summary": (info.get("longBusinessSummary") or "")[:1500] or None,
        },
        "market": {
            "price": price,
            "market_cap": info.get("marketCap"),
            "week52_high": info.get("fiftyTwoWeekHigh"),
            "week52_low": info.get("fiftyTwoWeekLow"),
            "off_52w_high": pct_change(info.get("fiftyTwoWeekHigh"), price),
            "avg_volume": info.get("averageVolume"),
        },
        "analyst": {
            "target_mean": target,
            "target_high": info.get("targetHighPrice"),
            "target_low": info.get("targetLowPrice"),
            "upside_to_target": pct_change(price, target),
            "recommendation": info.get("recommendationKey"),
            "n_analysts": info.get("numberOfAnalystOpinions"),
        },
        "annual": {"periods": periods, **annual},
        "metrics": metrics,
    }


def _p(v):
    return "  n/a" if v is None else "{:5.1f}%".format(v * 100)


def _n(v):
    return "  n/a" if v is None else "{:5.1f}".format(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "tickers",
        nargs="*",
        help="tickers, a universe group name, or blank for the whole watchlist",
    )
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--out-date", default=today(), help="filename date stamp")
    ap.add_argument("--workers", type=int, default=4, help="parallel fetches; 1 is sequential. Kept low because Yahoo rate-limits.")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    tickers = resolve_tickers(args.tickers)
    if not tickers:
        print(
            "No tickers. Pass them as arguments or fill config/universe.yaml.",
            file=sys.stderr,
        )
        return 2

    ok = failed = 0
    results = {}

    def work(tk):
        return tk, fetch_one(tk, years=args.years)

    # Concurrency is capped low on purpose. Yahoo rate-limits, and a fetch that
    # comes back 429 or silently empty is worse than a slow one: the empty case
    # looks like a company with no statements rather than like an error. Results
    # are collected first and printed in the order the tickers were given, so a
    # run stays reproducible and diffable regardless of which finished first.
    if args.workers > 1 and len(tickers) > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(work, tk): tk for tk in tickers}
            for fut in as_completed(futures):
                tk = futures[fut]
                try:
                    _tk, payload = fut.result()
                    results[tk] = payload
                except Exception as e:
                    results[tk] = e
    else:
        for tk in tickers:
            try:
                results[tk] = fetch_one(tk, years=args.years)
            except Exception as e:
                results[tk] = e

    for tk in tickers:
        payload = results.get(tk)
        if isinstance(payload, Exception) or payload is None:
            failed += 1
            e = payload or RuntimeError("no result")
            get_logger().error("fetch_fundamentals %s failed: %s: %s",
                               tk.upper(), type(e).__name__, e)
            print("{:<8} FAILED: {}: {}".format(tk.upper(), type(e).__name__, e), file=sys.stderr)
            if args.verbose:
                traceback.print_exception(type(e), e, e.__traceback__)
            continue
        path = write_json(RAW / tk.upper() / "{}.json".format(args.out_date), payload)
        m = payload["metrics"]
        name = str(payload["profile"]["name"] or "?")[:30]
        print(
            "{:<8} {:<30} revCAGR={} opMgn={} ROIC={} fwdPE={}  -> {}".format(
                tk.upper(),
                name,
                _p(m["revenue_cagr"]),
                _p(m["operating_margin_latest"]),
                _p(m["roic_est"]),
                _n(m["forward_pe"]),
                path.relative_to(RAW.parent.parent),
            )
        )
        ok += 1
    print("\ndone: {} ok, {} failed".format(ok, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
