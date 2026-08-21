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

from tests.source_asserts import calls_attribute, iterates_mapping

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
    assert calls_attribute(VPSSegmentEditorDialog.pick_color, "colorchooser", "askcolor"), (
        "pick_color no longer calls colorchooser.askcolor")


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


def test_rn_the_editor_refuses_a_case_only_duplicate_and_keeps_the_edit(vps, monkeypatch):
    """P25 — the guard has to reach the surface a person actually uses.

    `update_segment` refusing is worth nothing if Save swallows the refusal or
    closes the dialog anyway. This drives the editor's own save_segment with a
    colliding name and asserts three things: the table is unchanged, the user
    is told why, and the dialog is still open with their typing in it.
    """
    import customtkinter as ctk
    from src.getmoredone.screens import vps_segment_editor

    existing = vps.get_all_segments(active_only=False)[0]["name"]
    segment_id = vps.create_segment("Utterly Distinct", "d", "#0a1b2c", 95)
    segment = dict(vps.get_segment(segment_id))

    errors = []
    monkeypatch.setattr(
        vps_segment_editor.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )

    root = ctk.CTk()
    root.withdraw()
    try:
        dialog = VPSSegmentEditorDialog(root, vps, segment)
        dialog.name_entry.delete(0, "end")
        dialog.name_entry.insert(0, existing.upper())

        dialog.save_segment()

        assert errors, "the editor saved or failed silently — the user was told nothing"
        assert "already exists" in errors[-1][1], (
            f"the refusal reason did not reach the user: {errors[-1]}")

        names = [seg["name"] for seg in vps.get_all_segments(active_only=False)]
        assert sum(1 for n in names if n.lower() == existing.lower()) == 1, (
            f"a case-duplicate reached the table through the editor: {names}")
        assert vps.get_segment(segment_id)["name"] == "Utterly Distinct", (
            "the segment was renamed despite the refusal")

        assert dialog.winfo_exists(), "the dialog closed and discarded the edit"
        assert dialog.name_entry.get() == existing.upper(), (
            "the user's typing was thrown away")
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
    assert iterates_mapping(SettingsScreen.delete_segment, "counts"), (
        "the Settings screen no longer iterates the counts mapping — if "
        "delete_segment went back to returning a scalar, this is what breaks")
    assert calls_attribute(SettingsScreen.delete_segment, "counts", "values"), (
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


# ------------------------------------- deletion guard: every table, not one


def _full_vsp_chain(vps, segment_id, year=2026):
    """Build one row in each of the seven tables delete_segment counts.

    Entirely through the manager's public API — this is what ordinary use
    produces, which is the point: an earlier note in this repo claimed these
    rows "cannot be exercised" because every table has a NOT NULL foreign key
    to its parent. That confused *orphan* with *linked*. delete_segment counts
    `WHERE segment_description_id = ?`, and a normal chain sets that column on
    every row.
    """
    tl = vps.create_tl_vision(
        segment_description_id=segment_id, start_year=year - 1,
        end_year=year + 4, title="TL")
    annual_vision = vps.create_annual_vision(
        tl_vision_id=tl, segment_description_id=segment_id, year=year, title="AV")
    plan = vps.create_annual_plan(
        annual_vision_id=annual_vision, segment_description_id=segment_id,
        year=year, theme="Theme")
    initiative = vps.create_annual_initiative(
        annual_plan_id=plan, segment_description_id=segment_id, year=year,
        title="AI", auto_create_chain=False)
    quarter = vps.create_quarter_initiative(
        segment_description_id=segment_id, quarter=1, year=year, title="QI",
        annual_initiative_id=initiative, annual_plan_id=plan,
        auto_create_chain=False)
    tactic = vps.create_month_tactic(
        quarter_initiative_id=quarter, segment_description_id=segment_id,
        month=1, year=year, priority_focus="Focus", auto_create_weeks=False)
    vps.create_week_action(
        month_tactic_id=tactic, segment_description_id=segment_id,
        week_start_date=f"{year}-01-05", week_end_date=f"{year}-01-11",
        title="WA")
    return {"annual_plan_id": plan, "quarter_initiative_id": quarter,
            "month_tactic_id": tactic}


ALL_VSP_LABELS = [
    "TL Visions", "Annual Visions", "Annual Plans", "Annual Initiatives",
    "Quarter Initiatives", "Month Tactics", "Week Actions",
]


def test_bc3_delete_segment_counts_every_vsp_table(vps):
    """The docstring says it checks ALL VSP tables. Check all of them."""
    segment_id = vps.create_segment("Full chain", "desc", "#123456", 90)
    _full_vsp_chain(vps, segment_id)

    deleted, counts = vps.delete_segment(segment_id)

    assert deleted is False
    for label in ALL_VSP_LABELS:
        assert counts.get(label) == 1, (
            f"{label} was not counted — delete_segment does not check every "
            f"table after all: {counts}")


@pytest.mark.parametrize("label,table", [
    ("Annual Plans", "annual_plans"),
    ("Annual Initiatives", "annual_initiatives"),
    ("Quarter Initiatives", "quarter_initiatives"),
    ("Month Tactics", "month_tactics"),
    ("Week Actions", "week_actions"),
])
def test_bc3_a_single_non_vision_table_blocks_deletion_on_its_own(vps, label, table):
    """Each table must block by itself, not only as part of a full chain.

    The parents hang off a *second* segment, so the segment under test is
    referenced by exactly one row in exactly one table — which is what proves
    the check is per-table rather than a proxy for "has a TL Vision".
    """
    parents = vps.create_segment("Parents", "desc", "#222222", 89)
    target = vps.create_segment("Target", "desc", "#333333", 88)
    ids = _full_vsp_chain(vps, parents)

    vps.db.conn.execute(
        f"UPDATE {table} SET segment_description_id = ? WHERE id = ("
        f"  SELECT id FROM {table} WHERE segment_description_id = ? LIMIT 1)",
        (target, parents),
    )
    vps.db.conn.commit()

    deleted, counts = vps.delete_segment(target)

    assert deleted is False, f"a segment referenced only by {table} was deleted"
    assert counts == {label: 1}, (
        f"expected exactly {label}, got {counts} — the check is not per-table")
