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


class TestConcurrentFetchOrdering:
    """Parallel fetching must not make a run's output depend on timing.

    Snapshots are the audit trail of this project, so two runs over the same
    tickers have to produce the same file set and the same printed order however
    the threads interleave. The fetcher collects results first and prints in the
    order the tickers were given.
    """

    def test_results_are_emitted_in_input_order(self, monkeypatch, capsys):
        import fetch_fundamentals as ff

        order = ["CCC", "AAA", "BBB"]

        def fake_fetch_one(tk, years=5):
            import time, random
            time.sleep(random.random() * 0.05)   # finish out of order on purpose
            return {
                "profile": {"name": tk + " Inc"},
                "metrics": {"revenue_cagr": 0.1, "operating_margin_latest": 0.2,
                            "roic_est": 0.15, "forward_pe": 20.0},
            }

        written = []
        monkeypatch.setattr(ff, "fetch_one", fake_fetch_one)
        monkeypatch.setattr(ff, "write_json",
                            lambda path, payload: (written.append(path), path)[1])
        monkeypatch.setattr(ff, "resolve_tickers", lambda a: order)
        monkeypatch.setattr(sys, "argv", ["fetch_fundamentals.py", "--workers", "4"])

        ff.main()
        printed = [l.split()[0] for l in capsys.readouterr().out.splitlines()
                   if l[:3] in ("CCC", "AAA", "BBB")]
        assert printed == order

    def test_a_single_worker_still_works(self, monkeypatch, capsys):
        import fetch_fundamentals as ff

        monkeypatch.setattr(ff, "fetch_one", lambda tk, years=5: {
            "profile": {"name": tk}, "metrics": {
                "revenue_cagr": 0.1, "operating_margin_latest": 0.2,
                "roic_est": 0.15, "forward_pe": 20.0}})
        monkeypatch.setattr(ff, "write_json", lambda path, payload: path)
        monkeypatch.setattr(ff, "resolve_tickers", lambda a: ["AAA"])
        monkeypatch.setattr(sys, "argv", ["fetch_fundamentals.py", "--workers", "1"])
        assert ff.main() == 0

    def test_one_failure_does_not_lose_the_others(self, monkeypatch, capsys):
        import fetch_fundamentals as ff

        def flaky(tk, years=5):
            if tk == "BAD":
                raise RuntimeError("simulated network failure")
            return {"profile": {"name": tk}, "metrics": {
                "revenue_cagr": 0.1, "operating_margin_latest": 0.2,
                "roic_est": 0.15, "forward_pe": 20.0}}

        monkeypatch.setattr(ff, "fetch_one", flaky)
        monkeypatch.setattr(ff, "write_json", lambda path, payload: path)
        monkeypatch.setattr(ff, "resolve_tickers", lambda a: ["AAA", "BAD", "CCC"])
        monkeypatch.setattr(sys, "argv", ["fetch_fundamentals.py", "--workers", "3"])

        rc = ff.main()
        out = capsys.readouterr()
        assert rc == 1                      # a failure is reported, not hidden
        assert "AAA" in out.out and "CCC" in out.out
        assert "BAD" in out.err


class TestStreamlitSecretsBridge:
    """A hosted deployment has no .env.

    Streamlit Community Cloud keeps secrets in its own panel and serves them
    through st.secrets, while everything under tools/ reads os.environ. Without
    a bridge, REPORTSTOCK_UA stays at its placeholder on the host and EDGAR
    throttles every fetch while looking like companies that never filed.
    """

    def _bridge(self, monkeypatch, secrets, env=None):
        import types

        import common

        fake = types.SimpleNamespace(secrets=types.SimpleNamespace(get=secrets.get))
        monkeypatch.setitem(sys.modules, "streamlit", fake)
        for k in ("REPORTSTOCK_UA", "ANTHROPIC_API_KEY", "APP_PASSWORD"):
            monkeypatch.delenv(k, raising=False)
        for k, v in (env or {}).items():
            monkeypatch.setenv(k, v)
        return common._load_streamlit_secrets()

    def test_secrets_reach_the_environment(self, monkeypatch):
        import os

        self._bridge(monkeypatch, {"REPORTSTOCK_UA": "Host User host@example.org"})
        assert os.environ["REPORTSTOCK_UA"] == "Host User host@example.org"

    def test_a_real_environment_variable_still_wins(self, monkeypatch):
        import os

        self._bridge(
            monkeypatch,
            {"REPORTSTOCK_UA": "from secrets"},
            env={"REPORTSTOCK_UA": "from the shell"},
        )
        assert os.environ["REPORTSTOCK_UA"] == "from the shell"

    def test_no_streamlit_installed_is_not_an_error(self, monkeypatch):
        import common

        monkeypatch.setitem(sys.modules, "streamlit", None)
        # A None module makes `import streamlit` fail the attribute lookup;
        # every tool runs outside Streamlit, so this must stay silent.
        try:
            common._load_streamlit_secrets()
        except Exception as e:
            pytest.fail("bridge raised outside Streamlit: {}".format(e))

    def test_non_string_secrets_are_ignored(self, monkeypatch):
        import os

        self._bridge(monkeypatch, {"REPORTSTOCK_UA": 12345})
        assert "REPORTSTOCK_UA" not in os.environ
