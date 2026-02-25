"""Theme wiring and small semantic style helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import customtkinter as ctk

from .paths import resolve_theme_path

APPEARANCE_MODES = ("system", "dark", "light")
THEME_NAMES = ("green", "orange", "pink", "grey", "apple_grey")


def normalize_appearance_mode(value: str) -> str:
    mode = (value or "").strip().lower()
    return mode if mode in APPEARANCE_MODES else "dark"


def normalize_theme_name(value: str) -> str:
    name = (value or "").strip().lower()
    return name if name in THEME_NAMES else "apple_grey"


def theme_path_for(theme_name: str) -> Path:
    return resolve_theme_path(normalize_theme_name(theme_name))


def apply_theme_settings(settings) -> Tuple[str, str]:
    """Apply appearance mode + color theme from settings."""
    mode = normalize_appearance_mode(getattr(settings, "appearance_mode", "dark"))
    theme_name = normalize_theme_name(getattr(settings, "theme_name", "apple_grey"))

    ctk.set_appearance_mode(mode)

    theme_path = theme_path_for(theme_name)
    ctk.set_default_color_theme(str(theme_path))

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
    return {
        "primary": primary,
        "primary_hover": primary_hover,
        "ghost_hover": _theme_value("DropdownMenu", "hover_color", "gray28"),
        "border": _theme_value("CTkFrame", "border_color", "gray28"),
        "muted_text": muted_text,
        "body_text": label_text,
        "on_primary": _theme_value("CTkButton", "text_color", "#DCE4EE"),
        "surface_subtle": _theme_value("CTkFrame", "top_fg_color", "gray21"),
        "chip_bg": _theme_value("CTkSegmentedButton", "unselected_color", "gray29"),
        "date_start_text": label_text,
        "date_due_text": label_text,
        "time_text": label_text,
        "success_tint": "#E8F5EE" if mode == "light" else "#1F2B24",
        "critical_tint": "#FDECEC" if mode == "light" else "#3A2328",
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
            "fg_color": "#B91C1C",
            "hover_color": "#991B1B",
            "text_color": "#FEE2E2",
            "border_width": 0,
        }
    return {
        "fg_color": palette["primary"],
        "hover_color": palette["primary_hover"],
        "text_color": palette["on_primary"],
        "border_width": 0,
    }
