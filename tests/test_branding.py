"""The displayed name comes from one constant, and the data path does not.

Purpose: a rebrand must be a value change, not a hunt across three files —
         and it must NOT drag the user-data directory along with it.
Spec:    daVIPA_rebrand_prompt.md
Tests:   this file

The window title, the sidebar wordmark and the --selftest banner each held
their own copy of the name. These assert that changing the constant changes
all three, so the next rename cannot leave one behind.
"""

from __future__ import annotations

import io

import customtkinter as ctk
import pytest

from src.getmoredone import branding, paths, selftest


def test_window_title_uses_the_display_name():
    """The title is built from the constant, not a literal."""
    title = branding.window_title("[DEV]", "Thursday", "August 21, 2026")

    assert title.startswith(branding.APP_DISPLAY_NAME + " "), (
        f"the title does not start with the display name: {title!r}"
    )
    assert "[DEV]" in title and "Thursday, August 21, 2026" in title


def test_the_window_title_follows_a_rename(monkeypatch):
    """Change the constant and the real window's title changes with it."""
    monkeypatch.setattr(branding, "APP_DISPLAY_NAME", "Renamed Thing")

    title = branding.window_title("[PROD]", "Friday", "August 22, 2026")

    assert title == "Renamed Thing [PROD] - Friday, August 22, 2026"


def test_the_sidebar_wordmark_follows_a_rename(monkeypatch, tmp_path):
    """The sidebar label reads the constant, not its own copy of the string."""
    monkeypatch.setenv("GETMOREDONE_DB", str(tmp_path / "branding.db"))
    monkeypatch.setattr(branding, "APP_DISPLAY_NAME", "Renamed Thing")

    from src.getmoredone.app import GetMoreDoneApp

    app = GetMoreDoneApp()
    try:
        assert app.logo_label.cget("text") == "Renamed Thing", (
            "the sidebar wordmark kept its own copy of the name"
        )
        assert app.title().startswith("Renamed Thing "), (
            f"the window title kept its own copy: {app.title()!r}"
        )
    finally:
        app.destroy()


def test_the_selftest_banner_follows_a_rename(monkeypatch):
    """The --selftest banner reads the constant too."""
    monkeypatch.setattr(branding, "APP_DISPLAY_NAME", "Renamed Thing")
    stream = io.StringIO()

    selftest.run_selftest(out=stream)

    assert "Renamed Thing selftest" in stream.getvalue(), (
        f"the banner kept its own copy: {stream.getvalue().splitlines()[:1]}"
    )


def test_the_data_directory_does_not_follow_a_rename():
    """paths.APP_NAME is an identifier, not brand surface (rebrand Phase 3a).

    Renaming the data directory silently moves where the app looks for its
    database, so every existing install would look like data loss rather than
    a rename. The two constants are separate on purpose; this asserts nothing
    has quietly wired one to the other.
    """
    assert paths.APP_NAME == "GetMoreDone", (
        "the user-data directory name changed. That moves every existing "
        "user's database and settings, and needs a migration, not a rename."
    )
    assert paths.APP_AUTHOR == "GetMoreDone"
