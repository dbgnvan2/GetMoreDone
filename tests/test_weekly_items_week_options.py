from datetime import date
from types import SimpleNamespace

from src.getmoredone.screens.weekly_items import WeeklyItemsScreen


def test_week_start_for_honors_first_day_of_week_monday():
    screen = WeeklyItemsScreen.__new__(WeeklyItemsScreen)
    screen.app = SimpleNamespace(settings=SimpleNamespace(first_day_of_week=0))

    assert screen._week_start_for(date(2026, 3, 18)).isoformat() == "2026-03-16"


def test_week_start_for_honors_first_day_of_week_sunday():
    screen = WeeklyItemsScreen.__new__(WeeklyItemsScreen)
    screen.app = SimpleNamespace(settings=SimpleNamespace(first_day_of_week=6))

    assert screen._week_start_for(date(2026, 3, 18)).isoformat() == "2026-03-15"


def test_build_selectable_week_options_prepends_current_and_three_future_weeks(monkeypatch):
    screen = WeeklyItemsScreen.__new__(WeeklyItemsScreen)
    screen.app = SimpleNamespace(settings=SimpleNamespace(first_day_of_week=0))

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 3, 18)

    monkeypatch.setattr("src.getmoredone.screens.weekly_items.date", FakeDate)

    options = screen._build_selectable_week_options(["2026-03-02", "2026-03-09", "2026-03-23"])

    assert options[:4] == ["2026-03-16", "2026-03-23", "2026-03-30", "2026-04-06"]
    assert "2026-03-02" in options
    assert options.count("2026-03-23") == 1
