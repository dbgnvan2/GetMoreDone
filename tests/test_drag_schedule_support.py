from datetime import date, timedelta

from src.getmoredone.app_settings import AppSettings
from src.getmoredone.screens.drag_schedule_support import (
    color_for_day_stats,
    date_background_for,
    format_day_stats_text,
    future_options_for,
    interpolate_hex_color,
    normalized_date_text_color,
)


def test_normalized_date_text_color_normalizes_hash_and_fallback():
    assert normalized_date_text_color("ffffff") == "#ffffff"
    assert normalized_date_text_color("#ABCDEF") == "#ABCDEF"
    assert normalized_date_text_color("bad") == "#FFFFFF"


def test_format_day_stats_text_formats_hours_and_pluralization():
    assert format_day_stats_text(1, 75) == "1 item - 1h 15m"
    assert format_day_stats_text(3, 30) == "3 items - 0h 30m"


def test_interpolate_hex_color_midpoint():
    assert interpolate_hex_color("#000000", "#FFFFFF", 0.5) == "#808080"


def test_color_for_day_stats_progresses_beyond_green():
    low = color_for_day_stats(1, 30)
    high = color_for_day_stats(12, 360)

    assert low.startswith("#")
    assert high.startswith("#")
    assert low != high


def test_future_options_for_returns_sorted_dates():
    settings = AppSettings(
        mid_term_offset_days=30,
        long_term_offset_days=90,
        next_month_offset_days=0,
        next_quarter_offset_days=0,
    )
    options = future_options_for(date(2026, 3, 19), settings)

    assert len(options) == 4
    assert [label for label, *_rest in options] == [label for label, *_rest in sorted(options, key=lambda item: item[1])]


def test_date_background_for_tracks_past_present_future():
    today = date.today()
    assert date_background_for((today - timedelta(days=1)).isoformat()).startswith("#")
    assert date_background_for(today.isoformat()).startswith("#")
    assert date_background_for((today + timedelta(days=1)).isoformat()).startswith("#")
