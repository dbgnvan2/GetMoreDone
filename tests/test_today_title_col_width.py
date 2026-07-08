"""Tests for the resizable Today "Title" column width setting and clamping.

Covers the persisted `today_title_col_width` AppSettings field and the pure
`clamp_title_col_width` helper used by the drag handlers in the Today screen.
GUI drag behaviour itself is verified interactively in the running app.
"""

import json

from src.getmoredone.app_settings import AppSettings
from src.getmoredone.screens.today import (
    clamp_title_col_width,
    TITLE_COL_MIN_WIDTH,
    TITLE_COL_MAX_WIDTH,
)


def test_default_today_title_col_width():
    """Fresh settings default to 260px for the Title column."""
    assert AppSettings().today_title_col_width == 260


def test_today_title_col_width_round_trips(tmp_path, monkeypatch):
    """save() then load() preserves a changed width (P8: over a prior value)."""
    settings_path = tmp_path / "settings.json"
    # Dirty state: a *different* prior value already on disk.
    settings_path.write_text(json.dumps({"today_title_col_width": 999}))
    monkeypatch.setattr(
        AppSettings, "get_settings_path",
        classmethod(lambda cls: settings_path),
    )

    settings = AppSettings.load()
    assert settings.today_title_col_width == 999  # prior value read back

    settings.today_title_col_width = 420
    settings.save()

    reloaded = AppSettings.load()
    assert reloaded.today_title_col_width == 420


def test_clamp_title_col_width_bounds():
    """Requested widths are clamped into [MIN, MAX]."""
    assert clamp_title_col_width(0) == TITLE_COL_MIN_WIDTH
    assert clamp_title_col_width(TITLE_COL_MIN_WIDTH - 50) == TITLE_COL_MIN_WIDTH
    assert clamp_title_col_width(TITLE_COL_MAX_WIDTH + 500) == TITLE_COL_MAX_WIDTH
    assert clamp_title_col_width(300) == 300
    # Float input is coerced to int.
    assert clamp_title_col_width(255.9) == 255
