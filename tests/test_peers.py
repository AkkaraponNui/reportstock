"""Tests for peer comparison.

The point of this module is to catch a specific failure of judgement: reading an
absolute band as if it knew what is normal for an industry. These tests use
synthetic companies so the expected percentiles are known exactly, rather than
depending on whatever happens to be on disk.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from peers import (  # noqa: E402
    MIN_PEERS,
    PEER_METRICS,
    _median,
    _percentile_rank,
    absolute_vs_relative,
    peer_context,
    sector_table,
)


def company(ticker, sector, **metrics):
    return {
        "ticker": ticker,
        "company": ticker + " Inc",
        "sector": sector,
        "industry": sector + " widgets",
        "metrics": metrics,
        "snapshot": "2026-09-18",
    }


@pytest.fixture
def software_sector():
    """Five software companies whose gross margins are all high by any absolute
    standard, so the absolute band cannot separate them but peers can."""
    return [
        company("AAA", "Technology", gross_margin_latest=0.85, forward_pe=30.0,
                revenue_cagr=0.30, roic_est=0.25),
        company("BBB", "Technology", gross_margin_latest=0.78, forward_pe=25.0,
                revenue_cagr=0.20, roic_est=0.18),
        company("CCC", "Technology", gross_margin_latest=0.74, forward_pe=22.0,
                revenue_cagr=0.15, roic_est=0.14),
        company("DDD", "Technology", gross_margin_latest=0.70, forward_pe=18.0,
                revenue_cagr=0.10, roic_est=0.10),
        company("EEE", "Technology", gross_margin_latest=0.66, forward_pe=15.0,
                revenue_cagr=0.05, roic_est=0.06),
    ]


class TestHelpers:
    def test_median_of_odd_and_even(self):
        assert _median([3, 1, 2]) == 2
        assert _median([4, 1, 2, 3]) == pytest.approx(2.5)

    def test_median_ignores_missing(self):
        assert _median([1, None, 3]) == 2

    def test_median_of_nothing_is_none(self):
        assert _median([]) is None
        assert _median([None, None]) is None

    def test_percentile_rank_top_and_bottom(self):
        pop = [1, 2, 3, 4, 5]
        assert _percentile_rank(5, pop, True) == pytest.approx(1.0)
        assert _percentile_rank(1, pop, True) == pytest.approx(0.0)

    def test_percentile_inverts_when_lower_is_better(self):
        pop = [10.0, 20.0, 30.0, 40.0]
        cheap = _percentile_rank(10.0, pop, higher_is_better=False)
        dear = _percentile_rank(40.0, pop, higher_is_better=False)
        assert cheap is not None and dear is not None
        assert cheap > dear, "a cheaper multiple must rank better"

    def test_percentile_needs_a_population(self):
        assert _percentile_rank(1.0, [], True) is None
        assert _percentile_rank(None, [1, 2, 3], True) is None


class TestSectorTable:
    def test_reports_group_size_and_reliability(self, software_sector):
        table = sector_table(software_sector)
        assert table["Technology"]["n"] == 5
        assert table["Technology"]["reliable"] is True

    def test_small_group_is_flagged_unreliable(self):
        rows = [company("XXX", "Energy", roic_est=0.1),
                company("YYY", "Energy", roic_est=0.2)]
        table = sector_table(rows)
        assert table["Energy"]["reliable"] is False
        assert table["Energy"]["n"] < MIN_PEERS

    def test_medians_are_computed_per_sector(self, software_sector):
        table = sector_table(software_sector)
        med = table["Technology"]["medians"]["gross_margin_latest"]["median"]
        assert med == pytest.approx(0.74)


class TestPeerContext:
    def test_finds_the_company_and_its_group(self, software_sector):
        ctx = peer_context("CCC", rows=software_sector)
        assert ctx["ok"]
        assert ctx["group"] == "Technology"
        assert ctx["n_in_group"] == 5
        assert set(ctx["peers"]) == {"AAA", "BBB", "DDD", "EEE"}

    def test_unknown_ticker_reports_rather_than_raises(self, software_sector):
        ctx = peer_context("ZZZZ", rows=software_sector)
        assert ctx["ok"] is False
        assert "ZZZZ" in ctx["reason"]

    def test_best_in_group_is_top_percentile(self, software_sector):
        ctx = peer_context("AAA", rows=software_sector)
        gm = next(c for c in ctx["comparisons"] if c["key"] == "gross_margin_latest")
        assert gm["percentile"] == pytest.approx(1.0)

    def test_cheapest_multiple_ranks_best(self, software_sector):
        ctx = peer_context("EEE", rows=software_sector)
        pe = next(c for c in ctx["comparisons"] if c["key"] == "forward_pe")
        assert pe["percentile"] == pytest.approx(1.0), "lowest P/E should rank first"

    def test_strongest_and_weakest_are_populated(self, software_sector):
        ctx = peer_context("AAA", rows=software_sector)
        assert ctx["strongest"]
        assert ctx["weakest"]
        assert ctx["strongest"][0]["percentile"] >= ctx["weakest"][0]["percentile"]

    def test_small_group_is_marked_unreliable(self):
        rows = [company("XXX", "Energy", roic_est=0.10),
                company("YYY", "Energy", roic_est=0.20)]
        ctx = peer_context("XXX", rows=rows)
        assert ctx["ok"] is True
        assert ctx["reliable"] is False, "two companies cannot support a percentile"

    def test_every_metric_carries_both_labels(self, software_sector):
        ctx = peer_context("AAA", rows=software_sector)
        for c in ctx["comparisons"]:
            assert c["label"] and c["label_en"]
            assert c["key"] in PEER_METRICS


class TestAbsoluteVsRelative:
    def test_flags_a_metric_that_rides_its_industry(self, software_sector):
        # EEE's 66% gross margin scores well on the absolute band, because the
        # band was built for the whole market, yet it is last among software peers.
        ctx = absolute_vs_relative("EEE", rows=software_sector)
        assert ctx["ok"]
        keys = [d["key"] for d in ctx["disagreements"]]
        assert "gross_margin_latest" in keys, (
            "a high absolute score with a bottom peer rank is the case this exists for"
        )
        gm = next(d for d in ctx["disagreements"] if d["key"] == "gross_margin_latest")
        assert gm["gap"] > 0
        assert "อุตสาหกรรม" in gm["reading"]

    def test_no_disagreement_when_the_two_views_agree(self, software_sector):
        # AAA is both top of its group and high on the absolute band, so there is
        # nothing to report.
        ctx = absolute_vs_relative("AAA", rows=software_sector)
        gm = [d for d in ctx["disagreements"] if d["key"] == "gross_margin_latest"]
        assert not gm

    def test_disagreements_are_ranked_by_size(self, software_sector):
        ctx = absolute_vs_relative("EEE", rows=software_sector)
        gaps = [abs(d["gap"]) for d in ctx["disagreements"]]
        assert gaps == sorted(gaps, reverse=True)

    def test_unknown_ticker_propagates_the_failure(self, software_sector):
        ctx = absolute_vs_relative("NOPE", rows=software_sector)
        assert ctx["ok"] is False
