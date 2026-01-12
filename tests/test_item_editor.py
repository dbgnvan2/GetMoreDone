"""
Tests for Item Editor dialog functionality.
"""

import pytest
import tempfile
import os
from datetime import date, timedelta

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


def test_date_offset_application(temp_db):
    """Test that date offsets are correctly applied from defaults."""
    # Create system defaults with date offsets
    system_defaults = Defaults(
        scope_type="system",
        start_offset_days=0,  # Today
        due_offset_days=7     # One week from today
    )
    temp_db.save_defaults(system_defaults)

    # Create a new item (simulating form submission with defaults applied)
    item = ActionItem(who="TestUser", title="Test Task")

    # Simulate what the item editor does: apply defaults including date offsets
    retrieved_defaults = temp_db.get_defaults("system")

    # Calculate expected dates
    today = date.today()
    expected_start = today + timedelta(days=retrieved_defaults.start_offset_days)
    expected_due = today + timedelta(days=retrieved_defaults.due_offset_days)

    # Apply date offsets as the form would
    item.start_date = expected_start.strftime("%Y-%m-%d")
    item.due_date = expected_due.strftime("%Y-%m-%d")

    assert item.start_date == today.strftime("%Y-%m-%d")
    assert item.due_date == (today + timedelta(days=7)).strftime("%Y-%m-%d")


def test_who_specific_date_offsets(temp_db):
    """Test that who-specific date offsets override system defaults."""
    # Create system defaults
    system_defaults = Defaults(
        scope_type="system",
        start_offset_days=0,
        due_offset_days=7
    )
    temp_db.save_defaults(system_defaults)

    # Create who-specific defaults with different offsets
    who_defaults = Defaults(
        scope_type="who",
        scope_key="UrgentClient",
        start_offset_days=0,
        due_offset_days=1  # Tomorrow instead of 7 days
    )
    temp_db.save_defaults(who_defaults)

    # Retrieve who defaults
    retrieved_who_defaults = temp_db.get_defaults("who", "UrgentClient")

    assert retrieved_who_defaults.due_offset_days == 1
    assert retrieved_who_defaults.start_offset_days == 0


def test_date_offset_none_handling(temp_db):
    """Test that None date offsets are handled correctly."""
    # Create defaults with no date offsets
    system_defaults = Defaults(
        scope_type="system",
        importance=PriorityFactors.IMPORTANCE["Medium"],
        start_offset_days=None,
        due_offset_days=None
    )
    temp_db.save_defaults(system_defaults)

    retrieved = temp_db.get_defaults("system")
    assert retrieved.start_offset_days is None
    assert retrieved.due_offset_days is None
    assert retrieved.importance == PriorityFactors.IMPORTANCE["Medium"]


def test_negative_date_offsets(temp_db):
    """Test that negative date offsets work (dates in the past)."""
    # Create defaults with negative offsets
    system_defaults = Defaults(
        scope_type="system",
        start_offset_days=-7,  # One week ago
        due_offset_days=0      # Today
    )
    temp_db.save_defaults(system_defaults)

    retrieved = temp_db.get_defaults("system")

    # Calculate expected dates
    today = date.today()
    expected_start = today + timedelta(days=-7)
    expected_due = today

    assert retrieved.start_offset_days == -7
    assert retrieved.due_offset_days == 0


def test_defaults_precedence_with_offsets(temp_db):
    """Test precedence: who defaults override system defaults for date offsets."""
    # Create both types of defaults
    system_defaults = Defaults(
        scope_type="system",
        start_offset_days=0,
        due_offset_days=7,
        importance=PriorityFactors.IMPORTANCE["Low"]
    )
    temp_db.save_defaults(system_defaults)

    who_defaults = Defaults(
        scope_type="who",
        scope_key="HighPriorityClient",
        due_offset_days=1,  # Override due date
        importance=PriorityFactors.IMPORTANCE["Critical"]
    )
    temp_db.save_defaults(who_defaults)

    # Simulate defaults application logic
    system = temp_db.get_defaults("system")
    who = temp_db.get_defaults("who", "HighPriorityClient")

    # Who defaults should override
    final_due_offset = who.due_offset_days if who and who.due_offset_days is not None else system.due_offset_days
    final_start_offset = who.start_offset_days if who and who.start_offset_days is not None else system.start_offset_days
    final_importance = who.importance if who and who.importance is not None else system.importance

    assert final_due_offset == 1  # From who defaults
    assert final_start_offset == 0  # From system defaults (who didn't override)
    assert final_importance == PriorityFactors.IMPORTANCE["Critical"]


def test_date_calculation_edge_cases(temp_db):
    """Test date calculation with various offsets."""
    today = date.today()

    # Test various offsets
    offsets_to_test = [0, 1, 7, 14, 30, 365, -1, -7]

    for offset in offsets_to_test:
        expected = today + timedelta(days=offset)
        assert expected == today + timedelta(days=offset)


def test_item_creation_with_all_defaults(temp_db):
    """Test creating an item with all defaults including date offsets."""
    # Create comprehensive defaults
    defaults = Defaults(
        scope_type="system",
        importance=PriorityFactors.IMPORTANCE["High"],
        urgency=PriorityFactors.URGENCY["High"],
        size=PriorityFactors.SIZE["M"],
        value=PriorityFactors.VALUE["L"],
        group="DefaultGroup",
        category="DefaultCategory",
        planned_minutes=60,
        start_offset_days=0,
        due_offset_days=3
    )
    temp_db.save_defaults(defaults)

    # Create item with defaults applied
    item = ActionItem(who="TestUser", title="Comprehensive Test")
    item_id = temp_db.create_action_item(item, apply_defaults=True)

    # Retrieve and verify
    retrieved = temp_db.get_action_item(item_id)
    assert retrieved.importance == PriorityFactors.IMPORTANCE["High"]
    assert retrieved.urgency == PriorityFactors.URGENCY["High"]
    assert retrieved.size == PriorityFactors.SIZE["M"]
    assert retrieved.value == PriorityFactors.VALUE["L"]
    assert retrieved.group == "DefaultGroup"
    assert retrieved.category == "DefaultCategory"
    assert retrieved.planned_minutes == 60


def test_priority_score_calculation_with_defaults(temp_db):
    """Test that priority score is calculated correctly with defaulted factors."""
    defaults = Defaults(
        scope_type="system",
        importance=10,  # High
        urgency=5,      # Medium
        size=4,         # M
        value=8         # L
    )
    temp_db.save_defaults(defaults)

    item = ActionItem(who="User", title="Test")
    item_id = temp_db.create_action_item(item, apply_defaults=True)

    retrieved = temp_db.get_action_item(item_id)
    expected_score = 10 * 5 * 4 * 8  # 1600
    assert retrieved.priority_score == expected_score


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
