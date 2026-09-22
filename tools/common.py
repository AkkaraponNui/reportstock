"""Shared helpers for the reportstock data tools."""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
NEWS = DATA / "news"
FILINGS = DATA / "filings"
SCORES = DATA / "scores"
REPORTS = DATA / "reports"
CONFIG = ROOT / "config"

for _d in (RAW, NEWS, FILINGS, SCORES, REPORTS, CONFIG):
    _d.mkdir(parents=True, exist_ok=True)


LOGS = DATA / "logs"


def get_logger(name="reportstock"):
    """A logger that writes to data/logs/<date>.log as well as stderr.

    The reason this exists: roughly forty `except Exception` blocks across these
    tools swallow a failure and return None. That is the right behaviour for a
    scraper where any field can be missing, but with nothing recording it, a
    network blip and a company that genuinely does not report a metric are the
    same event downstream - an absent number. The log is what tells them apart
    after the fact, so a score built on a degraded fetch can be recognised as
    one rather than trusted.

    Console output stays at WARNING so the tools' own stdout tables are not
    drowned; the file keeps INFO and above.
    """
    import logging

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s  %(message)s")

    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOGS / "{}.log".format(today()), encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        # A read-only filesystem is normal on a free host. Console still works.
        pass

    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.propagate = False
    return logger


def _load_dotenv():
    """Read `.env` at the project root into the environment, if it is there.

    Every tool and the Streamlit app import this module, so this is the one
    place that runs before anything reads a credential. Two things matter:

    The path is anchored to ROOT rather than the working directory, because a
    tool is as likely to be run from the repo root as from `tools/`, and a
    loader that silently finds nothing is worse than no loader at all.

    A real environment variable always wins over the file (`override=False`).
    On a deployed host the platform injects its own secrets, and a stale `.env`
    that shadowed them would be a very quiet way to leak the wrong contact
    string to EDGAR or bill the wrong API key.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        # Optional at runtime: the shell can export these instead.
        return False
    return load_dotenv(ROOT / ".env", override=False)


_load_dotenv()

UA = os.environ.get(
    "REPORTSTOCK_UA",
    "reportstock/0.1 (research; contact: set REPORTSTOCK_UA env var)",
)


def ua_is_configured(ua: str | None = None) -> bool:
    """Whether REPORTSTOCK_UA carries a real contact, not the placeholder.

    EDGAR throttles anonymous traffic, and the failure shows up as filings that
    look like they were never made rather than as an error, so the tools check
    this and say so rather than quietly collecting nothing.

    Takes an argument so it can be tested against every placeholder form; the
    previous check looked only for "example.com" and therefore never fired on
    the default value, which does not contain it.
    """
    ua = UA if ua is None else ua
    if not ua or "@" not in ua:
        return False
    return "example.com" not in ua and "set REPORTSTOCK_UA" not in ua


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("_") or "unknown"


def clean(x):
    """Make a value JSON-safe: NaN/inf -> None, numpy -> python."""
    if x is None:
        return None
    if isinstance(x, (str, bool)):
        return x
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    try:
        if hasattr(x, "item") and not isinstance(x, (int, float)):
            x = x.item()
    except Exception:
        return str(x)
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            return None
        return round(x, 6)
    if isinstance(x, int):
        return x
    try:
        import datetime as _dt
        if isinstance(x, (_dt.date, _dt.datetime)):
            return x.isoformat()
    except Exception:
        pass
    return str(x)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(clean(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def read_json(path: Path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def latest_snapshot(directory: Path, pattern: str = "*.json"):
    """Newest JSON file in a directory, by filename (files are date-stamped)."""
    d = Path(directory)
    if not d.exists():
        return None
    files = sorted(d.glob(pattern))
    return files[-1] if files else None


def cagr(first: float | None, last: float | None, years: float) -> float | None:
    """Compound annual growth rate. None when undefined (needs positive endpoints)."""
    if first is None or last is None or years <= 0:
        return None
    try:
        first, last = float(first), float(last)
    except (TypeError, ValueError):
        return None
    if first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / years) - 1.0


def pct_change(first: float | None, last: float | None) -> float | None:
    if first in (None, 0) or last is None:
        return None
    try:
        return (float(last) - float(first)) / abs(float(first))
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def safe_div(a, b):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if b == 0:
        return None
    r = a / b
    return None if (math.isnan(r) or math.isinf(r)) else r


def slope_per_year(values: list[float | None]) -> float | None:
    """Least-squares slope of a series ordered oldest -> newest, per step."""
    pts = [(i, float(v)) for i, v in enumerate(values) if v is not None]
    if len(pts) < 2:
        return None
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    num = sum((p[0] - mx) * (p[1] - my) for p in pts)
    den = sum((p[0] - mx) ** 2 for p in pts)
    return safe_div(num, den)


def with_retry(fn, attempts=4, base_delay=1.5, label="request", quiet=False):
    """Call fn(), retrying on transient failures with exponential backoff.

    Rate limits and brief network faults are the normal failure mode when this
    runs against a free data source, and without a retry a single 429 drops a
    ticker silently, which is worse than being slow. Only transient errors are
    retried: a 404 means the symbol does not exist and trying again cannot help.

    Raises the last exception when every attempt fails, so the caller still sees
    a real failure rather than a None that looks like missing data.
    """
    import random
    import time

    transient_markers = ("429", "timeout", "timed out", "connection", "temporarily",
                         "too many requests", "502", "503", "504", "reset")
    last = None

    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - the caller decides what is fatal
            last = e
            text = "{} {}".format(type(e).__name__, e).lower()
            status = getattr(getattr(e, "response", None), "status_code", None)

            retryable = (
                status in (408, 425, 429, 500, 502, 503, 504)
                or any(m in text for m in transient_markers)
            )
            get_logger().warning(
                "%s attempt %d/%d failed: %s: %s",
                label, attempt + 1, attempts, type(e).__name__, str(e)[:200],
            )
            if not retryable or attempt == attempts - 1:
                raise

            # Honour Retry-After when the server sends one, else back off with
            # jitter so parallel callers do not retry in lockstep.
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            headers = getattr(getattr(e, "response", None), "headers", None) or {}
            retry_after = headers.get("retry-after") or headers.get("Retry-After")
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except (TypeError, ValueError):
                    pass
            delay = min(delay, 30.0)

            if not quiet:
                print(
                    "  retrying {} in {:.1f}s (attempt {}/{}): {}".format(
                        label, delay, attempt + 2, attempts, type(e).__name__
                    ),
                    file=sys.stderr,
                )
            time.sleep(delay)

    if last:
        raise last
    raise RuntimeError("with_retry exhausted without an exception")


def load_universe() -> dict:
    """Read config/universe.yaml; tolerate a missing file."""
    import yaml

    path = CONFIG / "universe.yaml"
    if not path.exists():
        return {"watchlist": [], "groups": {}}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve_funds(args_funds: list[str] | None) -> list[str]:
    """Fund symbols from CLI args, else every fund in the universe.

    An arg may name a group from `fund_groups` (e.g. "core"). Kept separate from
    resolve_tickers because a fund and a stock are not interchangeable here: the
    equity scorecard has nothing to say about an ETF.
    """
    uni = load_universe()
    groups = uni.get("fund_groups") or {}
    listed = [f["ticker"] if isinstance(f, dict) else f for f in (uni.get("funds") or [])]
    if not args_funds:
        return listed
    out: list[str] = []
    for a in args_funds:
        if a in groups:
            out.extend(groups[a])
        elif a.lower() in ("all", "funds"):
            out.extend(listed)
        else:
            out.append(a)
    seen, uniq = set(), []
    for t in out:
        t = t.strip().upper()
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def resolve_tickers(args_tickers: list[str] | None) -> list[str]:
    """Tickers from CLI args, else every ticker in the universe watchlist.

    A CLI arg may also name a group in universe.yaml (e.g. "ai_infra").
    """
    uni = load_universe()
    groups = uni.get("groups") or {}
    watch = [t["ticker"] if isinstance(t, dict) else t for t in (uni.get("watchlist") or [])]
    if not args_tickers:
        return watch
    out: list[str] = []
    for a in args_tickers:
        if a in groups:
            out.extend(groups[a])
        elif a.lower() in ("all", "watchlist"):
            out.extend(watch)
        else:
            out.append(a)
    seen, uniq = set(), []
    for t in out:
        t = t.strip().upper()
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq
