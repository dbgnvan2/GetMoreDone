"""Tests for the reusable date picker.

Purpose: record the picker's public contract before tkcalendar is swapped out,
         then hold the replacement to it.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m2b
Tests:   this file

Written against the *tkcalendar-backed* picker first, deliberately. tkcalendar
is GPLv3 and cannot ship inside a proprietary binary (finding F2), so the widget
is being reimplemented on the stdlib ``calendar`` module. The contract tests
below passed before that swap, which is what makes them meaningful afterwards —
a contract recorded after a rewrite only describes the rewrite.

The month-grid tests are pure functions on purpose: correct week layout is
arithmetic, and arithmetic should not need a display to verify.
"""

from __future__ import annotations

import calendar
import inspect
from datetime import date, datetime

import pytest

import customtkinter as ctk

from src.getmoredone.widgets.date_picker import DatePickerButton


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _root():
    # Teardown is owned by conftest's _destroy_windows_left_behind_by_this_test,
    # which destroys any window created during a test that is still alive at
    # its end. This helper returns a window to many call sites and had nothing
    # anywhere to destroy it; that was 29 of the 37 leaked windows in a run.
    try:
        root = ctk.CTk()
    except Exception as exc:  # Headless without a display.
        pytest.skip(f"Tk display unavailable: {exc}")
    root.withdraw()
    return root


# --------------------------------------------------------------------------
# R-M2.B.1 — the public interface must survive the swap
# --------------------------------------------------------------------------

# Recorded from the tkcalendar-backed widget on 2026-08-18, before the rewrite.
EXPECTED_INIT_PARAMS = ("parent", "initial_date", "on_date_changed")
EXPECTED_PUBLIC_METHODS = ("get_date", "set_date", "open_calendar")


def test_rm2b1_date_picker_public_interface_unchanged():
    """Calling screens must not have to change (vps_editors.py builds two)."""
    sig = inspect.signature(DatePickerButton.__init__)
    params = list(sig.parameters)

    for name in EXPECTED_INIT_PARAMS:
        assert name in params, f"constructor lost parameter {name!r}: {params}"

    assert any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    ), "constructor must still forward **kwargs to CTkFrame"

    for name in EXPECTED_PUBLIC_METHODS:
        assert callable(getattr(DatePickerButton, name, None)), f"lost method {name!r}"


def test_rm2b1_optional_params_keep_their_defaults():
    """initial_date and on_date_changed must stay optional — vps_editors.py
    constructs the picker with a parent and nothing else."""
    sig = inspect.signature(DatePickerButton.__init__)
    assert sig.parameters["initial_date"].default is None
    assert sig.parameters["on_date_changed"].default is None


def test_rm2b1_picker_returns_selected_date():
    """Behavioural: what set_date stores is what get_date returns."""
    root = _root()
    try:
        picker = DatePickerButton(root)
        picker.set_date("2026-03-17")
        assert picker.get_date() == "2026-03-17"
    finally:
        root.destroy()


def test_rm2b1_picker_accepts_a_datetime_for_set_date():
    root = _root()
    try:
        picker = DatePickerButton(root)
        picker.set_date(datetime(2026, 12, 1, 9, 30))
        assert picker.get_date() == "2026-12-01"
    finally:
        root.destroy()


def test_rm2b1_initial_date_is_honoured():
    root = _root()
    try:
        picker = DatePickerButton(root, initial_date="2025-01-02")
        assert picker.get_date() == "2025-01-02"
    finally:
        root.destroy()


def test_rm2b1_picker_defaults_to_today():
    root = _root()
    try:
        picker = DatePickerButton(root)
        assert picker.get_date() == datetime.now().strftime("%Y-%m-%d")
    finally:
        root.destroy()


def test_rm2b1_on_date_changed_fires_with_the_new_value():
    root = _root()
    try:
        seen = []
        picker = DatePickerButton(root, on_date_changed=seen.append)
        seen.clear()  # drop the callback fired by the constructor's initial set
        picker.set_date("2026-06-06")
        assert seen == ["2026-06-06"]
    finally:
        root.destroy()


def test_rm2b1_open_calendar_builds_a_popup_and_reuses_it():
    """A second click must lift the existing popup, not stack a new one."""
    root = _root()
    try:
        picker = DatePickerButton(root, initial_date="2026-05-15")
        picker.open_calendar()
        root.update_idletasks()
        first = picker.calendar_popup
        assert first is not None and first.winfo_exists()

        picker.open_calendar()
        root.update_idletasks()
        assert picker.calendar_popup is first, "a second open created a new popup"
        first.destroy()
    finally:
        root.destroy()


# --------------------------------------------------------------------------
# R-M2.B.2 — the replacement honours settings.first_day_of_week
# --------------------------------------------------------------------------

def test_rm2b2_weekday_headers_honour_first_day_of_week():
    """0 = Monday .. 6 = Sunday, matching AppSettings.first_day_of_week."""
    from src.getmoredone.widgets.date_picker import weekday_headers

    monday_first = weekday_headers(0)
    sunday_first = weekday_headers(6)

    assert len(monday_first) == 7 and len(sunday_first) == 7
    assert monday_first[0].lower().startswith("mo")
    assert sunday_first[0].lower().startswith("su")
    # Same seven names, rotated — not a different set.
    assert set(monday_first) == set(sunday_first)
    assert sunday_first == monday_first[6:] + monday_first[:6]


@pytest.mark.parametrize("first_day", [0, 1, 2, 3, 4, 5, 6])
def test_rm2b2_month_grid_matches_stdlib_calendar(first_day):
    """The grid is stdlib arithmetic; assert it against stdlib, not a snapshot."""
    from src.getmoredone.widgets.date_picker import month_grid

    for year, month in ((2024, 2), (2026, 2), (2023, 10), (2026, 3), (2027, 8)):
        expected = calendar.Calendar(firstweekday=first_day).monthdayscalendar(year, month)
        assert month_grid(year, month, first_day) == expected, (
            f"grid mismatch for {year}-{month:02d} with first_day={first_day}"
        )


def test_rm2b2_month_grid_covers_awkward_boundaries():
    """February of a leap year, and a month that starts on the first column."""
    from src.getmoredone.widgets.date_picker import month_grid

    leap = month_grid(2024, 2, 0)
    days = [d for week in leap for d in week if d]
    assert days == list(range(1, 30)), "2024-02 should run 1..29"

    # 2026-06-01 is a Monday: with Monday first there is no leading padding.
    june = month_grid(2026, 6, 0)
    assert june[0][0] == 1, f"expected 2026-06 to start flush, got {june[0]}"


@pytest.mark.parametrize("bad_first_day", [-1, 7, 99, None, "monday"])
def test_rm2b2_month_grid_tolerates_a_bad_first_day_setting(bad_first_day):
    """settings.json is user-writable; a junk value must not raise."""
    from src.getmoredone.widgets.date_picker import month_grid

    grid = month_grid(2026, 8, bad_first_day)
    assert grid == calendar.Calendar(firstweekday=0).monthdayscalendar(2026, 8)


def test_rm2b2_picker_uses_the_injected_settings_first_day_of_week():
    """The widget must read the real setting, not a hardcoded default (P25:
    a value that exists but never reaches the call is decoration)."""
    from src.getmoredone.widgets.date_picker import weekday_headers

    root = _root()
    try:
        settings = type("S", (), {"first_day_of_week": 6})()
        picker = DatePickerButton(root, initial_date="2026-05-15", settings=settings)
        picker.open_calendar()
        root.update_idletasks()
        assert picker.calendar_popup is not None

        headers = picker.header_labels()
        assert headers == weekday_headers(6), (
            f"picker ignored settings.first_day_of_week=6; rendered {headers}"
        )
        picker.calendar_popup.destroy()
    finally:
        root.destroy()


def test_rm2b2_picker_grid_renders_the_month_of_the_current_value():
    root = _root()
    try:
        picker = DatePickerButton(root, initial_date="2024-02-15")
        picker.open_calendar()
        root.update_idletasks()
        assert picker.visible_month() == (2024, 2)
        picker.calendar_popup.destroy()
    finally:
        root.destroy()


# --------------------------------------------------------------------------
# R-M2.B.1 — selecting a day in the popup writes it back
# --------------------------------------------------------------------------

def test_rm2b1_selecting_a_day_sets_the_date_and_closes_the_popup():
    root = _root()
    try:
        picker = DatePickerButton(root, initial_date="2026-05-15")
        picker.open_calendar()
        root.update_idletasks()

        picker.select_day(3)
        root.update_idletasks()

        assert picker.get_date() == "2026-05-03"
        assert picker.calendar_popup is None or not picker.calendar_popup.winfo_exists()
    finally:
        root.destroy()


def test_rm2b1_month_navigation_moves_across_a_year_boundary():
    root = _root()
    try:
        picker = DatePickerButton(root, initial_date="2026-12-10")
        picker.open_calendar()
        root.update_idletasks()

        picker.show_next_month()
        assert picker.visible_month() == (2027, 1)
        picker.show_previous_month()
        picker.show_previous_month()
        assert picker.visible_month() == (2026, 11)
        picker.calendar_popup.destroy()
    finally:
        root.destroy()


def test_rm2b1_navigating_months_does_not_change_the_stored_date():
    """Browsing is not selecting — the entry must not move until a day is clicked."""
    root = _root()
    try:
        picker = DatePickerButton(root, initial_date="2026-12-10")
        picker.open_calendar()
        root.update_idletasks()
        picker.show_next_month()
        picker.show_next_month()
        assert picker.get_date() == "2026-12-10"
        picker.calendar_popup.destroy()
    finally:
        root.destroy()


def test_rm2b1_today_button_jumps_to_today():
    root = _root()
    try:
        picker = DatePickerButton(root, initial_date="2020-01-01")
        picker.open_calendar()
        root.update_idletasks()
        picker.select_today()
        root.update_idletasks()
        assert picker.get_date() == date.today().strftime("%Y-%m-%d")
    finally:
        root.destroy()


def test_rm2b1_open_calendar_survives_a_corrupt_entry_value():
    """The entry is free text; a bad value must fall back to today, not raise."""
    root = _root()
    try:
        picker = DatePickerButton(root)
        picker.date_entry.delete(0, "end")
        picker.date_entry.insert(0, "not-a-date")
        picker.open_calendar()
        root.update_idletasks()
        today = date.today()
        assert picker.visible_month() == (today.year, today.month)
        picker.calendar_popup.destroy()
    finally:
        root.destroy()


# --------------------------------------------------------------------------
# Theme compliance (project CLAUDE.md: no hard-coded colors in widgets)
# --------------------------------------------------------------------------

def test_date_picker_has_no_hardcoded_hex_colors():
    """The tkcalendar version hardcoded darkblue/white/lightgray, which ignored
    the active theme entirely. The replacement must use theme tokens."""
    import re
    from pathlib import Path

    # Named colors too, not just hex — the tkcalendar version used 'darkblue',
    # 'white' and 'lightgray', which a hex-only check would wave straight through.
    NAMED = (
        "white", "black", "darkblue", "lightblue", "lightgray", "lightgrey",
        "gray", "grey", "red", "green", "blue", "yellow", "orange", "pink",
        "purple", "cyan", "magenta",
    )

    source = Path(__file__).resolve().parents[1] / "src/getmoredone/widgets/date_picker.py"
    text = source.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )

    hexes = re.findall(r"['\"]#[0-9a-fA-F]{3,8}['\"]", code)
    assert not hexes, f"hard-coded hex colors in date_picker.py: {hexes}"

    named_hits = sorted({
        m for m in re.findall(r"['\"]([A-Za-z]+)['\"]", code)
        if m.lower() in NAMED
    })
    assert not named_hits, (
        f"hard-coded named colors in date_picker.py: {named_hits}. "
        "Use theme tokens (see theme.semantic_colors) so the picker follows "
        "the active theme."
    )
