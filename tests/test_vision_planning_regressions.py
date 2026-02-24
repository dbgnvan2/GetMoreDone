"""
Regression tests for recent Vision Planning and Drag Schedule behavior.
"""

from types import SimpleNamespace

from src.getmoredone.screens.drag_schedule import DragScheduleScreen
from src.getmoredone.vps_manager import VPSManager


def test_weekly_prefix_shortening():
    value = VPSManager.shorten_pipe_prefix("Purposeful Work|Living Systems|Blog")
    assert value == "PW|LS|Blog"


def test_weekly_prefix_shortening_no_pipe_passthrough():
    value = VPSManager.shorten_pipe_prefix("Already Short")
    assert value == "Already Short"


def test_week_token_normalization():
    value = VPSManager.normalize_week_token("Purposeful Work|Living Systems|Blog - Week 8 - write")
    assert value == "Purposeful Work|Living Systems|Blog - W8 - write"


def test_drag_schedule_stats_text_format():
    screen = DragScheduleScreen.__new__(DragScheduleScreen)
    assert screen.format_day_stats_text(9, 360) == "9 items - 6h 0m"
    assert screen.format_day_stats_text(1, 65) == "1 item - 1h 5m"


def test_drag_schedule_text_color_setting_defaults_and_validation():
    screen = DragScheduleScreen.__new__(DragScheduleScreen)

    screen.settings = SimpleNamespace(drag_schedule_date_text_color="#FFFFFF")
    assert screen._get_date_text_color() == "#FFFFFF"

    screen.settings = SimpleNamespace(drag_schedule_date_text_color="00FFAA")
    assert screen._get_date_text_color() == "#00FFAA"

    screen.settings = SimpleNamespace(drag_schedule_date_text_color="#XYZ")
    assert screen._get_date_text_color() == "#FFFFFF"
