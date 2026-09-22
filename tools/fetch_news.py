"""Collect news headlines and articles that can move a stock.

Usage:
    uv run python tools/fetch_news.py NVDA --days 30
    uv run python tools/fetch_news.py ai_infra --days 14
    uv run python tools/fetch_news.py --macro --days 7
    uv run python tools/fetch_news.py NVDA --topic "export controls"

Writes data/news/<TICKER>/<YYYY-MM-DD>.json (or data/news/_macro/... for --macro).
Sources: Google News RSS, plus Finnhub and Alpha Vantage when an API key is set.
Everything works with no API key at all; keys only add depth.

Environment variables (all optional):
    FINNHUB_API_KEY         company news with per-article summaries
    ALPHAVANTAGE_API_KEY    news with a sentiment score per article
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    NEWS,
    RAW,
    UA,
    latest_snapshot,
    read_json,
    resolve_tickers,
    today,
    utc_now,
    with_retry,
    write_json,
)

GOOGLE_NEWS = "https://news.google.com/rss/search"

# Query angles per ticker. Each becomes its own Google News search so that
# slow-moving structural stories are not buried under daily price chatter.
DEFAULT_ANGLES = [
    "{q} stock",
    "{q} earnings guidance",
    "{q} revenue forecast",
    "{q} analyst price target",
    "{q} lawsuit OR regulation OR antitrust",
    "{q} competition OR market share",
    "{q} acquisition OR partnership",
    "{q} capacity OR supply chain OR capex",
]

# Macro and thematic feeds that affect a whole portfolio, not one name.
MACRO_ANGLES = [
    "Federal Reserve interest rate decision",
    "US inflation CPI report",
    "semiconductor export controls China",
    "AI capital expenditure hyperscalers",
    "global recession risk outlook",
    "US dollar strength emerging markets",
    "oil price forecast OPEC",
    "tariffs trade policy technology",
]

# Lightweight event tagging. The analyst agent still reads the text; these tags
# just make filtering and counting cheap.
#
# The vocabulary was widened after measuring it: 47% of a 1,750-article pull
# came back with no tag at all, and the misses were not exotic. "Amazon sued by
# FTC" missed `regulatory` because the list held "lawsuit" but not "sued";
# "Meta cash flow craters as Zuckerberg doubles down on AI spending" missed
# `capacity` because it held "capex" but not "spending". Untagged is the one
# state that carries no information, so it is worth attacking directly.
EVENT_TAGS = {
    "earnings": ["earnings", "q1", "q2", "q3", "q4", "quarterly results", "beats",
                 "misses", "eps", "revenue rose", "revenue fell", "results",
                 "posts", "double-digit growth", "profit"],
    "guidance": ["guidance", "forecast", "outlook", "raises", "lowers", "cuts outlook",
                 "guides", "reaffirms", "full-year"],
    "analyst": ["price target", "upgrade", "downgrade", "initiated", "overweight",
                "underweight", "buy rating", "mean target", "analyst says",
                "street", "consensus"],
    "regulatory": ["antitrust", "regulator", "lawsuit", "investigation", "probe",
                   "suing", "trial", "ruling", "appeal", "complaint",
                   "fine", "sanction", "export control", "export curb", "tariff",
                   "ban", "sue", "sued", "sues", "suit", "injunction",
                   "class action", "accused", "accuses", "patent", "subpoena",
                   "settlement", "settles", "court", "judge", "doj", "ftc", "sec ",
                   "compliance", "license", "licence"],
    "product": ["launch", "unveils", "announces", "new chip", "release", "roadmap",
                "next-gen", "introduces", "debuts", "rolls out"],
    "mna": ["acquire", "acquisition", "merger", "buyout", "stake", "takeover",
            "divest", "acquires", "buys", "to buy", "to acquire", "joint venture"],
    "capacity": ["capex", "capacity", "fab", "factory", "plant", "supply chain",
                 "shortage", "expansion", "spending", "data center", "datacenter",
                 "build", "investment", "invests", "production"],
    "management": ["ceo", "cfo", "resign", "steps down", "appoints", "layoff",
                   "restructuring", "hires", "departs"],
    "demand": ["demand", "orders", "backlog", "bookings", "contract", "deal worth",
               "interest in", "adoption", "customers", "sales", "deal", "partnership",
               "supply", "wins", "says no"],
    "macro": ["fed", "inflation", "rate cut", "rate hike", "recession", "gdp",
              "tariff", "yield", "interest rates", "treasury", "dollar"],
    "capital_return": ["buyback", "share repurchase", "repurchase program",
                       "dividend", "special dividend", "split"],
    # Not an event. This is the filter that matters most, because it separates
    # "classified as not worth reading" from "we could not tell", and those two
    # were indistinguishable while both came back with an empty tag list.
    "speculation": ["price prediction", "could hit", "where the stock will go",
                    "is it too late", "should you buy", "best stocks",
                    "stocks to buy", "buying opportunity", "prediction:",
                    "what will", "here's why", "heres why", "is this a",
                    "millionaire", "if you invested", "better buy",
                    "stock forecast", "1 year", "by 2030", "wall street thinks",
                    "upside", "priced in", "fairly priced", "price really justified",
                    "how much", "worth buying", "still a buy", "too late to buy"],
    # Also not an event: a day's price move reported as news. Roughly a fifth of
    # every pull is this, and it says nothing about five-year earnings power.
    "price_move": ["stock sinks", "stock jumps", "stock drops", "stock falls",
                   "stock rises", "stock rallied", "stock soars", "stock slides",
                   "shares fall", "shares rise", "shares jump", "shares drop",
                   "outpaces", "market gains", "what you should know",
                   "why .* stock", "hits new high", "52-week"],
}

NEGATIVE_HINTS = ["falls", "drops", "plunge", "slump", "cuts", "misses", "downgrade", "lawsuit", "probe", "ban", "warns", "layoff", "delay", "recall", "loss"]
POSITIVE_HINTS = ["rises", "surge", "jumps", "beats", "raises", "upgrade", "record", "wins", "approval", "expands", "partnership", "soars", "growth"]


def _get(url, params=None, timeout=25, headers=None):
    """GET with retries, so one throttled query does not drop a whole angle."""
    import requests

    h = {"User-Agent": UA}
    if headers:
        h.update(headers)

    def once():
        r = requests.get(url, params=params, timeout=timeout, headers=h)
        r.raise_for_status()
        return r

    return with_retry(once, attempts=3, base_delay=1.0, label="news")


def _norm_title(t):
    t = re.sub(r"\s+", " ", (t or "").lower()).strip()
    t = re.sub(r"\s*-\s*[a-z0-9 .]+$", "", t)  # strip the trailing " - Publisher"
    return re.sub(r"[^a-z0-9 ]+", "", t)


def tag_article(title, summary=""):
    blob = "{} {}".format(title or "", summary or "").lower()
    tags = [name for name, words in EVENT_TAGS.items() if any(w in blob for w in words)]
    neg = sum(1 for w in NEGATIVE_HINTS if w in blob)
    pos = sum(1 for w in POSITIVE_HINTS if w in blob)
    lean = "neutral"
    if pos > neg:
        lean = "positive"
    elif neg > pos:
        lean = "negative"
    return tags, lean


def _parse_date(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def google_news(query, days, limit=25, lang="en-US", country="US"):
    import feedparser

    when = "when:{}d".format(max(1, int(days)))
    params = {
        "q": "{} {}".format(query, when),
        "hl": lang,
        "gl": country,
        "ceid": "{}:{}".format(country, lang.split("-")[0]),
    }
    url = "{}?{}".format(GOOGLE_NEWS, urllib.parse.urlencode(params))
    try:
        raw = _get(url).content
    except Exception as e:
        print("  ! google news failed for {!r}: {}".format(query, e), file=sys.stderr)
        return []

    feed = feedparser.parse(raw)
    out = []
    for e in feed.entries[:limit]:
        title = e.get("title")
        dt = _parse_date(e)
        summary = re.sub(r"<[^>]+>", " ", e.get("summary", "") or "")[:400]
        tags, lean = tag_article(title, summary)
        out.append(
            {
                "title": title,
                "url": e.get("link"),
                "published": dt.isoformat() if dt else None,
                "publisher": (e.get("source", {}) or {}).get("title")
                if isinstance(e.get("source"), dict)
                else e.get("source"),
                "summary": summary.strip() or None,
                "query": query,
                "source_api": "google_news_rss",
                "tags": tags,
                "lean": lean,
            }
        )
    return out


def finnhub_news(ticker, days):
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        return []
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    try:
        r = _get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": ticker,
                "from": start.isoformat(),
                "to": end.isoformat(),
                "token": key,
            },
        )
        items = r.json()
    except Exception as e:
        print("  ! finnhub failed: {}".format(e), file=sys.stderr)
        return []

    out = []
    for it in items[:80]:
        title = it.get("headline")
        summary = (it.get("summary") or "")[:400]
        tags, lean = tag_article(title, summary)
        ts = it.get("datetime")
        out.append(
            {
                "title": title,
                "url": it.get("url"),
                "published": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
                "publisher": it.get("source"),
                "summary": summary or None,
                "query": "finnhub:{}".format(ticker),
                "source_api": "finnhub",
                "tags": tags,
                "lean": lean,
            }
        )
    return out


def alphavantage_news(ticker, days, limit=50):
    key = os.environ.get("ALPHAVANTAGE_API_KEY")
    if not key:
        return []
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%dT%H%M")
    try:
        r = _get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "time_from": start,
                "limit": limit,
                "apikey": key,
            },
        )
        data = r.json()
    except Exception as e:
        print("  ! alphavantage failed: {}".format(e), file=sys.stderr)
        return []

    out = []
    for it in (data.get("feed") or [])[:limit]:
        title = it.get("title")
        summary = (it.get("summary") or "")[:400]
        tags, lean = tag_article(title, summary)
        score = None
        for ts_item in it.get("ticker_sentiment", []) or []:
            if ts_item.get("ticker", "").upper() == ticker.upper():
                try:
                    score = float(ts_item.get("ticker_sentiment_score"))
                except (TypeError, ValueError):
                    score = None
        raw_dt = it.get("time_published")
        published = None
        if raw_dt:
            try:
                published = datetime.strptime(raw_dt, "%Y%m%dT%H%M%S").replace(
                    tzinfo=timezone.utc
                ).isoformat()
            except ValueError:
                published = None
        out.append(
            {
                "title": title,
                "url": it.get("url"),
                "published": published,
                "publisher": it.get("source"),
                "summary": summary or None,
                "query": "alphavantage:{}".format(ticker),
                "source_api": "alphavantage",
                "tags": tags,
                "lean": lean,
                "sentiment_score": score,
            }
        )
    return out


def dedupe(articles):
    seen_url, seen_title, out = set(), set(), []
    for a in articles:
        u = (a.get("url") or "").split("?")[0]
        t = _norm_title(a.get("title"))
        if (u and u in seen_url) or (t and t in seen_title):
            continue
        if u:
            seen_url.add(u)
        if t:
            seen_title.add(t)
        out.append(a)
    out.sort(key=lambda x: x.get("published") or "", reverse=True)
    return out


def company_name(ticker):
    snap = latest_snapshot(RAW / ticker.upper())
    if not snap:
        return None
    data = read_json(snap) or {}
    name = (data.get("profile") or {}).get("name")
    if not name:
        return None
    # "NVIDIA Corporation" -> "NVIDIA" reads better as a news query.
    return re.sub(
        r"\b(inc|corp|corporation|company|co|ltd|limited|plc|holding|holdings|nv|sa|ag|group)\b\.?",
        "",
        name,
        flags=re.I,
    ).strip(" .,&")


def collect_for_ticker(ticker, days, angles, extra_topics, limit_per_query, pause):
    name = company_name(ticker)
    queries = []
    for angle in angles:
        queries.append(angle.format(q=ticker))
        if name and name.upper() != ticker.upper():
            queries.append(angle.format(q='"{}"'.format(name)))
    for topic in extra_topics or []:
        queries.append("{} {}".format(ticker, topic))
        if name:
            queries.append('"{}" {}'.format(name, topic))

    articles = []
    for q in queries:
        articles.extend(google_news(q, days, limit=limit_per_query))
        time.sleep(pause)

    articles.extend(finnhub_news(ticker, days))
    articles.extend(alphavantage_news(ticker, days))
    return name, dedupe(articles)


def summarize(articles):
    by_tag = {}
    for a in articles:
        for t in a.get("tags") or []:
            by_tag[t] = by_tag.get(t, 0) + 1
    leans = {"positive": 0, "negative": 0, "neutral": 0}
    for a in articles:
        leans[a.get("lean", "neutral")] = leans.get(a.get("lean", "neutral"), 0) + 1
    publishers = {}
    for a in articles:
        p = a.get("publisher") or "unknown"
        publishers[p] = publishers.get(p, 0) + 1
    return {
        "total": len(articles),
        "by_event_tag": dict(sorted(by_tag.items(), key=lambda kv: -kv[1])),
        "headline_lean": leans,
        "top_publishers": dict(sorted(publishers.items(), key=lambda kv: -kv[1])[:10]),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="*", help="tickers, a universe group, or blank for the watchlist")
    ap.add_argument("--days", type=int, default=30, help="lookback window (default 30)")
    ap.add_argument("--macro", action="store_true", help="collect macro and thematic news instead")
    ap.add_argument("--topic", action="append", default=[], help="extra query angle; repeatable")
    ap.add_argument("--limit-per-query", type=int, default=15)
    ap.add_argument("--pause", type=float, default=0.6, help="seconds between requests")
    ap.add_argument("--out-date", default=today())
    args = ap.parse_args()

    if args.macro:
        articles = []
        for q in MACRO_ANGLES + list(args.topic):
            articles.extend(google_news(q, args.days, limit=args.limit_per_query))
            time.sleep(args.pause)
        articles = dedupe(articles)
        payload = {
            "scope": "macro",
            "as_of": utc_now(),
            "lookback_days": args.days,
            "summary": summarize(articles),
            "articles": articles,
        }
        path = write_json(NEWS / "_macro" / "{}.json".format(args.out_date), payload)
        print("macro    {:>4} articles -> {}".format(len(articles), path.relative_to(NEWS.parent.parent)))
        return 0

    tickers = resolve_tickers(args.tickers)
    if not tickers:
        print("No tickers. Pass them as arguments or fill config/universe.yaml.", file=sys.stderr)
        return 2

    for tk in tickers:
        tk = tk.upper()
        name, articles = collect_for_ticker(
            tk, args.days, DEFAULT_ANGLES, args.topic, args.limit_per_query, args.pause
        )
        payload = {
            "ticker": tk,
            "company": name,
            "as_of": utc_now(),
            "lookback_days": args.days,
            "summary": summarize(articles),
            "articles": articles,
        }
        path = write_json(NEWS / tk / "{}.json".format(args.out_date), payload)
        s = payload["summary"]
        print(
            "{:<8} {:>4} articles  lean +{}/-{}  top={}  -> {}".format(
                tk,
                s["total"],
                s["headline_lean"]["positive"],
                s["headline_lean"]["negative"],
                ",".join(list(s["by_event_tag"])[:3]) or "-",
                path.relative_to(NEWS.parent.parent),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
