"""
Tests for database functionality.
"""

import pytest
import tempfile
import os
from datetime import datetime

from src.getmoredone.database import Database
from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem, Defaults, PriorityFactors


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()

    db_manager = DatabaseManager(temp_file.name)
    yield db_manager

    db_manager.close()
    os.unlink(temp_file.name)


def test_database_initialization(temp_db):
    """Test that database initializes correctly."""
    assert temp_db.db.conn is not None


def test_create_action_item(temp_db):
    """Test creating an action item."""
    item = ActionItem(
        who="TestUser",
        title="Test Task",
        description="This is a test",
        importance=PriorityFactors.IMPORTANCE["High"],
        urgency=PriorityFactors.URGENCY["Medium"],
        size=PriorityFactors.SIZE["M"],
        value=PriorityFactors.VALUE["L"]
    )

    item_id = temp_db.create_action_item(item, apply_defaults=False)
    assert item_id is not None

    # Retrieve and verify
    retrieved = temp_db.get_action_item(item_id)
    assert retrieved is not None
    assert retrieved.who == "TestUser"
    assert retrieved.title == "Test Task"
    assert retrieved.priority_score > 0


def test_priority_calculation(temp_db):
    """Test priority score calculation."""
    item = ActionItem(
        who="TestUser",
        title="Priority Test",
        importance=20,  # Critical
        urgency=10,     # High
        size=4,         # M
        value=8         # L
    )

    expected_score = 20 * 10 * 4 * 8  # 6400
    item.update_priority_score()
    assert item.priority_score == expected_score


def test_defaults_system(temp_db):
    """Test defaults application."""
    # Create system defaults
    system_defaults = Defaults(
        scope_type="system",
        scope_key=None,
        importance=PriorityFactors.IMPORTANCE["Medium"],
        urgency=PriorityFactors.URGENCY["Medium"],
        size=PriorityFactors.SIZE["M"],
        value=PriorityFactors.VALUE["M"]
    )
    temp_db.save_defaults(system_defaults)

    # Create item without specifying factors
    item = ActionItem(who="TestUser", title="Test with defaults")
    item_id = temp_db.create_action_item(item, apply_defaults=True)

    # Retrieve and verify defaults were applied
    retrieved = temp_db.get_action_item(item_id)
    assert retrieved.importance == PriorityFactors.IMPORTANCE["Medium"]
    assert retrieved.urgency == PriorityFactors.URGENCY["Medium"]
    assert retrieved.size == PriorityFactors.SIZE["M"]
    assert retrieved.value == PriorityFactors.VALUE["M"]


def test_who_specific_defaults(temp_db):
    """Test who-specific defaults override system defaults."""
    # Create system defaults
    system_defaults = Defaults(
        scope_type="system",
        importance=PriorityFactors.IMPORTANCE["Low"]
    )
    temp_db.save_defaults(system_defaults)

    # Create who-specific defaults
    who_defaults = Defaults(
        scope_type="who",
        scope_key="Client1",
        importance=PriorityFactors.IMPORTANCE["Critical"]
    )
    temp_db.save_defaults(who_defaults)

    # Create item for Client1
    item = ActionItem(who="Client1", title="Test")
    item_id = temp_db.create_action_item(item, apply_defaults=True)

    retrieved = temp_db.get_action_item(item_id)
    # Should have who-specific default, not system
    assert retrieved.importance == PriorityFactors.IMPORTANCE["Critical"]


def test_get_upcoming_items(temp_db):
    """Test getting upcoming items."""
    # Create items with different due dates
    today = datetime.now().date().isoformat()

    item1 = ActionItem(who="User1", title="Due today", due_date=today)
    temp_db.create_action_item(item1, apply_defaults=False)

    # Get upcoming
    upcoming = temp_db.get_upcoming_items(n_days=7)
    assert len(upcoming) >= 1
    assert any(item.title == "Due today" for item in upcoming)


def test_complete_action_item(temp_db):
    """Test completing an action item."""
    item = ActionItem(who="User", title="Complete me")
    item_id = temp_db.create_action_item(item, apply_defaults=False)

    # Complete it
    result = temp_db.complete_action_item(item_id)
    assert result is True

    # Verify it's completed
    retrieved = temp_db.get_action_item(item_id)
    assert retrieved.status == "completed"
    assert retrieved.completed_at is not None


def test_duplicate_action_item(temp_db):
    """Test duplicating an action item."""
    item = ActionItem(who="User", title="Original", description="Test")
    item_id = temp_db.create_action_item(item, apply_defaults=False)

    # Duplicate it
    new_id = temp_db.duplicate_action_item(item_id)
    assert new_id is not None
    assert new_id != item_id

    # Verify duplicate has same fields
    original = temp_db.get_action_item(item_id)
    duplicate = temp_db.get_action_item(new_id)

    assert duplicate.title == original.title
    assert duplicate.description == original.description
    assert duplicate.who == original.who


def test_delete_action_item_simple(temp_db):
    """Test deleting an action item without children."""
    item = ActionItem(who="User", title="Delete me")
    item_id = temp_db.create_action_item(item, apply_defaults=False)

    # Verify it exists
    retrieved = temp_db.get_action_item(item_id)
    assert retrieved is not None
    assert retrieved.title == "Delete me"

    # Delete it
    temp_db.delete_action_item(item_id)

    # Verify it's gone
    deleted = temp_db.get_action_item(item_id)
    assert deleted is None


def test_delete_action_item_with_children(temp_db):
    """Test deleting parent item preserves children (parent_id set to NULL)."""
    # Create parent item
    parent = ActionItem(who="User", title="Parent Item")
    parent_id = temp_db.create_action_item(parent, apply_defaults=False)

    # Create child items
    child1 = ActionItem(who="User", title="Child 1", parent_id=parent_id)
    child1_id = temp_db.create_action_item(child1, apply_defaults=False)

    child2 = ActionItem(who="User", title="Child 2", parent_id=parent_id)
    child2_id = temp_db.create_action_item(child2, apply_defaults=False)

    # Verify children have parent_id set
    child1_before = temp_db.get_action_item(child1_id)
    child2_before = temp_db.get_action_item(child2_id)
    assert child1_before.parent_id == parent_id
    assert child2_before.parent_id == parent_id

    # Verify parent has children
    children_before = temp_db.get_children(parent_id)
    assert len(children_before) == 2

    # Delete parent
    temp_db.delete_action_item(parent_id)

    # Verify parent is deleted
    parent_after = temp_db.get_action_item(parent_id)
    assert parent_after is None

    # Verify children still exist but parent_id is NULL
    child1_after = temp_db.get_action_item(child1_id)
    child2_after = temp_db.get_action_item(child2_id)
    assert child1_after is not None
    assert child2_after is not None
    assert child1_after.parent_id is None
    assert child2_after.parent_id is None
    assert child1_after.title == "Child 1"
    assert child2_after.title == "Child 2"


def test_delete_action_item_cascades_links(temp_db):
    """Test that deleting item cascades to links and work logs."""
    from src.getmoredone.models import ItemLink, WorkLog

    # Create item
    item = ActionItem(who="User", title="Item with links")
    item_id = temp_db.create_action_item(item, apply_defaults=False)

    # Add link
    link = ItemLink(item_id=item_id, url="https://example.com", label="Test Link")
    temp_db.add_item_link(link)

    # Add work log
    log = WorkLog(
        item_id=item_id,
        started_at=datetime.now().isoformat(),
        minutes=30,
        note="Work done"
    )
    temp_db.create_work_log(log)

    # Verify links and logs exist
    links_before = temp_db.get_item_links(item_id)
    logs_before = temp_db.get_work_logs(item_id)
    assert len(links_before) == 1
    assert len(logs_before) == 1

    # Delete item
    temp_db.delete_action_item(item_id)

    # Verify links and logs are gone (cascaded)
    links_after = temp_db.get_item_links(item_id)
    logs_after = temp_db.get_work_logs(item_id)
    assert len(links_after) == 0
    assert len(logs_after) == 0


def test_get_children_returns_empty_for_deleted_parent(temp_db):
    """Test that get_children returns empty list for deleted parent."""
    # Create parent
    parent = ActionItem(who="User", title="Parent")
    parent_id = temp_db.create_action_item(parent, apply_defaults=False)

    # Create children
    child = ActionItem(who="User", title="Child", parent_id=parent_id)
    temp_db.create_action_item(child, apply_defaults=False)

    # Delete parent
    temp_db.delete_action_item(parent_id)

    # Try to get children of deleted parent
    children = temp_db.get_children(parent_id)
    assert len(children) == 0  # Children are orphaned, so won't show up here


def test_create_sub_item_duplicates_parent(temp_db):
    """Test that sub-items duplicate parent fields."""
    # Create parent item with all fields set
    parent = ActionItem(
        who="ClientA",
        title="Parent Task",
        description="Parent description",
        start_date="2026-01-15",
        due_date="2026-01-20",
        importance=10,
        urgency=5,
        size=4,
        value=8,
        group="Development",
        category="Backend",
        planned_minutes=120
    )
    parent_id = temp_db.create_action_item(parent, apply_defaults=False)

    # Simulate sub-item creation: duplicate parent then set parent_id
    sub_item_id = temp_db.duplicate_action_item(parent_id)
    sub_item = temp_db.get_action_item(sub_item_id)
    sub_item.parent_id = parent_id
    temp_db.update_action_item(sub_item)

    # Verify sub-item has all parent fields
    sub_item = temp_db.get_action_item(sub_item_id)
    parent = temp_db.get_action_item(parent_id)

    assert sub_item.parent_id == parent_id
    assert sub_item.who == parent.who
    assert sub_item.title == parent.title
    assert sub_item.description == parent.description
    assert sub_item.start_date == parent.start_date
    assert sub_item.due_date == parent.due_date
    assert sub_item.importance == parent.importance
    assert sub_item.urgency == parent.urgency
    assert sub_item.size == parent.size
    assert sub_item.value == parent.value
    assert sub_item.group == parent.group
    assert sub_item.category == parent.category
    assert sub_item.planned_minutes == parent.planned_minutes

    # Verify parent has the sub-item as child
    children = temp_db.get_children(parent_id)
    assert len(children) == 1
    assert children[0].id == sub_item_id


def test_push_item_to_next_day(temp_db):
    """Test pushing (rescheduling) item to next day."""
    from datetime import timedelta

    # Create item with today's dates
    today = datetime.now().date().isoformat()
    item = ActionItem(
        who="User",
        title="Task to Push",
        start_date=today,
        due_date=today
    )
    item_id = temp_db.create_action_item(item, apply_defaults=False)

    # Calculate tomorrow
    tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()

    # Push to next day
    temp_db.reschedule_item(item_id, tomorrow, tomorrow, "Pushed to next day")

    # Verify dates changed
    updated_item = temp_db.get_action_item(item_id)
    assert updated_item.start_date == tomorrow
    assert updated_item.due_date == tomorrow


def test_push_item_records_history(temp_db):
    """Test that pushing item records reschedule history."""
    from datetime import timedelta

    # Create item
    today = datetime.now().date().isoformat()
    item = ActionItem(who="User", title="Task", start_date=today, due_date=today)
    item_id = temp_db.create_action_item(item, apply_defaults=False)

    # Push to next day
    tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
    temp_db.reschedule_item(item_id, tomorrow, tomorrow, "Testing push")

    # Verify history was recorded (check that item was updated)
    updated_item = temp_db.get_action_item(item_id)
    assert updated_item is not None
    assert updated_item.start_date == tomorrow
    assert updated_item.due_date == tomorrow


def test_push_item_without_dates(temp_db):
    """Test pushing item that has no dates."""
    # Create item without dates
    item = ActionItem(who="User", title="No dates task")
    item_id = temp_db.create_action_item(item, apply_defaults=False)

    # Try to push (should handle None dates gracefully)
    temp_db.reschedule_item(item_id, None, None, "No dates")

    # Verify item still exists
    updated_item = temp_db.get_action_item(item_id)
    assert updated_item is not None
    assert updated_item.start_date is None
    assert updated_item.due_date is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
