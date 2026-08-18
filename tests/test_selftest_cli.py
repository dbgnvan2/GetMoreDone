"""Tests for ``run.py --selftest``.

Purpose: prove the headless startup check is real — it passes on a sound build,
         fails on a broken one, and never opens a window.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m1b
Tests:   this file

The negative test matters more than the positive one. A selftest that always
exits 0 is worse than no selftest: CI would report every broken bundle green
(P24 — success decided by something that cannot distinguish pass from fail).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.getmoredone import selftest

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_PY = REPO_ROOT / "run.py"


def _run_selftest_subprocess(env_overrides: dict, timeout: int = 120):
    """Invoke run.py --selftest in a clean subprocess; return the CompletedProcess."""
    env = dict(os.environ)
    env.update({k: str(v) for k, v in env_overrides.items()})
    env.setdefault("PYTHONPATH", str(REPO_ROOT / "src"))
    return subprocess.run(
        [sys.executable, str(RUN_PY), "--selftest"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# --------------------------------------------------------------------------
# R-M1.B — the selftest passes on a sound build
# --------------------------------------------------------------------------

def test_rm1b_selftest_exits_zero_on_temp_db(tmp_path):
    result = _run_selftest_subprocess({
        "GETMOREDONE_DB": tmp_path / "selftest.db",
        "GETMOREDONE_RESOURCE_ROOT": REPO_ROOT,
    })
    assert result.returncode == 0, (
        f"selftest failed on a sound source tree.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_rm1b_selftest_creates_the_database_file(tmp_path):
    db_path = tmp_path / "created.db"
    result = _run_selftest_subprocess({
        "GETMOREDONE_DB": db_path,
        "GETMOREDONE_RESOURCE_ROOT": REPO_ROOT,
    })
    assert result.returncode == 0, result.stdout + result.stderr
    assert db_path.exists(), "selftest reported success but created no database"


# --------------------------------------------------------------------------
# R-M1.B — and fails on a broken one. Guards against a no-op selftest.
# --------------------------------------------------------------------------

def test_rm1b_selftest_exits_nonzero_when_theme_missing(tmp_path):
    """Point the resource root at an empty dir: this is exactly finding F1."""
    empty_root = tmp_path / "empty_bundle"
    empty_root.mkdir()

    result = _run_selftest_subprocess({
        "GETMOREDONE_DB": tmp_path / "selftest.db",
        "GETMOREDONE_RESOURCE_ROOT": empty_root,
    })
    assert result.returncode != 0, (
        "selftest passed against a bundle with no themes/ — it would have waved "
        f"finding F1 straight through CI.\nstdout:\n{result.stdout}"
    )
    assert "themes" in result.stdout.lower()


def test_rm1b_selftest_reports_the_failing_check_by_name(tmp_path):
    empty_root = tmp_path / "empty_bundle"
    empty_root.mkdir()
    result = _run_selftest_subprocess({
        "GETMOREDONE_DB": tmp_path / "selftest.db",
        "GETMOREDONE_RESOURCE_ROOT": empty_root,
    })
    assert "[FAIL]" in result.stdout, f"no failing check named in output:\n{result.stdout}"


def test_rm1b_selftest_runs_every_check_even_after_a_failure(tmp_path):
    """One broken check must not hide the state of the others."""
    empty_root = tmp_path / "empty_bundle"
    empty_root.mkdir()
    result = _run_selftest_subprocess({
        "GETMOREDONE_DB": tmp_path / "selftest.db",
        "GETMOREDONE_RESOURCE_ROOT": empty_root,
    })
    reported = result.stdout.count("[PASS]") + result.stdout.count("[FAIL]")
    assert reported == len(selftest.CHECKS), (
        f"expected {len(selftest.CHECKS)} check lines, saw {reported}:\n{result.stdout}"
    )


# --------------------------------------------------------------------------
# R-M1.B — headless: no window is ever created
# --------------------------------------------------------------------------

def test_rm1b_selftest_creates_no_window(tmp_path, monkeypatch):
    """Intercept the CTk boundary and assert it is never constructed."""
    import customtkinter as ctk

    calls = []

    class _Recorder:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

    monkeypatch.setattr(ctk, "CTk", _Recorder)
    monkeypatch.setenv("GETMOREDONE_DB", str(tmp_path / "selftest.db"))
    monkeypatch.setenv("GETMOREDONE_RESOURCE_ROOT", str(REPO_ROOT))

    assert selftest.run_selftest() == 0
    assert calls == [], f"selftest instantiated a window: {calls}"


def test_rm1b_selftest_does_not_import_the_main_window_module(tmp_path):
    """A frozen --selftest must not need the whole GUI to answer."""
    code = (
        "import sys; sys.path.insert(0, 'src');\n"
        "from getmoredone.selftest import run_selftest;\n"
        "rc = run_selftest();\n"
        "print('APP_IMPORTED', 'getmoredone.app' in sys.modules);\n"
        "sys.exit(rc)"
    )
    env = dict(os.environ)
    env["GETMOREDONE_DB"] = str(tmp_path / "selftest.db")
    env["GETMOREDONE_RESOURCE_ROOT"] = str(REPO_ROOT)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "APP_IMPORTED False" in result.stdout, result.stdout


# --------------------------------------------------------------------------
# R-M1.B — the launch path still works (the flag must not swallow normal runs)
# --------------------------------------------------------------------------

def test_rm1b_run_py_without_selftest_does_not_call_run_selftest(monkeypatch):
    """`python run.py` must still launch the app, not the selftest."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("gmd_run_module", RUN_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    launched = []
    fake_app = type(sys)("getmoredone.app")
    fake_app.main = lambda: launched.append("launched")
    monkeypatch.setitem(sys.modules, "getmoredone.app", fake_app)
    monkeypatch.setattr(sys, "argv", ["run.py"])

    assert module.main() == 0
    assert launched == ["launched"]
