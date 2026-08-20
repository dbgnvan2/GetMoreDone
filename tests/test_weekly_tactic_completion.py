"""WT-M5 — completing an item re-files it to the week it was completed in.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m5
"""

from datetime import datetime
from unittest.mock import patch

from src.getmoredone import db_manager as db_manager_module
from tests.weekly_tactic_fixtures import (
    make_daily_item,
    make_vps,
    make_week_item,
    seed_ape,
)


def _filed_item(vps, start="2026-02-25", week_start="2026-02-23"):
    ape_id = seed_ape(vps)
    week_end = vps.db_manager.weekly_tactic_engine.calendar.end(week_start).isoformat()
    tactic = make_week_item(vps, ape_id, start=week_start, due=week_end)
    item = make_daily_item(vps, "Task", start=start, due=start)
    stored = vps.db_manager.get_action_item(item.id)
    stored.weekly_tactic_id = tactic.id
    vps.db_manager.update_action_item(stored)
    return ape_id, tactic, vps.db_manager.get_action_item(item.id)


class _FrozenDatetime(datetime):
    """A datetime whose ``now()`` is fixed, so completion week is controllable."""

    frozen = datetime(2026, 3, 12, 16, 45, 3)

    @classmethod
    def now(cls, tz=None):
        return cls.frozen


def _complete_at(manager, item_id, when: datetime):
    frozen = type("Frozen", (_FrozenDatetime,), {"frozen": when})
    with patch.object(db_manager_module, "datetime", frozen):
        return manager.complete_action_item(item_id)


def test_wt_m5a1_completion_refiles_to_current_week(tmp_path):
    """A late completion lands on the completion week, start date moved (WT-D1)."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        assert _complete_at(manager, item.id, datetime(2026, 3, 12, 9, 0)) is True

        after = manager.get_action_item(item.id)
        assert after.status == "completed"
        assert after.weekly_tactic_id != tactic.id, "it should be on the completion week"

        week = manager.get_action_item(after.weekly_tactic_id)
        assert week.start_date == "2026-03-09"
        assert week.start_date <= after.start_date <= week.due_date, "WT-INV1"
        assert week.start_date <= after.due_date <= week.due_date, "WT-INV2"
    finally:
        vps.close()


def test_wt_m5a2_original_week_survives_completion(tmp_path):
    """WT-D3 — the stamp still holds the week it was meant to start in."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)
        assert item.weekly_tactic_start_date == "2026-02-23"

        _complete_at(manager, item.id, datetime(2026, 3, 12, 9, 0))

        assert manager.get_action_item(item.id).weekly_tactic_start_date == "2026-02-23"
    finally:
        vps.close()


def test_wt_m5a3_completion_on_last_day_of_week_is_in_range(tmp_path):
    """completed_at is a full ISO datetime; only its date part names a week.

    Completing at 23:59 on a Sunday must file into that week, not the next —
    which a naive string comparison against the week's end date gets wrong.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        _complete_at(manager, item.id, datetime(2026, 3, 15, 23, 59, 59))

        after = manager.get_action_item(item.id)
        assert "T" in after.completed_at, "completed_at is a datetime, not a date"

        week = manager.get_action_item(after.weekly_tactic_id)
        assert week.start_date == "2026-03-09"
        assert week.due_date == "2026-03-15", "the last day belongs to that week"
        assert week.start_date <= after.start_date <= week.due_date
    finally:
        vps.close()


def test_wt_m5a4_completion_leaves_unlinked_item_unlinked(tmp_path):
    """WT-D2 — completing an item with no tactic attaches nothing."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        seed_ape(vps)
        item = make_daily_item(vps, "Unlinked", start="2026-02-25", due="2026-02-25")

        assert _complete_at(manager, item.id, datetime(2026, 3, 12, 9, 0)) is True

        after = manager.get_action_item(item.id)
        assert after.status == "completed"
        assert after.weekly_tactic_id is None
        assert after.weekly_tactic_start_date is None
        assert after.start_date == "2026-02-25", "its dates must not move either"
        assert manager.db.conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE item_type = 'week'"
        ).fetchone()["n"] == 0
    finally:
        vps.close()


def test_wt_m5a5_completion_across_year_boundary(tmp_path):
    """Completing in the following year triggers the rollover, not a failure."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        _complete_at(manager, item.id, datetime(2027, 1, 13, 10, 0))

        after = manager.get_action_item(item.id)
        week = manager.get_action_item(after.weekly_tactic_id)
        assert week.start_date == "2027-01-11"

        new_ape = manager.db.conn.execute(
            "SELECT year, vision_element_id FROM annual_plan_elements WHERE id = ?",
            (week.annual_plan_element_id,)).fetchone()
        assert new_ape["year"] == 2027
        source = manager.db.conn.execute(
            "SELECT vision_element_id FROM annual_plan_elements WHERE id = ?",
            (ape_id,)).fetchone()
        assert new_ape["vision_element_id"] == source["vision_element_id"]
    finally:
        vps.close()


def test_wt_m5a6_completion_refile_records_history(tmp_path):
    """WT-F8 — the planned start day stays recoverable after the re-file."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        _complete_at(manager, item.id, datetime(2026, 3, 12, 9, 0))

        row = manager.db.conn.execute(
            "SELECT * FROM reschedule_history WHERE item_id = ? AND reason = ?",
            (item.id, "completion_refile"),
        ).fetchone()
        assert row is not None, "the re-file must leave a trail"
        assert row["from_start"] == "2026-02-25"
        after = manager.get_action_item(item.id)
        assert row["to_start"] == after.start_date
        assert row["to_due"] == after.due_date
    finally:
        vps.close()


def test_wt_m5b1_reopen_keeps_completion_week_tactic(tmp_path):
    """WT-M5.B — re-opening does not un-file."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        _complete_at(manager, item.id, datetime(2026, 3, 12, 9, 0))
        completed = manager.get_action_item(item.id)
        completion_week = completed.weekly_tactic_id

        assert manager.uncomplete_action_item(item.id) is True

        reopened = manager.get_action_item(item.id)
        assert reopened.status == "open"
        assert reopened.weekly_tactic_id == completion_week
        assert reopened.weekly_tactic_start_date == "2026-02-23"
    finally:
        vps.close()


def test_wt_m5c1_create_followup_item_also_inherits(tmp_path):
    """The copy path must not lose the item's place in the plan.

    ``create_followup_item`` is now the only copy path: BP4 deleted
    ``complete_and_create``, which had no caller in ``src/``. Its assertions
    live here rather than being deleted with it, so what WT-M5.C.1 actually
    guarantees is still pinned.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        new_id = manager.create_followup_item(item.id)
        assert new_id

        follow_up = manager.get_action_item(new_id)
        assert follow_up.weekly_tactic_id, "the follow-up lost its Weekly Tactic"
        assert follow_up.annual_plan_element_id
        assert follow_up.segment_description_id
        assert follow_up.parent_id == item.id, "it is still a follow-up of the original"

        week = manager.get_action_item(follow_up.weekly_tactic_id)
        assert week.start_date <= follow_up.start_date <= week.due_date, "WT-INV1"
        assert week.start_date <= follow_up.due_date <= week.due_date, "WT-INV2"
        assert follow_up.annual_plan_element_id == week.annual_plan_element_id

        # The stamp. ``_inherit_weekly_lineage`` sets the copy's to None and
        # the re-file then stamps it with the copy's *own* original week — the
        # original item's history stays the original's. This pair was in the
        # deleted complete_and_create test and the note replacing it claimed to
        # have carried its assertions over; these two were not, leaving
        # ``copy.weekly_tactic_start_date = None`` with no test anywhere.
        original = manager.get_action_item(item.id)
        assert original.weekly_tactic_start_date == "2026-02-23", (
            "the copy's re-file rewrote the original's history")
        assert follow_up.weekly_tactic_start_date == week.start_date, (
            "the copy's stamp is not its own week")
    finally:
        vps.close()
