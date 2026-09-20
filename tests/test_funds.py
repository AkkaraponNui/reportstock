"""Tests for the fund modules.

Yahoo mixes three unit conventions inside one fund payload: the expense ratio is
a percentage number, the yield is already a fraction, the year-to-date return is
a percentage number while the multi-year averages are fractions, and the fund
operations table reports the expense ratio as a fraction again. Reading any of
them wrong is off by 100x and still looks like a number, so the normalizers get
the most attention below.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from fetch_funds import (  # noqa: E402
    _as_fraction,
    _as_fraction_from_percent,
    _herfindahl,
    concentration,
    expense_ratio,
)
from score_funds import (  # noqa: E402
    FUND_BANDS,
    FUND_PILLARS,
    band_score,
    flags,
    flatten,
    grade_for,
    score_pillars,
)


class FakeOps:
    """Stands in for the fund_operations frame, which is indexed by attribute name."""

    def __init__(self, rows):
        self._rows = rows

    @property
    def loc(self):
        return self

    def __getitem__(self, key):
        if key not in self._rows:
            raise KeyError(key)
        return FakeRow(self._rows[key])


class FakeRow:
    def __init__(self, value):
        self._value = value

    @property
    def iloc(self):
        return [self._value]


class FakeHoldings:
    def __init__(self, rows):
        self.rows = rows
        self.empty = not rows
        self.index = [r[0] for r in rows]

    def __contains__(self, key):
        return key in ("Name", "Holding Percent")

    def __getitem__(self, key):
        # Both columns come back as pandas Series in the real payload, so the
        # fake has to expose .tolist() on each of them.
        if key == "Name":
            return FakeSeries([r[1] for r in self.rows])
        if key == "Holding Percent":
            return FakeSeries([r[2] for r in self.rows])
        raise KeyError(key)


class FakeSeries:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


# --------------------------------------------------------------------------
# unit normalization
# --------------------------------------------------------------------------

class TestUnits:
    def test_percent_field_becomes_a_fraction(self):
        # Yahoo sends 0.18 for an 0.18% expense ratio.
        assert _as_fraction_from_percent(0.18) == pytest.approx(0.0018)
        assert _as_fraction_from_percent(0.75) == pytest.approx(0.0075)

    def test_fraction_field_passes_through(self):
        assert _as_fraction(0.0042) == pytest.approx(0.0042)
        assert _as_fraction(0.03) == pytest.approx(0.03)

    def test_absurd_fraction_is_rejected(self):
        assert _as_fraction(45.0, cap=2.0) is None

    def test_none_and_junk_survive(self):
        assert _as_fraction_from_percent(None) is None
        assert _as_fraction(None) is None
        assert _as_fraction_from_percent("not a number") is None


class TestExpenseRatio:
    def test_cross_checks_two_sources_that_agree(self):
        info = {"netExpenseRatio": 0.18}
        ops = FakeOps({"Annual Report Expense Ratio": 0.0018})
        value, basis = expense_ratio(info, ops)
        assert value == pytest.approx(0.0018)
        assert "agree" in basis

    def test_reports_disagreement_and_takes_the_lower(self):
        # The net ratio after waivers is what the holder actually pays.
        info = {"netExpenseRatio": 0.20}
        ops = FakeOps({"Annual Report Expense Ratio": 0.0035})
        value, basis = expense_ratio(info, ops)
        assert value == pytest.approx(0.0020)
        assert "differ" in basis

    def test_single_source_is_labelled(self):
        value, basis = expense_ratio({"netExpenseRatio": 0.09}, None)
        assert value == pytest.approx(0.0009)
        assert basis == "single source"

    def test_no_source_is_honest_about_it(self):
        value, basis = expense_ratio({}, None)
        assert value is None
        assert basis == "unavailable"

    def test_a_fraction_mistaken_for_a_percent_is_rejected(self):
        # 60 as a percentage number would be a 60% expense ratio, which is not a
        # fund, it is a data error.
        value, _ = expense_ratio({"netExpenseRatio": 60.0}, None)
        assert value is None


# --------------------------------------------------------------------------
# composition
# --------------------------------------------------------------------------

class TestConcentration:
    def test_sums_the_published_weights(self):
        h = FakeHoldings([("NVDA", "NVIDIA", 0.085), ("AAPL", "Apple", 0.074)])
        c = concentration(h)
        assert c["available"] is True
        assert c["top_10_weight"] == pytest.approx(0.159)
        assert c["largest_weight"] == pytest.approx(0.085)
        assert c["holdings"][0]["symbol"] == "NVDA"

    def test_missing_holdings_are_reported_not_faked(self):
        assert concentration(None)["available"] is False
        assert concentration(FakeHoldings([]))["available"] is False

    def test_herfindahl_detects_a_single_sector(self):
        assert _herfindahl([1.0]) == pytest.approx(1.0)

    def test_herfindahl_is_low_when_spread_evenly(self):
        assert _herfindahl([0.25, 0.25, 0.25, 0.25]) == pytest.approx(0.25)

    def test_herfindahl_of_nothing_is_none(self):
        assert _herfindahl([]) is None
        assert _herfindahl([0.0, 0.0]) is None


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------

def fund_payload(**over):
    p = {
        "ticker": "TEST",
        "is_fund": True,
        "quote_type": "ETF",
        "profile": {"name": "Test Fund", "category": "Large Blend"},
        "market": {"total_assets": 5.0e10},
        "costs": {"expense_ratio": 0.0003, "turnover": 0.05},
        "returns": {"distribution_yield": 0.015, "total_cagr_estimate": 0.11},
        "risk": {"volatility_annual": 0.16, "max_drawdown": -0.24,
                 "return_per_unit_of_risk": 0.44},
        "composition": {
            "concentration": {"available": True, "top_10_weight": 0.30,
                              "largest_weight": 0.07, "holdings": []},
            "sector_weights": {"technology": 0.3, "financial_services": 0.2,
                               "healthcare": 0.2, "industrials": 0.3},
            "sector_concentration_hhi": 0.26,
        },
    }
    for section, fields in over.items():
        if isinstance(fields, dict) and section in p:
            p[section] = {**p[section], **fields}
        else:
            p[section] = fields
    return p


class TestFundBands:
    def test_every_band_ascends_in_the_metric(self):
        for name, pts in FUND_BANDS.items():
            xs = [x for x, _ in pts]
            assert xs == sorted(xs), "{} is not ordered by metric value".format(name)

    def test_scores_stay_in_range(self):
        for name, pts in FUND_BANDS.items():
            for _x, y in pts:
                assert 0 <= y <= 100, "{} has a score outside 0-100".format(name)

    def test_cheaper_scores_higher(self):
        cheap = band_score("expense_ratio", 0.0003)
        dear = band_score("expense_ratio", 0.0075)
        assert cheap is not None and dear is not None
        assert cheap > dear

    def test_shallower_drawdown_scores_higher(self):
        mild = band_score("max_drawdown", -0.12)
        brutal = band_score("max_drawdown", -0.70)
        assert mild is not None and brutal is not None
        assert mild > brutal

    def test_more_concentrated_scores_lower(self):
        spread = band_score("top_10_weight", 0.10)
        packed = band_score("top_10_weight", 0.60)
        assert spread is not None and packed is not None
        assert spread > packed


class TestFundPillars:
    def test_weights_sum_to_one(self):
        assert sum(p["weight"] for p in FUND_PILLARS.values()) == pytest.approx(1.0)

    def test_metric_weights_sum_to_one_per_pillar(self):
        for name, p in FUND_PILLARS.items():
            assert sum(p["metrics"].values()) == pytest.approx(1.0), name

    def test_every_pillar_metric_has_a_band(self):
        for p in FUND_PILLARS.values():
            for m in p["metrics"]:
                assert m in FUND_BANDS, "{} has no band".format(m)

    def test_cost_outweighs_past_return(self):
        # A deliberate choice: the expense ratio predicts future relative
        # performance more reliably than past performance does.
        assert (FUND_PILLARS["cost"]["weight"]
                > FUND_PILLARS["risk_adjusted_return"]["weight"])

    def test_a_cheap_broad_fund_beats_an_expensive_narrow_one(self):
        cheap = fund_payload()
        pricey = fund_payload(
            costs={"expense_ratio": 0.0075, "turnover": 1.5},
            composition={"concentration": {"available": True, "top_10_weight": 0.62,
                                           "largest_weight": 0.18, "holdings": []},
                         "sector_weights": {"technology": 0.9, "industrials": 0.1},
                         "sector_concentration_hhi": 0.82},
        )
        a, _, _ = score_pillars(flatten(cheap))
        b, _, _ = score_pillars(flatten(pricey))
        assert a is not None and b is not None and a > b

    def test_missing_pillars_renormalize(self):
        # A bond fund publishes no equity holdings, so diversification has no
        # inputs. That pillar should drop out rather than score zero.
        bond = fund_payload(composition={"concentration": {"available": False},
                                         "sector_weights": {},
                                         "sector_concentration_hhi": None})
        composite, detail, coverage = score_pillars(flatten(bond))
        assert detail["diversification"]["score"] is None
        assert composite is not None
        assert coverage == pytest.approx(1.0 - FUND_PILLARS["diversification"]["weight"])

    def test_grades_are_ordered(self):
        assert grade_for(90).startswith("A")
        assert grade_for(20).startswith("E")
        assert grade_for(None).startswith("n/a")


class TestFlags:
    def test_expensive_fund_is_called_out_in_money(self):
        p = fund_payload(costs={"expense_ratio": 0.0075, "turnover": 0.2})
        out = flags(p, flatten(p), 50)
        assert any("100,000" in f or "per 100,000" in f.lower() or "750" in f for f in out)

    def test_concentration_is_called_out(self):
        p = fund_payload(composition={
            "concentration": {"available": True, "top_10_weight": 0.62,
                              "largest_weight": 0.2, "holdings": []},
            "sector_weights": {"technology": 0.85, "industrials": 0.15},
            "sector_concentration_hhi": 0.75,
        })
        out = flags(p, flatten(p), 50)
        assert any("concentrated" in f.lower() for f in out)

    def test_deep_drawdown_is_called_out(self):
        p = fund_payload(risk={"volatility_annual": 0.43, "max_drawdown": -0.74,
                               "return_per_unit_of_risk": 0.05})
        out = flags(p, flatten(p), 40)
        assert any("peak" in f.lower() for f in out)

    def test_tiny_fund_is_called_out(self):
        p = fund_payload(market={"total_assets": 2.0e8})
        out = flags(p, flatten(p), 60)
        assert any("small" in f.lower() for f in out)

    def test_a_stock_passed_as_a_fund_is_rejected_loudly(self):
        p = fund_payload(is_fund=False, quote_type="EQUITY")
        out = flags(p, flatten(p), 70)
        assert any("rather than a fund" in f for f in out)

    def test_a_clean_fund_still_gets_the_overlap_prompt(self):
        p = fund_payload()
        out = flags(p, flatten(p), 85)
        assert any("duplicates" in f for f in out)


class TestFlatten:
    def test_pulls_every_scored_metric(self):
        m = flatten(fund_payload())
        for metric in FUND_BANDS:
            assert metric in m, "{} is scored but never flattened".format(metric)

    def test_tolerates_an_empty_payload(self):
        m = flatten({})
        assert all(v is None for v in m.values())
