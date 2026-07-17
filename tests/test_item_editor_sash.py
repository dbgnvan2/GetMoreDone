"""
Regression tests for the draggable divider (sash) between the two columns of
the Item Editor.

Contract (as specified by the user):
  * the right panel's right edge stays pinned to the window's right edge;
  * dragging the divider moves the boundary — the right panel's LEFT edge moves;
  * when the left panel gets narrower the right panel gets wider (and vice versa);
  * the right panel's content fills the panel as it widens.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import customtkinter as ctk

from src.getmoredone.screens.item_editor import ItemEditorDialog
from src.getmoredone.models import ActionItem


def _make_dialog():
    db = MagicMock()
    db.get_defaults.return_value = None
    db.get_all_contacts.return_value = []
    db.get_distinct_groups.return_value = []
    db.get_distinct_categories.return_value = []
    db.get_item_links.return_value = []
    db.get_action_item.return_value = ActionItem(id="i", who="Self", title="T")

    root = ctk.CTk()
    root.withdraw()
    dialog = ItemEditorDialog(root, db, vps_manager=MagicMock())
    dialog.geometry("920x600+0+0")
    dialog.update_idletasks()
    dialog.update()
    return root, dialog


def test_sash_drag_resizes_both_panels_and_pins_right_edge():
    root, dialog = _make_dialog()
    try:
        mf = dialog.main_frame
        left_before = dialog.left_col.winfo_width()
        right_before = dialog.right_col.winfo_width()
        window_right_edge = mf.winfo_rootx() + mf.winfo_width()
        right_edge_before = dialog.right_col.winfo_rootx() + dialog.right_col.winfo_width()

        # Right panel's right edge starts flush with the window's right edge.
        assert abs(right_edge_before - window_right_edge) <= 1

        # Drag the divider LEFT by 120px.
        dialog._start_sash_drag(SimpleNamespace(x_root=500))
        dialog._do_sash_drag(SimpleNamespace(x_root=380))
        dialog.update_idletasks()
        dialog.update()

        left_after = dialog.left_col.winfo_width()
        right_after = dialog.right_col.winfo_width()
        right_edge_after = dialog.right_col.winfo_rootx() + dialog.right_col.winfo_width()

        # Right grew, left shrank (both panels changed).
        assert right_after > right_before, (right_before, right_after)
        assert left_after < left_before, (left_before, left_after)
        # Space is conserved: what the right panel gained the left panel lost.
        assert abs((right_after - right_before) - (left_before - left_after)) <= 2
        # Right edge is STILL pinned to the window's right edge.
        assert abs(right_edge_after - window_right_edge) <= 1
    finally:
        root.destroy()


def test_sash_drag_is_clamped_to_a_minimum_left_panel():
    root, dialog = _make_dialog()
    try:
        # Drag the divider far to the right (huge positive delta) — the right
        # panel must not collapse below its minimum.
        dialog._start_sash_drag(SimpleNamespace(x_root=500))
        dialog._do_sash_drag(SimpleNamespace(x_root=5000))
        assert dialog.right_pane_width >= 280
    finally:
        root.destroy()


def test_right_panel_content_fills_widened_panel():
    root, dialog = _make_dialog()
    try:
        tabview_before = dialog.tabview.winfo_width()
        dialog._start_sash_drag(SimpleNamespace(x_root=500))
        dialog._do_sash_drag(SimpleNamespace(x_root=380))
        dialog.update_idletasks()
        dialog.update()
        # The tabview grows with the panel rather than leaving an empty gap.
        assert dialog.tabview.winfo_width() > tabview_before
    finally:
        root.destroy()
