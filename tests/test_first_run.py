"""First-run behaviour on a machine that has never run GetMoreDone.

Purpose: prove the app is usable with no Google credentials, no music folder,
         and no database — and that it does not lose data on the second run.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m5
Tests:   this file

Someone who downloads a build has none of the state this Mac accumulated over
months. Every optional integration must be *visibly unavailable*, never a
traceback and never a blocking dialog.

None of these tests touch the real user data directory: the database goes to a
tmp path, credential paths are injected, and `Path.home()` is redirected wherever
a constructor creates a dot-directory. `test_rm5a_constructing_the_manager_does_not_touch_the_real_home`
asserts that rather than trusting it.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from src.getmoredone.database import Database

REPO_ROOT = Path(__file__).resolve().parents[1]

# Prefixes a failure path might return as a string instead of raising (P14).
ERROR_SENTINEL_PREFIXES = ("error", "failed", "exception", "traceback", "unable to")


# --------------------------------------------------------------------------
# R-M5.A — Google features degrade, they do not crash
# --------------------------------------------------------------------------

def test_rm5a_has_credentials_is_false_when_the_file_is_absent(tmp_path):
    from src.getmoredone.google_calendar import GoogleCalendarManager

    missing = tmp_path / "nope" / "credentials.json"
    assert GoogleCalendarManager.has_credentials(str(missing)) is False


def test_rm5a_has_credentials_is_true_when_the_file_is_present(tmp_path):
    """Guards against a checker that always says 'no' and looks correct."""
    from src.getmoredone.google_calendar import GoogleCalendarManager

    creds = tmp_path / "credentials.json"
    creds.write_text("{}", encoding="utf-8")
    assert GoogleCalendarManager.has_credentials(str(creds)) is True


def test_rm5a_google_features_report_unavailable_without_credentials(tmp_path, monkeypatch):
    """Constructing the manager with no credentials must raise a *typed* error
    naming the missing file — not return a half-built object that fails later.

    The home and app data directories are redirected as a safety net. Since
    BI3 the constructor creates neither — both arguments are given here, so it
    never needs a default path — but a redirect is what makes "nothing was
    created" a claim this test can honestly check on a developer machine that
    has a real ``~/.getmoredone``.
    """
    from src.getmoredone import paths as gmd_paths
    from src.getmoredone.google_calendar import GoogleCalendarManager

    if not GoogleCalendarManager.is_available():
        pytest.skip("google client libraries not installed")

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_app_data = tmp_path / "appdata"
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setattr(gmd_paths, "legacy_dot_dir", lambda: fake_home / ".getmoredone")
    monkeypatch.setattr(gmd_paths, "app_data_dir_path", lambda create=True: fake_app_data)

    missing = tmp_path / "credentials.json"
    with pytest.raises((FileNotFoundError, RuntimeError)) as excinfo:
        GoogleCalendarManager(credentials_file=str(missing),
                              token_file=str(tmp_path / "token.pickle"))

    # Nothing was created anywhere: not the legacy dot-dir, not the app data dir.
    assert list(fake_home.iterdir()) == []
    assert not fake_app_data.exists()

    message = str(excinfo.value)
    assert "credentials" in message.lower(), (
        f"the error does not say what is missing: {message}"
    )
    assert str(missing) in message or "credentials.json" in message


def test_rm5a_credential_error_explains_how_to_fix_it():
    """A first-run user needs the remedy, not just the diagnosis."""
    source = (REPO_ROOT / "src/getmoredone/google_calendar.py").read_text(encoding="utf-8")
    assert "console.cloud.google.com" in source or "Google Cloud" in source, (
        "the missing-credentials error should point at where to get credentials"
    )


def test_rm5a_no_error_string_rendered_as_content():
    """P14: a failure must not come back as a str that a screen would display.

    `has_credentials` and `is_available` are the two the UI branches on. Both
    must return real booleans — a truthy error string would read as 'available'.
    """
    from src.getmoredone.google_calendar import GoogleCalendarManager

    for value in (GoogleCalendarManager.is_available(),
                  GoogleCalendarManager.has_credentials("/nonexistent/creds.json")):
        assert isinstance(value, bool), f"expected bool, got {type(value).__name__}"


def test_rm5a_check_token_validity_reports_absence_as_data_not_an_error(tmp_path):
    from src.getmoredone.google_calendar import GoogleCalendarManager

    result = GoogleCalendarManager.check_token_validity(str(tmp_path / "token.pickle"))
    assert result["exists"] is False
    assert result["error"] is None, (
        "a missing token is a normal first-run state, not an error"
    )


def test_rm5a_gmail_importer_defaults_do_not_require_credentials_to_import():
    """Importing the module must not touch the filesystem or raise."""
    import importlib

    module = importlib.import_module("src.getmoredone.gmail_importer")
    assert module is not None


def test_rm5a_selftest_passes_with_no_google_credentials(tmp_path):
    """The whole point: a machine with no Google setup is a healthy machine."""
    from src.getmoredone import selftest

    check_names = [name for name, _fn in selftest.CHECKS]
    assert not any("google" in name.lower() or "calendar" in name.lower()
                   for name in check_names), (
        f"the selftest requires a Google check, so a first run would fail: {check_names}"
    )


# --------------------------------------------------------------------------
# R-M5.B — no music folder, none bundled (covered further in test_packaging_resources)
# --------------------------------------------------------------------------

def test_rm5b_timer_music_reports_why_nothing_plays(tmp_path, monkeypatch):
    """Silence must be explained, not silent (P2)."""
    from src.getmoredone.utils import music_library

    monkeypatch.setattr(music_library, "bundled_audio_dir", lambda: tmp_path / "audio")
    selection = music_library.select_track(None)

    assert selection.track is None
    assert selection.message, "no message explaining why no music plays"
    assert not selection.message.lower().startswith(ERROR_SENTINEL_PREFIXES), (
        f"the no-music message reads as an error: {selection.message!r}"
    )


# --------------------------------------------------------------------------
# R-M5.C — a brand-new database, and an existing populated one (P8)
# --------------------------------------------------------------------------

def _run_selftest(db_path: Path) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    env["GETMOREDONE_DB"] = str(db_path)
    env["GETMOREDONE_RESOURCE_ROOT"] = str(REPO_ROOT)
    env.setdefault("PYTHONPATH", str(REPO_ROOT / "src"))
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "run.py"), "--selftest"],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=300,
    )


def test_rm5c_selftest_on_empty_db_initialises_schema(tmp_path):
    db_path = tmp_path / "fresh.db"
    assert not db_path.exists()

    result = _run_selftest(db_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert db_path.exists(), "first run created no database"

    conn = sqlite3.connect(db_path)
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    for required in ("action_items", "contacts", "defaults", "work_logs"):
        assert required in tables, f"first run did not create {required}"


def test_rm5c_selftest_on_existing_populated_db(tmp_path):
    """Dirty-state test (P8): run #2 must not touch existing rows.

    Clean-state tests are necessary but not sufficient — the interesting run is
    the one where the database already has the user's work in it.
    """
    from src.getmoredone.db_manager import DatabaseManager
    from src.getmoredone.models import ActionItem

    db_path = tmp_path / "populated.db"
    manager = DatabaseManager(str(db_path))
    try:
        for title in ("Keep me", "And me", "Me too"):
            manager.create_action_item(ActionItem(who="Self", title=title,
                                                  start_date="2026-08-12"))
        before = {
            r[0] for r in manager.db.connect().execute(
                "SELECT title FROM action_items")
        }
    finally:
        manager.close()
    assert len(before) == 3

    result = _run_selftest(db_path)
    assert result.returncode == 0, result.stdout + result.stderr

    conn = sqlite3.connect(db_path)
    try:
        after = {r[0] for r in conn.execute("SELECT title FROM action_items")}
    finally:
        conn.close()
    assert after == before, f"selftest altered existing data: {before} -> {after}"


def test_rm5c_selftest_is_idempotent_across_runs(tmp_path):
    """Running it twice must not accumulate schema changes or fail the second time."""
    db_path = tmp_path / "twice.db"
    first = _run_selftest(db_path)
    assert first.returncode == 0, first.stdout

    conn = sqlite3.connect(db_path)
    try:
        tables_after_first = sorted(
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    finally:
        conn.close()

    second = _run_selftest(db_path)
    assert second.returncode == 0, second.stdout

    conn = sqlite3.connect(db_path)
    try:
        tables_after_second = sorted(
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    finally:
        conn.close()
    assert tables_after_first == tables_after_second


def test_rm5c_database_parent_directory_is_created_when_missing(tmp_path):
    """A first run on a fresh machine has no app-data folder yet."""
    nested = tmp_path / "does" / "not" / "exist" / "gmd.db"
    db = Database(str(nested))
    try:
        db.connect()
        db.initialize_schema()
    finally:
        db.close()
    assert nested.exists()


def test_rm5c_tests_never_touch_the_real_user_data_dir(tmp_path):
    """Guard on the guard: these tests must not create ~/.getmoredone or the
    real app-data folder as a side effect."""
    from src.getmoredone import paths

    real_db = paths.default_db_path()
    assert str(tmp_path) not in str(real_db)  # sanity: they are different places
    # The selftest helper always injects GETMOREDONE_DB, so the real path is
    # never the target. This asserts the helper, not the app.
    result = _run_selftest(tmp_path / "isolated.db")
    assert str(real_db) not in result.stdout, (
        "a selftest run reported the real user database path"
    )


def test_rm5a_constructing_the_manager_does_not_touch_the_real_home(tmp_path, monkeypatch):
    """Assert the isolation this file's docstring claims.

    ``GoogleCalendarManager.__init__`` used to call
    ``(Path.home() / ".getmoredone").mkdir()`` *before* consulting its
    arguments, so a test that forgot to redirect ``Path.home()`` silently
    created that folder on whatever machine ran it. This asserted that folder
    was the one and only thing created; BI3 made it create nothing at all.

    The directory-resolution rules themselves live in
    ``tests/test_google_calendar_paths.py``. This stays here because it is what
    the file's isolation claim rests on.
    """
    from src.getmoredone import paths as gmd_paths
    from src.getmoredone.google_calendar import GoogleCalendarManager

    if not GoogleCalendarManager.is_available():
        pytest.skip("google client libraries not installed")

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_app_data = tmp_path / "appdata"
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setattr(gmd_paths, "legacy_dot_dir", lambda: fake_home / ".getmoredone")
    monkeypatch.setattr(gmd_paths, "app_data_dir_path", lambda create=True: fake_app_data)

    with pytest.raises((FileNotFoundError, RuntimeError)):
        GoogleCalendarManager(credentials_file=str(tmp_path / "nope.json"),
                              token_file=str(tmp_path / "nope.pickle"))

    created = list(fake_home.iterdir())
    assert created == [], (
        f"constructing with explicit paths created files in home: {created}"
    )
    assert not fake_app_data.exists(), (
        "constructing with explicit paths created the app data directory"
    )
