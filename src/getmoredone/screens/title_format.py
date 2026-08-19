"""Helpers for splitting structured action-item titles for list views."""

from __future__ import annotations

import re
from dataclasses import dataclass


_STRUCTURED_TITLE_RE = re.compile(
    r"^\s*(?P<context>.+?\bW\s*\d+\b)\s*[-–—]\s*(?P<title>.+?)\s*$",
    flags=re.IGNORECASE,
)
_DATE_ONLY_RE = re.compile(r"^\(?\d{4}-\d{2}-\d{2}\)?$")
_LEADING_DATE_STUB_RE = re.compile(r"^\(?\d{4}-\d{2}-\d{2}\)?\s*[-–—:]\s*")

TITLE_COL_CHARS = 30
CONTACT_COL_CHARS = 10


@dataclass(frozen=True)
class ParsedTitle:
    context: str
    title: str


def split_action_item_title(raw_title: str | None) -> ParsedTitle:
    """Split title into context and body.

    The editor no longer offers a Context field and no list view shows a
    Context column; this remains because list views display the short task
    body, and the Scheduler and item lineage derive segment/subsegment colours
    from the prefix (see item_lineage.resolve_lineage_colors).

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
    body = _normalize_title_body(match.group("title"))
    return ParsedTitle(context=context, title=body)


def _normalize_title_body(value: str | None) -> str:
    """Strip legacy weekly date stubs from title body text."""
    body = (value or "").strip()
    if not body:
        return ""
    body = _LEADING_DATE_STUB_RE.sub("", body).strip()
    if _DATE_ONLY_RE.fullmatch(body):
        return ""
    return body


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


def responsive_column_chars(available_width: int) -> dict[str, int]:
    """Keep Immediate Step, SubSegment, and Category stable while other fields shrink."""
    limits = {
        "title": TITLE_COL_CHARS,
        "subsegment": 15,
        "category": 15,
        "who": 10,
    }
    return limits
