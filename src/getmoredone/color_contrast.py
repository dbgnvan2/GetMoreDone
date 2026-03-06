"""WCAG-based color contrast helpers for foreground text selection."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging


logger = logging.getLogger(__name__)


def _normalize_hex(hex_color: str) -> str:
    text = (hex_color or "").strip().upper()
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) != 7:
        raise ValueError(f"Invalid hex color: {hex_color}")
    try:
        int(text[1:], 16)
    except ValueError as exc:
        raise ValueError(f"Invalid hex color: {hex_color}") from exc
    return text


def _srgb_channel_to_linear(channel: int) -> float:
    c_srgb = max(0.0, min(1.0, channel / 255.0))
    if c_srgb <= 0.04045:
        return c_srgb / 12.92
    return ((c_srgb + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """Compute WCAG relative luminance for #RRGGBB."""
    color = _normalize_hex(hex_color)
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    r_lin = _srgb_channel_to_linear(r)
    g_lin = _srgb_channel_to_linear(g)
    b_lin = _srgb_channel_to_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(bg_hex: str, fg_hex: str) -> float:
    """Compute WCAG contrast ratio between two colors."""
    l_bg = relative_luminance(bg_hex)
    l_fg = relative_luminance(fg_hex)
    l1, l2 = (l_bg, l_fg) if l_bg >= l_fg else (l_fg, l_bg)
    return (l1 + 0.05) / (l2 + 0.05)


def meets_wcag(bg_hex: str, fg_hex: str, large_text: bool = False) -> bool:
    """Return True when contrast meets WCAG AA threshold."""
    threshold = 3.0 if large_text else 4.5
    return contrast_ratio(bg_hex, fg_hex) >= threshold


@dataclass(frozen=True)
class ContrastChoice:
    text_color: str
    contrast_ratio: float
    meets_threshold: bool


@lru_cache(maxsize=512)
def _pick_text_color_cached(bg_hex: str, light: str, dark: str, large_text: bool) -> ContrastChoice:
    bg = _normalize_hex(bg_hex)
    light_color = _normalize_hex(light)
    dark_color = _normalize_hex(dark)

    light_cr = contrast_ratio(bg, light_color)
    dark_cr = contrast_ratio(bg, dark_color)

    if dark_cr >= light_cr:
        chosen = dark_color
        chosen_cr = dark_cr
    else:
        chosen = light_color
        chosen_cr = light_cr

    threshold = 3.0 if large_text else 4.5
    meets = chosen_cr >= threshold
    if not meets:
        logger.warning(
            "WCAG AA contrast not met: bg=%s chosen=%s contrast=%.2f threshold=%.1f",
            bg,
            chosen,
            chosen_cr,
            threshold,
        )

    return ContrastChoice(text_color=chosen, contrast_ratio=chosen_cr, meets_threshold=meets)


def pick_text_color_with_meta(
    bg_hex: str,
    light: str = "#FFFFFF",
    dark: str = "#000000",
    large_text: bool = False,
) -> ContrastChoice:
    """Pick the best text color and include contrast metadata."""
    return _pick_text_color_cached(bg_hex, light, dark, large_text)


def pick_text_color(bg_hex: str, light: str = "#FFFFFF", dark: str = "#000000") -> str:
    """Pick the best-contrast text color against background."""
    try:
        return pick_text_color_with_meta(bg_hex, light=light, dark=dark, large_text=False).text_color
    except ValueError:
        return "#000000"
