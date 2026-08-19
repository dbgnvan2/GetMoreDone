"""VPS Segment management — Settings controls, colour validation, deletion guard.

BC3. This file used to be a standalone script renamed into the suite. Every
test was wrapped in ``except Exception: return False`` and returned a bool
instead of asserting, so pytest ignored the verdict and reported green whatever
happened — including an exception. Several checks only printed a ``⚠`` and
carried on, so they could not fail at all.

That was not theoretical. ``test_enhanced_deletion_protection`` **was returning
False**: `delete_segment` had moved from a `vision_count` int to a `counts`
dict, and the test that existed to guard it went on passing. It was checking
the source text for a name that no longer existed.

Rewritten to assert, and to exercise behaviour rather than grep source wherever
that is cheap.

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#batch-1
"""

import inspect

import pytest

from src.getmoredone.screens.settings import SettingsScreen
from src.getmoredone.screens.vps_segment_editor import VPSSegmentEditorDialog
from src.getmoredone.vps_manager import VPSManager


@pytest.fixture
def vps(tmp_path):
    manager = VPSManager(str(tmp_path / "segments.db"))
    yield manager
    manager.close()


# ------------------------------------------------------------------ surface


@pytest.mark.parametrize("method", [
    "create_vps_segments_section",
    "refresh_segments_list",
    "create_segment_row",
    "create_new_segment",
    "edit_segment",
    "delete_segment",
])
def test_bc3_settings_screen_exposes_the_segment_controls(method):
    assert callable(getattr(SettingsScreen, method, None)), (
        f"SettingsScreen.{method} is gone — the Settings segment UI lost a control")


@pytest.mark.parametrize("method", [
    "create_form",
    "load_segment_data",
    "pick_color",
    "validate_color",
    "save_segment",
])
def test_bc3_segment_editor_exposes_its_form_methods(method):
    assert callable(getattr(VPSSegmentEditorDialog, method, None)), (
        f"VPSSegmentEditorDialog.{method} is gone")


@pytest.mark.parametrize("method", [
    "get_all_segments",
    "get_segment",
    "create_segment",
    "update_segment",
    "delete_segment",
])
def test_bc3_vps_manager_exposes_its_segment_methods(method):
    assert callable(getattr(VPSManager, method, None))


def test_bc3_the_colour_picker_is_wired_to_a_real_chooser():
    """The editor must reach tkinter's colour chooser, not just mention it."""
    from src.getmoredone.screens import vps_segment_editor

    assert hasattr(vps_segment_editor, "colorchooser"), (
        "colorchooser is not imported — the colour picker cannot open")
    assert callable(getattr(vps_segment_editor.colorchooser, "askcolor", None))
    assert "askcolor" in inspect.getsource(VPSSegmentEditorDialog.pick_color), (
        "pick_color no longer calls askcolor")


def test_bc3_the_editor_seeds_its_colour_from_the_segment(vps):
    """Restored, and asserted on the built dialog rather than its source.

    The conversion dropped this check; the first attempt to restore it grepped
    __init__ for two words that sit on one line, which is the same shape as the
    grep that had been silently failing.
    """
    import customtkinter as ctk

    segment_id = vps.create_segment("Coloured", "desc", "#0a1b2c", 94)
    segment = dict(vps.get_segment(segment_id))

    root = ctk.CTk()
    root.withdraw()
    try:
        dialog = VPSSegmentEditorDialog(root, vps, segment)
        assert dialog.selected_color == "#0a1b2c", (
            "the editor did not seed its colour from the segment")

        blank = VPSSegmentEditorDialog(root, vps)
        assert blank.selected_color.startswith("#"), (
            "a new segment must start from a usable default colour")
        assert VPSSegmentEditorDialog.validate_color(None, blank.selected_color)
    finally:
        root.destroy()


# -------------------------------------------------------- colour validation


@pytest.mark.parametrize("value", ["#000000", "#ffffff", "#AABBCC", "#1a2b3c"])
def test_bc3_validate_color_accepts_a_full_hex_colour(value):
    assert VPSSegmentEditorDialog.validate_color(None, value) is True


@pytest.mark.parametrize("value,reason", [
    ("aabbcc", "no leading #"),
    ("#abc", "shorthand is not accepted"),
    ("#aabbccdd", "too long"),
    ("#gggggg", "not hexadecimal"),
    ("#12345z", "one bad digit"),
    ("", "empty"),
])
def test_bc3_validate_color_rejects_everything_else(value, reason):
    assert VPSSegmentEditorDialog.validate_color(None, value) is False, reason


# ------------------------------------------------------------- round trip


def test_bc3_a_segment_round_trips_through_the_manager(vps):
    segment_id = vps.create_segment("Test Segment", "desc", "#123456", 99)

    stored = vps.get_segment(segment_id)
    assert stored is not None
    assert stored["name"] == "Test Segment"
    assert stored["color_hex"] == "#123456"

    assert vps.update_segment(
        segment_id, name="Renamed", color_hex="#654321", order_index=98) is True
    stored = vps.get_segment(segment_id)
    assert stored["name"] == "Renamed"
    assert stored["color_hex"] == "#654321"

    # A field the allowlist does not accept must not silently succeed.
    assert vps.update_segment(segment_id, not_a_field="x") is False

    deleted, counts = vps.delete_segment(segment_id)
    assert deleted is True
    assert counts == {}
    assert vps.get_segment(segment_id) is None


# --------------------------------------------------------- deletion guard


def test_bc3_delete_segment_refuses_while_records_are_linked(vps):
    """The guard this file exists for, asserted on behaviour.

    The previous version grepped `delete_segment`'s source for the string
    "vision_count". That name was removed when the return shape changed to a
    dict, so the test had been returning False — reported as a pass — ever
    since.
    """
    segment_id = vps.create_segment("Linked Segment", "desc", "#123456", 97)
    vps.db.conn.execute(
        """
        INSERT INTO tl_visions (id, segment_description_id, start_year, end_year,
                                title, is_active, created_at, updated_at)
        VALUES ('vis-bc3', ?, 2026, 2030, 'A vision', 1, '2026-01-01', '2026-01-01')
        """,
        (segment_id,),
    )
    vps.db.conn.commit()

    deleted, counts = vps.delete_segment(segment_id)

    assert deleted is False, "a segment with a linked vision was deleted"
    assert counts, "the refusal reported no counts, so the UI cannot say why"
    assert any("vision" in label.lower() for label in counts), counts
    assert vps.get_segment(segment_id) is not None, "the row went anyway"


def test_bc3_the_refusal_counts_every_linked_row(vps):
    segment_id = vps.create_segment("Busy Segment", "desc", "#123456", 96)
    for index in (1, 2, 3):
        vps.db.conn.execute(
            """
            INSERT INTO tl_visions (id, segment_description_id, start_year, end_year,
                                    title, is_active, created_at, updated_at)
            VALUES (?, ?, 2026, 2030, 'A vision', 1, '2026-01-01', '2026-01-01')
            """,
            (f"vis-bc3-{index}", segment_id),
        )
    vps.db.conn.commit()

    deleted, counts = vps.delete_segment(segment_id)

    assert deleted is False
    assert sum(counts.values()) == 3, counts


def test_bc3_settings_consumes_the_counts_as_a_mapping(vps):
    """Pin the shape, not the word.

    The original bug was a return-contract drift: `delete_segment` went from
    `tuple[bool, int]` to `tuple[bool, dict]`, and the test guarding it grepped
    for a name that no longer existed. `"counts" in source` would have passed on
    a comment, which is the same failure shape.

    Behaviour is not reachable here without a display — the consumer builds a
    CTkToplevel for typed confirmation — so this asserts the two expressions
    that would break if the return shape changed again.
    """
    source = inspect.getsource(SettingsScreen.delete_segment)

    assert "counts.items()" in source, (
        "the Settings screen no longer iterates the counts mapping — if "
        "delete_segment went back to returning a scalar, this is what breaks")
    assert "sum(counts.values())" in source, (
        "the total shown to the user is no longer derived from the counts")


def test_bc3_delete_segment_returns_a_mapping_not_a_scalar(vps):
    """The contract the Settings screen depends on, asserted on the real call."""
    segment_id = vps.create_segment("Contract", "desc", "#123456", 95)
    vps.db.conn.execute(
        """
        INSERT INTO tl_visions (id, segment_description_id, start_year, end_year,
                                title, is_active, created_at, updated_at)
        VALUES ('vis-contract', ?, 2026, 2030, 'A vision', 1, '2026-01-01', '2026-01-01')
        """,
        (segment_id,),
    )
    vps.db.conn.commit()

    result = vps.delete_segment(segment_id)

    assert isinstance(result, tuple) and len(result) == 2
    success, counts = result
    assert success is False
    assert isinstance(counts, dict), (
        f"delete_segment returned {type(counts).__name__}, and the Settings "
        f"screen calls .items() and sum(.values()) on it")
    assert all(isinstance(value, int) for value in counts.values())
