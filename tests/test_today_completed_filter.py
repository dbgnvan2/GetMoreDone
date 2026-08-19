"""BC1 — Today shows only what belongs to today.

BACKLOG.md carried "Today listing shows all completed items (should only show
today's)" as an open bug. It is not open: both paths in
``TodayScreen.get_todays_items`` restrict completed items to
``DATE(completed_at) = today``. Verified against a real database rather than
read off the source, then pinned here — the entry survived because nothing
asserted the behaviour either way.

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#batch-1
"""

from datetime import date, datetime, timedelta

import pytest

from src.getmoredone.models import ActionItem
from src.getmoredone.screens.today import TodayScreen
from src.getmoredone.vps_manager import VPSManager

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture
def manager(tmp_path):
    vps = VPSManager(str(tmp_path / "today.db"))
    yield vps.db_manager
    vps.close()


def _screen(manager):
    """The dialog's own method, driven without a display."""
    return type("TodayStub", (), {"db_manager": manager, "search_query": ""})()


def _add(manager, title, start=YESTERDAY):
    item = ActionItem(who="Self", title=title, start_date=start, due_date=start)
    manager.create_action_item(item, apply_defaults=False)
    return item


def _complete_on(manager, item, when_iso):
    manager.complete_action_item(item.id)
    manager.db.conn.execute(
        "UPDATE action_items SET completed_at = ? WHERE id = ?", (when_iso, item.id))
    manager.db.conn.commit()


def test_bc1_an_item_completed_today_is_shown(manager):
    item = _add(manager, "done today")
    _complete_on(manager, item, datetime.now().isoformat())

    titles = [i.title for i in TodayScreen.get_todays_items(_screen(manager))]

    assert "done today" in titles


def test_bc1_an_item_completed_earlier_is_not_shown(manager):
    """The reported bug. A completion from another day is history, not today."""
    item = _add(manager, "done last week")
    _complete_on(manager, item, (datetime.now() - timedelta(days=9)).isoformat())

    titles = [i.title for i in TodayScreen.get_todays_items(_screen(manager))]

    assert "done last week" not in titles


def test_bc1_an_item_completed_yesterday_is_not_shown(manager):
    """The boundary: one day out, not one week."""
    item = _add(manager, "done yesterday")
    _complete_on(manager, item, (datetime.now() - timedelta(days=1)).isoformat())

    titles = [i.title for i in TodayScreen.get_todays_items(_screen(manager))]

    assert "done yesterday" not in titles


def test_bc1_open_items_due_today_or_earlier_are_shown(manager):
    _add(manager, "open from yesterday", start=YESTERDAY)
    _add(manager, "open today", start=TODAY)

    titles = [i.title for i in TodayScreen.get_todays_items(_screen(manager))]

    assert "open from yesterday" in titles
    assert "open today" in titles


def test_bc1_an_open_item_starting_later_is_not_shown(manager):
    _add(manager, "open next week",
         start=(date.today() + timedelta(days=7)).isoformat())

    titles = [i.title for i in TodayScreen.get_todays_items(_screen(manager))]

    assert "open next week" not in titles


def test_bc1_the_search_path_filters_completions_the_same_way(manager):
    """Searching takes the Python branch, not the SQL one — same rule (P3).

    Two paths compute this list; a fix or a regression in one of them says
    nothing about the other.
    """
    recent = _add(manager, "alpha done today")
    _complete_on(manager, recent, datetime.now().isoformat())
    old = _add(manager, "alpha done last week")
    _complete_on(manager, old, (datetime.now() - timedelta(days=9)).isoformat())

    stub = _screen(manager)
    stub.search_query = "alpha"
    titles = [i.title for i in TodayScreen.get_todays_items(stub)]

    assert "alpha done today" in titles
    assert "alpha done last week" not in titles
