"""One owner of the ``getmoredone.weekly_tactic`` logger.

Purpose: make sure the log handler exists *before* the first thing that writes
         to it, whoever that turns out to be.
Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7a5
Tests:   tests/test_weekly_tactic_dedupe.py::test_wt_m7a5_dedupe_log_reaches_a_handler

The handler used to be installed lazily by ``VPSManager``. But ``app.py`` builds
the ``DatabaseManager`` — which runs the whole migration — before it builds the
``VPSManager``, so at migration time the logger had no handler and no level: the
record of which tactic rows were merged and deleted was discarded, and that
record is the only place a user could ever see what happened to their data.

Imports nothing but ``paths``, so every module in the chain can call it without
an import cycle.
"""

import logging

from .paths import app_data_dir_path

LOGGER_NAME = "getmoredone.weekly_tactic"
LOG_FILENAME = "weekly_tactic_debug.log"


def get_weekly_tactic_logger() -> logging.Logger:
    """The weekly-tactic logger, with its file handler attached.

    Idempotent — a logger that already has handlers is returned untouched.
    Falls back to a plain logger if the log file cannot be opened, so a
    read-only data directory can never stop the app from starting.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    try:
        handler = logging.FileHandler(app_data_dir_path() / LOG_FILENAME, encoding="utf-8")
    except OSError:
        return logger
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
