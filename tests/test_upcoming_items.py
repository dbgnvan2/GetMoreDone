"""
Tests for upcoming items functionality - ensuring overdue items don't get left behind.
"""
import pytest
from datetime import datetime, timedelta
from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem


@pytest.fixture
def db_manager():
    """Create a temporary database manager."""
    manager = DatabaseManager(":memory:")
    yield manager
    manager.close()


def test_upcoming_includes_all_overdue_items(db_manager):
    """Test that upcoming items include ALL overdue tasks (no matter how old)."""
    today = datetime.now().date()

    # Create items with various due dates, including very old overdue items
    items = [
        ActionItem(who="Test", title="Due today", due_date=today.isoformat()),
        ActionItem(who="Test", title="Due yesterday", due_date=(today - timedelta(days=1)).isoformat()),
        ActionItem(who="Test", title="Due 3 days ago", due_date=(today - timedelta(days=3)).isoformat()),
        ActionItem(who="Test", title="Due 30 days ago", due_date=(today - timedelta(days=30)).isoformat()),
        ActionItem(who="Test", title="Due 100 days ago", due_date=(today - timedelta(days=100)).isoformat()),
        ActionItem(who="Test", title="Due in 2025", due_date="2025-12-12"),
        ActionItem(who="Test", title="Due tomorrow", due_date=(today + timedelta(days=1)).isoformat()),
        ActionItem(who="Test", title="Due in 8 days", due_date=(today + timedelta(days=8)).isoformat()),
    ]

    for item in items:
        db_manager.create_action_item(item)

    # Get upcoming items (default 7 days ahead)
    upcoming = db_manager.get_upcoming_items(n_days=7)
    titles = [item.title for item in upcoming]

    # Should include ALL overdue items, no matter how old
    assert "Due today" in titles
    assert "Due yesterday" in titles
    assert "Due 3 days ago" in titles
    assert "Due 30 days ago" in titles
    assert "Due 100 days ago" in titles
    assert "Due in 2025" in titles
    assert "Due tomorrow" in titles

    # Should NOT include items beyond the 7-day future window
    assert "Due in 8 days" not in titles


def test_upcoming_respects_future_cutoff(db_manager):
    """Test that upcoming items respect the N-day future cutoff."""
    today = datetime.now().date()

    # Create items with future due dates
    items = [
        ActionItem(who="Test", title="Due in 5 days", due_date=(today + timedelta(days=5)).isoformat()),
        ActionItem(who="Test", title="Due in 7 days", due_date=(today + timedelta(days=7)).isoformat()),
        ActionItem(who="Test", title="Due in 10 days", due_date=(today + timedelta(days=10)).isoformat()),
        ActionItem(who="Test", title="Due in 30 days", due_date=(today + timedelta(days=30)).isoformat()),
    ]

    for item in items:
        db_manager.create_action_item(item)

    # Get upcoming items (7 days ahead)
    upcoming = db_manager.get_upcoming_items(n_days=7)
    titles = [item.title for item in upcoming]

    # Should include items within 7 days
    assert "Due in 5 days" in titles
    assert "Due in 7 days" in titles

    # Should NOT include items beyond 7 days
    assert "Due in 10 days" not in titles
    assert "Due in 30 days" not in titles


def test_upcoming_sorted_by_due_date(db_manager):
    """Test that upcoming items are sorted by due date (overdue first)."""
    today = datetime.now().date()

    # Create items in random order
    items = [
        ActionItem(who="Test", title="C: Due tomorrow", due_date=(today + timedelta(days=1)).isoformat()),
        ActionItem(who="Test", title="A: Due 3 days ago", due_date=(today - timedelta(days=3)).isoformat()),
        ActionItem(who="Test", title="B: Due today", due_date=today.isoformat()),
        ActionItem(who="Test", title="D: Due in 5 days", due_date=(today + timedelta(days=5)).isoformat()),
    ]

    for item in items:
        db_manager.create_action_item(item)

    # Get upcoming items (7 days ahead)
    upcoming = db_manager.get_upcoming_items(n_days=7)

    # Should be sorted by due_date ascending (oldest/most overdue first)
    assert len(upcoming) == 4
    assert upcoming[0].title == "A: Due 3 days ago"
    assert upcoming[1].title == "B: Due today"
    assert upcoming[2].title == "C: Due tomorrow"
    assert upcoming[3].title == "D: Due in 5 days"


def test_upcoming_excludes_completed_items(db_manager):
    """Test that completed items are not shown in upcoming."""
    today = datetime.now().date()

    # Create an overdue item and complete it
    item = ActionItem(who="Test", title="Overdue but completed", due_date=(today - timedelta(days=2)).isoformat())
    item_id = db_manager.create_action_item(item)
    db_manager.complete_action_item(item_id)

    # Get upcoming items
    upcoming = db_manager.get_upcoming_items(n_days=7)
    titles = [item.title for item in upcoming]

    # Should not include completed items
    assert "Overdue but completed" not in titles


def test_upcoming_excludes_items_without_due_date(db_manager):
    """Test that items without due dates are not shown in upcoming."""
    # Create item without due date
    item = ActionItem(who="Test", title="No due date", due_date=None)
    db_manager.create_action_item(item)

    # Get upcoming items
    upcoming = db_manager.get_upcoming_items(n_days=7)
    titles = [item.title for item in upcoming]

    # Should not include items without due dates
    assert "No due date" not in titles


def test_upcoming_with_custom_lookahead_period(db_manager):
    """Test that n_days parameter controls how far ahead to look."""
    today = datetime.now().date()

    # Create items with various future dates
    items = [
        ActionItem(who="Test", title="Very old overdue", due_date=(today - timedelta(days=100)).isoformat()),
        ActionItem(who="Test", title="Due tomorrow", due_date=(today + timedelta(days=1)).isoformat()),
        ActionItem(who="Test", title="Due in 3 days", due_date=(today + timedelta(days=3)).isoformat()),
        ActionItem(who="Test", title="Due in 7 days", due_date=(today + timedelta(days=7)).isoformat()),
        ActionItem(who="Test", title="Due in 10 days", due_date=(today + timedelta(days=10)).isoformat()),
    ]

    for item in items:
        db_manager.create_action_item(item)

    # Get upcoming items with 3-day lookahead
    upcoming_3 = db_manager.get_upcoming_items(n_days=3)
    titles_3 = [item.title for item in upcoming_3]

    assert "Very old overdue" in titles_3  # ALL overdue items included
    assert "Due tomorrow" in titles_3
    assert "Due in 3 days" in titles_3
    assert "Due in 7 days" not in titles_3  # Beyond 3-day window
    assert "Due in 10 days" not in titles_3

    # Get upcoming items with 10-day lookahead
    upcoming_10 = db_manager.get_upcoming_items(n_days=10)
    titles_10 = [item.title for item in upcoming_10]

    assert "Very old overdue" in titles_10  # ALL overdue items always included
    assert "Due tomorrow" in titles_10
    assert "Due in 3 days" in titles_10
    assert "Due in 7 days" in titles_10
    assert "Due in 10 days" in titles_10


def test_upcoming_with_who_filter(db_manager):
    """Test that who filter works correctly with new upcoming logic."""
    today = datetime.now().date()

    # Create items for different people, including very old overdue
    items = [
        ActionItem(who="Alice", title="Alice very old", due_date=(today - timedelta(days=100)).isoformat()),
        ActionItem(who="Alice", title="Alice recent", due_date=(today - timedelta(days=2)).isoformat()),
        ActionItem(who="Bob", title="Bob overdue", due_date=(today - timedelta(days=2)).isoformat()),
        ActionItem(who="Alice", title="Alice future", due_date=(today + timedelta(days=5)).isoformat()),
    ]

    for item in items:
        db_manager.create_action_item(item)

    # Get upcoming items for Alice only
    upcoming_alice = db_manager.get_upcoming_items(n_days=7, who_filter="Alice")
    titles_alice = [item.title for item in upcoming_alice]

    # Should include ALL Alice's overdue items (no matter how old)
    assert "Alice very old" in titles_alice
    assert "Alice recent" in titles_alice
    assert "Alice future" in titles_alice
    # Should not include Bob's items
    assert "Bob overdue" not in titles_alice
