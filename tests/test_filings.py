"""Tests for SEC filing retrieval and risk-factor extraction.

Every case here is a bug that shipped. None of them raised: each one produced a
filing record that looked ordinary while carrying the wrong section, or no
section at all for a company that had filed one. That is the failure mode this
module is most exposed to, because nobody reads 80,000 characters to check that
the extractor picked the right 80,000 characters.

No network: each test drives the pure functions over hand-built fragments.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from fetch_filings import (  # noqa: E402
    _HEADING_10K,
    _HEADING_20F,
    _SECTION_END,
    _SECTION_END_20F,
    _XREF_BEFORE,
    _strip_html,
    risk_factors,
)


class TestStripHtml:
    def test_inline_tags_do_not_split_a_word(self):
        # Microsoft's 10-K writes RIS<span>K</span> FACTORS. Replacing the span
        # with a space produced "RIS K FACTORS" and the whole section was
        # reported as missing for every filer using inline XBRL.
        assert _strip_html("<p>ITEM 1A. RIS<span>K</span> FACTORS</p>").count("RISK FACTORS") == 1

    def test_inline_xbrl_wrappers_disappear_cleanly(self):
        html = "<div>EXECUTIV<ix:nonNumeric contextRef='c'>E</ix:nonNumeric> OFFICERS</div>"
        assert "EXECUTIVE OFFICERS" in _strip_html(html)

    def test_block_tags_still_break_lines(self):
        # A </p> ends a line; losing that would run two headings together.
        out = _strip_html("<p>Risk Factors</p><p>Our business</p>")
        assert "\n" in out
        assert "FactorsOur" not in out

    def test_scripts_styles_and_comments_are_dropped(self):
        html = "<style>.a{color:red}</style><!-- hidden --><script>x=1</script><p>Real text</p>"
        out = _strip_html(html)
        assert "Real text" in out
        assert "color" not in out and "hidden" not in out and "x=1" not in out

    def test_entities_and_hard_spaces_become_plain_text(self):
        assert "AT&T" in _strip_html("<p>AT&amp;T</p>")
        assert "\xa0" not in _strip_html("<p>a&nbsp;b</p>")


class TestCrossReferenceFilter:
    def test_a_real_lead_in_word_is_matched(self):
        for lead in ("see", "refer to", "described in", "Part I,", "under"):
            assert _XREF_BEFORE.search(lead), lead

    def test_a_word_merely_ending_in_in_is_not_a_lead_in(self):
        # Without \b the pattern matched the tail of any such word, so a heading
        # preceded by "operating margin" was thrown away as a citation.
        for text in ("our operating margin", "risks within", "the origin"):
            assert _XREF_BEFORE.search(text) is None, text


class TestHeadingPatterns:
    def test_the_10k_heading_matches_its_usual_spellings(self):
        for s in ("Item 1A. Risk Factors", "ITEM 1A RISK FACTORS", "Item 1A - Risk Factors"):
            assert _HEADING_10K.search(s), s

    def test_the_20f_heading_matches_the_sub_item_letter(self):
        for s in ("D. RISK FACTORS", "Item 3.D Risk Factors", "\nRisk Factors\n"):
            assert _HEADING_20F.search(s), s

    def test_the_20f_heading_does_not_match_the_d_of_and(self):
        # SAP's 20-F: "...Forward-Looking Statements and Risk Factors sections"
        # matched on the "d" of "and" and won on length, so the extractor
        # returned 153,132 characters of the wrong span.
        assert _HEADING_20F.search("Statements and Risk Factors sections") is None

    def test_the_two_forms_have_different_end_boundaries(self):
        assert _SECTION_END.search("Item 1B. Unresolved Staff Comments")
        assert _SECTION_END_20F.search("Item 4. Information on the Company")
        # A 20-F never ends at Item 1B, and a 10-K never ends at Item 4.
        assert _SECTION_END_20F.search("Item 1B. Unresolved Staff Comments") is None


class TestTickerResolution:
    def test_a_share_class_resolves_whichever_way_it_is_punctuated(self, monkeypatch):
        # EDGAR's own map writes BRK-B. The lookup rewrote "-" to "." before
        # searching, so Berkshire resolved to nothing and was reported as a
        # non-US listing with no SEC presence.
        import fetch_filings

        monkeypatch.setattr(fetch_filings, "_MAP_CACHE", {"BRK-B": "0001067983"})
        assert fetch_filings.ticker_to_cik("BRK-B") == "0001067983"
        assert fetch_filings.ticker_to_cik("BRK.B") == "0001067983"
        assert fetch_filings.ticker_to_cik("brk-b") == "0001067983"

    def test_a_ticker_with_no_sec_presence_resolves_to_none(self, monkeypatch):
        import fetch_filings

        monkeypatch.setattr(fetch_filings, "_MAP_CACHE", {"NVDA": "0001045810"})
        assert fetch_filings.ticker_to_cik("7203.T") is None


def _doc(body, form="10-K"):
    """Build a filing whose risk section is `body`, with a table of contents,
    a running page header, and a cross-reference: the three things that fooled
    earlier versions."""
    if form == "10-K":
        return (
            "<p>Table of Contents</p><p>Item 1A. Risk Factors</p><p>22</p>"
            "<p>Item 1B. Unresolved Staff Comments</p><p>24</p>"
            "<p>As discussed in Item 1A. Risk Factors, our results may vary.</p>"
            "<p>Table of Contents</p><p>Part I</p>"
            "<p>Item 1A. Risk Factors</p><p>" + body + "</p>"
            "<p>Item 1B. Unresolved Staff Comments</p><p>None.</p>"
        )
    return (
        "<p>ITEM 3. KEY INFORMATION</p><p>3</p><p>ITEM 4. INFORMATION ON THE COMPANY</p><p>14</p>"
        "<p>C. Offer and Use of Proceeds</p><p>Not applicable.</p>"
        "<p>D. RISK FACTORS</p><p>" + body + "</p>"
        "<p>ITEM 4. INFORMATION ON THE COMPANY</p><p>Our history.</p>"
    )


class TestRiskFactorSelection:
    """`risk_factors` fetches, so these drive it through a stubbed _get."""

    def _extract(self, monkeypatch, html, form="10-K"):
        import fetch_filings

        class FakeResp:
            content = html.encode("utf-8")

        monkeypatch.setattr(fetch_filings, "_get", lambda *a, **k: FakeResp())
        return fetch_filings.risk_factors("http://example.invalid/f.htm", form=form)

    def test_it_skips_the_contents_entry_and_the_cross_reference(self, monkeypatch):
        body = "We face many risks. " * 400          # comfortably over the minimum
        out = self._extract(monkeypatch, _doc(body))
        assert "error" not in out
        assert out["text"].startswith("We face many risks")

    def test_a_running_page_header_does_not_veto_the_real_heading(self, monkeypatch):
        # ServiceNow prints "Table of Contents / Part I" immediately above the
        # heading. Treating that "Part I" as a citation returned no section at
        # all for a filing carrying 82,701 characters of risk factors.
        body = "Investing in our securities involves risk. " * 250
        out = self._extract(monkeypatch, _doc(body))
        assert "error" not in out
        assert out["chars"] > 5000

    def test_a_20f_is_read_with_20f_boundaries(self, monkeypatch):
        body = "We wish to caution readers about the following. " * 250
        out = self._extract(monkeypatch, _doc(body, "20-F"), form="20-F")
        assert "error" not in out
        assert out["text"].startswith("We wish to caution readers")

    def test_a_10k_pattern_finds_nothing_in_a_20f(self, monkeypatch):
        # Reading a 20-F with Item 1A rules is how the foreign issuers silently
        # came back empty before the form was passed through.
        body = "We wish to caution readers about the following. " * 250
        out = self._extract(monkeypatch, _doc(body, "20-F"), form="10-K")
        assert "error" in out

    def test_a_pointer_to_another_document_is_reported_as_such(self, monkeypatch):
        # Novo Nordisk incorporates most of its risk factors by reference. That
        # is a different answer from "no section found" and the caller can act
        # on it, so it gets its own flag.
        body = "For information on risk factors, reference is made to page 41. " * 120
        out = self._extract(monkeypatch, _doc(body, "20-F"), form="20-F")
        assert out.get("incorporated_by_reference") is True

    def test_a_section_that_is_too_short_is_not_returned(self, monkeypatch):
        out = self._extract(monkeypatch, _doc("Too short to be real."))
        assert "error" in out
        assert "source_url" in out
