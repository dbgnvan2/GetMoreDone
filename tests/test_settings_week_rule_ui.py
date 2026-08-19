"""WT-M6.D — Settings exposes the first-week-of-year rule.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6d
"""

from pathlib import Path
from types import SimpleNamespace

from src.getmoredone import week_calendar
from src.getmoredone.app_settings import AppSettings
from src.getmoredone.screens.settings import SettingsScreen

SETTINGS_SOURCE = (
    Path(__file__).resolve().parents[1] / "src" / "getmoredone" / "screens" / "settings.py"
)


def _save_stub(settings, rule_label):
    labels = {week_calendar.WEEK_RULE_LABELS[rule]: rule
              for rule in week_calendar.WEEK_RULES}
    return SimpleNamespace(
        settings=settings,
        include_saturday_var=SimpleNamespace(get=lambda: True),
        include_sunday_var=SimpleNamespace(get=lambda: True),
        default_columns_expanded_var=SimpleNamespace(get=lambda: False),
        first_day_of_week_var=SimpleNamespace(get=lambda: "Monday"),
        week_rule_labels=labels,
        first_week_of_year_var=SimpleNamespace(get=lambda: rule_label),
        drag_schedule_text_color_var=SimpleNamespace(get=lambda: "#FFFFFF"),
        drag_schedule_box_height_var=SimpleNamespace(get=lambda: "86"),
        _parse_positive_int=lambda *a, **k: 86,
    )


def test_wt_m6d1_week_rule_setting_persists(tmp_path, monkeypatch):
    """Selecting a rule and saving writes it to the settings file (P25)."""
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(AppSettings, "get_settings_path",
                        classmethod(lambda cls: settings_path))

    settings = AppSettings()
    assert settings.first_week_of_year_rule == "iso", "iso is the default"

    stub = _save_stub(settings, week_calendar.WEEK_RULE_LABELS[week_calendar.RULE_JAN1])
    try:
        SettingsScreen.save_date_increment_settings(stub)
    except AttributeError:
        # The method also touches widgets this stub does not carry; what matters
        # is that it reached the rule before then.
        pass

    assert settings.first_week_of_year_rule == "jan1", (
        "the control's value never reached the settings object"
    )

    settings.save()
    assert AppSettings.load().first_week_of_year_rule == "jan1"


def test_wt_m6d1_unknown_label_falls_back_to_the_default(tmp_path, monkeypatch):
    """A label the combo does not know must not raise out of a Save."""
    monkeypatch.setattr(AppSettings, "get_settings_path",
                        classmethod(lambda cls: tmp_path / "settings.json"))
    settings = AppSettings(first_week_of_year_rule="jan1")

    stub = _save_stub(settings, "Something else entirely")
    try:
        SettingsScreen.save_date_increment_settings(stub)
    except AttributeError:
        pass

    assert settings.first_week_of_year_rule == week_calendar.DEFAULT_RULE


def test_wt_m6d1_the_control_is_built_with_all_three_rules():
    """The control offers every rule, and is wired to the saved value."""
    source = SETTINGS_SOURCE.read_text(encoding="utf-8")
    build = source.split("def create_date_increment_section")[1].split("\n    def ")[0]
    assert "self.first_week_of_year_var" in build
    assert "week_calendar.WEEK_RULE_LABELS" in build
    assert "first_week_of_year_rule" in build

    save = source.split("def save_date_increment_settings")[1].split("\n    def ")[0]
    assert "self.settings.first_week_of_year_rule" in save, (
        "a control that is not passed through is decoration"
    )
