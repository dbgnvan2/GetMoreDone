"""
Tests for the Today list "drag to top" pin feature.

Covers:
  * AC1 - migration adds today_pin_rank to an existing (older-shape) DB.
  * AC2 - pin_item_to_today_top ranks an item above the current max; a second
          pin beats the first.
  * AC3 - a pin survives update_action_item / reschedule / priority edits
          (round-trip; the derived priority_score is never confused with it).
  * AC4 - the Today open-row sort key floats a pinned item to the very top even
          when it has a later date and a lower priority score (adversarial).
"""

import sqlite3

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem
from src.getmoredone.screens.today import TodayScreen


def _make_item(**kwargs) -> ActionItem:
    base = dict(who="Self", title="T")
    base.update(kwargs)
    return ActionItem(**base)


def test_migration_adds_today_pin_rank(tmp_path):
    """AC1: an existing DB that predates today_pin_rank gets the column added
    idempotently when DatabaseManager initializes over it.

    We build a real, current DB, drop the column to emulate an older DB, and
    confirm re-opening restores it (and leaves existing rows non-null-safe).
    """
    db_file = tmp_path / "old.db"

    # Create a full, valid DB, seed a row, then strip the new column.
    db = DatabaseManager(str(db_file))
    db.create_action_item(_make_item(title="Existing", start_date="2026-08-12"))
    db.close()

    conn = sqlite3.connect(str(db_file))
    conn.execute("ALTER TABLE action_items DROP COLUMN today_pin_rank")
    conn.commit()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(action_items)").fetchall()]
    assert "today_pin_rank" not in cols
    conn.close()

    # Re-opening through DatabaseManager runs migrations and re-adds it.
    db = DatabaseManager(str(db_file))
    try:
        cols = [
            r[1]
            for r in db.db.conn.execute("PRAGMA table_info(action_items)").fetchall()
        ]
        assert "today_pin_rank" in cols
        # Existing rows load cleanly with an unpinned (None) rank.
        rows = db.db.conn.execute("SELECT id FROM action_items").fetchall()
        assert rows
        assert db.get_action_item(rows[0]["id"]).today_pin_rank is None
    finally:
        db.close()


def test_pin_item_to_today_top_orders(tmp_path):
    """AC2: pinning sets a rank above the current max; a later pin outranks it."""
    db = DatabaseManager(str(tmp_path / "t.db"))
    try:
        a = _make_item(title="A", start_date="2026-08-12")
        b = _make_item(title="B", start_date="2026-08-12")
        db.create_action_item(a)
        db.create_action_item(b)

        # Nothing pinned yet.
        assert db.get_action_item(a.id).today_pin_rank is None
        assert db.get_action_item(b.id).today_pin_rank is None

        assert db.pin_item_to_today_top(a.id) is True
        rank_a = db.get_action_item(a.id).today_pin_rank
        assert rank_a is not None and rank_a > 0

        assert db.pin_item_to_today_top(b.id) is True
        rank_b = db.get_action_item(b.id).today_pin_rank
        assert rank_b > rank_a  # most recently dragged to top wins

        # Pinning a missing item reports failure.
        assert db.pin_item_to_today_top("does-not-exist") is False
    finally:
        db.close()


def test_today_pin_rank_persists_through_update(tmp_path):
    """AC3: a pin is not recomputed or dropped by ordinary saves.

    priority_score is derived (I x U x S x V) and recomputed on every save, but
    today_pin_rank must round-trip untouched through update_action_item,
    reschedule_item, and a priority-factor edit.
    """
    db = DatabaseManager(str(tmp_path / "t.db"))
    try:
        item = _make_item(
            title="Pinned", start_date="2026-08-12", due_date="2026-08-13",
            importance=5, urgency=5, size=4, value=4,
        )
        db.create_action_item(item)
        db.pin_item_to_today_top(item.id)
        pinned_rank = db.get_action_item(item.id).today_pin_rank
        assert pinned_rank is not None

        # Full update (e.g. edited from the item editor).
        reloaded = db.get_action_item(item.id)
        reloaded.title = "Pinned (renamed)"
        db.update_action_item(reloaded)
        assert db.get_action_item(item.id).today_pin_rank == pinned_rank

        # Priority-factor edit recomputes priority_score but keeps the pin.
        reloaded = db.get_action_item(item.id)
        reloaded.importance = 20
        reloaded.urgency = 20
        db.update_action_item(reloaded, normalize_week_dates=False)
        after = db.get_action_item(item.id)
        assert after.today_pin_rank == pinned_rank
        assert after.priority_score == 20 * 20 * 4 * 4  # derived, still honest

        # Reschedule keeps the pin too.
        db.reschedule_item(item.id, "2026-08-20", "2026-08-21", reason="test")
        assert db.get_action_item(item.id).today_pin_rank == pinned_rank
    finally:
        db.close()


def test_today_open_sort_key_pin_wins():
    """AC4 (adversarial): a pinned item with a LATER date and LOWER priority
    still sorts ahead of an unpinned earlier/higher-priority item."""
    pinned_but_worse = _make_item(
        title="Pinned", start_date="2026-08-20", due_date="2026-08-20",
    )
    pinned_but_worse.priority_score = 10
    pinned_but_worse.today_pin_rank = 1

    unpinned_better = _make_item(
        title="Unpinned", start_date="2026-08-12", due_date="2026-08-12",
    )
    unpinned_better.priority_score = 10000
    unpinned_better.today_pin_rank = None

    ordered = sorted(
        [unpinned_better, pinned_but_worse],
        key=TodayScreen._today_open_sort_key,
    )
    assert ordered[0].title == "Pinned"
    assert ordered[1].title == "Unpinned"

    # Two pinned items: higher rank (dragged to top more recently) comes first.
    older_pin = _make_item(title="OldPin", start_date="2026-08-12")
    older_pin.today_pin_rank = 1
    newer_pin = _make_item(title="NewPin", start_date="2026-08-12")
    newer_pin.today_pin_rank = 2
    ordered = sorted(
        [older_pin, newer_pin], key=TodayScreen._today_open_sort_key
    )
    assert [i.title for i in ordered] == ["NewPin", "OldPin"]


def test_today_top3_sort_key_pin_first_then_priority():
    """Top-3 mode floats pinned rows first, then ranks the rest by priority."""
    high = _make_item(title="High")
    high.priority_score = 5000
    low_pinned = _make_item(title="LowPinned")
    low_pinned.priority_score = 1
    low_pinned.today_pin_rank = 1

    ordered = sorted([high, low_pinned], key=TodayScreen._today_top3_sort_key)
    assert [i.title for i in ordered] == ["LowPinned", "High"]
