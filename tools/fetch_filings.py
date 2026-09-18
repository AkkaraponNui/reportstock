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
    FILINGS, UA, resolve_tickers, today, utc_now, with_retry, write_json,
)

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{doc}"

DEFAULT_FORMS = ["10-K", "10-Q", "8-K", "20-F", "6-K"]
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
    """Resolve a ticker to its zero-padded 10-digit CIK, or None if not on EDGAR."""
    if not _MAP_CACHE:
        data = _get(TICKER_MAP_URL).json()
        for row in data.values():
            _MAP_CACHE[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
    return _MAP_CACHE.get(ticker.upper().replace("-", "."))


def recent_filings(cik, forms, limit=25):
    data = _get(SUBMISSIONS_URL.format(cik=cik)).json()
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


def _strip_html(raw):
    import html as _html

    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</tr>", " \n ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = _html.unescape(raw)
    raw = raw.replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", raw).strip()


# Punctuation that sits between a lead-in word and the heading it points at, as
# in: Refer to "Item 1A. Risk Factors - Risks Related to ...". It has to come off
# before the cross-reference test or the lead-in word is never adjacent.
_LEAD_IN_NOISE = " \t\r\n\"'“”‘’(–—-"

# A heading preceded by one of these is a cross-reference in running text
# ("see Item 1A. Risk Factors"), not the start of the section itself.
_XREF_BEFORE = re.compile(
    r"(?i)(see|refer to|described in|set forth in|contained in|included in|"
    r"discussed in|part i,?|under|in)\s*$"
)
_SECTION_END = re.compile(
    r"(?i)item\s*1b\.?\s*[-–—:.\s]*unresolved"
    r"|item\s*1c\.?\s*[-–—:.\s]*cybersecurity"
    r"|item\s*2\.?\s*[-–—:.\s]*propert"
    r"|unresolved\s+staff\s+comments"
)

# A real Item 1A runs to tens of thousands of characters. Anything far outside
# this range is a table-of-contents entry or a mis-detected boundary.
_MIN_SECTION = 5000
_MAX_SECTION = 400000


def risk_factors(url, max_chars=120000) -> dict:
    """Extract Item 1A Risk Factors from an annual report, best-effort.

    A 10-K mentions "Item 1A. Risk Factors" several times: in the table of
    contents, in cross-references inside other sections, and once as the real
    heading. Only occurrences that are followed by a real Item 1B, 1C or Item 2
    boundary are considered, which rules out both the contents entry and any
    match whose section would otherwise run to the end of the document. Among
    those the longest section wins. When nothing qualifies this returns an error
    rather than a plausible-looking slice of the wrong section.
    """
    try:
        resp = _get(url, timeout=60)
        text = _strip_html(_decode(resp.content))
    except Exception as e:
        return {"error": "{}: {}".format(type(e).__name__, e)}

    heading = re.compile(r"(?i)item\s*1a\.?\s*[-–—:.\s]*risk\s*factors")
    candidates = []
    for m in heading.finditer(text):
        # Trailing quotes and dashes must come off before the cross-reference
        # test, since filings write: Refer to "Item 1A. Risk Factors - ...".
        preceding = text[max(0, m.start() - 40) : m.start()]
        preceding = preceding.rstrip(_LEAD_IN_NOISE)
        if _XREF_BEFORE.search(preceding):
            continue
        end_m = _SECTION_END.search(text, m.end())
        if not end_m:
            continue
        length = end_m.start() - m.end()
        if _MIN_SECTION <= length <= _MAX_SECTION:
            candidates.append((length, m.end(), end_m.start()))

    if not candidates:
        return {
            "error": "No Item 1A section with a clear end boundary was found. The "
            "filing may use an unusual layout or incorporate risk factors by "
            "reference; read it at the source URL instead.",
            "source_url": url,
        }

    length, start, end = max(candidates, key=lambda c: c[0])
    body = re.sub(r"\n{2,}", "\n", text[start:end][:max_chars]).strip()

    # Risk sub-headings in a 10-K are usually full sentences on their own line.
    headings = [
        h.strip()
        for h in re.findall(r"\n\s*([A-Z][^\n]{40,240}?[.?])\s*(?=\n)", body)
        if not h.strip().startswith(("Item", "Table of"))
    ]

    return {
        "source_url": url,
        "chars": len(body),
        "truncated": length > max_chars,
        "text": body,
        "candidate_risk_headings": headings[:40],
    }


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

    if "example.com" in UA:
        print(
            "Note: set REPORTSTOCK_UA to your name and email. EDGAR throttles anonymous traffic.",
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
            annual = next((f for f in payload["filings"] if f["form"] in ("10-K", "20-F")), None)
            if annual:
                time.sleep(args.pause)
                payload["risk_factors"] = risk_factors(annual["url"])
                payload["risk_factors"]["from_filing"] = {
                    "form": annual["form"],
                    "filed": annual["filed"],
                }
            else:
                payload["risk_factors"] = {"error": "No 10-K or 20-F in the fetched window."}

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
