"""Database connections must not outlive the test that opened them.

Purpose: every DatabaseManager and VPSManager holds an open SQLite connection
         and its file descriptor. Twelve test functions built one and never
         closed it — several of them helpers called from many tests, so the
         real count was higher.
Spec:    BACKLOG.md, "What else may be leaking"
Tests:   this file

The window leak's question, asked of the next finite resource (P30): who gives
this back, and when?
"""

from __future__ import annotations

import pytest

from conftest import _LIVE_CONNECTIONS, close_connections_created_since
from src.getmoredone.db_manager import DatabaseManager


def _is_open(manager) -> bool:
    try:
        manager.db.conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def test_a_manager_left_open_is_closed_at_teardown(tmp_path):
    """The net under every test, including one that fails before its own close."""
    before = set(_LIVE_CONNECTIONS)
    leaked = DatabaseManager(str(tmp_path / "leak.db"))
    assert leaked in _LIVE_CONNECTIONS, "the manager was not registered"
    assert _is_open(leaked), "precondition: the connection is open"

    closed = close_connections_created_since(before)

    assert closed >= 1
    assert not _is_open(leaked), "the connection survived the sweep"


def test_the_sweeper_leaves_earlier_connections_alone(tmp_path):
    """Only managers created during this test are closed."""
    keep = DatabaseManager(str(tmp_path / "keep.db"))
    try:
        snapshot = set(_LIVE_CONNECTIONS)          # taken AFTER `keep` exists
        transient = DatabaseManager(str(tmp_path / "transient.db"))

        close_connections_created_since(snapshot)

        assert _is_open(keep), "the sweeper closed a connection still in use"
        assert not _is_open(transient)
    finally:
        keep.close()


def test_closing_something_already_closed_does_not_stop_the_sweep(tmp_path):
    """A manager a test closed itself must not abort the rest of the sweep."""
    before = set(_LIVE_CONNECTIONS)
    already = DatabaseManager(str(tmp_path / "a.db"))
    already.close()
    still_open = DatabaseManager(str(tmp_path / "b.db"))

    close_connections_created_since(before)

    assert not _is_open(still_open), (
        "a raise on an already-closed manager stopped the rest being closed"
    )
