"""Pytest path setup for the whole repository.

Purpose: make every test importable regardless of collection order or which
         subset of the suite is invoked.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m3d
Tests:   tests/test_ci_contract.py::test_rm3d_every_test_file_passes_in_isolation

Two import styles coexist in this suite: `from src.getmoredone...` (needs the
repo root on sys.path) and `from getmoredone...` (needs src/). Several test
files used to insert src/ themselves — and two of them imported `getmoredone`
*before* their own insert ran, so they only worked when an alphabetically
earlier file had already done it. Running either alone was an error.

Putting both roots on the path once, here, removes that ordering dependency:
pytest imports conftest.py before collecting anything.
"""

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
    from src.getmoredone.app_settings import AppSettings

    settings_path = tmp_path_factory.mktemp("settings") / "settings.json"
    original = AppSettings.get_settings_path
    AppSettings.get_settings_path = classmethod(lambda cls: settings_path)
    try:
        yield settings_path
    finally:
        AppSettings.get_settings_path = original


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
