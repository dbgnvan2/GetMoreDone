"""PL8–PL10 — the Action Item editor layout rework.

Spec: docs/implementation_plan_2026-08-19_item_editor_project_link.md

Driven through a real dialog against a mocked DatabaseManager, because the
claims here are about *where* controls sit — a stub cannot answer that. Grid
position is asserted, not mere existence: a pair that renders in the wrong row
is the regression this file exists to catch.
"""

from unittest.mock import MagicMock

import customtkinter as ctk
import pytest

from src.getmoredone.models import ActionItem, ProjectBoard
from src.getmoredone.screens.item_editor import ItemEditorDialog


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_defaults.return_value = None
    db.get_all_contacts.return_value = []
    db.get_distinct_groups.return_value = []
    db.get_distinct_categories.return_value = []
    db.get_item_links.return_value = []
    db.get_action_item.return_value = ActionItem(
        id="test-item", who="Self", title="Test Item")
    db.get_project_board_ids_for_item.return_value = []
    db.get_project_boards.return_value = []
    db.get_project_board.return_value = ProjectBoard(
        id="test-board", title="Test Board", status="active")
    return db


@pytest.fixture
def root():
    window = ctk.CTk()
    yield window
    window.destroy()


def _cell(widget):
    info = widget.grid_info()
    return int(info["row"]), int(info["column"])


# ------------------------------------------------------------------- PL8


def test_pl8_org_tab_has_no_weekly_widgets(root, mock_db):
    """The weekly fields left the Organization tab for the Action Plan block."""
    dialog = ItemEditorDialog(root, mock_db, item_id="test-item")

    assert dialog.weekly_tactic_label.master is dialog.action_plan_frame
    assert dialog.weekly_tactic_start_entry.master is dialog.action_plan_frame

    org_descendants = []

    def walk(widget):
        for child in widget.winfo_children():
            org_descendants.append(child)
            walk(child)

    walk(dialog.tab_org)
    assert dialog.weekly_tactic_label not in org_descendants
    assert dialog.weekly_tactic_start_entry not in org_descendants
    # Group and Category stay.
    assert dialog.group_combo in org_descendants
    assert dialog.category_combo in org_descendants


# ------------------------------------------------------------------- PL9


def test_pl9_action_plan_block_holds_project_and_tactic(root, mock_db):
    """Project, Wk Tactic and the original-week stamp sit together, top left."""
    dialog = ItemEditorDialog(root, mock_db, item_id="test-item")

    assert dialog.project_label.master is dialog.action_plan_frame
    assert dialog.weekly_tactic_label.master is dialog.action_plan_frame
    assert dialog.weekly_tactic_start_entry.master is dialog.action_plan_frame
    # The block is in the left column, not in the tabbed right column.
    assert dialog.action_plan_frame.master is dialog.left_col

    labels = [
        child.cget("text") for child in dialog.action_plan_frame.winfo_children()
        if isinstance(child, ctk.CTkLabel)
    ]
    assert "Action Plan" in labels
    assert "Project:" in labels
    assert "Wk Tactic:" in labels


def test_pl9_1_unlinked_item_shows_no_project(root, mock_db):
    dialog = ItemEditorDialog(root, mock_db, item_id="test-item")
    assert dialog.project_label.cget("text") == ItemEditorDialog.NO_PROJECT_TEXT


# ------------------------------------------------------------------ PL10


def test_pl10_button_pairs_share_a_row(root, mock_db):
    """The pairings from the layout rework, asserted by grid cell."""
    dialog = ItemEditorDialog(root, mock_db, item_id="test-item")

    timer_row, timer_col = _cell(dialog.btn_timer)
    cancel_row, cancel_col = _cell(dialog.btn_cancel)
    assert timer_row == cancel_row, "Cancel is not on the Timer row"
    assert (timer_col, cancel_col) == (0, 1)

    for left, right in [
        (dialog.btn_followup, dialog.btn_create_tasks),
        (dialog.btn_set_parent, dialog.btn_show_related),
        (dialog.btn_set_weekly, dialog.btn_set_project),
        (dialog.btn_complete, dialog.btn_delete),
    ]:
        left_row, left_col = _cell(left)
        right_row, right_col = _cell(right)
        assert left_row == right_row, (
            f"{left.cget('text')} and {right.cget('text')} are not on one row")
        assert (left_col, right_col) == (0, 1)


def test_pl10_1_labels_and_removed_duplicate(root, mock_db):
    dialog = ItemEditorDialog(root, mock_db, item_id="test-item")

    assert dialog.btn_create_tasks.cget("text") == "Add Subtasks"
    assert dialog.btn_set_project.cget("text") == "Set Project"
    assert not hasattr(dialog, "btn_duplicate")


def test_pl10_2_new_item_still_has_cancel(root, mock_db):
    """A new item has no Timer — Cancel must not vanish with it (P25)."""
    dialog = ItemEditorDialog(root, mock_db)

    assert hasattr(dialog, "btn_cancel")
    save_new_row, save_new_col = _cell(dialog.btn_save_new)
    cancel_row, cancel_col = _cell(dialog.btn_cancel)
    assert save_new_row == cancel_row
    assert (save_new_col, cancel_col) == (0, 1)


def test_pl10_3_completed_item_still_has_cancel(root, mock_db):
    """A completed item has no Timer either — Cancel still has a home."""
    mock_db.get_action_item.return_value = ActionItem(
        id="done-item", who="Self", title="Done", status="completed")
    dialog = ItemEditorDialog(root, mock_db, item_id="done-item")

    assert not hasattr(dialog, "btn_timer")
    assert hasattr(dialog, "btn_cancel")
    assert dialog.btn_cancel.grid_info(), "Cancel was created but never placed"


def test_pl10_4_new_item_can_set_a_project_before_it_is_saved(root, mock_db):
    """P25 — the headline case must be reachable from the UI, not just the API.

    Creating an Action Item and filing it under a Project (creating that Project
    if need be) is the whole point of the feature; putting the button behind
    "save it first" would make it unreachable on the screen where it matters.
    """
    dialog = ItemEditorDialog(root, mock_db)

    assert hasattr(dialog, "btn_set_project"), "a new item cannot set a project"
    assert hasattr(dialog, "btn_set_weekly")
    weekly_row, weekly_col = _cell(dialog.btn_set_weekly)
    project_row, project_col = _cell(dialog.btn_set_project)
    assert weekly_row == project_row
    assert (weekly_col, project_col) == (0, 1)


def test_pl10_5_new_item_selection_survives_to_the_save(root, mock_db):
    """The choice made before the first save is held, not discarded."""
    dialog = ItemEditorDialog(root, mock_db)

    dialog.apply_project_selection("test-board")

    assert dialog._selected_project_id == "test-board"
    assert dialog._project_choice_made is True
    assert dialog.project_label.cget("text") == "Test Board"
