
"""
UI Presence and Regression Tests.
These tests enforce the "Screen Contract" defined in ../docs/AGENT_UI_REGRESSION_POLICY.md.
Every critical user-visible control must be verified here to prevent accidental removal.
"""

import pytest
import customtkinter as ctk
from unittest.mock import MagicMock
from src.getmoredone.screens.item_editor import ItemEditorDialog
from src.getmoredone.screens.project_boards import ProjectBoardsScreen
from src.getmoredone.models import ActionItem, ProjectBoard

@pytest.fixture
def mock_app():
    app = MagicMock()
    app.vps_manager = MagicMock()
    return app

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_defaults.return_value = None
    db.get_all_contacts.return_value = []
    db.get_distinct_groups.return_value = []
    db.get_distinct_categories.return_value = []
    db.get_item_links.return_value = []
    db.get_action_item.return_value = ActionItem(id="test-item", who="Self", title="Test Item")
    db.get_project_boards.return_value = [{"id": "test-board", "title": "Test Board", "status": "active"}]
    db.get_project_board_ids_for_item.return_value = []
    db.get_project_board.return_value = ProjectBoard(id="test-board", title="Test Board", status="active")
    db.get_project_board_items.return_value = []
    db.get_project_board_links.return_value = []
    return db

def test_item_editor_ui_elements_presence(mock_app, mock_db):
    """Verify that all critical UI elements are present in ItemEditorDialog for new items."""
    root = ctk.CTk()
    dialog = ItemEditorDialog(root, mock_db, vps_manager=mock_app.vps_manager)
    
    # Left column fields
    assert hasattr(dialog, "who_entry"), "Missing 'Who' entry"
    # The Context entry was removed: it was never a field of its own, only the
    # front half of the Title string.
    assert not hasattr(dialog, "title_context_entry"), "Context entry is meant to be gone"
    assert hasattr(dialog, "title_entry"), "Missing Title entry"
    assert hasattr(dialog, "description_text"), "Missing Description text"
    assert hasattr(dialog, "next_action_text"), "Missing Next Action text"
    assert hasattr(dialog, "planned_minutes_entry"), "Missing Planned Minutes entry"

    # PL9 — the Action Plan block: where this item sits in the plan.
    assert hasattr(dialog, "action_plan_frame"), "Missing 'Action Plan' block"
    assert hasattr(dialog, "project_label"), "Missing Action Plan Project label"
    assert hasattr(dialog, "weekly_tactic_label"), "Missing Action Plan Wk Tactic label"
    assert hasattr(dialog, "weekly_tactic_start_entry"), "Missing Action Plan Orig. Week entry"
    
    # Tabs
    assert hasattr(dialog, "tabview"), "Missing Tabview"
    tabs = dialog.tabview._tab_dict.keys()
    for tab_name in ["Dates", "Priority", "Organization", "Notes"]:
        assert tab_name in tabs, f"Missing tab: {tab_name}"
        
    # Primary action buttons
    assert hasattr(dialog, "btn_save_close"), "Missing 'Save & Close' button"
    assert hasattr(dialog, "btn_save"), "Missing 'Save' button"
    assert hasattr(dialog, "btn_cancel"), "Missing 'Cancel' button"
    assert hasattr(dialog, "btn_save_new"), "Missing 'Save + New' button"
    
    root.destroy()

def test_item_editor_existing_item_buttons(mock_app, mock_db):
    """Verify that secondary action buttons are present for existing items."""
    root = ctk.CTk()
    dialog = ItemEditorDialog(root, mock_db, item_id="test-item", vps_manager=mock_app.vps_manager)
    
    # Secondary action buttons (only for existing items)
    assert hasattr(dialog, "btn_followup"), "Missing 'Add Follow-up' button"
    assert hasattr(dialog, "btn_create_tasks"), "Missing 'Add Subtasks' button"
    assert hasattr(dialog, "btn_show_related"), "Missing 'Show Related' button"
    assert hasattr(dialog, "btn_set_parent"), "Missing 'Set Parent' button"
    assert hasattr(dialog, "btn_set_weekly"), "Missing 'Set Wk Tactic' button"
    assert hasattr(dialog, "btn_set_project"), "Missing 'Set Project' button"
    assert hasattr(dialog, "btn_complete"), "Missing 'Complete' button"
    assert hasattr(dialog, "btn_delete"), "Missing 'Delete' button"
    # PL10.1 — Duplicate was merged into Add Follow-up; it must not come back
    # as a second, unhardened copy path.
    assert not hasattr(dialog, "btn_duplicate"), "'Duplicate' button is meant to be gone"
    # Cancel exists on the existing-item path too, not only on a new item.
    assert hasattr(dialog, "btn_cancel"), "Missing 'Cancel' button"
    
    root.destroy()

def test_item_editor_layout_contract(mock_app, mock_db):
    """Verify layout constraints in ItemEditorDialog to prevent resizing regressions."""
    root = ctk.CTk()
    dialog = ItemEditorDialog(root, mock_db, vps_manager=mock_app.vps_manager)
    
    # Find the main container
    main_frame = None
    for child in dialog.winfo_children():
        if isinstance(child, ctk.CTkFrame):
            main_frame = child
            break
    
    assert main_frame is not None, "Missing main container frame"

    # Layout: [left col | draggable sash | right col].
    # column 0 (left) fills (weight 1); the sash (col 1) and right col (col 2)
    # are fixed-width (weight 0).
    assert main_frame.grid_columnconfigure(0)["weight"] == 1
    assert main_frame.grid_columnconfigure(1)["weight"] == 0
    assert main_frame.grid_columnconfigure(2)["weight"] == 0

    # A draggable sash sits between the two columns at grid column 1.
    assert hasattr(dialog, "sash"), "Missing draggable sash between columns"
    assert dialog.sash.grid_info()["column"] == 1

    # The right column carries the configured pane width and lives at column 2.
    right_col = dialog.right_col
    assert right_col.grid_info()["column"] == 2
    assert right_col.cget("width") == dialog.right_pane_width == 350, \
        f"Right column width should be 350, got {right_col.cget('width')}"

    # Verify left column row weights (Description and Next Action)
    left_col = dialog.left_col
    assert left_col.grid_info()["column"] == 0, "Left column should be at grid column 0"
    
    # Check that at least two rows in the left column have weight > 0 (resizing rows)
    resizing_rows = 0
    # There are many rows, we just need to ensure the ones holding textboxes expand
    for i in range(20): # Check first 20 rows
        if left_col.grid_rowconfigure(i)["weight"] > 0:
            resizing_rows += 1
            
    assert resizing_rows >= 2, f"Expected at least 2 resizing rows (Description/Next Action), found {resizing_rows}"
    
    root.destroy()

def test_project_board_ui_elements_presence(mock_app, mock_db):
    """Verify that critical UI elements are present in ProjectBoardsScreen."""
    root = ctk.CTk()
    # Ensure a board is selected to show the detail toolbar
    mock_db.get_project_boards.return_value = [{"id": "test-board", "title": "Test Board", "status": "active"}]
    screen = ProjectBoardsScreen(root, mock_db, mock_app)
    screen.selected_board_id = "test-board"
    screen._render_detail()
    
    assert hasattr(screen, "cards_frame"), "Missing cards frame"
    assert hasattr(screen, "items_frame"), "Missing items frame (detail panel)"
    assert hasattr(screen, "detail_title"), "Missing detail title"
    
    # Header buttons
    assert hasattr(screen, "btn_add_project"), "Missing '+ New Project' button"
    assert hasattr(screen, "btn_refresh"), "Missing 'Refresh' button"
    
    # Detail toolbar buttons
    assert hasattr(screen, "btn_create_action"), "Missing 'Create Action Item' button"
    assert hasattr(screen, "btn_link_action"), "Missing 'Link Action Item' button"
    assert hasattr(screen, "btn_edit_project"), "Missing 'Edit Project' button"
    assert hasattr(screen, "btn_create_note"), "Missing 'Create Note' button"
    assert hasattr(screen, "btn_link_note"), "Missing 'Link Note' button"
    assert hasattr(screen, "btn_open_notes"), "Missing 'Open Notes' button"
    
    root.destroy()
