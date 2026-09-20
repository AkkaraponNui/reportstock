"""Pull SEC filing metadata and risk-factor text for US-listed tickers.

Usage:
    uv run python tools/fetch_filings.py NVDA --forms 10-K 10-Q 8-K
    uv run python tools/fetch_filings.py ai_infra --risk-factors

Writes data/filings/<TICKER>/<YYYY-MM-DD>.json.

Source: SEC EDGAR, which is free and needs no key, but does require a real
User-Agent with contact details. Set REPORTSTOCK_UA before running, e.g.
    export REPORTSTOCK_UA="yourname you@example.com"
EDGAR asks for no more than 10 requests a second; this tool stays well under that.

Non-US listings (7203.T, 0700.HK, NESN.SW) have no EDGAR presence and are
skipped with a note rather than an error.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    FILINGS, UA, ua_is_configured, resolve_tickers, today, utc_now, with_retry, write_json,
)

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{doc}"

DEFAULT_FORMS = ["10-K", "10-Q", "8-K", "20-F", "6-K"]
# The annual reports that carry a risk-factor section. A 10-K puts it in
# Item 1A; a 20-F, filed by foreign private issuers, puts it in Item 3.D.
ANNUAL_FORMS = ("10-K", "20-F")
_MAP_CACHE = {}


def _get(url, timeout=30):
    """GET with retries. EDGAR throttles hard, and a dropped filing looks like a
    company that never filed, which is a worse error than being slow."""
    import requests

    def once():
        r = requests.get(
            url, timeout=timeout,
            headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"},
        )
        r.raise_for_status()
        return r

    return with_retry(once, label="edgar")


def ticker_to_cik(ticker):
    """Resolve a ticker to its zero-padded 10-digit CIK, or None if not on EDGAR.

    Share classes are punctuated differently by different sources: Yahoo writes
    BRK-B, some feeds write BRK.B, and EDGAR's own map uses BRK-B. Rewriting one
    into the other unconditionally is what made Berkshire look like a non-US
    listing with no SEC presence, so try the spelling as given first and then
    both substitutions.
    """
    if not _MAP_CACHE:
        data = _get(TICKER_MAP_URL).json()
        for row in data.values():
            _MAP_CACHE[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
    t = ticker.upper()
    for candidate in (t, t.replace(".", "-"), t.replace("-", ".")):
        cik = _MAP_CACHE.get(candidate)
        if cik:
            return cik
    return None


_SUBMISSIONS_CACHE = {}


def _submissions(cik):
    """The submissions index, fetched once per company per run."""
    if cik not in _SUBMISSIONS_CACHE:
        _SUBMISSIONS_CACHE[cik] = _get(SUBMISSIONS_URL.format(cik=cik)).json()
    return _SUBMISSIONS_CACHE[cik]


def recent_filings(cik, forms, limit=25):
    data = _submissions(cik)
    recent = (data.get("filings") or {}).get("recent") or {}
    keys = ["accessionNumber", "filingDate", "reportDate", "form", "primaryDocument", "primaryDocDescription"]
    rows = list(zip(*[recent.get(k, []) for k in keys]))
    out = []
    cik_int = int(cik)
    for acc, fdate, rdate, form, doc, desc in rows:
        if forms and form not in forms:
            continue
        acc_nodash = acc.replace("-", "")
        out.append(
            {
                "form": form,
                "filed": fdate,
                "period": rdate or None,
                "accession": acc,
                "description": desc or None,
                "url": ARCHIVE_URL.format(cik_int=cik_int, accession=acc_nodash, doc=doc),
            }
        )
        if len(out) >= limit:
            break
    return {
        "company": data.get("name"),
        "sic_description": data.get("sicDescription"),
        "fiscal_year_end": data.get("fiscalYearEnd"),
        "exchanges": data.get("exchanges"),
        "filings": out,
    }


def _decode(blob):
    """EDGAR documents are a mix of UTF-8 and Windows-1252. Try both in order."""
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return blob.decode(enc)
        except UnicodeDecodeError:
            continue
    return blob.decode("utf-8", errors="replace")


# Tags that end a line of text. Everything else is inline and must vanish
# without leaving a space behind, because a filing writes RIS<span>K</span>
# FACTORS and a browser renders "RISK FACTORS". Replacing that span with a
# space produces "RIS K FACTORS", which no heading pattern will ever match.
_BLOCK_TAGS = (
    "p|div|br|hr|tr|td|th|table|thead|tbody|tfoot|caption|col|colgroup|"
    "h1|h2|h3|h4|h5|h6|li|ul|ol|dl|dt|dd|"
    "section|article|header|footer|nav|aside|main|"
    "blockquote|pre|center|form|fieldset|figure|figcaption"
)
_BLOCK_RE = re.compile(r"(?is)</?(?:{})(?:\s[^>]*)?/?>".format(_BLOCK_TAGS))


def _strip_html(raw):
    """HTML to text, preserving word boundaries the way a browser would.

    The distinction that matters is block versus inline. A </p> ends a line, so
    it becomes a newline. A </span> does not, so it becomes nothing at all.

    Modern 10-Ks are Inline XBRL and wrap <ix:nonNumeric> tags around fragments
    of ordinary sentences, frequently mid-word. Treating those as whitespace
    splits words apart, which is invisible in the output and silently breaks
    every regex downstream: Microsoft's 2026 10-K came through as
    "ITEM 1A. RIS K FACTORS" and the section was reported as missing.
    """
    import html as _html

    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<!--.*?-->", " ", raw)
    raw = _BLOCK_RE.sub(" \n ", raw)
    # Every remaining tag is inline: drop it without inserting anything.
    raw = re.sub(r"(?s)<[^>]+>", "", raw)
    raw = _html.unescape(raw)
    raw = raw.replace("\xa0", " ").replace("\u200b", "")
    raw = re.sub(r"[ \t]+", " ", raw)
    return re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n", raw).strip()


# Punctuation that sits between a lead-in word and the heading it points at, as
# in: Refer to "Item 1A. Risk Factors - Risks Related to ...". It has to come off
# before the cross-reference test or the lead-in word is never adjacent.
_LEAD_IN_NOISE = " \t\r\n\"'“”‘’(–—-"

# A heading preceded by one of these is a cross-reference in running text
# ("see Item 1A. Risk Factors"), not the start of the section itself.
_XREF_BEFORE = re.compile(
    r"(?i)\b(see|refer to|described in|set forth in|contained in|included in|"
    r"discussed in|part i,?|under|in)\s*$"
)
_SECTION_END = re.compile(
    r"(?i)item\s*1b\.?\s*[-–—:.\s]*unresolved"
    r"|item\s*1c\.?\s*[-–—:.\s]*cybersecurity"
    r"|item\s*2\.?\s*[-–—:.\s]*propert"
    r"|unresolved\s+staff\s+comments"
)

# A 20-F is the annual report of a foreign private issuer, and it is laid out by
# a different rule book: risk factors sit in Item 3.D rather than Item 1A, and
# the section that follows is Item 4, Information on the Company. Several filers
# print the sub-item letter and several print only the words, so the letter is
# optional here and the false positives are caught by the same end-boundary and
# minimum-length tests the 10-K path uses.
_HEADING_20F = re.compile(
    # \b before the sub-item letter is load-bearing: without it the "d" of
    # "and Risk Factors" matches, and SAP's 20-F picked a cross-reference
    # 153,132 characters long over its real 111,690-character section.
    r"(?i)(?:item\s*3\s*[-–—:.]?\s*)?\bd\.?\s*[-–—:.\s]*risk\s*factors"
    r"|(?:^|\n)\s*risk\s*factors\s*(?=\n)"
)
_SECTION_END_20F = re.compile(
    r"(?i)item\s*4a?\s*[-–—:.\s]*information\s+on\s+the\s+company"
    r"|item\s*4a\s*[-–—:.\s]*unresolved\s+staff\s+comments"
)

_HEADING_10K = re.compile(r"(?i)item\s*1a\.?\s*[-–—:.\s]*risk\s*factors")

# Filers are allowed to incorporate risk factors from another document instead
# of printing them. Novo Nordisk's 20-F does exactly that, and the section is
# three lines long. Reporting that as "not found" would be wrong: the section
# was found, and it says the content lives somewhere else.
_INCORPORATED = re.compile(
    r"(?i)(reference\s+is\s+made\s+to|incorporated\s+(herein\s+)?by\s+reference"
    r"|for\s+information\s+on\s+risk\s+factors,\s*reference)"
)

# A real risk-factor section runs to tens of thousands of characters. Anything
# far outside this range is a table-of-contents entry or a bad boundary.
_MIN_SECTION = 5000
_MAX_SECTION = 400000


def risk_factors(url, max_chars=120000, form="10-K") -> dict:
    """Extract the risk-factor section from an annual report, best-effort.

    An annual report names its risk factors several times: in the table of
    contents, in cross-references inside other sections, in running page
    headers, and once as the real heading. Only occurrences followed by a real
    next-section boundary are considered, which rules out the contents entry and
    any match whose section would run to the end of the document. Among those
    the longest wins. When nothing qualifies this returns an error rather than a
    plausible-looking slice of the wrong section.

    `form` selects the layout: a 10-K keeps its risk factors in Item 1A and ends
    at Item 1B, 1C or 2; a 20-F keeps them in Item 3.D and ends at Item 4.
    """
    is_20f = str(form).upper().startswith("20-F")
    heading = _HEADING_20F if is_20f else _HEADING_10K
    ender = _SECTION_END_20F if is_20f else _SECTION_END

    try:
        resp = _get(url, timeout=60)
        text = _strip_html(_decode(resp.content))
    except Exception as e:
        return {"error": "{}: {}".format(type(e).__name__, e)}

    candidates = []
    short_matches = []
    for m in heading.finditer(text):
        # A cross-reference sits inside a sentence ("see Item 1A. Risk
        # Factors"); a real heading starts its own line. Filings also print
        # "Table of Contents / Part I" as a running page header immediately
        # above the heading, and treating that as a citation threw away the
        # genuine section: ServiceNow's 10-K reported no risk factors while
        # carrying an 82,705-character Item 1A. So the citation test only
        # applies to a heading that does not begin a line.
        window = text[max(0, m.start() - 40) : m.start()]
        at_line_start = window.rstrip(" \t\r") == "" or window.rstrip(" \t\r").endswith("\n")
        if not at_line_start:
            # Trailing quotes and dashes come off first, since filings write:
            # Refer to "Item 1A. Risk Factors - ...".
            if _XREF_BEFORE.search(window.rstrip(_LEAD_IN_NOISE)):
                continue
        end_m = ender.search(text, m.end())
        if not end_m:
            continue
        length = end_m.start() - m.end()
        if _MIN_SECTION <= length <= _MAX_SECTION:
            candidates.append((length, m.end(), end_m.start()))
        elif 0 < length < _MIN_SECTION:
            short_matches.append(text[m.end() : end_m.start()])

    if not candidates:
        # A section that exists but is only a pointer is a different answer from
        # a section that could not be located, and the caller can act on it.
        for frag in short_matches:
            if _INCORPORATED.search(frag):
                return {
                    "error": "The filer incorporates its risk factors by reference "
                    "rather than printing them in this filing. The pointer reads: "
                    + " ".join(frag.split())[:300],
                    "incorporated_by_reference": True,
                    "source_url": url,
                }
        return {
            "error": "No risk-factor section with a clear end boundary was found. "
            "The filing may use an unusual layout, such as an integrated annual "
            "report with its own structure; read it at the source URL instead.",
            "source_url": url,
        }

    length, start, end = max(candidates, key=lambda c: c[0])
    body = re.sub(r"\n{2,}", "\n", text[start:end][:max_chars]).strip()

    # Risk sub-headings are usually full sentences on their own line.
    headings = [
        h.strip()
        for h in re.findall(r"\n\s*([A-Z][^\n]{40,240}?[.?])\s*(?=\n)", body)
        if not h.strip().startswith(("Item", "Table of"))
    ]

    out = {
        "source_url": url,
        "chars": len(body),
        "truncated": length > max_chars,
        "text": body,
        "candidate_risk_headings": headings[:40],
    }
    # Some filers print a couple of risks in full and point elsewhere for the
    # rest, so a section can be real and incomplete at the same time. Novo
    # Nordisk prints only its cybersecurity and climate risks. Say so, because
    # the length alone reads as a short risk section rather than a partial one.
    if _INCORPORATED.search(body[:400]):
        out["incorporated_by_reference"] = True
        out["note"] = ("This section points to another document for part of its "
                       "content, so what is here is incomplete. See the opening "
                       "sentences for where the rest lives.")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--forms", nargs="*", default=DEFAULT_FORMS)
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--risk-factors", action="store_true", help="also extract Item 1A from the newest 10-K or 20-F")
    ap.add_argument("--pause", type=float, default=0.4)
    ap.add_argument("--out-date", default=today())
    args = ap.parse_args()

    tickers = resolve_tickers(args.tickers)
    if not tickers:
        print("No tickers. Pass them as arguments or fill config/universe.yaml.", file=sys.stderr)
        return 2

    if not ua_is_configured():
        print(
            "Note: REPORTSTOCK_UA is not set to a real contact, so EDGAR sees"
            " anonymous traffic and throttles it. Put a line in .env at the"
            " repo root:\n"
            '  REPORTSTOCK_UA="Your Name you@example.com"',
            file=sys.stderr,
        )

    for tk in tickers:
        tk = tk.upper()
        try:
            cik = ticker_to_cik(tk)
        except Exception as e:
            print("{:<10} EDGAR lookup failed: {}".format(tk, e), file=sys.stderr)
            continue
        if not cik:
            print("{:<10} not on EDGAR (non-US listing), skipped".format(tk))
            continue

        try:
            payload = recent_filings(cik, args.forms, args.limit)
        except Exception as e:
            print("{:<10} submissions fetch failed: {}".format(tk, e), file=sys.stderr)
            continue

        payload.update({"ticker": tk, "cik": cik, "as_of": utc_now(), "source": "sec_edgar"})

        if args.risk_factors:
            # Not `next(... in payload["filings"])`: that list is the newest N
            # filings of every requested form mixed together, and a foreign
            # issuer files 6-K constantly, so its one annual 20-F falls off the
            # end. TSM and NVO both reported "no annual report" while having
            # filed one. Ask for the annual forms specifically instead.
            annual = next(
                (f for f in payload["filings"] if f["form"] in ANNUAL_FORMS), None
            )
            if annual is None:
                try:
                    annual = next(
                        iter(recent_filings(cik, ANNUAL_FORMS, 3)["filings"]), None
                    )
                except Exception as e:
                    print("{:<10} annual lookup failed: {}".format(tk, e), file=sys.stderr)
            if annual:
                time.sleep(args.pause)
                payload["risk_factors"] = risk_factors(annual["url"], form=annual["form"])
                payload["risk_factors"]["from_filing"] = {
                    "form": annual["form"],
                    "filed": annual["filed"],
                }
            else:
                payload["risk_factors"] = {
                    "error": "This company has filed no 10-K or 20-F. Non-US "
                    "listings without an SEC registration have no risk-factor "
                    "section here; use the home-market annual report instead."
                }

        path = write_json(FILINGS / tk / "{}.json".format(args.out_date), payload)
        rf = payload.get("risk_factors") or {}
        note = ""
        if args.risk_factors:
            note = "  riskFactors={}".format(
                "{} chars".format(rf["chars"]) if "chars" in rf else "none"
            )
        print(
            "{:<10} {:<28} {:>3} filings{}  -> {}".format(
                tk,
                str(payload.get("company") or "?")[:28],
                len(payload["filings"]),
                note,
                path.relative_to(FILINGS.parent.parent),
            )
        )
        time.sleep(args.pause)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
