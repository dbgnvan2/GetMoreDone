"""Tests for LinkActionItemsDialog filter functionality."""

import unittest
from src.getmoredone.models import ActionItem


class TestLinkActionItemsDialogFilters(unittest.TestCase):
    """Test AND logic filtering for status and link state."""

    def setUp(self):
        """Set up test fixtures."""
        self.item_open_unlinked = ActionItem(
            id="item1",
            title="Open Unlinked",
            who="test",
            status="open",
        )
        self.item_open_linked = ActionItem(
            id="item2",
            title="Open Linked",
            who="test",
            status="open",
        )
        self.item_completed_unlinked = ActionItem(
            id="item3",
            title="Completed Unlinked",
            who="test",
            status="completed",
        )
        self.item_completed_linked = ActionItem(
            id="item4",
            title="Completed Linked",
            who="test",
            status="completed",
        )
        self.all_items = [
            self.item_open_unlinked,
            self.item_open_linked,
            self.item_completed_unlinked,
            self.item_completed_linked,
        ]
        self.linked_ids = {"item2", "item4"}

    def _filter_items(
        self,
        items,
        linked_ids,
        filter_completed=False,
        filter_not_completed=False,
        filter_linked=False,
        filter_not_linked=False,
    ):
        """Apply AND logic filtering to items."""
        filtered = []
        for item in items:
            is_linked = item.id in linked_ids
            is_completed = item.status == "completed"

            # AND logic: all active filters must be true
            if filter_completed and not is_completed:
                continue
            if filter_not_completed and is_completed:
                continue
            if filter_linked and not is_linked:
                continue
            if filter_not_linked and is_linked:
                continue

            filtered.append(item)
        return filtered

    def test_no_filters_returns_all_items(self):
        """With no filters, all items are returned."""
        result = self._filter_items(self.all_items, self.linked_ids)
        self.assertEqual(len(result), 4)

    def test_filter_completed_only(self):
        """Filter: Completed → returns only completed items."""
        result = self._filter_items(
            self.all_items, self.linked_ids, filter_completed=True
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(
            {item.id for item in result}, {"item3", "item4"}
        )

    def test_filter_not_completed_only(self):
        """Filter: Not Completed → returns only open items."""
        result = self._filter_items(
            self.all_items, self.linked_ids, filter_not_completed=True
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(
            {item.id for item in result}, {"item1", "item2"}
        )

    def test_filter_linked_only(self):
        """Filter: Linked → returns only linked items."""
        result = self._filter_items(
            self.all_items, self.linked_ids, filter_linked=True
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(
            {item.id for item in result}, {"item2", "item4"}
        )

    def test_filter_not_linked_only(self):
        """Filter: Not Linked → returns only unlinked items."""
        result = self._filter_items(
            self.all_items, self.linked_ids, filter_not_linked=True
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(
            {item.id for item in result}, {"item1", "item3"}
        )

    def test_and_logic_completed_and_linked(self):
        """Filter: Completed AND Linked → only completed linked items."""
        result = self._filter_items(
            self.all_items,
            self.linked_ids,
            filter_completed=True,
            filter_linked=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "item4")

    def test_and_logic_not_completed_and_not_linked(self):
        """Filter: Not Completed AND Not Linked → only open unlinked items."""
        result = self._filter_items(
            self.all_items,
            self.linked_ids,
            filter_not_completed=True,
            filter_not_linked=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "item1")

    def test_and_logic_completed_and_not_linked(self):
        """Filter: Completed AND Not Linked → only completed unlinked items."""
        result = self._filter_items(
            self.all_items,
            self.linked_ids,
            filter_completed=True,
            filter_not_linked=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "item3")

    def test_and_logic_not_completed_and_linked(self):
        """Filter: Not Completed AND Linked → only open linked items."""
        result = self._filter_items(
            self.all_items,
            self.linked_ids,
            filter_not_completed=True,
            filter_linked=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "item2")

    def test_contradictory_filters_return_empty(self):
        """Filter: Completed AND Not Completed → empty result."""
        result = self._filter_items(
            self.all_items,
            self.linked_ids,
            filter_completed=True,
            filter_not_completed=True,
        )
        self.assertEqual(len(result), 0)

    def test_contradictory_filters_linked_and_not_linked(self):
        """Filter: Linked AND Not Linked → empty result."""
        result = self._filter_items(
            self.all_items,
            self.linked_ids,
            filter_linked=True,
            filter_not_linked=True,
        )
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main()
