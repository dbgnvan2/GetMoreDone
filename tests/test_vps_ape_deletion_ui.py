"""Deleting an Annual Plan Element: both refusals reach the user.

An Annual Plan Element is deleted only when it has no child records. There are
two ways it can have them — attached Projects and attached Action Items — and
each raises its own exception. The screen caught the first and not the second,
so the newer refusal would have escaped a Tk ``command`` into a stderr a
double-clicked app has nowhere to send: the user would press Delete, see
nothing happen, and have no idea why (P5).
"""

from types import SimpleNamespace

import pytest

import src.getmoredone.screens.annual_vision_segments as avs
from src.getmoredone.models import ActionItem
from src.getmoredone.vps_manager import (
    ActionItemsAttachedError,
    ProjectBoardsAttachedError,
)
from tests.weekly_tactic_fixtures import make_vps, seed_ape


def _screen_stub(vps, raising):
    """Enough of the screen to drive the delete handler without a display."""
    return SimpleNamespace(
        vps_manager=SimpleNamespace(
            delete_annual_records_for_vision_element=raising),
        refresh_lists=lambda: None,
        _parse_year=lambda: 2026,
    )


@pytest.fixture
def dialogs(monkeypatch):
    seen = {"errors": [], "asked": []}
    monkeypatch.setattr(avs.messagebox, "askyesno",
                        lambda *a, **k: seen["asked"].append(a) or True)
    monkeypatch.setattr(avs.messagebox, "showerror",
                        lambda title, message, **k: seen["errors"].append((title, message)))
    return seen


def _delete(stub, row=None):
    avs.AnnualVisionSegmentsScreen.delete_annual_item(
        stub, row or {"vision_element_id": "ve-1", "key_field": "Blog"})


def test_action_items_attached_is_reported_not_raised(dialogs):
    def raising(year, ve_id):
        raise ActionItemsAttachedError(["Draft the outline", "Publish it"])

    _delete(_screen_stub(None, raising))

    assert dialogs["errors"], "the refusal reached nobody"
    title, message = dialogs["errors"][0]
    assert "Action Items Attached" == title
    assert "Draft the outline" in message and "Publish it" in message
    assert "2 action item(s)" in message


def test_a_long_list_of_items_is_capped(dialogs):
    def raising(year, ve_id):
        raise ActionItemsAttachedError([f"Item {i}" for i in range(25)])

    _delete(_screen_stub(None, raising))

    _title, message = dialogs["errors"][0]
    assert "25 action item(s)" in message
    assert "and 15 more" in message, message
    assert message.count("  • ") == 11        # ten named plus the "more" line


def test_the_projects_refusal_still_works(dialogs):
    def raising(year, ve_id):
        raise ProjectBoardsAttachedError(["Website Rebuild"])

    _delete(_screen_stub(None, raising))

    title, message = dialogs["errors"][0]
    assert "Projects Attached" == title
    assert "Website Rebuild" in message


def test_a_clean_delete_refreshes_and_says_nothing(dialogs):
    stub = _screen_stub(None, lambda year, ve_id: True)
    refreshed = []
    stub.refresh_lists = lambda: refreshed.append(True)

    _delete(stub)

    assert refreshed == [True]
    assert dialogs["errors"] == []


def test_the_refusal_is_raised_for_a_real_attached_item(tmp_path):
    """...and the exception the screen handles is the one the manager raises."""
    vps = make_vps(tmp_path)
    try:
        ape_id = seed_ape(vps)
        item = ActionItem(who="Self", title="On the plan",
                          annual_plan_element_id=ape_id)
        vps.db_manager.create_action_item(item, apply_defaults=False)

        row = vps.db.conn.execute(
            "SELECT vision_element_id FROM annual_plan_elements WHERE id = ?",
            (ape_id,)).fetchone()
        with pytest.raises(ActionItemsAttachedError) as excinfo:
            vps.delete_annual_records_for_vision_element(2026, row["vision_element_id"])
        assert "On the plan" in str(excinfo.value)
    finally:
        vps.close()
