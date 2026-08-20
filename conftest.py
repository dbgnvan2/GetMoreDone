"""Pytest path setup for the whole repository.

Purpose: make every test importable regardless of collection order or which
         subset of the suite is invoked.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m3d
Tests:   tests/test_ci_contract.py::test_rm3d_every_test_file_is_importable_on_its_own

Two import styles coexist in this suite: `from src.getmoredone...` (needs the
repo root on sys.path) and `from getmoredone...` (needs src/). Several test
files used to insert src/ themselves — and two of them imported `getmoredone`
*before* their own insert ran, so they only worked when an alphabetically
earlier file had already done it. Running either alone was an error.

Putting both roots on the path once, here, removes that ordering dependency:
pytest imports conftest.py before collecting anything.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

for path in (ROOT, ROOT / "src"):
    entry = str(path)
    if entry not in sys.path:
        sys.path.insert(0, entry)


# ---------------------------------------------------------------------------
# Keep the test suite out of the user's real application data directory.
# ---------------------------------------------------------------------------

import logging

import pytest


def _user_data_fingerprint():
    """(mtime, size, sha256) for the real settings file and database.

    Content as well as mtime, because the app rewriting the same values on a
    window move is not the same event as a test corrupting the file, and the
    two deserve different words (P1: a transient condition must not be reported
    as a terminal one).

    Built without ``paths.default_settings_path()``, which calls
    ``app_data_dir_path()`` and *creates* the directory — a read-only guard
    should not bring the user's data directory into existence on a machine
    where the app has never run.
    """
    import hashlib

    from platformdirs import user_data_dir

    from src.getmoredone.paths import APP_AUTHOR, APP_NAME

    # Test-only seam: the guard's own test points a nested pytest run at a fake
    # data directory, so exercising the guard does not require touching the real
    # files it exists to protect. This lives in conftest, not in the app.
    override = os.environ.get("GETMOREDONE_TEST_GUARD_DIR")
    if override:
        base = Path(override)
    else:
        # user_data_dir() computes the path; app_data_dir_path() would also
        # create it, and a read-only guard must not.
        base = Path(user_data_dir(APP_NAME, APP_AUTHOR)).expanduser().resolve()

    fingerprint = {}
    for key, name in (("settings", "settings.json"), ("database", "getmoredone.db")):
        target = base / name
        if not target.exists():
            fingerprint[key] = None
            continue
        stat = target.stat()
        digest = hashlib.sha256(target.read_bytes()).hexdigest() if key == "settings" else None
        fingerprint[key] = (stat.st_mtime_ns, stat.st_size, digest, str(target))
    return fingerprint


def pytest_sessionstart(session):
    """Stamp the user's real data files so an escape is detected, not assumed.

    The redirect fixture below patches class objects. That is exactly the kind
    of guard that can be defeated without anyone noticing — the suite once
    imported `getmoredone.*` and `src.getmoredone.*` in different files, which
    Python loads as two distinct modules with two distinct classes, so patching
    one left the other writing the user's real file while a test asserting "the
    redirect is in force" passed against the patched twin.

    This checks the artifacts instead of the mechanism (P6). It also points
    GETMOREDONE_DB at a temporary file: an environment variable has one
    identity, so it cannot be defeated the way a patched class was.
    """
    import tempfile

    session.config._user_data_before = _user_data_fingerprint()

    # DatabaseManager() with no path resolves to the real database and runs
    # migrations on it. paths.resolve_db_path honours this variable first.
    if not os.environ.get("GETMOREDONE_DB"):
        handle = tempfile.mkdtemp(prefix="gmd-test-db-")
        os.environ["GETMOREDONE_DB"] = str(Path(handle) / "test.db")
        session.config._gmd_db_env_set = True


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Report an escape without destroying the test report.

    Raising here aborts the hook chain before the terminal reporter writes its
    summary: the run goes red, but with no FAILURES section and no counts —
    only this message, which may not even be the real problem. So it writes a
    line and sets the exit status instead (P24: the human must be shown the
    real cause, not a substituted one).
    """
    if getattr(session.config, "_gmd_db_env_set", False):
        os.environ.pop("GETMOREDONE_DB", None)

    before = getattr(session.config, "_user_data_before", None)
    if before is None:
        return
    after = _user_data_fingerprint()

    touched = [key for key in before if before[key] != after[key]]
    if not touched:
        return

    lines = []
    for key in touched:
        old, new = before[key], after[key]
        path = (new or old)[3] if (new or old) else key
        content_changed = (
            old is None or new is None
            or old[1] != new[1] or (old[2] is not None and old[2] != new[2])
        )
        lines.append(
            f"GUARD: the user's real {key} file changed during this run: {path}"
        )
        lines.append(
            "  Its CONTENT changed — a test wrote it, or it was edited."
            if content_changed else
            "  Only its timestamp moved — most likely the GetMoreDone app is "
            "running and saved on a window move or column drag, which is "
            "harmless. Re-run with the app closed to be sure."
        )
    lines.append(
        "  If a test did it: something bypassed the isolation in conftest.py."
    )

    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        for line in lines:
            reporter.write_line(line, red=True)
    else:
        print("\n".join(lines))

    if any(
        before[key] is None or after[key] is None
        or before[key][1] != after[key][1]
        or (before[key][2] is not None and before[key][2] != after[key][2])
        for key in touched
    ):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture(autouse=True, scope="session")
def _isolate_user_settings(tmp_path_factory):
    """Keep the suite out of the user's real settings.json.

    Purpose: several tests call ``AppSettings.load()`` and ``.save()`` with no
             path. ``get_settings_path`` resolves to the real application data
             directory, so a test run rewrote the user's settings file — and
             ``save()`` writes ``asdict(self)`` while ``load()`` filters to the
             dataclass fields, so any key the file carried that the dataclass no
             longer has would be destroyed by a test. One of those tests
             (``test_list_view_setting``) flips a value with no try/finally, so
             a failing assert left the real setting flipped.
    Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#batch-1
    Tests:   tests/test_settings_isolation.py

    Session-scoped and autouse, the same shape as the log fixture below: this
    has to be in place before the first test that touches settings, whichever
    file that turns out to be.
    """
    import importlib

    settings_path = tmp_path_factory.mktemp("settings") / "settings.json"
    redirect = classmethod(lambda cls: settings_path)

    # Both import spellings, because they are two different class objects and
    # patching one leaves the other pointed at the user's real file.
    originals = []
    for module_name in ("src.getmoredone.app_settings", "getmoredone.app_settings"):
        module = importlib.import_module(module_name)
        cls = module.AppSettings
        originals.append((cls, cls.__dict__.get("get_settings_path")))
        cls.get_settings_path = redirect
    try:
        yield settings_path
    finally:
        for cls, original in originals:
            if original is not None:
                cls.get_settings_path = original
            else:
                # Inherited rather than defined here: removing the override
                # restores the inherited one. Silently skipping would leave the
                # redirect installed on that class for the rest of the process.
                delattr(cls, "get_settings_path")


@pytest.fixture(autouse=True, scope="session")
def _isolate_weekly_tactic_log(tmp_path_factory):
    """Redirect the weekly-tactic log away from the real app data directory.

    Purpose: `weekly_tactic_debug.log` is where the migration records which rows
             it merged, deleted and moved — the file a human reads to audit an
             automatic data change. A test run appending its own tracebacks to
             it makes that audit harder, and one of those tracebacks is
             deliberately raised by a test.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7b

    Session-scoped and autouse because the logger is built at import time, so
    the handler is already attached before any test runs.
    """
    from src.getmoredone.weekly_tactic_logging import LOGGER_NAME

    logger = logging.getLogger(LOGGER_NAME)
    original = list(logger.handlers)
    for handler in original:
        logger.removeHandler(handler)

    handler = logging.FileHandler(
        tmp_path_factory.mktemp("logs") / "weekly_tactic_debug.log", encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()
        for restored in original:
            logger.addHandler(restored)


# Set while a test has explicitly asked for a mapped window (see the
# ``mapped_windows`` fixture). Everything else is withdrawn on creation.
_WINDOWS_MAY_BE_MAPPED = False


@pytest.fixture
def mapped_windows():
    """Let this test's windows actually appear.

    Only for tests that read real geometry — ``winfo_width`` on a withdrawn
    window returns 1, so the sash-drag contract cannot be checked without a
    laid-out window. Everything else stays withdrawn, so a full run puts one
    window on screen briefly instead of dozens of modals over the user's work.
    """
    global _WINDOWS_MAY_BE_MAPPED
    _WINDOWS_MAY_BE_MAPPED = True
    try:
        yield
    finally:
        _WINDOWS_MAY_BE_MAPPED = False


@pytest.fixture(autouse=True, scope="session")
def _keep_tk_windows_off_screen():
    """No test may put a window over the user's work or take their keyboard.

    Purpose: several tests build a real ``CTk`` root or ``CTkToplevel`` because
             that is the only way to prove a control is wired to the database
             rather than merely rendered (P25). On macOS every one of those
             appears, raises itself and grabs focus, so a full run threw dozens
             of modals over whatever the user was doing.
    Tests:   tests/test_tk_offscreen.py

    Windows are withdrawn on creation. Moving them off-screen instead does not
    work here: macOS clamps a window back onto the display (``+12000+12000``
    lands at the bottom-right corner), so it would still be visible.

    Session-scoped and autouse because the classes are patched once, at import
    time, and a window built at module scope has to be covered too.
    """
    import customtkinter as ctk
    import tkinter as tk

    patched = []

    def _silence(cls, name, replacement):
        if hasattr(cls, name):
            patched.append((cls, name, getattr(cls, name)))
            setattr(cls, name, replacement)

    for cls in (ctk.CTk, ctk.CTkToplevel):
        original_init = cls.__init__

        def _init(self, *args, __original=original_init, **kwargs):
            __original(self, *args, **kwargs)
            if _WINDOWS_MAY_BE_MAPPED:
                return
            try:
                self.withdraw()
            except Exception:
                pass

        patched.append((cls, "__init__", original_init))
        cls.__init__ = _init

        # The calls that would show a window, raise it, or seize the keyboard.
        _silence(cls, "lift", lambda self, *a, **k: None)
        _silence(cls, "focus_force", lambda self, *a, **k: None)
        _silence(cls, "grab_set", lambda self, *a, **k: None)

    try:
        yield
    finally:
        for cls, name, original in reversed(patched):
            setattr(cls, name, original)
