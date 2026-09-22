"""Tests for the scoring model.

These cover the arithmetic that decides what the system recommends. Four real
bugs were found here during development, and none of them crashed anything: a
currency mismatch that inflated an ADR's return, a margin ceiling that silently
capped high-margin businesses, a bull case that landed below its own base case,
and a regression dominated by two outliers. Every one of them produced a
plausible-looking wrong number, which is the only kind of bug that matters in a
tool like this. Each has a test below.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import score  # noqa: E402
from score import (  # noqa: E402
    BANDS,
    PILLARS,
    _sales_multiple,
    band_score,
    blended_growth,
    dividend_component,
    grade_for,
    project,
    score_pillars,
)


def base_metrics(**over):
    """A healthy, unremarkable company. Tests override one field at a time."""
    m = {
        "revenue_cagr": 0.12,
        "revenue_growth_ttm": 0.14,
        "net_income_cagr": 0.15,
        "forward_eps_growth": 0.13,
        "gross_margin_latest": 0.55,
        "operating_margin_latest": 0.25,
        "operating_margin_trend": 0.005,
        "net_margin_latest": 0.18,
        "fcf_margin_latest": 0.20,
        "fcf_cagr": 0.14,
        "fcf_yield": 0.035,
        "roic_est": 0.20,
        "roe": 0.25,
        "net_debt_to_ebitda": 0.8,
        "debt_to_equity": 45.0,
        "current_ratio": 1.9,
        "forward_pe": 20.0,
        "trailing_pe": 24.0,
        "peg_est": 1.4,
        "ev_to_ebitda": 15.0,
        "price_to_sales": 4.3,
        "market_cap": 1.0e11,
        "dividend_yield": None,
        "payout_ratio": None,
        "currency_mismatch": False,
        "years_of_data": 5,
    }
    m.update(over)
    return m


# --------------------------------------------------------------------------
# band_score
# --------------------------------------------------------------------------

class TestBandScore:
    def test_interpolates_between_breakpoints(self):
        # revenue_cagr band: 0.10 -> 60, 0.20 -> 80. Halfway should be 70.
        assert band_score("revenue_cagr", 0.15) == pytest.approx(70.0)

    def test_clamps_below_and_above(self):
        assert band_score("revenue_cagr", -5.0) == 0.0
        assert band_score("revenue_cagr", 99.0) == 100.0

    def test_lower_is_better_bands_invert(self):
        cheap = band_score("forward_pe", 8.0)
        dear = band_score("forward_pe", 45.0)
        assert cheap is not None and dear is not None
        assert cheap > dear, "a lower P/E must score higher"

    def test_missing_value_returns_none(self):
        assert band_score("revenue_cagr", None) is None
        assert band_score("not_a_metric", 0.5) is None

    def test_every_band_is_ascending_in_x(self):
        # band_score clamps on the assumption that x rises monotonically. A band
        # entered out of order would silently score everything at an endpoint.
        for name, pts in BANDS.items():
            xs = [p[0] for p in pts]
            assert xs == sorted(xs), "band {} is not ordered by metric value".format(name)

    def test_every_band_score_is_in_range(self):
        for name, pts in BANDS.items():
            for _value, y in pts:
                assert 0 <= y <= 100, "band {} has a score outside 0-100".format(name)


# --------------------------------------------------------------------------
# pillars
# --------------------------------------------------------------------------

class TestPillars:
    def test_pillar_weights_sum_to_one(self):
        assert sum(p["weight"] for p in PILLARS.values()) == pytest.approx(1.0)

    def test_metric_weights_sum_to_one_per_pillar(self):
        for name, p in PILLARS.items():
            total = sum(p["metrics"].values())
            assert total == pytest.approx(1.0), "{} weights sum to {}".format(name, total)

    def test_every_pillar_metric_has_a_band(self):
        for p in PILLARS.values():
            for metric in p["metrics"]:
                assert metric in BANDS, "{} has no band".format(metric)

    def test_missing_metrics_renormalize_rather_than_zero(self):
        full, _, cov_full = score_pillars(base_metrics())
        # Drop one metric. The pillar should reweight, not treat it as a zero.
        partial, _, cov_part = score_pillars(base_metrics(roic_est=None))
        assert cov_full == pytest.approx(1.0)
        assert cov_part == pytest.approx(1.0), "pillar still has other metrics"
        assert partial is not None and full is not None
        assert abs(partial - full) < 20, "dropping one metric must not collapse the score"

    def test_no_data_gives_no_score(self):
        composite, _pillars, coverage = score_pillars({})
        assert composite is None
        assert coverage == 0

    def test_grades_are_ordered(self):
        assert grade_for(95).startswith("A")
        assert grade_for(30).startswith("E")
        assert grade_for(None).startswith("n/a")


# --------------------------------------------------------------------------
# sales multiple: the currency bug
# --------------------------------------------------------------------------

class TestSalesMultiple:
    def test_prefers_the_reported_multiple_when_currencies_agree(self):
        # This once preferred trailing_pe x net_margin everywhere, which pairs a
        # trailing price multiple with an annual margin. The reported figure is
        # the same vintage as the price, so it wins whenever it can be trusted.
        mult, basis = _sales_multiple(base_metrics(price_to_sales=4.3, trailing_pe=24.0))
        assert mult == pytest.approx(4.3)
        assert "reported price_to_sales" in basis

    def test_falls_back_to_reported_ps_when_pe_missing(self):
        mult, basis = _sales_multiple(
            base_metrics(trailing_pe=None, net_margin_latest=None, price_to_sales=6.0)
        )
        assert mult == pytest.approx(6.0)
        assert "price_to_sales" in basis

    def test_refuses_reported_ps_when_currencies_differ(self):
        # An ADR trades in one currency and reports in another, so Yahoo's P/S is
        # off by the exchange rate. With no P/E fallback there is no safe answer,
        # and guessing is worse than declining.
        mult, reason = _sales_multiple(
            base_metrics(trailing_pe=None, net_margin_latest=None,
                         price_to_sales=0.56, currency_mismatch=True)
        )
        assert mult is None
        assert "currenc" in reason.lower()

    def test_currency_mismatch_is_survivable_via_pe(self):
        # The same ADR with a usable trailing P/E is fine: price and EPS are both
        # quoted in the trading currency, so the units cancel.
        mult, basis = _sales_multiple(
            base_metrics(trailing_pe=10.45, net_margin_latest=0.331,
                         price_to_sales=0.56, currency_mismatch=True)
        )
        assert mult == pytest.approx(10.45 * 0.331)
        assert "trailing_pe" in basis


# --------------------------------------------------------------------------
# growth blend
# --------------------------------------------------------------------------

class TestBlendedGrowth:
    def test_caps_heroic_growth(self):
        g = blended_growth(base_metrics(revenue_cagr=3.0, revenue_growth_ttm=3.0,
                                        forward_eps_growth=3.0))
        assert g == pytest.approx(0.60)

    def test_eps_spike_cannot_dominate_a_revenue_projection(self):
        # A cyclical rebounding off a trough shows enormous EPS growth while
        # revenue barely moves. The EPS term must not drag the revenue estimate.
        modest = base_metrics(revenue_cagr=0.05, revenue_growth_ttm=0.06,
                              forward_eps_growth=2.00)
        g = blended_growth(modest)
        assert g < 0.15, "EPS spike leaked into the revenue growth estimate: {}".format(g)

    def test_returns_none_without_any_signal(self):
        assert blended_growth({"revenue_cagr": None, "revenue_growth_ttm": None,
                               "forward_eps_growth": None}) is None


# --------------------------------------------------------------------------
# dividends
# --------------------------------------------------------------------------

class TestDividends:
    def test_absent_dividend_is_zero_not_none(self):
        assert dividend_component(base_metrics(dividend_yield=None)) == 0.0
        assert dividend_component(base_metrics(dividend_yield=0.0)) == 0.0

    def test_normal_yield_passes_through(self):
        assert dividend_component(base_metrics(dividend_yield=0.033)) == pytest.approx(0.033)

    def test_absurd_yield_is_capped(self):
        # A yield above 15% is a distressed price or a bad field, not an input.
        assert dividend_component(base_metrics(dividend_yield=5.0)) == pytest.approx(0.15)

    def test_unfunded_payout_is_haircut(self):
        full = dividend_component(base_metrics(dividend_yield=0.04, payout_ratio=0.5))
        cut = dividend_component(base_metrics(dividend_yield=0.04, payout_ratio=1.07))
        assert full is not None and cut is not None
        assert cut < full, "a payout above earnings should not be taken at face value"

    def test_bear_case_haircuts_the_yield(self):
        base = dividend_component(base_metrics(dividend_yield=0.04), "base")
        bear = dividend_component(base_metrics(dividend_yield=0.04), "bear")
        assert bear < base

    def test_dividend_raises_total_return(self):
        payer = project(base_metrics(dividend_yield=0.04), scenario="base")
        none = project(base_metrics(dividend_yield=None), scenario="base")
        assert payer and none
        assert payer["annualized_return"] > none["annualized_return"]
        # And the price half must be identical: only the dividend changed.
        assert payer["price_return_annualized"] == pytest.approx(
            none["price_return_annualized"]
        )

    def test_total_return_is_the_product_not_the_sum(self):
        p = project(base_metrics(dividend_yield=0.04), scenario="base")
        assert p
        expected = (1 + p["price_return_annualized"]) * (1 + p["dividend_contribution"]) - 1
        assert p["annualized_return"] == pytest.approx(expected, abs=1e-4)


# --------------------------------------------------------------------------
# projection
# --------------------------------------------------------------------------

class TestProjection:
    def test_scenarios_are_ordered(self):
        m = base_metrics()
        bear = project(m, scenario="bear")
        base = project(m, scenario="base")
        bull = project(m, scenario="bull")
        assert bear and base and bull
        assert bear["annualized_return"] < base["annualized_return"] < bull["annualized_return"]

    def test_bull_margin_never_lands_below_base(self):
        # A fixed 0.50 ceiling once made the bull case assume a *lower* margin
        # than base for a company already above it.
        m = base_metrics(net_margin_latest=0.56)
        base = project(m, scenario="base")
        bull = project(m, scenario="bull")
        assert base and bull
        assert (bull["assumptions"]["end_net_margin"]
                >= base["assumptions"]["end_net_margin"])

    def test_high_margin_business_is_not_silently_capped(self):
        # The ceiling must sit above where the company already operates, or a
        # 56%-margin business is assumed to decline for no stated reason.
        # price_to_sales, trailing_pe and the margin are one arithmetic identity
        # (P/S divided by P/E is the margin), so a 56%-margin company has to be
        # given a consistent multiple or the fixture describes no real company.
        m = base_metrics(net_margin_latest=0.56, operating_margin_trend=0.0,
                         trailing_pe=24.0, price_to_sales=24.0 * 0.56)
        p = project(m, scenario="base")
        assert p
        assert p["assumptions"]["end_net_margin"] >= 0.50

    def test_returns_none_without_market_cap(self):
        assert project(base_metrics(market_cap=None)) is None

    def test_returns_none_without_a_growth_signal(self):
        m = base_metrics(revenue_cagr=None, revenue_growth_ttm=None, forward_eps_growth=None)
        assert project(m) is None

    def test_loss_maker_still_projects(self):
        p = project(base_metrics(net_margin_latest=-0.28, trailing_pe=None,
                                 price_to_sales=21.5), scenario="base")
        assert p is not None
        assert p["assumptions"]["end_net_margin"] > 0

    def test_paying_more_returns_less(self):
        # The entry multiple sets what you pay and the exit multiple sets what
        # you get. Anchoring them on different measures once made an expensive
        # stock score *better* than a cheap one, because raising forward P/E
        # lifted the terminal value while the entry price came from trailing P/E.
        returns = []
        for pe in (8.0, 12.0, 18.0, 25.0, 35.0, 50.0):
            p = project(base_metrics(trailing_pe=pe, forward_pe=pe,
                                     price_to_sales=pe * 0.18))
            assert p
            returns.append(p["annualized_return"])
        assert returns == sorted(returns, reverse=True), (
            "return must fall as the entry multiple rises, got {}".format(returns)
        )

    def test_exit_multiple_is_anchored_on_the_entry_basis(self):
        # Doubling the multiple must not double the exit assumption, or the two
        # cancel and valuation stops mattering at all.
        cheap = project(base_metrics(trailing_pe=10.0, forward_pe=10.0))
        dear = project(base_metrics(trailing_pe=20.0, forward_pe=20.0))
        assert cheap and dear
        ratio = dear["assumptions"]["exit_pe"] / cheap["assumptions"]["exit_pe"]
        assert 1.0 < ratio < 2.0, (
            "the exit multiple should move with the entry multiple but be pulled "
            "toward the justified one, got a ratio of {:.2f}".format(ratio)
        )

    def test_projection_is_currency_free(self):
        # Scaling market cap alone must not change the return: the model works in
        # ratios, so a company quoted in won and the same company quoted in
        # dollars must produce the same answer.
        small = project(base_metrics(market_cap=1.0e9))
        large = project(base_metrics(market_cap=1.0e15))
        assert small and large
        assert small["annualized_return"] == pytest.approx(large["annualized_return"])


class TestCurrencyContamination:
    """An ADR trades in one currency and reports in another.

    Any ratio dividing a market number by a statement number is then wrong by
    the exchange rate while still looking like an ordinary number. TSM scored
    99.9 on a price-to-sales of 0.51 and 100 on a 44% free cash flow yield;
    ASML scored 0 on an EV/EBITDA of 2657. The projection already guarded
    itself through `_sales_multiple`; the graded metrics did not.
    """

    def _adr(self, **over):
        m = {
            "currency_mismatch": True,
            "trading_currency": "USD",
            "financial_currency": "TWD",
            "price_to_sales": 0.51,
            "ev_to_ebitda": 4.93,
            "fcf_yield": 0.44,
            "forward_pe": 19.8,
            "peg_est": 0.26,
        }
        m.update(over)
        return m

    def test_the_contaminated_metrics_are_dropped(self):
        out, dropped = score.drop_currency_contaminated(self._adr())
        assert set(dropped) == {"price_to_sales", "ev_to_ebitda", "fcf_yield"}
        for k in dropped:
            assert out[k] is None

    def test_same_currency_metrics_survive(self):
        out, _ = score.drop_currency_contaminated(self._adr())
        assert out["forward_pe"] == 19.8
        assert out["peg_est"] == 0.26

    def test_a_domestic_company_is_untouched(self):
        m = self._adr(currency_mismatch=False)
        out, dropped = score.drop_currency_contaminated(m)
        assert dropped == []
        assert out["price_to_sales"] == 0.51

    def test_a_fake_cheap_adr_no_longer_outscores_its_real_valuation(self):
        cheap_looking = self._adr()
        honest = dict(cheap_looking, currency_mismatch=False)
        _, detail_guarded, _ = score.score_pillars(cheap_looking)
        _, detail_raw, _ = score.score_pillars(honest)
        assert (detail_guarded["valuation"]["score"]
                < detail_raw["valuation"]["score"])

    def test_the_pillar_renormalizes_rather_than_scoring_zero(self):
        _, detail, _ = score.score_pillars(self._adr())
        assert detail["valuation"]["score"] is not None
        assert detail["valuation"]["coverage"] < 1.0

    def test_the_exclusion_is_stated_in_the_flags(self):
        out = score.flags(self._adr(), 70, {})
        assert any("TWD" in f and "excluded" in f for f in out)


class TestMultipleAndMarginVintage:
    """The sales multiple and the margin must come from the same period.

    `trailing_pe x net_margin_latest` pairs a trailing-twelve-month price
    multiple with the last annual margin. For a company whose trailing year does
    not resemble its last annual report the product is not a sales multiple at
    all: Micron's TTM revenue grew 346%, and the route returned 5.24 against a
    reported price-to-sales of 12.71, which flowed straight into the projected
    return as a 2.4x understatement of the entry price.
    """

    MU = {
        "price_to_sales": 12.71, "trailing_pe": 22.94,
        "net_margin_latest": 0.228, "currency_mismatch": False,
    }
    ADR = {
        "price_to_sales": 0.51, "trailing_pe": 32.4,
        "net_margin_latest": 0.446, "currency_mismatch": True,
    }

    def test_a_clean_name_uses_the_reported_multiple(self):
        ps, margin, basis = score.sales_multiple_and_margin(self.MU)
        assert ps == 12.71
        assert "reported price_to_sales" in basis

    def test_the_margin_returned_matches_the_multiple(self):
        ps, margin, _ = score.sales_multiple_and_margin(self.MU)
        # price_to_sales / trailing_pe is the margin the market is implying now.
        assert margin == pytest.approx(12.71 / 22.94, rel=1e-6)
        # And it is nothing like the stale annual figure.
        assert margin > self.MU["net_margin_latest"] * 2

    def test_entry_multiple_is_self_consistent(self):
        ps, margin, _ = score.sales_multiple_and_margin(self.MU)
        assert ps / margin == pytest.approx(self.MU["trailing_pe"], rel=1e-6)

    def test_an_adr_falls_back_to_the_currency_safe_route(self):
        ps, margin, basis = score.sales_multiple_and_margin(self.ADR)
        # Never the corrupted reported figure.
        assert ps != 0.51
        assert ps == pytest.approx(32.4 * 0.446)
        assert margin == 0.446
        assert "currency-safe" in basis

    def test_an_absurd_implied_margin_is_refused(self):
        # A near-zero P/E would imply a margin above 95%, which is a data error
        # rather than a business.
        m = dict(self.MU, trailing_pe=1.0)
        _ps, margin, basis = score.sales_multiple_and_margin(m)
        assert margin is None
        assert basis == "reported price_to_sales"

    def test_no_usable_input_is_reported_honestly(self):
        ps, margin, basis = score.sales_multiple_and_margin({"currency_mismatch": False})
        assert ps is None and margin is None
        assert "unavailable" in basis

    def test_the_projection_uses_the_matched_margin(self):
        # The stale-margin route made MU look far cheaper than it is, so the
        # projected return has to come down when the vintages are aligned.
        base = base_metrics(price_to_sales=12.71, trailing_pe=22.94,
                            net_margin_latest=0.228, revenue_cagr=0.30,
                            revenue_growth_ttm=3.46, operating_margin_trend=0.0)
        out = score.project(base)
        assert out is not None
        # The multiple is the reported one, not 22.94 x 0.228 = 5.23.
        assert out["assumptions"]["current_sales_multiple"] == pytest.approx(12.71)
        assert out["assumptions"]["current_sales_multiple"] > 22.94 * 0.228 * 2
