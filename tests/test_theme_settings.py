"""Tests for persisted appearance/theme settings."""

import json

from src.getmoredone.app_settings import AppSettings
from src.getmoredone.theme import normalize_appearance_mode, normalize_theme_name, theme_path_for


def test_normalize_appearance_mode():
    assert normalize_appearance_mode("system") == "system"
    assert normalize_appearance_mode("LIGHT") == "light"
    assert normalize_appearance_mode("invalid") == "dark"


def test_normalize_theme_name():
    assert normalize_theme_name("apple_grey") == "apple_grey"
    assert normalize_theme_name("GREEN") == "green"
    assert normalize_theme_name("unknown") == "apple_grey"


def test_theme_path_for_known_themes():
    assert theme_path_for("apple_grey").name == "apple_grey.json"
    assert theme_path_for("green").name == "green.json"


def test_app_settings_load_normalizes_theme_fields(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "appearance_mode": "INVALID",
        "theme_name": "UNKNOWN",
        "music_volume": 0.4,
        "business_year_start_mmdd": "13-77",
        "completion_confetti_threshold": -4,
    }))

    monkeypatch.setattr(AppSettings, "get_settings_path", classmethod(lambda cls: settings_path))
    settings = AppSettings.load()

    assert settings.appearance_mode == "dark"
    assert settings.theme_name == "apple_grey"
    assert settings.music_volume == 0.4
    assert settings.business_year_start_mmdd == "01-01"
    assert settings.completion_confetti_threshold == 0
