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
