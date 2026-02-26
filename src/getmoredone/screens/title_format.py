"""Helpers for splitting structured action-item titles for list views."""

from __future__ import annotations

import re
from dataclasses import dataclass


_STRUCTURED_TITLE_RE = re.compile(
    r"^\s*(?P<context>.+?\bW\s*\d+\b)\s*[-–—]\s*(?P<title>.+?)\s*$",
    flags=re.IGNORECASE,
)

TITLE_COL_CHARS = 30
CONTEXT_COL_CHARS = 14
CONTACT_COL_CHARS = 10


@dataclass(frozen=True)
class ParsedTitle:
    context: str
    title: str


def split_action_item_title(raw_title: str | None) -> ParsedTitle:
    """Split title into context and body.

    Expected structured format examples:
    - ``PW|LS|Blog - W8 - write blog 3``
    - ``C\\W\\APW Book - W8 - c9 Session 3``
    """
    title = (raw_title or "").strip()
    if not title:
        return ParsedTitle(context="", title="")

    match = _STRUCTURED_TITLE_RE.match(title)
    if not match:
        return ParsedTitle(context="", title=title)

    context = (match.group("context") or "").strip()
    body = (match.group("title") or "").strip()
    return ParsedTitle(context=context, title=body or title)


def build_action_item_title(context: str | None, title: str | None) -> str:
    """Compose a stored title from context + title fields."""
    c = (context or "").strip()
    t = (title or "").strip()
    if c and t:
        return f"{c} - {t}"
    return t or c


def format_column_text(value: str | None, max_chars: int) -> str:
    """Clamp text for fixed-width list columns using character count."""
    text = (value or "").strip()
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return "." * max_chars
    return text[: max_chars - 3].rstrip() + "..."
