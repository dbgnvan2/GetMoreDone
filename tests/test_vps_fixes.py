"""VPS editor and planning screen — the structure two old bug fixes depend on.

BC3. Converted from a standalone script: every test returned a bool inside
``except Exception: return False``, so pytest ignored the verdict and an
exception read as a pass. None of these four were lying at the time of the
conversion — unlike ``test_vps_segments``, which was — but none of them could
have told us if they started.

The two fixes these guard:
  * the New Vision crash — `CTkMessageBox` replaced with tkinter's `messagebox`
  * segment selection on the planning screen — `selected_segments`

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#batch-1
"""

import inspect

import pytest

from src.getmoredone.screens import vps_editors
from src.getmoredone.screens.vps_editors import TLVisionEditorDialog
from src.getmoredone.screens.vps_planning import VPSPlanningScreen


def test_bc3_messagebox_is_imported_in_vps_editors():
    """The New Vision crash was a missing messagebox, so this is the guard."""
    assert hasattr(vps_editors, "messagebox"), (
        "vps_editors has no messagebox — save_vision's error paths will raise")
    assert callable(getattr(vps_editors.messagebox, "showerror", None))


def test_bc3_save_vision_does_not_use_ctkmessagebox():
    """`CTkMessageBox` does not exist in this CustomTkinter build — it crashed."""
    source = inspect.getsource(TLVisionEditorDialog.save_vision)

    assert "CTkMessageBox" not in source, (
        "CTkMessageBox is back in save_vision — this is the New Vision crash")


def test_bc3_save_vision_still_reports_errors_to_the_user():
    """Removing the crash must not have removed the error message with it.

    The original check printed a warning and passed when no messagebox call was
    found, so a silent save_vision would have gone unnoticed.
    """
    source = inspect.getsource(TLVisionEditorDialog.save_vision)

    assert ("messagebox.showerror" in source or "messagebox.showinfo" in source), (
        "save_vision no longer tells the user anything when it fails")


@pytest.mark.parametrize("method", [
    "show_segment_filter_dialog",
    "update_segment_filter",
])
def test_bc3_planning_screen_exposes_segment_selection(method):
    assert callable(getattr(VPSPlanningScreen, method, None)), (
        f"VPSPlanningScreen.{method} is gone — segment filtering is unreachable")


def test_bc3_planning_screen_tracks_selected_segments():
    source = inspect.getsource(VPSPlanningScreen.__init__)

    assert "selected_segments" in source, (
        "VPSPlanningScreen no longer initialises selected_segments, so the "
        "segment filter has nothing to write to")
