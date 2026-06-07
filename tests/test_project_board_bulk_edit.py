"""Tests for project board bulk edit functionality."""

import pytest
from datetime import date, timedelta
from src.getmoredone.models import ActionItem, ProjectBoard
from src.getmoredone.db_manager import DatabaseManager


@pytest.fixture
def db_manager(tmp_path):
    """Create a temporary database for testing."""
    db_path = str(tmp_path / "test_getmoredone.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


@pytest.fixture
def sample_project_board(db_manager):
    """Create a sample project board."""
    board = ProjectBoard(title="Test Project")
    board_id = db_manager.create_project_board(board)
    return db_manager.get_project_board(board_id)


@pytest.fixture
def sample_action_items(db_manager, sample_project_board):
    """Create sample action items linked to project board."""
    items = []
    for i in range(3):
        item = ActionItem(
            who="Test User",
            title=f"Task {i+1}",
            importance=3 + i,
            urgency=4,
            size=3,
            value=3,
            status="open",
        )
        item_id = db_manager.create_action_item(item)
        db_manager.link_action_item_to_project_board(sample_project_board.id, item_id)
        items.append(db_manager.get_action_item(item_id))
    return items


class TestBulkUpdateActionItems:
    """Test bulk_update_action_items database method."""

    def test_bulk_update_start_date_only(self, db_manager, sample_action_items):
        """AC6: Update only start_date, preserve priority."""
        # Arrange
        item_ids = [item.id for item in sample_action_items]
        new_start_date = (date.today() + timedelta(days=5)).isoformat()
        original_importance = [item.importance for item in sample_action_items]

        # Act
        db_manager.bulk_update_action_items(item_ids, start_date=new_start_date, priority=None)

        # Assert
        updated_items = [db_manager.get_action_item(item_id) for item_id in item_ids]
        for i, item in enumerate(updated_items):
            assert item.start_date == new_start_date, f"Item {i} start_date mismatch"
            assert item.importance == original_importance[i], f"Item {i} importance should not change"

    def test_bulk_update_priority_only(self, db_manager, sample_action_items):
        """AC6: Update only priority, preserve start_date."""
        # Arrange
        item_ids = [item.id for item in sample_action_items]
        new_priority = 7
        original_start_dates = [item.start_date for item in sample_action_items]

        # Act
        db_manager.bulk_update_action_items(item_ids, start_date=None, priority=new_priority)

        # Assert
        updated_items = [db_manager.get_action_item(item_id) for item_id in item_ids]
        for i, item in enumerate(updated_items):
            assert item.importance == new_priority, f"Item {i} priority mismatch"
            assert item.start_date == original_start_dates[i], f"Item {i} start_date should not change"

    def test_bulk_update_both_fields(self, db_manager, sample_action_items):
        """AC3 & AC7: Update both start_date and priority."""
        # Arrange
        item_ids = [item.id for item in sample_action_items]
        new_start_date = (date.today() + timedelta(days=10)).isoformat()
        new_priority = 9

        # Act
        db_manager.bulk_update_action_items(item_ids, start_date=new_start_date, priority=new_priority)

        # Assert
        updated_items = [db_manager.get_action_item(item_id) for item_id in item_ids]
        for item in updated_items:
            assert item.start_date == new_start_date
            assert item.importance == new_priority

    def test_due_date_calculation(self, db_manager, sample_action_items):
        """AC5: Due date = start_date + 1 day."""
        # Arrange
        item_ids = [item.id for item in sample_action_items]
        new_start_date = (date.today() + timedelta(days=7)).isoformat()
        expected_due_date = (date.fromisoformat(new_start_date) + timedelta(days=1)).isoformat()

        # Act
        db_manager.bulk_update_action_items(item_ids, start_date=new_start_date, priority=None)

        # Assert
        updated_items = [db_manager.get_action_item(item_id) for item_id in item_ids]
        for item in updated_items:
            assert item.due_date == expected_due_date, "Due date should be start_date + 1"

    def test_bulk_update_persists_to_database(self, db_manager, sample_action_items):
        """AC7: Changes persist after refresh from database."""
        # Arrange
        item_ids = [item.id for item in sample_action_items]
        new_start_date = (date.today() + timedelta(days=3)).isoformat()
        new_priority = 5

        # Act
        db_manager.bulk_update_action_items(item_ids, start_date=new_start_date, priority=new_priority)

        # Verify by fetching fresh from database
        updated_items = [db_manager.get_action_item(item_id) for item_id in item_ids]
        for item in updated_items:
            assert item.start_date == new_start_date
            assert item.importance == new_priority

    def test_bulk_update_empty_list(self, db_manager):
        """Handle empty item list gracefully."""
        # Act - should not raise
        db_manager.bulk_update_action_items([], start_date="2026-06-20", priority=5)
        # Pass

    def test_bulk_update_nonexistent_items(self, db_manager):
        """Handle nonexistent item IDs gracefully."""
        # Act - should not raise
        db_manager.bulk_update_action_items(
            ["nonexistent-1", "nonexistent-2"],
            start_date="2026-06-20",
            priority=5
        )
        # Pass

    def test_bulk_update_mixed_items(self, db_manager, sample_action_items):
        """Update mix of existing and nonexistent items - only process existing."""
        # Arrange
        item_ids = [sample_action_items[0].id, "nonexistent-id", sample_action_items[1].id]
        new_start_date = (date.today() + timedelta(days=2)).isoformat()

        # Act
        db_manager.bulk_update_action_items(item_ids, start_date=new_start_date, priority=None)

        # Assert - verify existing items were updated
        item_0 = db_manager.get_action_item(sample_action_items[0].id)
        item_1 = db_manager.get_action_item(sample_action_items[1].id)
        assert item_0.start_date == new_start_date
        assert item_1.start_date == new_start_date

    def test_priority_score_updated(self, db_manager, sample_action_items):
        """Ensure priority_score is recalculated after bulk update."""
        # Arrange
        item_ids = [item.id for item in sample_action_items]
        new_priority = 8

        # Act
        db_manager.bulk_update_action_items(item_ids, start_date=None, priority=new_priority)

        # Assert
        updated_items = [db_manager.get_action_item(item_id) for item_id in item_ids]
        for item in updated_items:
            # priority_score should be recalculated based on all factors
            # (importance * urgency * size * value)
            expected_score = new_priority * (item.urgency or 0) * (item.size or 0) * (item.value or 0)
            assert item.priority_score == expected_score


@pytest.fixture
def gui_screen(db_manager):
    """Build a real ProjectBoardsScreen against a temp DB.

    Skips when CustomTkinter or a display is unavailable (e.g., the default
    pytest environment). Run under the project's venv to exercise this:
        ./venv/bin/python -m pytest tests/test_project_board_bulk_edit.py -v
    """
    ctk = pytest.importorskip("customtkinter")
    from types import SimpleNamespace
    from src.getmoredone.screens.project_boards import ProjectBoardsScreen

    try:
        root = ctk.CTk()
    except Exception as exc:  # no display
        pytest.skip(f"No GUI display available: {exc}")
    root.withdraw()

    board = ProjectBoard(title="GUI Test Board")
    board_id = db_manager.create_project_board(board)
    item_ids = []
    for i in range(4):
        item = ActionItem(
            who="me", title=f"GUI Task {i}",
            importance=3, urgency=3, size=3, value=3, status="open",
        )
        iid = db_manager.create_action_item(item)
        db_manager.link_action_item_to_project_board(board_id, iid)
        item_ids.append(iid)

    screen = ProjectBoardsScreen(root, db_manager, SimpleNamespace(vps_manager=None))
    screen.selected_board_id = board_id
    screen.refresh()
    root.update_idletasks()

    yield screen, item_ids, root
    root.destroy()


class TestBulkEditUI:
    """GUI-level tests for checkbox selection and Bulk Edit button wiring.

    These exercise the real ProjectBoardsScreen widgets and would have caught
    the `selected_item_ids = {}` (dict instead of set) regression.
    """

    def test_selected_item_ids_is_a_set(self, gui_screen):
        """Regression: selection store must be a set (was mistakenly a dict)."""
        screen, _item_ids, _root = gui_screen
        assert isinstance(screen.selected_item_ids, set)

    def test_individual_checkbox_selection(self, gui_screen):
        """AC1: Clicking each item's checkbox adds it to the selection."""
        screen, item_ids, _root = gui_screen
        for iid in item_ids:
            screen.item_checkbox_vars[iid].set(True)
            screen._on_item_checkbox_changed(iid)
        assert screen.selected_item_ids == set(item_ids)

    def test_bulk_edit_button_enables_with_selection(self, gui_screen):
        """AC2: Bulk Edit button enables when ≥1 item selected, disables at 0."""
        screen, item_ids, _root = gui_screen
        assert screen.btn_bulk_edit.cget("state") == "disabled"

        screen.item_checkbox_vars[item_ids[0]].set(True)
        screen._on_item_checkbox_changed(item_ids[0])
        assert screen.btn_bulk_edit.cget("state") == "normal"

        screen.item_checkbox_vars[item_ids[0]].set(False)
        screen._on_item_checkbox_changed(item_ids[0])
        assert screen.btn_bulk_edit.cget("state") == "disabled"

    def test_select_all_selects_every_item(self, gui_screen):
        """AC1: Select All checks every item and selects all of them."""
        screen, item_ids, _root = gui_screen
        screen.check_all_var.set(True)
        screen._on_check_all_changed()
        assert screen.selected_item_ids == set(item_ids)
        assert all(v.get() for v in screen.item_checkbox_vars.values())
        assert screen.btn_bulk_edit.cget("state") == "normal"

    def test_select_all_then_clear(self, gui_screen):
        """AC1: Unchecking Select All clears every item."""
        screen, item_ids, _root = gui_screen
        screen.check_all_var.set(True)
        screen._on_check_all_changed()
        screen.check_all_var.set(False)
        screen._on_check_all_changed()
        assert screen.selected_item_ids == set()
        assert not any(v.get() for v in screen.item_checkbox_vars.values())
        assert screen.btn_bulk_edit.cget("state") == "disabled"


@pytest.fixture
def gui_screen_mixed(db_manager):
    """Real screen with a mix of open and completed items."""
    ctk = pytest.importorskip("customtkinter")
    from types import SimpleNamespace
    from src.getmoredone.screens.project_boards import ProjectBoardsScreen

    try:
        root = ctk.CTk()
    except Exception as exc:
        pytest.skip(f"No GUI display available: {exc}")
    root.withdraw()

    board_id = db_manager.create_project_board(ProjectBoard(title="Mixed Board"))
    open_ids, completed_ids = [], []
    for i in range(3):
        iid = db_manager.create_action_item(
            ActionItem(who="me", title=f"Open {i}", status="open")
        )
        db_manager.link_action_item_to_project_board(board_id, iid)
        open_ids.append(iid)
    for i in range(2):
        iid = db_manager.create_action_item(
            ActionItem(who="me", title=f"Done {i}", status="open")
        )
        db_manager.link_action_item_to_project_board(board_id, iid)
        db_manager.complete_action_item(iid)
        completed_ids.append(iid)

    screen = ProjectBoardsScreen(root, db_manager, SimpleNamespace(vps_manager=None))
    screen.selected_board_id = board_id
    screen.refresh()
    root.update_idletasks()
    yield screen, open_ids, completed_ids, root
    root.destroy()


class TestShowCompletedToggle:
    """GUI tests for the Show Completed filter in the action items panel."""

    def test_default_shows_completed(self, gui_screen_mixed):
        """Default state shows all items (open + completed)."""
        screen, open_ids, completed_ids, _root = gui_screen_mixed
        assert screen.show_completed_items_var.get() is True
        rendered = set(screen.item_checkbox_vars.keys())
        assert rendered == set(open_ids) | set(completed_ids)

    def test_hiding_completed_filters_them_out(self, gui_screen_mixed):
        """Unchecking Show Completed hides completed items, keeps open ones."""
        screen, open_ids, completed_ids, root = gui_screen_mixed
        screen.show_completed_items_var.set(False)
        screen._render_detail()
        root.update_idletasks()
        rendered = set(screen.item_checkbox_vars.keys())
        assert rendered == set(open_ids)
        for cid in completed_ids:
            assert cid not in rendered

    def test_select_all_respects_filter(self, gui_screen_mixed):
        """Select All only selects visible (open) items when completed are hidden."""
        screen, open_ids, completed_ids, root = gui_screen_mixed
        screen.show_completed_items_var.set(False)
        screen._render_detail()
        root.update_idletasks()
        screen.check_all_var.set(True)
        screen._on_check_all_changed()
        assert screen.selected_item_ids == set(open_ids)


class TestBulkEditIntegration:
    """Integration tests for bulk edit workflow."""

    def test_full_bulk_edit_workflow(self, db_manager, sample_project_board, sample_action_items):
        """AC1-AC8: Full workflow - select items, edit, save."""
        # Simulate user selecting items and calling bulk edit
        item_ids = [item.id for item in sample_action_items[:2]]
        new_start_date = (date.today() + timedelta(days=15)).isoformat()
        new_priority = 6

        # Apply bulk edit
        db_manager.bulk_update_action_items(item_ids, start_date=new_start_date, priority=new_priority)

        # Verify results
        for item_id in item_ids:
            updated_item = db_manager.get_action_item(item_id)
            assert updated_item.start_date == new_start_date
            assert updated_item.importance == new_priority
            assert updated_item.due_date == (
                date.fromisoformat(new_start_date) + timedelta(days=1)
            ).isoformat()

        # Verify unselected item was not modified
        untouched_item = db_manager.get_action_item(sample_action_items[2].id)
        assert untouched_item.start_date != new_start_date
        assert untouched_item.importance != new_priority

    def test_bulk_edit_linked_to_project(self, db_manager, sample_project_board, sample_action_items):
        """Verify bulk edit updates items correctly regardless of project linking."""
        # All items should be linked to the project
        linked_items = db_manager.get_project_board_items(sample_project_board.id)
        assert len(linked_items) == 3

        # Update all linked items
        item_ids = [item.id for item in linked_items]
        new_start_date = (date.today() + timedelta(days=20)).isoformat()

        db_manager.bulk_update_action_items(item_ids, start_date=new_start_date, priority=None)

        # Verify all items in project have been updated
        updated_linked = db_manager.get_project_board_items(sample_project_board.id)
        for item in updated_linked:
            assert item.start_date == new_start_date
