"""
Regression tests for recent Vision Planning and Scheduler behavior.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

from src.getmoredone.models import ActionItem
from src.getmoredone.screens.item_lineage import lineage_for_item
from src.getmoredone.screens.drag_schedule import DragScheduleScreen
from src.getmoredone.screens.title_format import responsive_column_chars
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


def test_scheduler_date_background_colors_follow_relative_date():
    screen = DragScheduleScreen.__new__(DragScheduleScreen)
    today = datetime.now().date()

    assert screen._date_background_for((today - timedelta(days=1)).strftime("%Y-%m-%d")) == "#FCA5A5"
    assert screen._date_background_for(today.strftime("%Y-%m-%d")) == "#86EFAC"
    assert screen._date_background_for((today + timedelta(days=1)).strftime("%Y-%m-%d")) == "#FDE68A"
    assert screen._date_background_for("not-a-date") == "transparent"


def test_scheduler_date_box_values_keep_full_weekday_name():
    screen = DragScheduleScreen.__new__(DragScheduleScreen)
    assert screen._date_box_values("Monday", "03/09", 17, 120) == ("Monday", "03/09", "17 items", "2h 0m")


def test_scheduler_clicking_date_toggles_filter():
    screen = DragScheduleScreen.__new__(DragScheduleScreen)
    screen.selected_date_filter = None
    calls = []
    screen.refresh = lambda: calls.append("refresh")

    screen.on_date_target_click("2026-03-09")
    assert screen.selected_date_filter == "2026-03-09"

    screen.on_date_target_click("2026-03-09")
    assert screen.selected_date_filter is None
    assert calls == ["refresh", "refresh"]


def test_scheduler_refresh_button_clears_date_filter():
    screen = DragScheduleScreen.__new__(DragScheduleScreen)
    screen.selected_date_filter = "2026-03-09"
    calls = []
    screen.refresh = lambda: calls.append("refresh")

    screen.refresh_all_dates()

    assert screen.selected_date_filter is None
    assert calls == ["refresh"]


def test_scheduler_future_options_include_calendar_footer_targets():
    screen = DragScheduleScreen.__new__(DragScheduleScreen)
    screen.settings = SimpleNamespace(
        mid_term_offset_days=90,
        long_term_offset_days=180,
        next_month_offset_days=0,
        next_quarter_offset_days=0,
    )

    options = screen._future_options_for(datetime(2026, 3, 9).date())
    names = {name for name, _date, _color in options}
    assert names == {"Next Month", "Next Quarter", "Near Term", "Long Term"}


def test_scheduler_item_filter_matches_segment_and_subsegment():
    screen = DragScheduleScreen.__new__(DragScheduleScreen)
    screen.segment_filter_var = SimpleNamespace(get=lambda: "Creative")
    screen.subsegment_filter_var = SimpleNamespace(get=lambda: "Books")
    screen._lineage_for_item = lambda item: ("Creative", "Books", "Learning")

    assert screen._item_matches_filters(object()) is True

    screen.subsegment_filter_var = SimpleNamespace(get=lambda: "Writing")
    assert screen._item_matches_filters(object()) is False


def test_list_view_lineage_helper_reads_structured_title():
    item = ActionItem(who="Tester", title="Purposeful Work|Living Systems|Blog - W9 - Write post")
    lineage = lineage_for_item(item, SimpleNamespace(get_action_item=lambda _id: None, db=None), {}, {}, {})
    assert lineage == ("Purposeful Work", "Living Systems", "Blog")


def test_list_view_lineage_helper_ignores_wrong_cache_shape():
    item = ActionItem(id="ai-1", who="Tester", title="Purposeful Work|Living Systems|Blog - W9 - Write post")
    lineage = lineage_for_item(
        item,
        SimpleNamespace(get_action_item=lambda _id: None, db=None),
        {"ai-1": "#4A90E2"},
        {},
        {},
    )
    assert lineage == ("Purposeful Work", "Living Systems", "Blog")


def test_list_view_column_budget_preserves_immediate_subsegment_and_category():
    wide = responsive_column_chars(1800)
    mid = responsive_column_chars(1450)
    narrow = responsive_column_chars(1100)

    assert wide["title"] == 30
    assert mid["subsegment"] == wide["subsegment"] == 15
    assert narrow["category"] == wide["category"] == 15
    assert wide["who"] == 10
    assert narrow["who"] == 10
    assert narrow["context"] == wide["context"] == 10
