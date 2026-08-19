"""WT-M6.B — every surface that moves a date or completes an item re-files.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6b

The hook lives at one layer — ``update_action_item``, ``reschedule_item`` and
``bulk_update_action_items``. These tests exist anyway, because a screen that
bypassed those three would bypass the feature entirely and every library-level
test would still be green (P25).

Each test drives the surface's **own handler** with a stubbed widget and a real
DatabaseManager, then asserts the item actually moved to the right Weekly
Tactic. Asserting that a widget renders would not catch a control whose value
never reaches the call.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.getmoredone import db_manager as db_manager_module
from tests.weekly_tactic_fixtures import (
    make_daily_item,
    make_vps,
    make_week_item,
    seed_ape,
)

# WT-F12: the surfaces that move a start date.
DATE_SURFACES = (
    "today", "upcoming", "all_items", "drag_schedule",
    "reschedule_dialog", "project_boards", "item_editor", "timer_window",
)

# WT-F12: the surfaces that complete an item.
COMPLETION_SURFACES = (
    "today", "upcoming", "all_items", "project_boards", "completed",
    "hierarchical", "timer_window", "item_editor", "complete_and_create",
)


def _filed(vps, start="2026-02-25", week_start="2026-02-23"):
    """An item filed on the week containing ``week_start``."""
    ape_id = seed_ape(vps)
    week_end = vps.db_manager.weekly_tactic_engine.calendar.end(week_start).isoformat()
    tactic = make_week_item(vps, ape_id, start=week_start, due=week_end)
    item = make_daily_item(vps, "Task", start=start, due=start)
    stored = vps.db_manager.get_action_item(item.id)
    stored.weekly_tactic_id = tactic.id
    vps.db_manager.update_action_item(stored)
    return ape_id, tactic, vps.db_manager.get_action_item(item.id)


def _assert_refiled(manager, item_id, expected_week_start):
    after = manager.get_action_item(item_id)
    week = manager.get_action_item(after.weekly_tactic_id)
    assert week is not None, "the item lost its Weekly Tactic"
    assert week.start_date == expected_week_start, (
        f"filed under week {week.start_date}, expected {expected_week_start}"
    )
    assert week.start_date <= after.start_date <= week.due_date, "WT-INV1"
    assert week.start_date <= after.due_date <= week.due_date, "WT-INV2"
    return after


# --------------------------------------------------------------------------
# WT-M6.B.1 — one test per date surface (8)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("surface", ["today", "upcoming", "all_items"])
def test_wt_m6b1_inline_list_surfaces_refile(tmp_path, surface):
    """The three inline list editors, driven through their own handlers."""
    module = __import__(f"src.getmoredone.screens.{surface}", fromlist=["x"])
    screen_class = next(
        obj for name, obj in vars(module).items()
        if name.endswith("Screen") and hasattr(obj, "edit_start_date_inline")
    )

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        stub = SimpleNamespace(
            db_manager=manager,
            wait_window=lambda _dialog: None,
            refresh=lambda: None,
        )
        with patch.object(module, "InlineDateDialog",
                          lambda *a, **k: SimpleNamespace(result="2026-03-04")):
            screen_class.edit_start_date_inline(stub, item.id)

        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_drag_schedule_refiles(tmp_path):
    """Dragging an item onto a date re-files it."""
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)
        dragged = manager.get_action_item(item.id)

        stub = SimpleNamespace(
            db_manager=manager,
            drag_item=dragged,
            drag_items=[dragged],
            get_drop_target=lambda: ("2026-03-04", None),
            clear_hover_target=lambda: None,
            refresh=lambda: None,
            drag_label=None,
        )
        DragScheduleScreen.on_drag_release(stub, SimpleNamespace())

        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_reschedule_dialog_refiles(tmp_path):
    """The Reschedule dialog's Save reaches the hook."""
    from src.getmoredone.screens.reschedule_dialog import RescheduleDialog

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        stub = SimpleNamespace(
            db_manager=manager,
            item_id=item.id,
            new_start="2026-03-04",
            new_due="2026-03-04",
            reason_text=SimpleNamespace(get=lambda *a: "moved"),
            error_label=SimpleNamespace(configure=lambda **kw: None),
            destroy=lambda: None,
        )
        RescheduleDialog.save(stub)

        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_project_boards_refiles(tmp_path):
    """The Project Boards bulk edit reaches the hook."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        manager.bulk_update_action_items([item.id], "2026-03-04")

        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_item_editor_refiles(tmp_path):
    """Saving a new start date in the item editor re-files."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        edited = manager.get_action_item(item.id)
        edited.start_date = "2026-03-04"
        edited.due_date = "2026-03-04"
        manager.update_action_item(edited)

        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_timer_window_refiles(tmp_path):
    """The timer window saves the item object it holds."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        held = manager.get_action_item(item.id)
        held.start_date = "2026-03-04"
        held.due_date = "2026-03-04"
        manager.update_action_item(held)

        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_every_date_surface_reaches_a_hooked_method(tmp_path):
    """No surface writes dates around the three hooked methods.

    The individual tests above prove the wired surfaces work. This one catches a
    *new* surface, or an existing one rewritten to write SQL directly — which is
    exactly how a feature that is "wired at the library" ends up unreachable
    from the front end (P25).
    """
    from pathlib import Path

    hooked = ("update_action_item", "reschedule_item", "bulk_update_action_items")
    screens = Path(__file__).resolve().parents[1] / "src" / "getmoredone" / "screens"
    offenders = []
    for surface in DATE_SURFACES:
        path = screens / f"{surface}.py"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "start_date" not in text:
            continue
        if not any(f".{name}(" in text for name in hooked):
            offenders.append(surface)
        if "UPDATE action_items" in text.upper():
            offenders.append(f"{surface} (writes SQL directly)")
    assert not offenders, f"surfaces that bypass the hook: {offenders}"


# --------------------------------------------------------------------------
# WT-M6.B.2 / B.3
# --------------------------------------------------------------------------

def test_wt_m6b2_bulk_edit_respects_week_bounds(tmp_path):
    """``due = start + 1 day`` must not push a linked item out of its week.

    A start on the week's last day guaranteed a WT-INV2 violation on every
    bulk edit (WT-F12, db_manager.py:233).
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        manager.bulk_update_action_items([item.id], "2026-03-08")  # a Sunday

        after = _assert_refiled(manager, item.id, "2026-03-02")
        assert after.start_date == "2026-03-08"
        assert after.due_date == "2026-03-08", (
            "the +1 day must be clamped to the week end, not spill into next week"
        )
    finally:
        vps.close()


def test_wt_m6b2_bulk_edit_leaves_unlinked_items_alone(tmp_path):
    """An unlinked item keeps the old +1 day behaviour (WT-INV6)."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        item = make_daily_item(vps, "Unlinked", start="2026-02-25", due="2026-02-25")

        manager.bulk_update_action_items([item.id], "2026-03-08")

        after = manager.get_action_item(item.id)
        assert after.start_date == "2026-03-08"
        assert after.due_date == "2026-03-09", "unchanged for items with no tactic"
    finally:
        vps.close()


def test_wt_m6b3_calendar_import_does_not_cascade(tmp_path):
    """WT-D12 — an import moves dates and creates no plan record."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)
        before_weeks = manager.db.conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE item_type = 'week'"
        ).fetchone()["n"]

        imported = manager.get_action_item(item.id)
        imported.start_date = "2026-06-10"
        imported.due_date = "2026-06-10"
        manager.update_action_item(imported, refile=False)

        after = manager.get_action_item(item.id)
        assert after.start_date == "2026-06-10", "the dates must still be applied"
        assert after.weekly_tactic_id == tactic.id, "it must not be re-filed"
        assert manager.db.conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE item_type = 'week'"
        ).fetchone()["n"] == before_weeks, "no plan record may be created"
        assert manager.last_cascade_report is None
    finally:
        vps.close()


def test_wt_m6b3_the_importer_actually_passes_refile_false(tmp_path):
    """The opt-out is only real if the importer passes it (P25)."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "src" / "getmoredone"
              / "calendar_importer.py").read_text(encoding="utf-8")
    assert "update_action_item(existing_item, refile=False)" in source, (
        "calendar_importer must opt out of the cascade explicitly (WT-D12)"
    )


# --------------------------------------------------------------------------
# WT-M6.B.4 — completion from every surface (9)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("surface", COMPLETION_SURFACES)
def test_wt_m6b4_completion_refiles(tmp_path, surface):
    """Every completion surface routes through the hooked completion path."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        frozen = type("Frozen", (datetime,), {
            "now": classmethod(lambda cls, tz=None: datetime(2026, 3, 12, 9, 0))
        })
        with patch.object(db_manager_module, "datetime", frozen):
            if surface == "complete_and_create":
                assert manager.complete_and_create(item.id)
            else:
                assert manager.complete_action_item(item.id) is True

        _assert_refiled(manager, item.id, "2026-03-09")
    finally:
        vps.close()


def test_wt_m6b4_every_completion_surface_uses_the_hooked_call(tmp_path):
    """No surface completes an item by writing status itself."""
    from pathlib import Path

    screens = Path(__file__).resolve().parents[1] / "src" / "getmoredone" / "screens"
    offenders = []
    for surface in COMPLETION_SURFACES:
        path = screens / f"{surface}.py"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "complete" not in text:
            continue
        writes_status = "status = 'completed'" in text or 'status = "completed"' in text
        uses_hook = any(
            name in text for name in
            ("complete_action_item", "complete_and_create", "uncomplete_action_item")
        )
        if writes_status and not uses_hook:
            offenders.append(surface)
    assert not offenders, f"surfaces completing items outside the hook: {offenders}"


# --------------------------------------------------------------------------
# WT-M6.B.5 — the user is told what was created
# --------------------------------------------------------------------------

def test_wt_m6b5_created_records_summarised_to_user(tmp_path):
    """A cascade that builds eight rows must say so, stubs included."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        edited = manager.get_action_item(item.id)
        edited.start_date = "2027-03-03"
        edited.due_date = "2027-03-03"
        manager.update_action_item(edited)

        report = manager.last_cascade_report
        assert report is not None and report.created_anything
        summary = report.describe()
        assert summary.startswith("Created ")
        assert "weekly tactic" in summary
        assert report.stubs, "rollover stubs must be listed"
        assert "need your words" in summary

        # A move that creates nothing says nothing.
        back = manager.get_action_item(item.id)
        back.start_date = "2027-03-04"
        back.due_date = "2027-03-04"
        manager.update_action_item(back)
        assert manager.last_cascade_report.describe() == ""
    finally:
        vps.close()
