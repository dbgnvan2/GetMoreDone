"""Theme wiring and small semantic style helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import customtkinter as ctk

from .paths import resolve_theme_path

APPEARANCE_MODES = ("system", "dark", "light")
# "davipa" is the brand theme, built from brand.py and the colour system
# document. The rest predate it and are untouched.
THEME_NAMES = ("davipa", "green", "orange", "pink", "grey", "blue", "purple",
               "apple_grey", "black_white")
DEFAULT_THEME_NAME = "apple_grey"
LIST_ROW_FONT_SIZE = 14


def normalize_appearance_mode(value: str) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in APPEARANCE_MODES else "dark"


def normalize_theme_name(value: str) -> str:
    """Coerce any persisted value to a known theme name.

    ``str()`` first: settings.json is user-writable, so the stored value may be a
    number, null, or anything else a hand-edit left behind.
    """
    name = str(value or "").strip().lower()
    return name if name in THEME_NAMES else DEFAULT_THEME_NAME


def theme_path_for(theme_name: str) -> Path:
    return resolve_theme_path(normalize_theme_name(theme_name))


def apply_theme_settings(settings) -> Tuple[str, str]:
    """Apply appearance mode + color theme from settings.

    Purpose: set the CustomTkinter theme at startup without ever raising.
    Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m1a2
    Tests:   tests/test_packaging_resources.py::test_rm1a2_apply_theme_settings_never_raises_on_bad_name
    """
    global LIST_ROW_FONT_SIZE
    mode = normalize_appearance_mode(getattr(settings, "appearance_mode", "dark"))
    theme_name = normalize_theme_name(getattr(settings, "theme_name", "apple_grey"))
    font_size = getattr(settings, "list_row_font_size", LIST_ROW_FONT_SIZE)
    try:
        LIST_ROW_FONT_SIZE = max(10, min(24, int(font_size)))
    except (TypeError, ValueError):
        LIST_ROW_FONT_SIZE = 14

    ctk.set_appearance_mode(mode)

    # A missing or unreadable theme file must not stop the app from starting —
    # this runs before the first window exists, so an exception here is a launch
    # crash with no UI to report it. Degrade to CustomTkinter's built-in default.
    theme_path = theme_path_for(theme_name)
    if theme_path.exists():
        try:
            ctk.set_default_color_theme(str(theme_path))
        except (OSError, ValueError, KeyError) as exc:
            print(f"[WARN] Could not load theme {theme_path}: {exc}. Using the built-in default.")
    else:
        print(f"[WARN] Theme file not found: {theme_path}. Using the built-in default.")

    return mode, theme_name


def _mode_index() -> int:
    return 0 if (ctk.get_appearance_mode() or "Dark").lower() == "light" else 1


def _theme_value(widget: str, key: str, fallback: str) -> str:
    theme = getattr(ctk.ThemeManager, "theme", {}) or {}
    value = theme.get(widget, {}).get(key, fallback)
    if isinstance(value, (list, tuple)):
        idx = _mode_index()
        if len(value) > idx:
            return value[idx]
        return value[0] if value else fallback
    return value


def semantic_colors() -> Dict[str, str]:
    mode = (ctk.get_appearance_mode() or "Dark").lower()
    primary = _theme_value("CTkButton", "fg_color", "#1f538d")
    primary_hover = _theme_value("CTkButton", "hover_color", "#14375e")
    muted_text = _theme_value("CTkEntry", "placeholder_text_color", "gray62")
    label_text = _theme_value("CTkLabel", "text_color", "gray84")
    input_surface = _theme_value("CTkComboBox", "fg_color", _theme_value("CTkEntry", "fg_color", "gray20"))
    input_button = _theme_value("CTkComboBox", "button_color", primary)
    input_button_hover = _theme_value("CTkComboBox", "button_hover_color", primary_hover)
    input_text = _theme_value("CTkComboBox", "text_color", label_text)
    dropdown_surface = _theme_value("DropdownMenu", "fg_color", input_surface)
    dropdown_text = _theme_value("DropdownMenu", "text_color", label_text)
    return {
        "primary": primary,
        "primary_hover": primary_hover,
        "surface": _theme_value("CTkFrame", "fg_color", "gray17"),
        "ghost_hover": _theme_value("DropdownMenu", "hover_color", "gray28"),
        "border": _theme_value("CTkFrame", "border_color", "gray28"),
        "muted_text": muted_text,
        "body_text": label_text,
        "row_text": label_text,
        "on_primary": _theme_value("CTkButton", "text_color", "#DCE4EE"),
        "input_surface": input_surface,
        "input_button": input_button,
        "input_button_hover": input_button_hover,
        "input_text": input_text,
        "dropdown_surface": dropdown_surface,
        "dropdown_text": dropdown_text,
        "surface_subtle": _theme_value("CTkFrame", "top_fg_color", "gray21"),
        # Align list accents with Drag Schedule visual language.
        "chip_bg": "gray30",
        "chip_text": "white",
        "date_start_text": "#FFB347",
        "date_due_text": "#FF5A8A",
        "time_text": "#FFD8A8",
        "success_tint": "#E8F5EE" if mode == "light" else "#1F2B24",
        "critical_tint": "#FDECEC" if mode == "light" else "#3A2328",
        "danger": "#B91C1C",
        "danger_hover": "#991B1B",
        "on_danger": "#FEE2E2",
        "warning": "#B45309" if mode == "light" else "#FBBF24",
        "selected_tint": "#E6EEF8" if mode == "light" else "#223247",
        "success_strong": "#166534" if mode == "light" else "#14532D",
        "on_strong": "#ECFDF5" if mode == "light" else "#DCFCE7",
    }


def apply_segment_accent(frame: ctk.CTkFrame, segment_color: str | None):
    """Apply a narrow accent stripe; segment colors should not fill full rows."""
    if not segment_color:
        return
    accent = ctk.CTkFrame(frame, width=5, fg_color=segment_color, corner_radius=0)
    accent.place(x=0, y=0, relheight=1)


def button_style(kind: str = "primary") -> Dict[str, object]:
    """Shared semantic button styles used across screens."""
    palette = semantic_colors()
    if kind == "ghost":
        return {
            "fg_color": "transparent",
            "hover_color": palette["ghost_hover"],
            "border_width": 0,
            "text_color": palette["body_text"],
        }
    if kind == "secondary":
        return {
            "fg_color": "transparent",
            "hover_color": palette["ghost_hover"],
            "border_width": 1,
            "border_color": palette["border"],
            "text_color": palette["body_text"],
        }
    if kind == "danger":
        return {
            "fg_color": palette["danger"],
            "hover_color": palette["danger_hover"],
            "text_color": palette["on_danger"],
            "border_width": 0,
        }
    return {
        "fg_color": palette["primary"],
        "hover_color": palette["primary_hover"],
        "text_color": palette["on_primary"],
        "border_width": 0,
    }


def list_row_font() -> ctk.CTkFont:
    """Standard larger font for item-list rows."""
    return ctk.CTkFont(size=LIST_ROW_FONT_SIZE)


def combo_box_style() -> Dict[str, object]:
    """Theme-aware combobox styling for filters and settings controls."""
    palette = semantic_colors()
    return {
        "fg_color": palette["input_surface"],
        "text_color": palette["input_text"],
        "button_color": palette["input_button"],
        "button_hover_color": palette["input_button_hover"],
        "dropdown_fg_color": palette["dropdown_surface"],
        "dropdown_text_color": palette["dropdown_text"],
    }


def status_text_color(kind: str) -> str:
    """Return semantic text colors for status messages.

    Accepts semantic names and legacy color words to ease incremental cleanup.
    """
    palette = semantic_colors()
    normalized = (kind or "").strip().lower()
    mapping = {
        "success": palette["success_strong"],
        "green": palette["success_strong"],
        "error": palette["danger"],
        "danger": palette["danger"],
        "red": palette["danger"],
        "warning": palette["warning"],
        "orange": palette["warning"],
        "yellow": palette["warning"],
        "info": palette["primary"],
        "blue": palette["primary"],
        "muted": palette["muted_text"],
        "gray": palette["muted_text"],
        "body": palette["body_text"],
        "default": palette["body_text"],
        "white": palette["body_text"],
    }
    return mapping.get(normalized, kind or palette["body_text"])


def schedule_colors() -> Dict[str, object]:
    """Shared Drag Schedule palette values."""
    return {
        "date_overdue": "#FCA5A5",
        "date_today": "#86EFAC",
        "date_future": "#FDE68A",
        "future_near_term": "#F4D35E",
        "future_long_term": "#E9C6CF",
        "future_next_month": "#EFE6A7",
        "future_next_quarter": "#E9CAA0",
        "low_load": "#6BCB77",
        "load_gradient": ["#FFD8A8", "#FFB347", "#F5A6BE", "#EF7292", "#D94B66"],
        "load_fallback": "#DFF8D8",
    }


def vps_level_colors() -> Dict[str, str]:
    """Shared planning-hierarchy legend colors."""
    return {
        "TL Vision": "#7C3AED",
        "Annual Vision": "#2563EB",
        "Annual Plan": "#0D9488",
        "Annual Initiative": "#F59E0B",
        "Quarter": "#EA580C",
        "Month": "#059669",
        "Week": "#0284C7",
    }


def celebration_colors() -> Tuple[str, ...]:
    """Shared celebratory accent colors."""
    return ("#00C800", "#FFD54F", "#3B82F6", "#EF4444", "#A855F7", "#F97316")
