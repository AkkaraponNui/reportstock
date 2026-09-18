"""Growth prediction model: fitted fade, Monte Carlo, and sensitivity.

Usage:
    uv run python tools/predict.py NVDA
    uv run python tools/predict.py ai_infra --runs 20000
    uv run python tools/predict.py --fit-only        # just show the fitted fade curve

Writes data/predictions/<TICKER>/<YYYY-MM-DD>.json.

What this is, precisely
----------------------
Three things, none of which is a forecast of price.

1. An empirical fade curve. Revenue growth mean-reverts: fast growers slow down,
   slow growers drift toward the middle. How fast that happens is measurable, so
   this fits `next_growth = a + b * current_growth` across every company with
   data on disk and uses the fitted line instead of the hand-picked linear fade
   in score.py. The fit reports its own sample size and R-squared, which are
   small and low. Read them before trusting the curve.

2. A Monte Carlo over the assumptions. The scorecard's projection picks one
   number for growth, margin and exit multiple. Reality has a range. This samples
   each input thousands of times from a distribution built out of the company's
   own history and reports the spread of outcomes, not a point estimate.

3. A sensitivity ranking. Which single assumption moves the answer most. Usually
   it is the exit multiple, which is the assumption nobody can forecast, and
   knowing that is worth more than any individual number here.

What it is not
--------------
It is not trained to predict returns and it has never been validated against
out-of-sample outcomes, because yfinance serves current data with no point-in-time
history, so an honest backtest is impossible with this data source. The spread it
produces is the spread of the assumptions, not a probability of anything in the
world. A model of this shape cannot see a business changing shape, which over
five years is usually what decides the result.
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DATA,
    RAW,
    latest_snapshot,
    read_json,
    resolve_tickers,
    safe_div,
    today,
    utc_now,
    write_json,
)
from score import _sales_multiple, blended_growth  # noqa: E402

PREDICTIONS = DATA / "predictions"
PREDICTIONS.mkdir(parents=True, exist_ok=True)

# Long-run nominal revenue growth for a mature business: real growth plus
# inflation. Every fade converges here.
DEFAULT_TERMINAL = 0.04

# Guard rails. A simulated path that leaves these is not informative, it is the
# model extrapolating past anything the inputs can support.
MAX_GROWTH = 1.50
MIN_GROWTH = -0.40
MIN_MARGIN = 0.005
MAX_MARGIN = 0.60
MIN_EXIT_PE = 5.0
MAX_EXIT_PE = 70.0


# ---------------------------------------------------------------------------
# growth series
# ---------------------------------------------------------------------------

def annual_growth_series(fundamentals):
    """Year-over-year revenue growth, oldest first. None entries are dropped."""
    a = (fundamentals or {}).get("annual") or {}
    rev = [v for v in (a.get("revenue") or [])]
    out = []
    for prev, cur in zip(rev, rev[1:]):
        if prev and cur and prev > 0:
            out.append(cur / prev - 1.0)
        else:
            out.append(None)
    return out


def growth_volatility(series, floor=0.05, cap=0.60):
    """Standard deviation of a company's own growth rate, as the uncertainty scale.

    Two observations give a meaningless standard deviation, so the floor does the
    work for young or thinly reported companies. The cap stops one hypergrowth
    year from making every simulated path noise.
    """
    vals = [v for v in series if v is not None]
    if len(vals) < 3:
        return 0.25  # not enough history to measure; assume substantial uncertainty
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return max(floor, min(math.sqrt(var), cap))


# ---------------------------------------------------------------------------
# the fitted fade
# ---------------------------------------------------------------------------

def _ols(pairs):
    """Least squares for y = a + b*x. Returns a, b, r2, residual sd, n."""
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    if sxx == 0:
        return None
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    b = sxy / sxx
    a = my - b * mx
    resid = [p[1] - (a + b * p[0]) for p in pairs]
    sse = sum(r * r for r in resid)
    sst = sum((p[1] - my) ** 2 for p in pairs)
    r2 = 1.0 - sse / sst if sst > 0 else 0.0
    dof = max(1, n - 2)
    resid_sd = math.sqrt(sse / dof)
    se_b = math.sqrt(sse / dof / sxx) if sxx > 0 else 0.0
    return {"a": a, "b": b, "r2": r2, "resid_sd": resid_sd, "n": n, "se_b": se_b}


# Company-years above this growth rate are hypergrowth. A handful of them in a
# small panel dominate a least-squares line through sheer leverage, so the fit is
# run twice and the version that is not driven by two points is preferred.
TRIM_AT = 0.50


def fit_fade(tickers=None, trim_at=TRIM_AT):
    """Fit growth persistence across every ticker with a snapshot on disk.

    Each observation is one company-year: this year's revenue growth paired with
    next year's. The slope is how much of a growth rate carries into the
    following year, and it is reliably below 1, which is mean reversion.

    Two fits are run. The full one uses every point; the trimmed one drops
    hypergrowth years above `trim_at`. In a panel this small the two can disagree
    sharply, because a couple of extreme points sit far out on the x axis and pull
    the line toward themselves while inflating R-squared. The trimmed fit wins
    when it still has enough observations, and the disagreement between them is
    folded into the slope's standard error so the simulation samples across it
    instead of pretending one line is right.
    """
    if tickers is None:
        tickers = [p.name for p in RAW.iterdir() if p.is_dir()] if RAW.exists() else []

    pairs, used = [], []
    for tk in tickers:
        snap = latest_snapshot(RAW / tk.upper())
        if not snap:
            continue
        f = read_json(snap) or {}
        series = annual_growth_series(f)
        contributed = 0
        for cur, nxt in zip(series, series[1:]):
            if cur is None or nxt is None:
                continue
            if abs(cur) > MAX_GROWTH or abs(nxt) > MAX_GROWTH:
                continue  # an acquisition or a restatement, not organic growth
            pairs.append((cur, nxt))
            contributed += 1
        if contributed:
            used.append({"ticker": tk.upper(), "observations": contributed})

    full = _ols(pairs)
    if not full:
        return {
            "fitted": False,
            "reason": "Fewer than three usable company-year pairs on disk. "
                      "Fetch more tickers, then refit.",
            "companies": used,
        }

    kept = [p for p in pairs if abs(p[0]) <= trim_at]
    trimmed = _ols(kept) if len(kept) >= 10 else None

    if trimmed:
        chosen, basis = dict(trimmed), "trimmed"
    else:
        chosen, basis = dict(full), "full"

    disagreement = abs(full["b"] - trimmed["b"]) if trimmed else 0.0
    # The gap between the two lines is real uncertainty about the slope, so widen
    # the standard error to cover it rather than discarding one answer.
    chosen["se_b"] = max(chosen["se_b"], disagreement / 2.0)

    chosen.update(
        {
            "fitted": True,
            "basis": basis,
            "trim_at": trim_at,
            "n_excluded_by_trim": len(pairs) - len(kept),
            "full_fit": {k: round(full[k], 4) for k in ("a", "b", "r2", "n", "resid_sd")},
            "trimmed_fit": ({k: round(trimmed[k], 4) for k in ("a", "b", "r2", "n", "resid_sd")}
                            if trimmed else None),
            "slope_disagreement": round(disagreement, 4),
            "companies": used,
            "n_companies": len(used),
        }
    )
    chosen["interpretation"] = _fade_words(chosen, full, trimmed)
    return chosen


def _fade_words(chosen, full, trimmed):
    b, a, r2, n = chosen["b"], chosen["a"], chosen["r2"], chosen["n"]
    steady = safe_div(a, 1 - b) if abs(1 - b) > 1e-6 else None
    parts = [
        "About {:.0f}% of a company's revenue growth carries into the next year; "
        "the rest fades.".format(b * 100)
    ]
    if steady is not None and -0.2 < steady < 0.5:
        parts.append(
            "Left alone the fit settles at roughly {:.1f}% a year, which is the "
            "long-run rate it pulls every company toward.".format(steady * 100)
        )
    parts.append(
        "It explains {:.0f}% of the variation across {} company-years, so treat it as "
        "a weak central tendency rather than a rule.".format(r2 * 100, n)
    )
    if trimmed and abs(full["b"] - trimmed["b"]) > 0.08:
        parts.append(
            "Including hypergrowth years moves the slope to {:.2f} and lifts R-squared "
            "to {:.2f}, but that version is held up by only {} extreme points, so the "
            "trimmed fit is used and the gap between the two is carried as extra "
            "uncertainty in the slope.".format(
                full["b"], full["r2"], chosen.get("n_excluded_by_trim", 0)
            )
        )
    if n < 40:
        parts.append(
            "With only {} observations the slope itself is uncertain, which the "
            "simulation accounts for by sampling it rather than fixing it.".format(n)
        )
    return " ".join(parts)


# ---------------------------------------------------------------------------
# simulation
# ---------------------------------------------------------------------------

def _clamp(x, lo, hi):
    return max(lo, min(x, hi))


def _percentile(sorted_vals, q) -> float:
    """Linear-interpolated percentile. Callers must pass a non-empty sorted list."""
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    idx = q * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(sorted_vals[lo])
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (idx - lo))


def simulate(metrics, fit, years=5, runs=10000, terminal=DEFAULT_TERMINAL,
             growth_series=None, seed=7, overrides=None):
    """Monte Carlo over growth path, margin path, and exit multiple.

    Every draw is anchored on the company's own reported history. The spread of
    the result is the spread of the assumptions, nothing more.

    `overrides` perturbs the model's own assumptions rather than the raw metrics,
    which is what the sensitivity pass needs. Perturbing a metric instead would
    be misleading here: net margin, for instance, sets both the projected margin
    and the current sales multiple it is measured against, so nudging it moves
    both sides of the ratio and measures nothing. Supported keys are
    `start_growth`, `persistence_slope`, `margin_end_shift`, and
    `exit_multiple_scale`.
    """
    rng = random.Random(seed)
    ov = overrides or {}

    g0 = ov.get("start_growth", blended_growth(metrics))
    if g0 is None:
        return {"ok": False, "reason": "No usable growth signal in the snapshot."}

    ps_now, ps_basis = _sales_multiple(metrics)
    if ps_now is None:
        return {"ok": False, "reason": ps_basis}

    reported_margin = metrics.get("net_margin_latest")
    # A loss-maker has no margin to project from, so stand in a modest one and
    # give the "never turns profitable" outcome real weight further down.
    if reported_margin is None or reported_margin <= 0:
        loss_maker = True
        net_margin = 0.08
    else:
        loss_maker = False
        net_margin = float(reported_margin)

    margin_trend = metrics.get("operating_margin_trend") or 0.0
    fwd_pe = metrics.get("forward_pe") or metrics.get("trailing_pe")
    # Implied P/E on the same basis as ps_now, so both ends of the trade agree.
    entry_pe = ps_now / net_margin if net_margin else None

    g_vol = growth_volatility(growth_series or [])
    b_hat = ov.get("persistence_slope", fit.get("b", 0.45) if fit.get("fitted") else 0.45)
    a_hat = fit.get("a", 0.05) if fit.get("fitted") else 0.05
    b_se = fit.get("se_b", 0.15) if fit.get("fitted") else 0.15
    resid_sd = fit.get("resid_sd", 0.20) if fit.get("fitted") else 0.20

    margin_shift = ov.get("margin_end_shift", 0.0)
    multiple_scale = ov.get("exit_multiple_scale", 1.0)

    # The margin ceiling has to sit above where the company already operates, or
    # it silently caps a high-margin business and turns every other lever into
    # noise against a flat wall.
    margin_ceiling = max(MAX_MARGIN, net_margin * 1.20)

    # Dividend assumptions. The yield is capped as a guard against a bad upstream
    # value; a payout the company does not earn is far likelier to be cut, so it
    # carries a higher cut probability.
    base_yield = ov.get("dividend_yield", metrics.get("dividend_yield") or 0.0)
    base_yield = min(max(float(base_yield or 0.0), 0.0), 0.15)
    payout = metrics.get("payout_ratio")
    cut_probability = 0.35 if (payout is not None and payout > 1.0) else 0.12

    returns, end_growths, end_margins, exit_pes, dividends = [], [], [], [], []

    for _ in range(runs):
        # The persistence slope is estimated, not known, so each path gets its own.
        b = _clamp(rng.gauss(b_hat, b_se), 0.0, 0.95)
        a = a_hat

        g = _clamp(rng.gauss(g0, g_vol * 0.5), MIN_GROWTH, MAX_GROWTH)
        rev_index = 1.0
        for _ in range(years):
            rev_index *= 1.0 + g
            # Next year's growth: the fitted fade plus this company's own noise,
            # pulled gently toward the terminal rate so long paths stay sane.
            g = a + b * g + rng.gauss(0.0, resid_sd)
            g = g * 0.85 + terminal * 0.15
            g = _clamp(g, MIN_GROWTH, MAX_GROWTH)

        # Margin drifts along its own trend with real uncertainty around it.
        margin_drift = margin_trend * years * 0.5
        margin_noise = max(0.01, abs(net_margin) * 0.25)
        margin_end = _clamp(
            rng.gauss(net_margin + margin_drift + margin_shift, margin_noise),
            MIN_MARGIN,
            margin_ceiling,
        )
        if loss_maker:
            # A company not yet profitable may never get there. Give that outcome
            # real weight instead of assuming the turn always happens.
            if rng.random() < 0.25:
                margin_end = _clamp(rng.gauss(0.02, 0.02), MIN_MARGIN, 0.06)

        # Exit multiple: the single assumption nobody can forecast. Sampled
        # lognormally around a blend of today's multiple and a growth-justified one.
        # The anchor is derived from ps_now so the entry and exit multiples sit on
        # one basis; anchoring the exit on forward P/E while the entry comes from
        # trailing P/E lets an expensive stock score better than a cheap one.
        justified = 10.0 + 55.0 * _clamp(terminal + g * 0.25, 0.0, 0.30)
        centre = (0.5 * entry_pe + 0.5 * justified) if entry_pe else justified
        centre = _clamp(centre * multiple_scale, MIN_EXIT_PE, MAX_EXIT_PE)
        exit_pe = _clamp(centre * math.exp(rng.gauss(0.0, 0.32)), MIN_EXIT_PE, MAX_EXIT_PE)

        value_ratio = rev_index * margin_end * exit_pe / ps_now
        if value_ratio <= 0:
            continue

        # Total return, not price return. A dividend is cash the holder receives
        # whatever the multiple does, and omitting it biases every comparison
        # against payers. The yield is sampled rather than fixed because a
        # dividend can be raised, frozen, or cut over five years.
        div = 0.0
        if base_yield > 0:
            div = max(0.0, rng.gauss(base_yield, base_yield * 0.35))
            if rng.random() < cut_probability:
                div *= 0.4  # a cut, which is what actually happens under stress
        price_ann = value_ratio ** (1.0 / years) - 1.0
        returns.append((1.0 + price_ann) * (1.0 + div) - 1.0)
        dividends.append(div)
        end_growths.append(g)
        end_margins.append(margin_end)
        exit_pes.append(exit_pe)

    if not returns:
        return {"ok": False, "reason": "Every simulated path was degenerate."}

    returns.sort()
    n = len(returns)

    return {
        "ok": True,
        "runs": n,
        "years": years,
        "inputs": {
            "start_growth": round(g0, 4),
            "growth_volatility": round(g_vol, 4),
            "persistence_slope": round(b_hat, 4),
            "persistence_slope_se": round(b_se, 4),
            "residual_sd": round(resid_sd, 4),
            "start_net_margin": None if metrics.get("net_margin_latest") is None
            else round(metrics["net_margin_latest"], 4),
            "assumed_margin_for_loss_maker": loss_maker,
            "margin_trend_per_year": round(margin_trend, 5),
            "current_sales_multiple": round(ps_now, 3),
            "sales_multiple_basis": ps_basis,
            "forward_pe": fwd_pe,
            "terminal_growth": terminal,
            "dividend_yield": round(base_yield, 4),
            "dividend_cut_probability": cut_probability,
        },
        "annualized_return": {
            "p05": round(_percentile(returns, 0.05), 4),
            "p25": round(_percentile(returns, 0.25), 4),
            "p50": round(_percentile(returns, 0.50), 4),
            "p75": round(_percentile(returns, 0.75), 4),
            "p95": round(_percentile(returns, 0.95), 4),
            "mean": round(sum(returns) / n, 4),
        },
        "probabilities": {
            "loses_money": round(sum(1 for r in returns if r < 0) / n, 4),
            "beats_4pct": round(sum(1 for r in returns if r > 0.04) / n, 4),
            "beats_8pct": round(sum(1 for r in returns if r > 0.08) / n, 4),
            "beats_15pct": round(sum(1 for r in returns if r > 0.15) / n, 4),
            "doubles_in_5y": round(sum(1 for r in returns if r > 0.1487) / n, 4),
        },
        "ending_state_median": {
            "growth_year5": round(sorted(end_growths)[n // 2], 4),
            "net_margin": round(sorted(end_margins)[n // 2], 4),
            "exit_pe": round(sorted(exit_pes)[n // 2], 2),
            "dividend_yield": round(sorted(dividends)[n // 2], 4) if dividends else 0.0,
        },
        "distribution": [round(r, 4) for r in returns[:: max(1, n // 400)]],
    }


def sensitivity(metrics, fit, years=5, runs=2500, terminal=DEFAULT_TERMINAL,
                growth_series=None):
    """Move one assumption at a time and record what it does to the median.

    The ranking matters more than the magnitudes: it tells you which number to
    argue about.
    """
    base = simulate(metrics, fit, years=years, runs=runs, terminal=terminal,
                    growth_series=growth_series, seed=11)
    if not base.get("ok"):
        return {"ok": False, "reason": base.get("reason")}
    base_median = base["annualized_return"]["p50"]

    g0 = blended_growth(metrics)
    margin_now = metrics.get("net_margin_latest") or 0.08
    b_now = fit.get("b", 0.45) if fit.get("fitted") else 0.45

    # Each lever is one assumption of the model, moved low and high by an amount
    # a reasonable person could disagree about. Same seed everywhere, so the
    # difference between runs is the lever and not the random draw.
    # Each lever carries a stable English key alongside the Thai label, so a report
    # in either language reads consistently without translating at the data layer.
    levers = []
    if g0 is not None:
        levers.append((
            "start_growth", "starting growth rate", "อัตราการเติบโตเริ่มต้น",
            "เริ่มต้นที่ {:.0%} ต่อปี".format(g0),
            {"start_growth": g0 * 0.70},
            {"start_growth": g0 * 1.30},
        ))
    levers.append((
        "persistence", "growth persistence", "ความคงทนของการเติบโต",
        "โตต่อเนื่อง {:.0%} ของปีก่อน".format(b_now),
        {"persistence_slope": max(0.0, b_now - 0.15)},
        {"persistence_slope": min(0.95, b_now + 0.15)},
    ))
    levers.append((
        "end_margin", "terminal net margin", "มาร์จิ้นปลายทาง",
        "ปัจจุบัน {:.0%}".format(margin_now),
        {"margin_end_shift": -abs(margin_now) * 0.20},
        {"margin_end_shift": abs(margin_now) * 0.20},
    ))
    div_now = min(max(float(metrics.get("dividend_yield") or 0.0), 0.0), 0.15)
    if div_now > 0.002:
        levers.append((
            "dividend", "dividend yield", "ปันผล",
            "ปัจจุบัน {:.2%} ต่อปี".format(div_now),
            {"dividend_yield": div_now * 0.5},
            {"dividend_yield": div_now * 1.3},
        ))
    levers.append((
        "exit_multiple", "exit multiple", "ตัวคูณตอนขาย",
        "P/E ข้างหน้า {}".format(
            "n/a" if metrics.get("forward_pe") is None else round(metrics["forward_pe"], 1)),
        {"exit_multiple_scale": 0.75},
        {"exit_multiple_scale": 1.25},
    ))

    rows = []
    for key, label_en, label_th, describe, low_ov, high_ov in levers:
        low = simulate(metrics, fit, years=years, runs=runs, terminal=terminal,
                       growth_series=growth_series, seed=11, overrides=low_ov)
        high = simulate(metrics, fit, years=years, runs=runs, terminal=terminal,
                        growth_series=growth_series, seed=11, overrides=high_ov)
        if not (low.get("ok") and high.get("ok")):
            continue
        lo = low["annualized_return"]["p50"]
        hi = high["annualized_return"]["p50"]
        rows.append(
            {
                "key": key,
                "lever": label_th,
                "lever_en": label_en,
                "description": describe,
                "low_median": lo,
                "high_median": hi,
                "swing": round(abs(hi - lo), 4),
            }
        )

    rows.sort(key=lambda r: -r["swing"])
    return {"ok": True, "base_median": base_median, "levers": rows}


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def predict_ticker(ticker, fit=None, years=5, runs=10000, terminal=DEFAULT_TERMINAL):
    snap_path = latest_snapshot(RAW / ticker.upper())
    if not snap_path:
        raise FileNotFoundError(
            "No fundamentals for {}. Run: uv run python tools/fetch_fundamentals.py {}".format(
                ticker, ticker
            )
        )
    f = read_json(snap_path) or {}
    metrics = f.get("metrics") or {}
    profile = f.get("profile") or {}
    series = annual_growth_series(f)

    if fit is None:
        fit = fit_fade()

    sim = simulate(metrics, fit, years=years, runs=runs, terminal=terminal,
                   growth_series=series)
    sens = sensitivity(metrics, fit, years=years, terminal=terminal,
                       growth_series=series) if sim.get("ok") else {"ok": False}

    return {
        "ticker": ticker.upper(),
        "company": profile.get("name"),
        "sector": profile.get("sector"),
        "as_of": utc_now(),
        "source_snapshot": str(snap_path.relative_to(RAW.parent.parent)),
        "historical_growth": [None if g is None else round(g, 4) for g in series],
        "historical_periods": ((f.get("annual") or {}).get("periods") or [])[1:],
        "fade_fit": fit,
        "simulation": sim,
        "sensitivity": sens,
        "disclaimer": (
            "A simulation of assumption uncertainty, not a forecast and not validated "
            "against out-of-sample outcomes. The spread shown is the spread of the "
            "inputs. Not investment advice."
        ),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--runs", type=int, default=10000)
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--terminal-growth", type=float, default=DEFAULT_TERMINAL)
    ap.add_argument("--fit-only", action="store_true", help="show the fitted fade and stop")
    ap.add_argument("--no-report", action="store_true",
                    help="skip the markdown report and write only the JSON")
    ap.add_argument("--report-name", default=None,
                    help="slug for the report filename; defaults to the ticker, or compare-N")
    ap.add_argument("--out-date", default=today())
    args = ap.parse_args()

    fit = fit_fade()

    print("Fitted fade across every ticker on disk")
    print("-" * 68)
    if not fit.get("fitted"):
        print(fit.get("reason"))
    else:
        print("  next_growth = {:.4f} + {:.4f} * current_growth".format(fit["a"], fit["b"]))
        print("  observations {}  companies {}  R-squared {:.3f}  residual sd {:.3f}".format(
            fit["n"], fit["n_companies"], fit["r2"], fit["resid_sd"]))
        print()
        print("  " + fit["interpretation"])
    print()

    if args.fit_only:
        return 0

    tickers = resolve_tickers(args.tickers)
    if not tickers:
        print("No tickers. Pass them as arguments or fill config/universe.yaml.", file=sys.stderr)
        return 2

    header = "{:<10} {:>8} {:>8} {:>8} {:>8} {:>8} {:>9}".format(
        "TICKER", "p05", "p25", "MEDIAN", "p75", "p95", "P(loss)")
    print(header)
    print("-" * len(header))

    completed = []
    for tk in tickers:
        try:
            res = predict_ticker(tk, fit=fit, years=args.years, runs=args.runs,
                                 terminal=args.terminal_growth)
            write_json(PREDICTIONS / tk.upper() / "{}.json".format(args.out_date), res)
            completed.append(res)
            sim = res["simulation"]
            if not sim.get("ok"):
                print("{:<10} {}".format(tk.upper(), sim.get("reason")))
                continue
            r = sim["annualized_return"]
            p = sim["probabilities"]
            print("{:<10} {:>7.1f}% {:>7.1f}% {:>7.1f}% {:>7.1f}% {:>7.1f}% {:>8.0f}%".format(
                tk.upper(), r["p05"] * 100, r["p25"] * 100, r["p50"] * 100,
                r["p75"] * 100, r["p95"] * 100, p["loses_money"] * 100))
        except Exception as e:
            print("{:<10} FAILED: {}: {}".format(tk.upper(), type(e).__name__, e), file=sys.stderr)

    print("\nWritten to data/predictions/<TICKER>/{}.json".format(args.out_date))

    if completed and not args.no_report:
        from predict_report import write_report

        try:
            path = write_report(completed, name=args.report_name, out_date=args.out_date)
            print("Report: {} ({:.0f} KB)".format(path, path.stat().st_size / 1024))
        except Exception as e:
            print("Report failed: {}: {}".format(type(e).__name__, e), file=sys.stderr)

    print("These are simulated ranges over stated assumptions, not forecasts, and they")
    print("have never been validated out of sample. Read the fit statistics above first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
