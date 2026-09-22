"""Smoke tests for the Streamlit pages.

These do not check layout or wording. They check the one thing that was never
checked at all: that each page renders against the snapshots actually on disk
without raising. 2,575 lines of `ui/` had no test of any kind, so a page could
break on a schema change and nothing would say so until someone opened it.

They are skipped rather than failed when a dependency the sandbox blocks is
missing, because an environment problem is not a code problem, and when there
are no snapshots to render.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "ui"))

pytest.importorskip("pyarrow", reason="Streamlit needs pyarrow to render tables")
AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

HAS_DATA = (ROOT / "data" / "raw").exists() and any((ROOT / "data" / "raw").iterdir())
needs_data = pytest.mark.skipif(not HAS_DATA, reason="no snapshots on disk to render")


def _run(source: str):
    """Render a page body and return the finished AppTest."""
    at = AppTest.from_string(source, default_timeout=90)
    at.run()
    return at


def _assert_clean(at, page):
    assert not at.exception, "{} raised: {}".format(
        page, at.exception[0].value if at.exception else "")


PAGE_SOURCE = """
import sys
from pathlib import Path
ROOT = Path(r"{root}")
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "ui"))
import {module}
{module}.{fn}()
"""


def _page(module, fn="render"):
    return PAGE_SOURCE.format(root=ROOT, module=module, fn=fn)


@needs_data
@pytest.mark.parametrize("module,fn", [
    ("page_search", "render"),
    ("page_ranking", "render"),
    ("page_funds", "render"),
    ("page_predict", "render"),
    ("page_report", "render"),
    ("page_macro", "render_macro"),
    ("page_macro", "render_reports"),
])
def test_page_renders_without_raising(module, fn):
    _assert_clean(_run(_page(module, fn)), "{}.{}".format(module, fn))


@needs_data
def test_chat_page_renders_without_credentials():
    # The chat page is the only one needing an API key, and it must degrade to
    # setup instructions rather than raising. Every other page has to work
    # without a credential, so this is the test that keeps that true.
    at = _run(_page("page_chat"))
    _assert_clean(at, "page_chat")


@needs_data
def test_the_report_page_does_not_show_currency_contaminated_ratios():
    # An ADR's EV/EBITDA and FCF yield divide a market number by a statement
    # number in another currency. TSM showed a 44% free cash flow yield here.
    tsm = ROOT / "data" / "raw" / "TSM"
    if not tsm.exists():
        pytest.skip("no TSM snapshot on disk")
    import json

    import score

    snap = sorted(tsm.glob("*.json"))[-1]
    metrics = json.loads(snap.read_text(encoding="utf-8"))["metrics"]
    cleaned, dropped = score.drop_currency_contaminated(metrics)
    assert dropped, "TSM should be flagged as a currency mismatch"
    for key in ("ev_to_ebitda", "fcf_yield", "price_to_sales"):
        assert cleaned[key] is None
