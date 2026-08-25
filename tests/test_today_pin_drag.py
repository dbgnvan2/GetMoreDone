"""
GUI tests for the Today drag-to-top gesture (Enhancement 1, AC5).

Two layers:
  * handler-level tests drive _start_pin_drag / _finish_pin_drag directly with
    synthetic events (fast, deterministic);
  * an event-level test fires the REAL Tk <ButtonPress-1>/<ButtonRelease-1>
    bindings on an actual grip widget, so a binding regression (like the earlier
    reliance on <B1-Motion>, which never fired on CTkLabel) is caught.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import customtkinter as ctk

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem
from src.getmoredone.screens.today import TodayScreen


def _make_screen(tmp_path, titles=("A", "B"), withdraw=True):
    # Teardown is owned by conftest's _destroy_windows_left_behind_by_this_test,
    # which destroys any window created during a test that is still alive at
    # its end. This helper returns a window to many call sites and had nothing
    # anywhere to destroy it; that was 29 of the 37 leaked windows in a run.
    try:
        root = ctk.CTk()
    except Exception as exc:  # Headless without a display.
        pytest.skip(f"Tk display unavailable: {exc}")
    root.geometry("1200x800+0+0")
    # event_generate + root.update() deadlocks on a withdrawn window, so the
    # event-level test keeps the window mapped; the rest withdraw it.
    if withdraw:
        root.withdraw()

    db = DatabaseManager(str(tmp_path / "t.db"))
    for t in titles:
        db.create_action_item(
            ActionItem(who="Self", title=t, start_date="2026-08-12"))

    app = MagicMock()
    app.vps_manager.get_segment_colors_by_id.return_value = {}
    app.vps_manager.get_segment_color_map.return_value = {}

    screen = TodayScreen(root, db, app)
    screen.pack(fill="both", expand=True)
    screen.update_idletasks()
    return root, db, screen


def _item_by_title(db, title):
    for row in db.db.conn.execute("SELECT id, title FROM action_items").fetchall():
        if row["title"] == title:
            return row["id"]
    raise AssertionError(f"no item titled {title}")


def _grips(screen):
    """Every drag-grip CTkLabel currently rendered, in row order."""
    found = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, ctk.CTkLabel) and str(c.cget("cursor")) == "fleur":
                found.append(c)
            walk(c)

    walk(screen)
    return found


def _first_open_row_title(screen):
    """Title of the top-most rendered OPEN row, read from the widget tree."""
    rows = []
    for w in screen.scroll_frame.winfo_children():
        item = getattr(w, "item", None)
        if item is not None and item.status == "open":
            grid_row = int(w.grid_info().get("row", 0))
            rows.append((grid_row, item.title))
    rows.sort()
    return rows[0][1] if rows else None


# ----------------------- handler-level tests -----------------------

def test_upward_drag_pins(tmp_path):
    root, db, screen = _make_screen(tmp_path)
    try:
        target_id = _item_by_title(db, "B")
        screen.refresh = MagicMock()

        screen._start_pin_drag(target_id, SimpleNamespace(y_root=500))
        screen._finish_pin_drag(SimpleNamespace(y_root=500 - 80))  # dragged up 80

        assert db.get_action_item(target_id).today_pin_rank is not None
        screen.refresh.assert_called_once()
    finally:
        db.close()
        root.destroy()


def test_click_without_travel_does_not_pin(tmp_path):
    root, db, screen = _make_screen(tmp_path)
    try:
        target_id = _item_by_title(db, "B")
        screen.refresh = MagicMock()

        screen._start_pin_drag(target_id, SimpleNamespace(y_root=500))
        screen._finish_pin_drag(SimpleNamespace(y_root=499))  # 1px, below threshold

        assert db.get_action_item(target_id).today_pin_rank is None
        screen.refresh.assert_not_called()
    finally:
        db.close()
        root.destroy()


def test_downward_drag_does_not_pin(tmp_path):
    root, db, screen = _make_screen(tmp_path)
    try:
        target_id = _item_by_title(db, "B")
        screen.refresh = MagicMock()

        screen._start_pin_drag(target_id, SimpleNamespace(y_root=200))
        screen._finish_pin_drag(SimpleNamespace(y_root=400))  # dragged down

        assert db.get_action_item(target_id).today_pin_rank is None
        screen.refresh.assert_not_called()
    finally:
        db.close()
        root.destroy()


# ----------------------- event-level test -----------------------

def test_real_grip_events_pin_on_upward_drag(tmp_path, mapped_windows):
    """Fires the actual Tk bindings on a grip widget (press + release, NO motion
    event) and confirms the item is pinned and re-renders at the top."""
    root, db, screen = _make_screen(tmp_path, titles=("A", "B", "C"), withdraw=False)
    try:
        root.update()
        grips = _grips(screen)
        assert len(grips) == 3
        assert _first_open_row_title(screen) == "A"  # default order

        # Drag the BOTTOM row's grip (item C) upward ~80px and release.
        inner = grips[-1]._label  # CTkLabel forwards binds to this inner Label
        inner.event_generate("<ButtonPress-1>", x=3, y=3)
        inner.event_generate("<ButtonRelease-1>", x=3, y=-80)
        root.update()

        pinned = _item_by_title(db, "C")
        assert db.get_action_item(pinned).today_pin_rank is not None
        # refresh() re-rendered with C floated to the top.
        assert _first_open_row_title(screen) == "C"
    finally:
        db.close()
        root.destroy()


def test_pinned_item_renders_as_first_open_row(tmp_path):
    """End-to-end: after a real pin + re-render, the pinned item is the top row."""
    root, db, screen = _make_screen(tmp_path, titles=("A", "B"))
    try:
        assert _first_open_row_title(screen) == "A"

        db.pin_item_to_today_top(_item_by_title(db, "B"))
        screen.load_items()  # real render, no mocks

        assert _first_open_row_title(screen) == "B"
    finally:
        db.close()
        root.destroy()
