"""Resolve any listed company in the world to a ticker symbol.

Usage:
    uv run python tools/search_tickers.py "Toyota"
    uv run python tools/search_tickers.py "Nestle" --limit 10
    uv run python tools/search_tickers.py NVDA --exact

The watchlist in config/universe.yaml is a convenience, not a boundary. Every
tool in this repository accepts any symbol Yahoo Finance knows, which covers
roughly every major exchange: US, Tokyo, Hong Kong, Shanghai, Seoul, London,
Frankfurt, Paris, Amsterdam, Zurich, Toronto, Sydney, Mumbai, Sao Paulo and more.

Search results carry an exchange and a quote type. Pick deliberately: a company
usually has several listings, and they are not equivalent. The home listing has
the deepest liquidity and reports in its own currency. A US ADR trades in dollars
while reporting in the home currency, which is exactly the mismatch the scoring
model has to work around.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import clean  # noqa: E402

# Yahoo exchange codes grouped by the market a user would name.
REGION_HINTS = {
    "NMS": "US Nasdaq", "NYQ": "US NYSE", "PCX": "US NYSE Arca", "ASE": "US NYSE American",
    "PNK": "US OTC", "OQB": "US OTC", "OQX": "US OTC",
    "JPX": "Japan Tokyo", "TYO": "Japan Tokyo",
    "HKG": "Hong Kong", "SHH": "China Shanghai", "SHZ": "China Shenzhen",
    "KSC": "Korea KOSPI", "KOE": "Korea KOSDAQ",
    "LSE": "UK London", "GER": "Germany Xetra", "FRA": "Germany Frankfurt",
    "PAR": "France Paris", "AMS": "Netherlands Amsterdam", "EBS": "Switzerland SIX",
    "MIL": "Italy Milan", "MCE": "Spain Madrid", "STO": "Sweden Stockholm",
    "CPH": "Denmark Copenhagen", "OSL": "Norway Oslo", "HEL": "Finland Helsinki",
    "TOR": "Canada Toronto", "ASX": "Australia", "NSI": "India NSE", "BSE": "India BSE",
    "SAO": "Brazil", "MEX": "Mexico", "TAI": "Taiwan", "SES": "Singapore",
    "SET": "Thailand", "JKT": "Indonesia", "KLS": "Malaysia", "TLV": "Israel",
}


def search(query, limit=10, equities_only=True) -> list:
    """Search every exchange Yahoo Finance indexes. Returns a list of dicts."""
    import yfinance as yf

    try:
        res = yf.Search(query, max_results=max(limit, 10))
        quotes = res.quotes or []
    except Exception as e:
        print("Search failed: {}: {}".format(type(e).__name__, e), file=sys.stderr)
        return []

    out = []
    for q in quotes:
        qtype = (q.get("quoteType") or "").upper()
        if equities_only and qtype not in ("EQUITY", "ETF"):
            continue
        code = q.get("exchange") or ""
        out.append(
            {
                "symbol": q.get("symbol"),
                "name": q.get("shortname") or q.get("longname"),
                "exchange": q.get("exchDisp") or code,
                "exchange_code": code,
                "region": REGION_HINTS.get(code, q.get("exchDisp") or code),
                "quote_type": qtype,
                "industry": q.get("industry"),
                "sector": q.get("sector"),
            }
        )
        if len(out) >= limit:
            break
    return [dict(row) for row in clean(out)]


def resolve(query):
    """Best single match for a query. Returns a dict or None.

    An exact symbol match wins. Otherwise the first equity result wins, which is
    Yahoo's own relevance ranking and usually the primary listing.
    """
    hits = search(query, limit=10)
    if not hits:
        return None
    q = query.strip().upper()
    for h in hits:
        if (h.get("symbol") or "").upper() == q:
            return h
    equities = [h for h in hits if h.get("quote_type") == "EQUITY"]
    return equities[0] if equities else hits[0]


def verify(symbol):
    """Confirm a symbol actually returns data before anything downstream uses it."""
    import yfinance as yf

    try:
        info = yf.Ticker(symbol).info or {}
    except Exception as e:
        return {"symbol": symbol, "ok": False, "error": "{}: {}".format(type(e).__name__, e)}

    name = info.get("longName") or info.get("shortName")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not name and price is None:
        return {"symbol": symbol, "ok": False, "error": "No data returned for this symbol."}
    return {
        "symbol": symbol,
        "ok": True,
        "name": name,
        "price": price,
        "currency": info.get("currency"),
        "financial_currency": info.get("financialCurrency"),
        "currency_mismatch": bool(
            info.get("currency")
            and info.get("financialCurrency")
            and info.get("currency") != info.get("financialCurrency")
        ),
        "exchange": info.get("exchange"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap"),
        "country": info.get("country"),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", help="company name or ticker symbol")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--exact", action="store_true", help="resolve to one symbol and verify it")
    ap.add_argument("--all-types", action="store_true", help="include funds, indices and futures")
    args = ap.parse_args()

    if args.exact:
        hit = resolve(args.query)
        if not hit:
            print("No match for {!r}.".format(args.query), file=sys.stderr)
            return 1
        v = verify(hit["symbol"])
        if not v["ok"]:
            print("{} resolved but returned no data: {}".format(hit["symbol"], v["error"]), file=sys.stderr)
            return 1
        print("{}  {}".format(v["symbol"], v.get("name") or ""))
        print("  {} | {} | {}".format(v.get("exchange") or "?", v.get("sector") or "?", v.get("country") or "?"))
        print("  price {} {} | market cap {}".format(
            v.get("price"), v.get("currency") or "", v.get("market_cap")))
        if v.get("currency_mismatch"):
            print("  note: trades in {} but reports in {}. Market-cap ratios are "
                  "unit-inconsistent; the scoring model corrects for this.".format(
                      v.get("currency"), v.get("financial_currency")))
        return 0

    hits = search(args.query, limit=args.limit, equities_only=not args.all_types)
    if not hits:
        print("No match for {!r}.".format(args.query), file=sys.stderr)
        return 1

    print("{:<14} {:<34} {:<22} {}".format("SYMBOL", "NAME", "EXCHANGE", "TYPE"))
    print("-" * 82)
    for h in hits:
        print("{:<14} {:<34} {:<22} {}".format(
            h["symbol"] or "?",
            (h["name"] or "?")[:34],
            (h["region"] or "?")[:22],
            h["quote_type"] or "?",
        ))
    print("\nAny of these works with every tool here, for example:")
    print("  uv run python tools/fetch_fundamentals.py {}".format(hits[0]["symbol"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
