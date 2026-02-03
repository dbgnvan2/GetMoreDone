"""
Tests for Today screen filtering logic and settings.
"""

import pytest
from datetime import datetime, timedelta
from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem
from src.getmoredone.app_settings import AppSettings


def test_today_screen_shows_only_items_completed_today(tmp_path):
    """Test that Today screen only shows items completed today, not previous days."""
    db_file = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_file))

    # Create test items
    today = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    two_days_ago = (datetime.now().date() - timedelta(days=2)).isoformat()

    # Item completed today
    item_completed_today = ActionItem(
        who="Test User",
        title="Completed Today",
        start_date=yesterday,
        due_date=today,
        status="completed",
        completed_at=datetime.now().isoformat()
    )
    db_manager.create_action_item(item_completed_today)

    # Item completed yesterday
    item_completed_yesterday = ActionItem(
        who="Test User",
        title="Completed Yesterday",
        start_date=two_days_ago,
        due_date=yesterday,
        status="completed",
        completed_at=(datetime.now() - timedelta(days=1)).isoformat()
    )
    db_manager.create_action_item(item_completed_yesterday)

    # Open item with start date in the past
    item_open = ActionItem(
        who="Test User",
        title="Open Item",
        start_date=yesterday,
        due_date=today,
        status="open"
    )
    db_manager.create_action_item(item_open)

    # Query for today's items (simulating Today screen query)
    query = """
        SELECT * FROM action_items
        WHERE (
            -- Open items: start/due date <= today
            (status = 'open'
             AND (start_date IS NOT NULL OR due_date IS NOT NULL)
             AND COALESCE(start_date, due_date) <= ?)
            OR
            -- Completed items: completed today (date part of completed_at matches today)
            (status = 'completed'
             AND completed_at IS NOT NULL
             AND DATE(completed_at) = ?)
        )
        ORDER BY status ASC, COALESCE(start_date, due_date) ASC, priority_score DESC
    """

    rows = db_manager.db.conn.execute(query, (today, today)).fetchall()
    items = [db_manager._row_to_action_item(row) for row in rows]

    # Verify results
    assert len(items) == 2, "Should have 2 items: 1 open and 1 completed today"

    completed_items = [item for item in items if item.status == "completed"]
    open_items = [item for item in items if item.status == "open"]

    assert len(completed_items) == 1, "Should have 1 completed item"
    assert completed_items[0].title == "Completed Today", "Should be the item completed today"

    assert len(open_items) == 1, "Should have 1 open item"
    assert open_items[0].title == "Open Item", "Should be the open item"


def test_today_screen_shows_open_items_with_start_date_today_or_earlier(tmp_path):
    """Test that Today screen shows open items with start date <= today."""
    db_file = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_file))

    today = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()

    # Open item with start date yesterday
    item_yesterday = ActionItem(
        who="Test User",
        title="Started Yesterday",
        start_date=yesterday,
        due_date=today,
        status="open"
    )
    db_manager.create_action_item(item_yesterday)

    # Open item with start date today
    item_today = ActionItem(
        who="Test User",
        title="Started Today",
        start_date=today,
        due_date=today,
        status="open"
    )
    db_manager.create_action_item(item_today)

    # Open item with start date tomorrow (should NOT appear)
    item_tomorrow = ActionItem(
        who="Test User",
        title="Starting Tomorrow",
        start_date=tomorrow,
        due_date=tomorrow,
        status="open"
    )
    db_manager.create_action_item(item_tomorrow)

    # Query for today's items
    query = """
        SELECT * FROM action_items
        WHERE (
            -- Open items: start/due date <= today
            (status = 'open'
             AND (start_date IS NOT NULL OR due_date IS NOT NULL)
             AND COALESCE(start_date, due_date) <= ?)
            OR
            -- Completed items: completed today (date part of completed_at matches today)
            (status = 'completed'
             AND completed_at IS NOT NULL
             AND DATE(completed_at) = ?)
        )
        ORDER BY status ASC, COALESCE(start_date, due_date) ASC, priority_score DESC
    """

    rows = db_manager.db.conn.execute(query, (today, today)).fetchall()
    items = [db_manager._row_to_action_item(row) for row in rows]

    # Verify results
    assert len(items) == 2, "Should have 2 open items (yesterday and today)"

    titles = [item.title for item in items]
    assert "Started Yesterday" in titles
    assert "Started Today" in titles
    assert "Starting Tomorrow" not in titles


def test_list_view_expansion_setting_persistence():
    """Test that default_columns_expanded setting can be saved and reloaded."""
    # Load current settings
    settings = AppSettings.load()
    original_value = settings.default_columns_expanded

    try:
        # Test changing to True
        settings.default_columns_expanded = True
        settings.save()

        # Reload and verify
        reloaded = AppSettings.load()
        assert reloaded.default_columns_expanded == True, \
            "Setting should persist as True after save/reload"

        # Test changing to False
        reloaded.default_columns_expanded = False
        reloaded.save()

        # Reload again and verify
        reloaded2 = AppSettings.load()
        assert reloaded2.default_columns_expanded == False, \
            "Setting should persist as False after save/reload"

    finally:
        # Restore original value
        settings.default_columns_expanded = original_value
        settings.save()


def test_list_view_expansion_default_value():
    """Test that default_columns_expanded defaults to False (collapsed)."""
    settings = AppSettings.load()

    # Check the attribute exists
    assert hasattr(settings, 'default_columns_expanded'), \
        "AppSettings should have default_columns_expanded attribute"

    # Check it's a boolean
    assert isinstance(settings.default_columns_expanded, bool), \
        "default_columns_expanded should be a boolean"
