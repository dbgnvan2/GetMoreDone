"""Tests for the Today Title-column width settings.

Covers the legacy `today_title_col_width` scalar and the newer
`today_col_widths` dict (managed by screens/column_resize.py). Width-clamp and
resizer logic live in tests/test_column_resize.py; GUI drag behaviour is
verified interactively in the running app.
"""

import json

from src.getmoredone.app_settings import AppSettings


def test_default_today_title_col_width():
    """Fresh settings default to 260px (legacy scalar) and an empty width dict."""
    settings = AppSettings()
    assert settings.today_title_col_width == 260
    assert settings.today_col_widths == {}


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


def test_today_col_widths_dict_round_trips(tmp_path, monkeypatch):
    """The per-column width dict persists through save()/load()."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"today_col_widths": {"title": 150}}))
    monkeypatch.setattr(
        AppSettings, "get_settings_path",
        classmethod(lambda cls: settings_path),
    )

    settings = AppSettings.load()
    assert settings.today_col_widths == {"title": 150}  # dirty prior value

    settings.today_col_widths = {"title": 333}
    settings.save()

    assert AppSettings.load().today_col_widths == {"title": 333}
