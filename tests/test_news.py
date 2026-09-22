"""Tests for news tagging.

Tagging is keyword matching and mislabels routinely; it is a filter, never a
verdict. What it must not do is come back empty, because an untagged article is
the one state carrying no information at all — it cannot be read as "nothing
happened" or as "we could not tell". A measured pull of 1,750 articles had 47%
untagged, and the misses were mundane word forms: "Amazon sued by FTC" missed
`regulatory` because the vocabulary held "lawsuit" but not "sued".
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from fetch_news import EVENT_TAGS, tag_article  # noqa: E402


def tags(title):
    return tag_article(title, "")[0]


class TestRealEventsAreCaught:
    def test_every_form_of_suing_is_regulatory(self):
        for title in (
            "Amazon sued by FTC, 22 US states over ad sales practices",
            "29 US states are suing Meta",
            "Online streamers sue Twitch, Amazon over generative AI training",
            "Novo Nordisk seeks preliminary injunction days after suing Eli Lilly",
            "Nvidia Faces Class Action Over Meal Break And Expense Claims",
        ):
            assert "regulatory" in tags(title), title

    def test_spending_counts_as_capacity_not_just_capex(self):
        title = "Meta cash flow craters as Zuckerberg doubles down on AI spending"
        assert "capacity" in tags(title)

    def test_an_acquisition_phrased_as_to_buy_is_mna(self):
        title = "Lilly to buy Merida Biosciences for up to $2.88 billion"
        assert "mna" in tags(title)

    def test_a_supply_deal_is_demand(self):
        title = "Broadcom Stock Jumps on New $30 Billion Deal to Supply Chips to Apple"
        assert "demand" in tags(title)

    def test_a_buyback_is_capital_return(self):
        title = "ASML reports transactions under its current share buyback program"
        assert "capital_return" in tags(title)

    def test_export_curbs_are_regulatory(self):
        title = "Attack the chokepoints: how years of US export curbs reshaped China"
        assert "regulatory" in tags(title)


class TestNoiseIsNamedRatherThanLeftBlank:
    """The point of these two tags is to separate 'classified as not worth
    reading' from 'could not tell'. Both used to arrive as an empty list."""

    def test_price_predictions_are_speculation(self):
        for title in (
            "What Will Nvidia Stock's Price Be in 1 Year?",
            "Price Prediction: Broadcom Stock Will End The Year at This Price",
            "Amazon Stock Is Historically Cheap. Is This a Once-in-a-Decade Buying Opportunity?",
            "How Much Upside Can MU Stock Deliver?",
        ):
            assert "speculation" in tags(title), title

    def test_a_days_price_move_is_its_own_tag(self):
        for title in (
            "Eli Lilly (LLY) Stock Sinks As Market Gains: What You Should Know",
            "Micron Technology (MU) Stock Jumps",
            "Toyota Motor Corporation (TM) Stock Sinks As Market Gains",
        ):
            assert "price_move" in tags(title), title

    def test_noise_tags_do_not_swallow_a_real_event(self):
        # A headline can be both: a real event reported through a price move.
        t = tags("Broadcom Stock Jumps on New $30 Billion Deal to Supply Chips to Apple")
        assert "demand" in t


class TestVocabulary:
    def test_every_tag_has_keywords(self):
        for name, words in EVENT_TAGS.items():
            assert words, name

    def test_keywords_are_lowercase(self):
        # tag_article lowercases the text, so an uppercase keyword never matches.
        for name, words in EVENT_TAGS.items():
            for w in words:
                assert w == w.lower(), "{}: {}".format(name, w)

    def test_tagging_is_case_insensitive(self):
        assert tags("AMAZON SUED BY FTC") == tags("amazon sued by ftc")

    def test_empty_input_is_safe(self):
        assert tag_article(None, None)[0] == []
        assert tag_article("", "")[1] == "neutral"
