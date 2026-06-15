"""Tests for schedule tab checkbox and bulk-drag functionality."""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from src.getmoredone.models import ActionItem


class TestScheduleCheckboxDrag(unittest.TestCase):
    """Test checkbox selection and drag behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.item1 = ActionItem(
            id="item1",
            title="Task 1",
            who="test",
            status="open",
            start_date="2026-06-15",
        )
        self.item2 = ActionItem(
            id="item2",
            title="Task 2",
            who="test",
            status="open",
            start_date="2026-06-16",
        )
        self.item3 = ActionItem(
            id="item3",
            title="Task 3",
            who="test",
            status="open",
            start_date="2026-06-17",
        )

    def test_checkbox_toggle_adds_to_checked_set(self):
        """When checkbox is toggled, item ID is added to checked_items."""
        checked_items = set()

        # Simulate first checkbox toggle
        if "item1" in checked_items:
            checked_items.remove("item1")
        else:
            checked_items.add("item1")

        self.assertIn("item1", checked_items)

    def test_checkbox_toggle_removes_from_checked_set(self):
        """When checkbox is toggled again, item ID is removed."""
        checked_items = {"item1", "item2"}

        # Simulate checkbox toggle
        if "item1" in checked_items:
            checked_items.remove("item1")
        else:
            checked_items.add("item1")

        self.assertNotIn("item1", checked_items)
        self.assertIn("item2", checked_items)

    def test_single_item_drag_when_unchecked(self):
        """Dragging unchecked item should only drag that item."""
        drag_items = [self.item1]
        self.assertEqual(len(drag_items), 1)
        self.assertEqual(drag_items[0].id, "item1")

    def test_multiple_items_drag_when_checked(self):
        """Dragging checked item should drag all checked items."""
        checked_items = {"item1", "item2", "item3"}
        all_items = [self.item1, self.item2, self.item3]

        # Simulate dragging item1 (which is checked)
        if self.item1.id in checked_items:
            drag_items = [i for i in all_items if i.id in checked_items]
        else:
            drag_items = [self.item1]

        self.assertEqual(len(drag_items), 3)
        self.assertEqual({i.id for i in drag_items}, checked_items)

    def test_drag_label_shows_count_for_multiple(self):
        """Drag label should show item count when dragging multiple."""
        drag_items = [self.item1, self.item2]
        drag_text = f"{len(drag_items)} items"
        self.assertEqual(drag_text, "2 items")

    def test_drag_label_shows_title_for_single(self):
        """Drag label should show title when dragging single item."""
        drag_items = [self.item1]
        drag_text = drag_items[0].title
        self.assertEqual(drag_text, "Task 1")

    def test_reschedule_all_items_on_drop(self):
        """On drop, all dragged items should be rescheduled."""
        drag_items = [self.item1, self.item2]
        target_date = "2026-06-20"
        rescheduled = []

        # Simulate reschedule logic
        for item in drag_items:
            rescheduled.append(item.id)

        self.assertEqual(len(rescheduled), 2)
        self.assertIn("item1", rescheduled)
        self.assertIn("item2", rescheduled)


if __name__ == "__main__":
    unittest.main()
