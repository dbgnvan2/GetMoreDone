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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
