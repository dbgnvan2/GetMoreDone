#!/usr/bin/env python3
"""Generate CustomTkinter themes from relative HSL differences.

Input base theme: themes/base_dark_blue.json
Output themes: green, orange, pink, grey, apple_grey
"""

from __future__ import annotations

import colorsys
import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
THEMES_DIR = REPO_ROOT / "themes"
BASE_THEME_PATH = THEMES_DIR / "base_dark_blue.json"

# Accent anchor: CTkButton.fg_color [light, dark]
ANCHOR_PATH: Tuple[str, str] = ("CTkButton", "fg_color")

# Only transform these accent keys.
ACCENT_KEYS: Tuple[Tuple[str, str], ...] = (
    ("CTkButton", "fg_color"),
    ("CTkButton", "hover_color"),
    ("CTkCheckBox", "fg_color"),
    ("CTkCheckBox", "hover_color"),
    ("CTkRadioButton", "fg_color"),
    ("CTkRadioButton", "hover_color"),
    ("CTkSwitch", "progress_color"),
    ("CTkProgressBar", "progress_color"),
    ("CTkSlider", "button_color"),
    ("CTkSlider", "button_hover_color"),
    ("CTkOptionMenu", "fg_color"),
    ("CTkOptionMenu", "button_color"),
    ("CTkOptionMenu", "button_hover_color"),
    ("CTkSegmentedButton", "selected_color"),
    ("CTkSegmentedButton", "selected_hover_color"),
)

ACCENT_ONLY_TARGET_ANCHORS: Dict[str, List[str]] = {
    "green": ["#2CC985", "#2FA572"],
    "orange": ["#C2410C", "#9A3412"],
    "pink": ["#BE185D", "#9D174D"],
    "grey": ["#475569", "#334155"],
}

APPLE_GREY_ANCHOR = ["#1D1D1F", "#D2D2D7"]
APPLE_GREY_HOVER = ["#000000", "#F5F5F7"]
APPLE_GREY_BUTTON_TEXT = ["#FFFFFF", "#1D1D1F"]

APPLE_NEUTRAL_OVERRIDES: Dict[Tuple[str, str], List[str]] = {
    ("CTk", "fg_color"): ["#F5F5F7", "#000000"],
    ("CTkToplevel", "fg_color"): ["#F5F5F7", "#000000"],
    ("CTkFrame", "fg_color"): ["#FFFFFF", "#1D1D1F"],
    ("CTkFrame", "top_fg_color"): ["#FFFFFF", "#1D1D1F"],
    ("CTkFrame", "border_color"): ["#D2D2D7", "#424245"],
    ("CTkLabel", "text_color"): ["#1D1D1F", "#F5F5F7"],
    ("CTkEntry", "fg_color"): ["#FFFFFF", "#1D1D1F"],
    ("CTkEntry", "border_color"): ["#D2D2D7", "#424245"],
    ("CTkEntry", "text_color"): ["#1D1D1F", "#F5F5F7"],
    ("CTkEntry", "placeholder_text_color"): ["#6E6E73", "#A1A1A6"],
}


def hex_to_rgb01(color: str) -> Tuple[float, float, float]:
    color = color.strip()
    if not color.startswith("#") or len(color) != 7:
        raise ValueError(f"Expected #RRGGBB, got: {color}")
    r = int(color[1:3], 16) / 255.0
    g = int(color[3:5], 16) / 255.0
    b = int(color[5:7], 16) / 255.0
    return r, g, b


def rgb01_to_hex(rgb: Tuple[float, float, float]) -> str:
    r, g, b = rgb
    return f"#{int(round(max(0.0, min(1.0, r)) * 255)):02X}{int(round(max(0.0, min(1.0, g)) * 255)):02X}{int(round(max(0.0, min(1.0, b)) * 255)):02X}"


def hex_to_hsl(color: str) -> Tuple[float, float, float]:
    r, g, b = hex_to_rgb01(color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h, s, l


def hsl_to_hex(h: float, s: float, l: float) -> str:
    h = h % 1.0
    s = max(0.0, min(1.0, s))
    l = max(0.0, min(1.0, l))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return rgb01_to_hex((r, g, b))


def shortest_hue_delta(from_h: float, to_h: float) -> float:
    """Signed shortest angular delta in normalized hue space."""
    d = (to_h - from_h) % 1.0
    if d > 0.5:
        d -= 1.0
    return d


def get_pair(theme: dict, widget: str, key: str) -> List[str]:
    value = theme.get(widget, {}).get(key)
    if not (isinstance(value, list) and len(value) == 2 and all(isinstance(c, str) for c in value)):
        raise ValueError(f"Expected 2-color list for {widget}.{key}, got {value!r}")
    return value


def transform_color(
    base_anchor_hex: str,
    base_key_hex: str,
    target_anchor_hex: str,
) -> str:
    base_anchor_h, base_anchor_s, base_anchor_l = hex_to_hsl(base_anchor_hex)
    base_key_h, base_key_s, base_key_l = hex_to_hsl(base_key_hex)
    target_anchor_h, target_anchor_s, target_anchor_l = hex_to_hsl(target_anchor_hex)

    dh = shortest_hue_delta(base_anchor_h, base_key_h)
    ds = base_key_s - base_anchor_s
    dl = base_key_l - base_anchor_l

    out_h = (target_anchor_h + dh) % 1.0
    out_s = target_anchor_s + ds
    out_l = target_anchor_l + dl
    return hsl_to_hex(out_h, out_s, out_l)


def generate_theme(base_theme: dict, target_anchor_pair: Sequence[str]) -> dict:
    theme = deepcopy(base_theme)

    base_anchor_pair = get_pair(base_theme, *ANCHOR_PATH)

    for widget, key in ACCENT_KEYS:
        base_pair = get_pair(base_theme, widget, key)
        transformed = [
            transform_color(base_anchor_pair[idx], base_pair[idx], target_anchor_pair[idx])
            for idx in (0, 1)
        ]
        theme[widget][key] = transformed

    # Ensure anchor is exactly what caller requested.
    theme[ANCHOR_PATH[0]][ANCHOR_PATH[1]] = list(target_anchor_pair)
    return theme


def apply_neutral_overrides(theme: dict, overrides: Dict[Tuple[str, str], List[str]]) -> None:
    for (widget, key), pair in overrides.items():
        if widget in theme and key in theme[widget]:
            theme[widget][key] = list(pair)

    # Disabled text is treated as neutral for all widgets where present.
    for widget_cfg in theme.values():
        if isinstance(widget_cfg, dict) and "text_color_disabled" in widget_cfg:
            widget_cfg["text_color_disabled"] = ["#86868B", "#6E6E73"]


def generate_apple_grey_theme(base_theme: dict) -> dict:
    theme = generate_theme(base_theme, APPLE_GREY_ANCHOR)
    apply_neutral_overrides(theme, APPLE_NEUTRAL_OVERRIDES)

    # Explicit button requirements for Apple-grey.
    if "CTkButton" in theme:
        theme["CTkButton"]["fg_color"] = list(APPLE_GREY_ANCHOR)
        theme["CTkButton"]["hover_color"] = list(APPLE_GREY_HOVER)
        theme["CTkButton"]["text_color"] = list(APPLE_GREY_BUTTON_TEXT)
    return theme


def main() -> int:
    if not BASE_THEME_PATH.exists():
        raise FileNotFoundError(f"Missing base theme: {BASE_THEME_PATH}")

    with BASE_THEME_PATH.open("r", encoding="utf-8") as f:
        base_theme = json.load(f)

    THEMES_DIR.mkdir(parents=True, exist_ok=True)

    for name, anchor_pair in ACCENT_ONLY_TARGET_ANCHORS.items():
        generated = generate_theme(base_theme, anchor_pair)
        out_path = THEMES_DIR / f"{name}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(generated, f, indent=2)
            f.write("\n")
        print(f"wrote {out_path}")

    apple_theme = generate_apple_grey_theme(base_theme)
    apple_path = THEMES_DIR / "apple_grey.json"
    with apple_path.open("w", encoding="utf-8") as f:
        json.dump(apple_theme, f, indent=2)
        f.write("\n")
    print(f"wrote {apple_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
