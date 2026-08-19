"""WT-M3 — attaching, changing and detaching a Weekly Tactic.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m3
"""

from datetime import date

from src.getmoredone.models import ActionItem
from src.getmoredone.weekly_tactic import bring_into_week, tactic_of
from tests.weekly_tactic_fixtures import (
    make_daily_item,
    make_vps,
    make_week_item,
    seed_ape,
)


def _attach(vps, item, tactic):
    stored = vps.db_manager.get_action_item(item.id)
    stored.weekly_tactic_id = tactic.id
    vps.db_manager.update_action_item(stored)
    return vps.db_manager.get_action_item(item.id)


# --------------------------------------------------------------------------
# WT-M3.A — the original-week stamp
# --------------------------------------------------------------------------

def test_wt_m3a1_first_attach_stamps_original_week(tmp_path):
    """The first attach records the week the item was meant to start in."""
    vps = make_vps(tmp_path)
    try:
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = make_daily_item(vps, "Task", start="2026-02-25", due="2026-02-25")

        stored = _attach(vps, item, tactic)
        assert stored.weekly_tactic_id == tactic.id
        assert stored.weekly_tactic_start_date == "2026-02-23"
    finally:
        vps.close()


def test_wt_m3a1_attach_at_create_time_stamps_too(tmp_path):
    """An item created already attached is an attach, and must be stamped.

    Found by driving the real item editor: every other test attaches through
    ``update_action_item``, so the create path was never exercised and an item
    born with a tactic carried no original-week stamp at all — the Org tab
    showed an empty field with nothing wrong anywhere in the DB tests.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")

        item = make_daily_item(vps, "Born attached", start="2026-02-25",
                               due="2026-02-25", weekly_tactic_id=tactic.id)

        stored = manager.get_action_item(item.id)
        assert stored.weekly_tactic_id == tactic.id
        assert stored.weekly_tactic_start_date == "2026-02-23"
        assert stored.annual_plan_element_id == ape_id, "WT-M4.A.3 on the create path"
    finally:
        vps.close()


def test_wt_m3a1_create_attached_outside_the_week_is_brought_into_range(tmp_path):
    """Creating attached but out of range re-files, exactly as an update would."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")

        item = make_daily_item(vps, "Far away", start="2026-04-08",
                               due="2026-04-08", weekly_tactic_id=tactic.id)

        stored = manager.get_action_item(item.id)
        week = manager.get_action_item(stored.weekly_tactic_id)
        assert week.start_date == "2026-04-06", "it files under the week it starts in"
        assert week.start_date <= stored.start_date <= week.due_date
    finally:
        vps.close()


def test_wt_m3a2_retarget_preserves_original_week(tmp_path):
    """WT-INV3 — moving to another week never moves the stamp."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        first = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        make_week_item(vps, ape_id, start="2026-03-09", due="2026-03-15", title="Later")
        item = make_daily_item(vps, "Task", start="2026-02-25", due="2026-02-25")
        _attach(vps, item, first)

        moved = manager.get_action_item(item.id)
        moved.start_date = "2026-03-11"
        moved.due_date = "2026-03-11"
        manager.update_action_item(moved)

        after = manager.get_action_item(item.id)
        assert after.start_date == "2026-03-11"
        assert after.weekly_tactic_id != first.id, "it should be on the new week"
        assert after.weekly_tactic_start_date == "2026-02-23", (
            "the stamp records where it was originally meant to start"
        )
    finally:
        vps.close()


def test_wt_m3a3_manual_override_persists(tmp_path):
    """WT-D3 — a hand-set stamp survives later saves."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = make_daily_item(vps, "Task", start="2026-02-25", due="2026-02-25")
        _attach(vps, item, tactic)

        edited = manager.get_action_item(item.id)
        edited.weekly_tactic_start_date = "2026-01-05"
        manager.update_action_item(edited)

        again = manager.get_action_item(item.id)
        again.next_action = "an ordinary later save"
        manager.update_action_item(again)

        assert manager.get_action_item(item.id).weekly_tactic_start_date == "2026-01-05"
    finally:
        vps.close()


def test_wt_m3a4_stamp_survives_tactic_deletion_and_is_surfaced(tmp_path):
    """ON DELETE SET NULL unlinks the item; the stamp is kept and reported."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = make_daily_item(vps, "Task", start="2026-02-25", due="2026-02-25")
        _attach(vps, item, tactic)

        manager.delete_action_item(tactic.id)

        orphan = manager.get_action_item(item.id)
        assert orphan.weekly_tactic_id is None
        assert orphan.weekly_tactic_start_date == "2026-02-23"

        # Surfaced rather than silently reused.
        engine = manager.weekly_tactic_engine
        assert engine.stale_stamp(orphan) == "2026-02-23"

        # A later re-attach does not overwrite it.
        replacement = make_week_item(vps, ape_id, start="2026-03-09",
                                     due="2026-03-15", title="New")
        reattached = _attach(vps, orphan, replacement)
        assert reattached.weekly_tactic_start_date == "2026-02-23"
        assert engine.stale_stamp(reattached) is None
    finally:
        vps.close()


# --------------------------------------------------------------------------
# WT-M3.B — bringing dates into range
# --------------------------------------------------------------------------

def test_wt_m3b1_whole_week_shift_preserves_weekday():
    """A Thursday item moved one week forward stays a Thursday."""
    item = ActionItem(who="Self", title="Thursday task",
                      start_date="2026-02-26", due_date="2026-02-27")
    assert date.fromisoformat(item.start_date).weekday() == 3

    bring_into_week(item, date(2026, 3, 2), date(2026, 3, 8))

    assert item.start_date == "2026-03-05"
    assert date.fromisoformat(item.start_date).weekday() == 3
    assert item.due_date == "2026-03-06"


def test_wt_m3b2_multi_week_item_due_date_clamped():
    """WT-D5 — an item never spans weeks; the clamp beats weekday preservation."""
    item = ActionItem(who="Self", title="Long task",
                      start_date="2026-02-24", due_date="2026-03-10")

    bring_into_week(item, date(2026, 3, 2), date(2026, 3, 8))

    assert item.start_date == "2026-03-03", "the start keeps its weekday"
    assert item.due_date == "2026-03-08", "the due date is clamped to the week end"
    assert date.fromisoformat(item.due_date).weekday() != 1, (
        "the clamp overrides weekday preservation"
    )


def test_wt_m3b3_invariants_hold_after_retarget(tmp_path):
    """WT-INV1 and WT-INV2 both hold after any attach or change."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = make_daily_item(vps, "Task", start="2026-02-25", due="2026-03-14")
        _attach(vps, item, tactic)

        for target in ("2026-03-05", "2026-01-14", "2027-01-06"):
            stored = manager.get_action_item(item.id)
            stored.start_date = target
            manager.update_action_item(stored)

            after = manager.get_action_item(item.id)
            week = manager.get_action_item(after.weekly_tactic_id)
            assert week.start_date <= after.start_date <= week.due_date, (
                f"WT-INV1 violated after moving to {target}"
            )
            assert week.start_date <= after.due_date <= week.due_date, (
                f"WT-INV2 violated after moving to {target}"
            )
    finally:
        vps.close()


def test_wt_m3b4_null_dates_handled():
    """A NULL start or due is handled explicitly, not by arithmetic on None."""
    no_start = ActionItem(who="Self", title="No start",
                          start_date=None, due_date="2026-03-04")
    bring_into_week(no_start, date(2026, 3, 2), date(2026, 3, 8))
    assert no_start.start_date == "2026-03-02"
    assert no_start.due_date == "2026-03-08"

    no_due = ActionItem(who="Self", title="No due",
                        start_date="2026-02-26", due_date=None)
    bring_into_week(no_due, date(2026, 3, 2), date(2026, 3, 8))
    assert no_due.start_date == "2026-03-05"
    assert no_due.due_date is None, "a missing due date stays missing"

    neither = ActionItem(who="Self", title="Neither", start_date=None, due_date=None)
    bring_into_week(neither, date(2026, 3, 2), date(2026, 3, 8))
    assert neither.start_date == "2026-03-02"
    assert neither.due_date is None


# --------------------------------------------------------------------------
# WT-M3.C — attach replaces, detach leaves dates alone
# --------------------------------------------------------------------------

def test_wt_m3c1_attach_preserves_daily_parent(tmp_path):
    """The WT-F9 regression: attaching a tactic must not clear the subtask parent."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        parent = make_daily_item(vps, "Parent")
        child = make_daily_item(vps, "Child", start="2026-02-25", due="2026-02-25",
                                parent_id=parent.id)

        stored = _attach(vps, child, tactic)
        assert stored.parent_id == parent.id
        assert stored.weekly_tactic_id == tactic.id
    finally:
        vps.close()


def test_wt_m3c2_set_parent_preserves_tactic(tmp_path):
    """The reverse WT-F9 regression: Set Parent must not clear the tactic."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        parent = make_daily_item(vps, "Parent")
        child = make_daily_item(vps, "Child", start="2026-02-25", due="2026-02-25")
        _attach(vps, child, tactic)

        stored = manager.get_action_item(child.id)
        stored.parent_id = parent.id
        manager.update_action_item(stored)

        after = manager.get_action_item(child.id)
        assert after.parent_id == parent.id
        assert after.weekly_tactic_id == tactic.id
    finally:
        vps.close()


def test_wt_m3c3_detach_leaves_dates_alone(tmp_path):
    """Detaching clears the link only — dates and stamp are untouched."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = make_daily_item(vps, "Task", start="2026-02-25", due="2026-02-26")
        attached = _attach(vps, item, tactic)
        dates = (attached.start_date, attached.due_date, attached.weekly_tactic_start_date)

        detached = manager.get_action_item(item.id)
        detached.weekly_tactic_id = None
        manager.update_action_item(detached)

        after = manager.get_action_item(item.id)
        assert after.weekly_tactic_id is None
        assert (after.start_date, after.due_date, after.weekly_tactic_start_date) == dates
    finally:
        vps.close()


# --------------------------------------------------------------------------
# WT-M3.D — an item with no tactic is never touched
# --------------------------------------------------------------------------

def test_wt_m3d1_single_tactic_predicate(tmp_path):
    """One named predicate decides whether an item is week-filed (WT-INV6)."""
    from pathlib import Path

    assert tactic_of(None) is None
    assert tactic_of(ActionItem(who="a", title="b")) is None
    assert tactic_of(ActionItem(who="a", title="b", weekly_tactic_id="")) is None
    assert tactic_of(ActionItem(who="a", title="b", weekly_tactic_id="w-1")) == "w-1"

    # And nothing decides it for itself by reading the column directly.
    src = Path(__file__).resolve().parents[1] / "src" / "getmoredone"
    offenders = []
    for path in sorted(src.rglob("*.py")):
        if path.name in {"weekly_tactic.py", "models.py", "db_manager.py",
                         "weekly_tactic_migrations.py", "weekly_tactic_maintenance.py"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if "item.weekly_tactic_id" in code and "weekly_tactic_id =" not in code:
                offenders.append(f"{path.name}:{number}")
    assert not offenders, (
        f"these read the tactic link directly instead of asking tactic_of(): {offenders}"
    )


def test_wt_m3d2_unlinked_item_untouched_on_every_path(tmp_path):
    """WT-INV6 across update_action_item, reschedule_item and bulk_update."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        seed_ape(vps)   # a lineage exists, but this item is not part of it

        for label, mutate in (
            ("update", lambda i: _plain_update(manager, i, "2026-06-10")),
            ("reschedule", lambda i: manager.reschedule_item(i.id, "2026-06-10",
                                                            "2026-06-11", reason="t")),
            ("bulk", lambda i: manager.bulk_update_action_items([i.id], "2026-06-10")),
        ):
            item = make_daily_item(vps, f"Unlinked {label}",
                                   start="2026-02-25", due="2026-02-26")
            mutate(item)

            after = manager.get_action_item(item.id)
            assert after.weekly_tactic_id is None, f"{label} attached a tactic"
            assert after.weekly_tactic_start_date is None, f"{label} stamped an item"
            assert after.start_date == "2026-06-10", f"{label} did not apply the date"
            assert manager.last_cascade_report is None, f"{label} ran a cascade"

        # ...and no plan records were invented for any of them.
        assert manager.db.conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE item_type = 'week'"
        ).fetchone()["n"] == 0
    finally:
        vps.close()


def _plain_update(manager, item, start):
    stored = manager.get_action_item(item.id)
    stored.start_date = start
    stored.due_date = start
    manager.update_action_item(stored)
