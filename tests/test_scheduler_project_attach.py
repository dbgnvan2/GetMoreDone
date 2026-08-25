"""
Tests for the Scheduler "Projects" tab: listing projects, attaching action
items to a project via drag-release, the header Project filter, and the
Select-All checkbox.

These instantiate the real DragScheduleScreen (same pattern as
tests/test_ui_presence.py) against a seeded temp DB.
"""

from types import SimpleNamespace

import customtkinter as ctk

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.vps_manager import VPSManager
from src.getmoredone.models import ActionItem
from src.getmoredone.screens.drag_schedule import DragScheduleScreen


def _seed_two_apes(db_path: str):
    mgr = VPSManager(db_path)
    try:
        seg = mgr.get_all_segments(active_only=False)[0]["name"]
        mgr.create_vision_subsegment(seg, "Board Test")
        ve_a = mgr.create_or_get_vision_element(seg, "Board Test", "Cat A")
        ve_b = mgr.create_or_get_vision_element(seg, "Board Test", "Cat B")
        ape_a = mgr.create_annual_records_from_vision_element(2026, ve_a)["annual_plan_element_id"]
        ape_b = mgr.create_annual_records_from_vision_element(2026, ve_b)["annual_plan_element_id"]
        return ape_a, ape_b
    finally:
        mgr.close()


def _build_screen(tmp_path):
    # Teardown is owned by conftest's _destroy_windows_left_behind_by_this_test,
    # which destroys any window created during a test that is still alive at
    # its end. This helper returns a window to many call sites and had nothing
    # anywhere to destroy it; that was 29 of the 37 leaked windows in a run.
    db_path = str(tmp_path / "sched.db")
    dbm = DatabaseManager(db_path)
    ape_a, ape_b = _seed_two_apes(db_path)
    board_a = dbm.ensure_project_board_for_ape(ape_a)
    board_b = dbm.ensure_project_board_for_ape(ape_b)

    items = []
    for i in range(3):
        it = ActionItem(who="Self", title=f"Task {i}")
        dbm.create_action_item(it)
        items.append(it)
    # Task 0 starts already linked to board_a.
    dbm.link_item_to_project_exclusive(board_a, items[0].id)

    vps = VPSManager(db_path)
    app = SimpleNamespace(vps_manager=vps)
    root = ctk.CTk()
    root.withdraw()
    scr = DragScheduleScreen(root, dbm, app)
    root.update_idletasks()
    return root, scr, dbm, vps, board_a, board_b, items


def test_projects_tab_lists_boards_and_filter_options(tmp_path):
    root, scr, dbm, vps, board_a, board_b, _items = _build_screen(tmp_path)
    try:
        box_ids = {b["id"] for b in scr.project_boxes}
        assert board_a in box_ids
        assert board_b in box_ids
        # Header Project filter offers All + Unlinked + both boards.
        values = list(scr.project_filter_combo.cget("values"))
        assert "All" in values and "(Unlinked)" in values
        assert len([v for v in values if v not in ("All", "(Unlinked)")]) >= 2
    finally:
        root.destroy(); vps.close(); dbm.close()


def test_select_all_checks_and_clears_every_row(tmp_path):
    root, scr, dbm, vps, _a, _b, _items = _build_screen(tmp_path)
    try:
        n = len(scr.item_checkboxes)
        assert n >= 3

        scr.select_all_var.set(True)
        scr._on_select_all_toggled()
        assert len(scr.checked_items) == n
        assert scr.checked_items == set(scr.item_checkboxes.keys())

        scr.select_all_var.set(False)
        scr._on_select_all_toggled()
        assert scr.checked_items == set()
    finally:
        root.destroy(); vps.close(); dbm.close()


def test_clicking_project_filters_item_list(tmp_path):
    root, scr, dbm, vps, board_a, _b, items = _build_screen(tmp_path)
    try:
        scr.on_project_target_click(board_a)
        assert scr.selected_project_id == board_a
        loaded_ids = {it.id for it in scr.load_items()}
        assert items[0].id in loaded_ids          # linked to board_a
        assert items[1].id not in loaded_ids       # not linked
        # The header Project combo re-synced to the clicked board.
        assert scr.project_filter_var.get() not in ("All", "(Unlinked)")
    finally:
        root.destroy(); vps.close(); dbm.close()


def test_project_filter_dropdown_selects_project(tmp_path):
    root, scr, dbm, vps, _a, board_b, items = _build_screen(tmp_path)
    try:
        # Find the display name mapped to board_b and select it.
        display_b = next(d for d, pid in scr.project_filter_map.items() if pid == board_b)
        scr.project_filter_var.set(display_b)
        scr.on_project_filter_changed()
        assert scr.selected_project_id == board_b
    finally:
        root.destroy(); vps.close(); dbm.close()


def test_stale_selected_project_is_cleared_on_sync(tmp_path):
    # P6 regression: if the selected project vanishes from the filter list
    # (completed/deleted), syncing must clear selected_project_id so the item
    # list and the combo don't disagree.
    root, scr, dbm, vps, _a, _b, _items = _build_screen(tmp_path)
    try:
        scr.selected_project_id = "no-such-board-id"
        scr._sync_project_filter_var()
        assert scr.selected_project_id is None
        assert scr.project_filter_var.get() == "All"
    finally:
        root.destroy(); vps.close(); dbm.close()


def test_drag_release_attaches_items_to_project(tmp_path):
    root, scr, dbm, vps, _a, board_b, items = _build_screen(tmp_path)
    try:
        # Simulate dragging Task 1 (unlinked) and releasing over project board_b.
        scr.drag_item = items[1]
        scr.drag_items = [items[1]]
        scr.get_drop_target = lambda: (None, board_b)  # instance is destroyed after test
        scr.on_drag_release(None)

        linked_ids = {it.id for it in dbm.get_project_board_items(board_b)}
        assert items[1].id in linked_ids
    finally:
        root.destroy(); vps.close(); dbm.close()
