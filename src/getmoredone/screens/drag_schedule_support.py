"""Pure helpers for Drag Schedule date styling and derived labels."""

from __future__ import annotations

from datetime import date, datetime

from ..app_settings import AppSettings
from ..color_contrast import pick_text_color, pick_text_color_with_meta
from ..date_utils import future_date_targets
from ..theme import schedule_colors


def date_background_for(date_text: str) -> str:
    palette = schedule_colors()
    if not date_text:
        return "transparent"
    try:
        target_date = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return "transparent"

    today = datetime.now().date()
    if target_date < today:
        return palette["date_overdue"]
    if target_date == today:
        return palette["date_today"]
    return palette["date_future"]


def future_options_for(today: date, settings: AppSettings) -> list[tuple[str, str, str]]:
    mid_days = int(settings.mid_term_offset_days)
    long_days = int(settings.long_term_offset_days)
    next_month_offset = int(settings.next_month_offset_days)
    next_quarter_offset = int(settings.next_quarter_offset_days)
    near_date, long_date_obj, next_month_obj, next_quarter_obj = future_date_targets(
        today, mid_days, long_days, next_month_offset, next_quarter_offset
    )
    palette = schedule_colors()
    return sorted(
        [
            ("Near Term", near_date.strftime("%Y-%m-%d"), palette["future_near_term"]),
            ("Long Term", long_date_obj.strftime("%Y-%m-%d"), palette["future_long_term"]),
            ("Next Month", next_month_obj.strftime("%Y-%m-%d"), palette["future_next_month"]),
            ("Next Quarter", next_quarter_obj.strftime("%Y-%m-%d"), palette["future_next_quarter"]),
        ],
        key=lambda option: option[1],
    )


def format_day_stats_text(count: int, total_minutes: int) -> str:
    item_label = "item" if count == 1 else "items"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{count} {item_label} - {hours}h {minutes}m"


def normalized_date_text_color(configured_value: str | None) -> str:
    color = str(configured_value or "#FFFFFF").strip()
    if not color.startswith("#"):
        color = f"#{color}"
    if len(color) != 7:
        return "#FFFFFF"
    return color


def date_text_color_for(bg_color: str, configured_color: str | None) -> str:
    configured = normalized_date_text_color(configured_color)
    try:
        meta = pick_text_color_with_meta(bg_color, light=configured, dark=pick_text_color(bg_color), large_text=True)
    except ValueError:
        return pick_text_color(bg_color)
    return configured if meta.meets_threshold else meta.text_color


def color_for_day_stats(count: int, total_minutes: int) -> str:
    palette = schedule_colors()
    count_ratio = min(max(count / 12.0, 0.0), 1.0)
    time_ratio = min(max(total_minutes / 360.0, 0.0), 1.0)
    intensity = max(count_ratio, time_ratio)

    if intensity < (1.0 / 3.0):
        return palette["low_load"]

    post_green_t = (intensity - (1.0 / 3.0)) / (2.0 / 3.0)
    return interpolate_palette(palette["load_gradient"], post_green_t)


def interpolate_palette(colors: list[str], t: float) -> str:
    t = min(max(t, 0.0), 1.0)
    if len(colors) < 2:
        return colors[0] if colors else schedule_colors()["load_fallback"]
    if t == 1.0:
        return colors[-1]

    segments = len(colors) - 1
    pos = t * segments
    left_idx = int(pos)
    right_idx = min(left_idx + 1, len(colors) - 1)
    local_t = pos - left_idx
    return interpolate_hex_color(colors[left_idx], colors[right_idx], local_t)


def interpolate_hex_color(start_hex: str, end_hex: str, t: float) -> str:
    t = min(max(t, 0.0), 1.0)

    s = start_hex.lstrip("#")
    e = end_hex.lstrip("#")

    sr, sg, sb = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    er, eg, eb = int(e[0:2], 16), int(e[2:4], 16), int(e[4:6], 16)

    r = round(sr + (er - sr) * t)
    g = round(sg + (eg - sg) * t)
    b = round(sb + (eb - sb) * t)

    return f"#{r:02X}{g:02X}{b:02X}"
