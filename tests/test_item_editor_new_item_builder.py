"""BP3 — one builder assembles a new Action Item, whichever button saves it.

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#bp3

``save_item`` (the Save button) and ``save_item_if_needed`` ("Create Note",
"Link Note", the calendar dialog) both insert a brand-new row. They used to
assemble its fields separately and had already drifted twice — the Project
link, then the order in which the Annual Plan Element is written. These tests
compare the two rows field by field on a fully-populated form, so a third drift
fails here rather than in the app.

Real dialogs on a real DatabaseManager: a stub cannot show that a control which
renders is actually reaching the database (P25).
"""

import customtkinter as ctk
import pytest

from src.getmoredone.models import ProjectBoard
from src.getmoredone.screens.item_editor import ItemEditorDialog
from tests.weekly_tactic_fixtures import make_vps, make_week_item, seed_ape, seed_second_ape


# Every column an insert can set. Compared wholesale rather than one-by-one so
# a field added later is covered without anyone remembering to add it here.
IGNORED_COLUMNS = {"id", "created_at", "updated_at"}


@pytest.fixture
def root():
    win = ctk.CTk()
    win.withdraw()
    yield win
    win.destroy()


def _row(manager, item_id):
    row = manager.db.conn.execute(
        "SELECT * FROM action_items WHERE id = ?", (item_id,)).fetchone()
    return {k: row[k] for k in row.keys() if k not in IGNORED_COLUMNS}


def _fill(dialog, board_id=None, tactic_id=None):
    """Populate every field the editor offers on a new item."""
    dialog.who_var.set("Self")
    dialog.title_entry.insert(0, "Fully populated task")
    dialog.description_text.insert("1.0", "A description")
    dialog.next_action_text.insert("1.0", "The next action")
    dialog.start_date_entry.insert(0, "2026-02-25")
    dialog.due_date_entry.insert(0, "2026-02-27")
    dialog.is_meeting_var.set(True)
    dialog.importance_var.set("High (10)")
    dialog.urgency_var.set("Medium (5)")
    dialog.size_var.set("L (8)")
    dialog.value_var.set("XL (16)")
    dialog.group_var.set("Group A")
    dialog.category_var.set("Category B")
    dialog.planned_minutes_entry.insert(0, "45")
    dialog.weekly_tactic_start_var.set("2026-01-05")
    if tactic_id:
        dialog.pending_weekly_tactic_id = tactic_id
    if board_id:
        dialog.apply_project_selection(board_id)
    return dialog


def test_bp3_both_insert_paths_store_the_same_row(tmp_path, root):
    """A fully-populated form must produce identical rows either way."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = ProjectBoard(title="Website Rebuild", annual_plan_element_id=ape_id)
        manager.create_project_board(board)

        via_save = _fill(ItemEditorDialog(root, manager, vps_manager=vps), board.id)
        assert via_save.save_item() is True, via_save.error_label.cget("text")

        via_note = _fill(ItemEditorDialog(root, manager, vps_manager=vps), board.id)
        assert via_note.save_item_if_needed() is True, via_note.error_label.cget("text")

        saved = _row(manager, via_save.item_id)
        noted = _row(manager, via_note.item_id)
        differences = {k: (saved[k], noted[k]) for k in saved if saved[k] != noted[k]}
        assert not differences, f"the two insert paths disagree: {differences}"

        # And the row is the form, not a subset of it.
        assert saved["title"] == "Fully populated task"
        assert saved["planned_minutes"] == 45
        assert saved["weekly_tactic_start_date"] == "2026-01-05"
        assert saved["is_meeting"] == 1
        assert saved["annual_plan_element_id"] == ape_id
    finally:
        vps.close()


def test_bp3_both_insert_paths_agree_with_a_tactic_and_a_project(tmp_path, root):
    """The case that drifted: a Weekly Tactic and a Project chosen together.

    The tactic re-file writes its own Annual Plan Element onto the row, so
    whichever of the two is applied last wins. One builder, one order.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        board_ape = seed_ape(vps)
        tactic_ape = seed_second_ape(vps)
        board = ProjectBoard(title="Website Rebuild", annual_plan_element_id=board_ape)
        manager.create_project_board(board)
        tactic = make_week_item(vps, tactic_ape)

        via_save = _fill(
            ItemEditorDialog(root, manager, vps_manager=vps), board.id, tactic.id)
        assert via_save.save_item() is True, via_save.error_label.cget("text")

        via_note = _fill(
            ItemEditorDialog(root, manager, vps_manager=vps), board.id, tactic.id)
        assert via_note.save_item_if_needed() is True, via_note.error_label.cget("text")

        saved = _row(manager, via_save.item_id)
        noted = _row(manager, via_note.item_id)
        differences = {k: (saved[k], noted[k]) for k in saved if saved[k] != noted[k]}
        assert not differences, f"the two insert paths disagree: {differences}"

        assert saved["weekly_tactic_id"] == tactic.id
        assert saved["annual_plan_element_id"] == board_ape, "the project should win the APE"
        assert manager.get_project_board_ids_for_item(via_note.item_id) == [board.id]
    finally:
        vps.close()


def test_bp3_a_followed_tactic_leaves_no_stale_in_memory_item(tmp_path, root):
    """``follow_tactic`` moves the row's dates; the editor must re-read it.

    Otherwise the dialog goes on displaying what it sent, not what was stored
    (P6 — a label with no row behind it).
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        # A tactic in a *different* week from the form's dates, so following it
        # genuinely moves the row. A tactic covering the same week would leave
        # the two copies equal by accident and prove nothing.
        tactic = make_week_item(vps, ape_id, start="2026-03-09", due="2026-03-15")

        dialog = _fill(ItemEditorDialog(root, manager, vps_manager=vps), tactic_id=tactic.id)
        assert dialog.save_item() is True, dialog.error_label.cget("text")

        stored = manager.get_action_item(dialog.item_id)
        assert stored.start_date != "2026-02-25", (
            "follow_tactic did not move the row, so this test proves nothing")
        assert dialog.item.start_date == stored.start_date
        assert dialog.item.annual_plan_element_id == stored.annual_plan_element_id
    finally:
        vps.close()


def test_bp3_the_pending_tactic_is_consumed_by_the_insert(tmp_path, root):
    """A tactic already applied must not be applied again on the next save."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id)

        dialog = _fill(ItemEditorDialog(root, manager, vps_manager=vps), tactic_id=tactic.id)
        assert dialog.save_item() is True, dialog.error_label.cget("text")

        assert dialog.pending_weekly_tactic_id is None
        assert dialog._follow_chosen_tactic is False
    finally:
        vps.close()
