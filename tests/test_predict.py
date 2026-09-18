"""Tests for the prediction model.

The simulation is random, so these assert on properties that must hold for every
seed rather than on exact numbers: ordering, monotonicity, currency-independence,
and the guard rails. The one place an exact number is checked is the fitted fade,
which is deterministic given its input.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from predict import (  # noqa: E402
    MAX_GROWTH,
    _ols,
    annual_growth_series,
    growth_volatility,
    sensitivity,
    simulate,
)

FIT = {"fitted": True, "a": 0.057, "b": 0.532, "r2": 0.333,
       "resid_sd": 0.104, "n": 24, "se_b": 0.10}


def metrics(**over):
    m = {
        "revenue_cagr": 0.15,
        "revenue_growth_ttm": 0.18,
        "forward_eps_growth": 0.16,
        "net_margin_latest": 0.20,
        "operating_margin_trend": 0.004,
        "trailing_pe": 22.0,
        "forward_pe": 19.0,
        "price_to_sales": 4.4,
        "market_cap": 5.0e10,
        "dividend_yield": None,
        "payout_ratio": None,
        "currency_mismatch": False,
    }
    m.update(over)
    return m


class TestGrowthSeries:
    def test_computes_year_over_year(self):
        f = {"annual": {"revenue": [100.0, 110.0, 121.0]}}
        s = annual_growth_series(f)
        assert s == pytest.approx([0.10, 0.10])

    def test_gaps_become_none_not_zero(self):
        f = {"annual": {"revenue": [100.0, None, 121.0]}}
        s = annual_growth_series(f)
        assert s[0] is None and s[1] is None

    def test_empty_input_is_safe(self):
        assert annual_growth_series({}) == []
        assert annual_growth_series(None) == []

    def test_volatility_floor_applies_to_thin_history(self):
        # Two observations cannot support a standard deviation.
        assert growth_volatility([0.1, 0.2]) == 0.25

    def test_volatility_is_capped(self):
        wild = [-0.3, 2.0, -0.4, 3.0, 0.1]
        assert growth_volatility(wild) <= 0.60


class TestFadeFit:
    def test_ols_recovers_a_known_line(self):
        pairs = [(x / 100.0, 0.05 + 0.5 * (x / 100.0)) for x in range(0, 50, 5)]
        fit = _ols(pairs)
        assert fit
        assert fit["b"] == pytest.approx(0.5, abs=1e-6)
        assert fit["a"] == pytest.approx(0.05, abs=1e-6)
        assert fit["r2"] == pytest.approx(1.0, abs=1e-6)

    def test_too_few_points_returns_none(self):
        assert _ols([(0.1, 0.2), (0.2, 0.3)]) is None

    def test_outliers_move_the_slope(self):
        # The reason the real fit is run twice: two extreme points drag the line
        # and inflate R-squared in a small panel.
        core = [(0.05 + i * 0.01, 0.06 + i * 0.005) for i in range(20)]
        fit_core = _ols(core)
        fit_with = _ols(core + [(1.26, 1.14), (1.14, 0.65)])
        assert fit_core and fit_with
        assert abs(fit_with["b"] - fit_core["b"]) > 0.1, (
            "outliers should visibly move the slope, which is why both fits are kept"
        )


class TestSimulate:
    def test_produces_an_ordered_distribution(self):
        out = simulate(metrics(), FIT, runs=2000, seed=1)
        assert out["ok"]
        r = out["annualized_return"]
        assert r["p05"] <= r["p25"] <= r["p50"] <= r["p75"] <= r["p95"]

    def test_probabilities_are_fractions(self):
        out = simulate(metrics(), FIT, runs=2000, seed=1)
        for key, v in out["probabilities"].items():
            assert 0.0 <= v <= 1.0, "{} is not a fraction".format(key)

    def test_harder_thresholds_are_never_more_likely(self):
        p = simulate(metrics(), FIT, runs=4000, seed=3)["probabilities"]
        assert p["beats_4pct"] >= p["beats_8pct"] >= p["beats_15pct"]

    def test_refuses_without_a_growth_signal(self):
        out = simulate(metrics(revenue_cagr=None, revenue_growth_ttm=None,
                               forward_eps_growth=None), FIT, runs=100)
        assert out["ok"] is False

    def test_refuses_when_the_currency_makes_the_multiple_meaningless(self):
        out = simulate(
            metrics(trailing_pe=None, net_margin_latest=None, currency_mismatch=True),
            FIT, runs=100,
        )
        assert out["ok"] is False
        assert "currenc" in out["reason"].lower()

    def test_same_seed_is_reproducible(self):
        a = simulate(metrics(), FIT, runs=1500, seed=42)
        b = simulate(metrics(), FIT, runs=1500, seed=42)
        assert a["annualized_return"] == b["annualized_return"]

    def test_market_cap_scale_does_not_change_the_answer(self):
        small = simulate(metrics(market_cap=1.0e9), FIT, runs=1500, seed=7)
        huge = simulate(metrics(market_cap=1.0e15), FIT, runs=1500, seed=7)
        assert small["annualized_return"]["p50"] == pytest.approx(
            huge["annualized_return"]["p50"]
        )

    def test_growth_paths_stay_inside_the_guard_rails(self):
        out = simulate(metrics(revenue_cagr=1.4, revenue_growth_ttm=1.4),
                       FIT, runs=1500, seed=5)
        assert out["ok"]
        assert out["ending_state_median"]["growth_year5"] <= MAX_GROWTH

    def test_loss_maker_gets_a_wider_spread(self):
        payer = simulate(metrics(), FIT, runs=3000, seed=9)
        loss = simulate(metrics(net_margin_latest=-0.28, trailing_pe=None,
                                price_to_sales=21.0), FIT, runs=3000, seed=9)
        assert loss["ok"] and payer["ok"]
        span = lambda o: o["annualized_return"]["p95"] - o["annualized_return"]["p05"]  # noqa: E731
        assert span(loss) > span(payer), "an unprofitable company is more uncertain"
        assert loss["inputs"]["assumed_margin_for_loss_maker"] is True


class TestDividendsInSimulation:
    def test_dividend_lifts_the_median(self):
        none = simulate(metrics(dividend_yield=None), FIT, runs=4000, seed=11)
        payer = simulate(metrics(dividend_yield=0.04), FIT, runs=4000, seed=11)
        assert payer["annualized_return"]["p50"] > none["annualized_return"]["p50"]

    def test_reported_yield_is_echoed_in_the_assumptions(self):
        out = simulate(metrics(dividend_yield=0.033), FIT, runs=800, seed=2)
        assert out["inputs"]["dividend_yield"] == pytest.approx(0.033)

    def test_unfunded_payout_raises_the_cut_probability(self):
        safe = simulate(metrics(dividend_yield=0.04, payout_ratio=0.4), FIT, runs=800, seed=2)
        risky = simulate(metrics(dividend_yield=0.04, payout_ratio=1.2), FIT, runs=800, seed=2)
        assert (risky["inputs"]["dividend_cut_probability"]
                > safe["inputs"]["dividend_cut_probability"])

    def test_absurd_yield_is_capped(self):
        out = simulate(metrics(dividend_yield=5.0), FIT, runs=800, seed=2)
        assert out["inputs"]["dividend_yield"] <= 0.15


class TestSensitivity:
    def test_every_lever_moves_in_the_right_direction(self):
        s = sensitivity(metrics(dividend_yield=0.03), FIT, runs=1200)
        assert s["ok"]
        assert s["levers"], "no lever produced a result"
        for lever in s["levers"]:
            assert lever["high_median"] >= lever["low_median"], (
                "{} moves the wrong way: low {} high {}".format(
                    lever["key"], lever["low_median"], lever["high_median"])
            )

    def test_levers_carry_both_labels(self):
        s = sensitivity(metrics(), FIT, runs=800)
        for lever in s["levers"]:
            assert lever["lever"] and lever["lever_en"], "a report needs both languages"
            assert lever["key"]

    def test_ranked_by_swing(self):
        s = sensitivity(metrics(), FIT, runs=1200)
        swings = [x["swing"] for x in s["levers"]]
        assert swings == sorted(swings, reverse=True)

    def test_no_lever_is_inert(self):
        # A lever whose swing is exactly zero means a clamp is binding and the
        # analysis is measuring nothing, which happened once with the margin cap.
        s = sensitivity(metrics(), FIT, runs=1500)
        inert = [x["key"] for x in s["levers"] if x["swing"] == 0.0]
        assert not inert, "these levers do nothing: {}".format(inert)

    def test_dividend_lever_appears_only_for_payers(self):
        payer = sensitivity(metrics(dividend_yield=0.035), FIT, runs=800)
        none = sensitivity(metrics(dividend_yield=None), FIT, runs=800)
        assert any(x["key"] == "dividend" for x in payer["levers"])
        assert not any(x["key"] == "dividend" for x in none["levers"])
