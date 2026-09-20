"""Tests for the shared helpers, and for how credentials reach them.

The credential path gets the attention here because its failure mode is the
quiet one this project cares about. A contact string that never reaches EDGAR
does not raise; it comes back as filings that look like they were never made.
A `.env` that shadows a deployed host's own secrets does not raise either.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from common import ROOT as COMMON_ROOT  # noqa: E402
from common import ua_is_configured  # noqa: E402

DEFAULT_PLACEHOLDER = "reportstock/0.1 (research; contact: set REPORTSTOCK_UA env var)"


class TestUaIsConfigured:
    def test_the_default_placeholder_is_not_configured(self):
        # This is the case the original check missed: the default value does
        # not contain "example.com", so the warning could never fire.
        assert ua_is_configured(DEFAULT_PLACEHOLDER) is False

    def test_the_documented_example_is_not_configured(self):
        assert ua_is_configured("Your Name your@email.example.com") is False

    def test_a_real_contact_is_configured(self):
        assert ua_is_configured("Jane Somebody jane@somewhere.org") is True

    def test_a_string_without_an_email_is_not_configured(self):
        # EDGAR wants a contact it can actually reach.
        assert ua_is_configured("reportstock research tool") is False

    @pytest.mark.parametrize("value", ["", None])
    def test_empty_is_not_configured(self, value):
        assert ua_is_configured(value or "") is False


class TestDotenvLoading:
    """These run the loader in a subprocess, because it fires at import time."""

    def _run(self, env, code):
        import os

        e = dict(os.environ)
        e.pop("REPORTSTOCK_UA", None)
        e.update(env)
        out = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(code)],
            capture_output=True, text=True, env=e, cwd=str(ROOT),
        )
        assert out.returncode == 0, out.stderr
        return out.stdout.strip()

    READ_UA = """
        import sys
        sys.path.insert(0, r"{tools}")
        from common import UA
        print(UA)
    """.replace("{tools}", str(ROOT / "tools"))

    def test_a_shell_variable_beats_the_dotenv_file(self):
        # On a deployed host the platform injects secrets; a stale .env that
        # overrode them would send the wrong contact to EDGAR very quietly.
        got = self._run({"REPORTSTOCK_UA": "shell wins shell@example.org"}, self.READ_UA)
        assert got == "shell wins shell@example.org"

    def test_the_file_is_anchored_to_the_repo_not_the_working_directory(self):
        # A loader that silently finds nothing when a tool is run from tools/
        # is worse than no loader, so the path comes from ROOT.
        assert COMMON_ROOT == ROOT
        assert (COMMON_ROOT / ".env").parent == ROOT

    def test_missing_dotenv_package_does_not_break_the_import(self):
        # The shell can export these instead; an ImportError here would take
        # every tool down over an optional convenience.
        code = """
            import sys, builtins
            real = builtins.__import__
            def blocked(name, *a, **k):
                if name == "dotenv":
                    raise ImportError("simulated missing package")
                return real(name, *a, **k)
            builtins.__import__ = blocked
            sys.path.insert(0, r"{tools}")
            from common import UA, _load_dotenv
            print("imported")
        """.replace("{tools}", str(ROOT / "tools"))
        assert self._run({}, code) == "imported"
