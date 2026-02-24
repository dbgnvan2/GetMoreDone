"""
Tests for future date calculations and settings persistence.
"""

from datetime import date

from src.getmoredone.app_settings import AppSettings
from src.getmoredone.date_utils import (
    first_of_next_month,
    first_of_next_quarter,
    future_date_targets,
)


def test_first_of_next_month_normal_case():
    assert first_of_next_month(date(2026, 2, 6)) == date(2026, 3, 1)


def test_first_of_next_month_year_rollover():
    assert first_of_next_month(date(2026, 12, 15)) == date(2027, 1, 1)


def test_first_of_next_quarter_mid_year():
    assert first_of_next_quarter(date(2026, 2, 6)) == date(2026, 4, 1)


def test_first_of_next_quarter_year_rollover():
    assert first_of_next_quarter(date(2026, 11, 20)) == date(2027, 1, 1)


def test_future_date_targets_offsets():
    today = date(2026, 2, 6)
    near, long_, next_month, next_quarter = future_date_targets(
        today, 90, 180, 0, 0
    )
    assert near == date(2026, 5, 7)
    assert long_ == date(2026, 8, 5)
    assert next_month == date(2026, 3, 1)
    assert next_quarter == date(2026, 4, 1)


def test_future_date_targets_month_quarter_offsets():
    today = date(2026, 2, 6)
    near, long_, next_month, next_quarter = future_date_targets(
        today, 30, 60, 3, 10
    )
    assert near == date(2026, 3, 8)
    assert long_ == date(2026, 4, 7)
    assert next_month == date(2026, 3, 4)
    assert next_quarter == date(2026, 4, 11)


def test_future_date_settings_persist():
    settings = AppSettings.load()
    original_near = settings.mid_term_offset_days
    original_long = settings.long_term_offset_days
    original_month = settings.next_month_offset_days
    original_quarter = settings.next_quarter_offset_days

    try:
        settings.mid_term_offset_days = 91
        settings.long_term_offset_days = 181
        settings.next_month_offset_days = 2
        settings.next_quarter_offset_days = 7
        settings.save()

        reloaded = AppSettings.load()
        assert reloaded.mid_term_offset_days == 91
        assert reloaded.long_term_offset_days == 181
        assert reloaded.next_month_offset_days == 2
        assert reloaded.next_quarter_offset_days == 7
    finally:
        settings.mid_term_offset_days = original_near
        settings.long_term_offset_days = original_long
        settings.next_month_offset_days = original_month
        settings.next_quarter_offset_days = original_quarter
        settings.save()


def test_drag_schedule_text_color_setting_persist():
    settings = AppSettings.load()
    original_color = getattr(settings, "drag_schedule_date_text_color", "#FFFFFF")

    try:
        settings.drag_schedule_date_text_color = "#FFFFFF"
        settings.save()

        reloaded = AppSettings.load()
        assert reloaded.drag_schedule_date_text_color == "#FFFFFF"
    finally:
        settings.drag_schedule_date_text_color = original_color
        settings.save()
