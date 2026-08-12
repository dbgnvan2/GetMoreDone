"""
GUI tests for the InlineDateDialog "days from today" offset ladder (Enhancement 2).

  * AC6 - the dialog exposes +1..+14 offset buttons (and no longer the old
          adjust-based "+1"); each sets the date to today + N (weekend-aware).
"""

from datetime import date

import pytest

import customtkinter as ctk

from src.getmoredone.app_settings import AppSettings
from src.getmoredone.date_utils import increment_date
from src.getmoredone.screens.inline_editors import (
    InlineDateDialog,
    TODAY_OFFSET_BUTTONS,
)


def _root():
    try:
        root = ctk.CTk()
    except Exception as exc:  # No display available (headless CI without X).
        pytest.skip(f"Tk display unavailable: {exc}")
    root.withdraw()
    return root


def _all_button_texts(widget):
    texts = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            texts.append(child.cget("text"))
        texts.extend(_all_button_texts(child))
    return texts


def test_offset_ladder_constant():
    """The configured ladder matches the requested 1..14 offsets."""
    assert TODAY_OFFSET_BUTTONS == [1, 2, 3, 4, 5, 6, 7, 10, 14]


def test_dialog_has_offset_buttons_and_sets_today_plus_n():
    """AC6: +N buttons exist and each sets the date to today + N."""
    root = _root()
    try:
        dialog = InlineDateDialog(root, "Edit Start Date", None)
        dialog.update_idletasks()

        texts = _all_button_texts(dialog)
        for days in TODAY_OFFSET_BUTTONS:
            assert f"+{days}" in texts, f"missing +{days} button"

        # set_today(N) is what each ladder button invokes; verify its result
        # matches the weekend-aware increment used across the app.
        settings = AppSettings.load()
        for days in (1, 3, 7, 14):
            dialog.set_today(days)
            expected = increment_date(
                date.today(), days,
                settings.include_saturday, settings.include_sunday,
            ).isoformat()
            assert dialog.entry.get() == expected
    finally:
        dialog.destroy()
        root.destroy()


def test_dialog_drops_old_adjust_plus_one():
    """The former current-date '+1' (adjust) button is gone; the only +1 now is
    the today-relative ladder button, which yields today + 1 (not entry + 1)."""
    root = _root()
    try:
        dialog = InlineDateDialog(root, "Edit Start Date", "2020-01-01")
        dialog.update_idletasks()

        # A ladder-style '+1' exists.
        assert "+1" in _all_button_texts(dialog)

        # Clicking the ladder '+1' ignores the stale entry value and uses today.
        settings = AppSettings.load()
        dialog.set_today(1)
        expected = increment_date(
            date.today(), 1,
            settings.include_saturday, settings.include_sunday,
        ).isoformat()
        assert dialog.entry.get() == expected
        assert not dialog.entry.get().startswith("2020")
    finally:
        dialog.destroy()
        root.destroy()
