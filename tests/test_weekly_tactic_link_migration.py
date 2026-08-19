"""WT-M1.D — the Weekly Tactic link gets its own column.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1d

Until this migration ran, ``parent_id`` served two relationships at once: 94
ordinary daily-to-daily nesting rows and 49 week-to-daily tactic links (WT-F9).
Writing either silently destroyed the other.
"""

import pytest

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem
from src.getmoredone.weekly_tactic_migrations import (
    migrate_parent_links_to_weekly_tactic,
)
from tests.weekly_tactic_fixtures import make_daily_item, make_vps, make_week_item, seed_ape


def _legacy_parent_link(vps, child, parent):
    """Write the pre-migration shape: the tactic link living in parent_id."""
    vps.db_manager.db.conn.execute(
        "UPDATE action_items SET parent_id = ?, weekly_tactic_id = NULL WHERE id = ?",
        (parent.id, child.id),
    )
    vps.db_manager.db.conn.commit()


def test_wt_m1d1_tactic_links_migrated_nesting_preserved(tmp_path):
    """Week links move onto weekly_tactic_id; daily nesting is untouched."""
    vps = make_vps(tmp_path)
    manager = vps.db_manager
    try:
        week = make_week_item(vps, seed_ape(vps))
        week_children = [make_daily_item(vps, f"Week child {i}") for i in range(3)]
        for child in week_children:
            _legacy_parent_link(vps, child, week)

        nest_parent = make_daily_item(vps, "Parent task")
        nest_children = [make_daily_item(vps, f"Subtask {i}") for i in range(2)]
        for child in nest_children:
            _legacy_parent_link(vps, child, nest_parent)

        report = migrate_parent_links_to_weekly_tactic(manager.db.conn)
        manager.db.conn.commit()

        assert report["moved"] == 3
        assert report["nesting_preserved"] == 2
        assert set(report["moved_ids"]) == {c.id for c in week_children}

        for child in week_children:
            row = manager.get_action_item(child.id)
            assert row.weekly_tactic_id == week.id
            assert row.parent_id is None, "the tactic link must leave parent_id free"

        for child in nest_children:
            row = manager.get_action_item(child.id)
            assert row.parent_id == nest_parent.id
            assert row.weekly_tactic_id is None
    finally:
        vps.close()


def test_wt_m1d2_parent_and_tactic_coexist(tmp_path):
    """An item can be a subtask and week-filed at once; neither clears the other."""
    vps = make_vps(tmp_path)
    manager = vps.db_manager
    try:
        week = make_week_item(vps, seed_ape(vps))
        parent = make_daily_item(vps, "Parent task")
        child = make_daily_item(vps, "Child task")

        child.parent_id = parent.id
        manager.update_action_item(child)
        assert manager.get_action_item(child.id).parent_id == parent.id

        # Attaching a tactic must not disturb the daily parent (the WT-F9 bug).
        child = manager.get_action_item(child.id)
        child.weekly_tactic_id = week.id
        manager.update_action_item(child)

        stored = manager.get_action_item(child.id)
        assert stored.parent_id == parent.id
        assert stored.weekly_tactic_id == week.id

        # ...and re-parenting must not disturb the tactic (the reverse bug).
        other_parent = make_daily_item(vps, "Other parent")
        stored.parent_id = other_parent.id
        manager.update_action_item(stored)

        again = manager.get_action_item(child.id)
        assert again.parent_id == other_parent.id
        assert again.weekly_tactic_id == week.id
    finally:
        vps.close()


def test_wt_m1d3_tactic_must_be_week_item(tmp_path):
    """WT-INV4 — weekly_tactic_id pointing at a non-week row is rejected."""
    vps = make_vps(tmp_path)
    manager = vps.db_manager
    try:
        daily = make_daily_item(vps, "Not a tactic")
        victim = make_daily_item(vps, "Victim")

        victim.weekly_tactic_id = daily.id
        with pytest.raises(ValueError, match="not a week item"):
            manager.update_action_item(victim)

        victim = manager.get_action_item(victim.id)
        assert victim.weekly_tactic_id is None

        missing = manager.get_action_item(victim.id)
        missing.weekly_tactic_id = "no-such-id"
        with pytest.raises(ValueError, match="does not exist"):
            manager.update_action_item(missing)

        selfref = manager.get_action_item(victim.id)
        selfref.weekly_tactic_id = selfref.id
        with pytest.raises(ValueError, match="its own Weekly Tactic"):
            manager.update_action_item(selfref)

        # The create path is guarded too, not only the update path.
        bad = ActionItem(who="Self", title="Bad on create",
                         weekly_tactic_id=daily.id)
        with pytest.raises(ValueError, match="not a week item"):
            manager.create_action_item(bad, apply_defaults=False)
    finally:
        vps.close()


def test_wt_m1d4_link_migration_idempotent(tmp_path):
    """A second run moves nothing and says so."""
    vps = make_vps(tmp_path)
    manager = vps.db_manager
    try:
        week = make_week_item(vps, seed_ape(vps))
        child = make_daily_item(vps)
        _legacy_parent_link(vps, child, week)

        first = migrate_parent_links_to_weekly_tactic(manager.db.conn)
        manager.db.conn.commit()
        assert first["moved"] == 1

        second = migrate_parent_links_to_weekly_tactic(manager.db.conn)
        manager.db.conn.commit()
        assert second["moved"] == 0
        assert second["moved_ids"] == []

        stored = manager.get_action_item(child.id)
        assert stored.weekly_tactic_id == week.id
        assert stored.parent_id is None
    finally:
        vps.close()


def test_wt_m1d_migration_on_populated_db_run_two(tmp_path):
    """Dirty-state (P8): reopening a populated database changes nothing.

    Clean-state tests say the migration works on an empty file. The interesting
    run is the second one, against a database that already holds the user's work.
    """
    vps = make_vps(tmp_path, "populated.db")
    db_path = vps.db_manager.db.db_path
    manager = vps.db_manager
    try:
        week = make_week_item(vps, seed_ape(vps))
        linked = make_daily_item(vps, "Linked")
        linked.weekly_tactic_id = week.id
        manager.update_action_item(linked)

        nest_parent = make_daily_item(vps, "Parent")
        nested = make_daily_item(vps, "Nested")
        nested.parent_id = nest_parent.id
        manager.update_action_item(nested)

        before = {
            row["id"]: (row["parent_id"], row["weekly_tactic_id"])
            for row in manager.db.conn.execute(
                "SELECT id, parent_id, weekly_tactic_id FROM action_items"
            )
        }
    finally:
        vps.close()

    reopened = DatabaseManager(str(db_path))
    try:
        report = reopened.db.weekly_tactic_migration_report
        assert report is not None
        assert report["link_column_added"] is False
        assert report["link_migration"]["moved"] == 0

        after = {
            row["id"]: (row["parent_id"], row["weekly_tactic_id"])
            for row in reopened.db.conn.execute(
                "SELECT id, parent_id, weekly_tactic_id FROM action_items"
            )
        }
        assert after == before, f"run #2 altered links: {before} -> {after}"
    finally:
        reopened.close()
