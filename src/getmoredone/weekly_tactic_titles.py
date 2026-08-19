"""Weekly Tactic title formatting — the canonical ``Prefix - Wn`` shape.

Purpose: build a Weekly Tactic's title from its APE key field and its week, in
         one place, so the dedupe, the editor and the creators cannot disagree.
Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7a2
Tests:   tests/test_weekly_tactic_dedupe.py::test_wt_m7a2_survivor_title_recanonicalised

These are pure string helpers with no database and no VPS import, so the
re-filing engine (which ``db_manager`` imports) can use them without a cycle.
``VPSManager.shorten_pipe_prefix`` and ``VPSManager.normalize_week_token``
delegate here and keep their existing signatures.
"""

import re
from typing import Optional

from . import week_calendar


def shorten_pipe_prefix(text: str) -> str:
    """Shorten the first two pipe-delimited segments to initials.

    ``Purposeful Work|Living Systems|Blog`` -> ``PW|LS|Blog``
    """
    raw = (text or "").strip()
    if not raw or "|" not in raw:
        return raw

    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 3:
        return raw

    def initials(phrase: str) -> str:
        words = [w for w in phrase.split() if w]
        return "".join(w[0].upper() for w in words) if words else phrase[:1].upper()

    parts[0] = initials(parts[0])
    parts[1] = initials(parts[1])
    return "|".join(parts)


def normalize_week_token(text: str) -> str:
    """Convert ``Week N`` to ``Wn`` in a title."""
    return re.sub(r"\bWeek\s+(\d+)\b", r"W\1", text or "", flags=re.IGNORECASE)


def title_prefix(key_field: Optional[str]) -> str:
    """The shortened, week-normalised prefix for an APE key field."""
    return normalize_week_token(shorten_pipe_prefix(key_field or "")).strip()


def canonical_weekly_tactic_title(
    key_field: Optional[str],
    start_date,
    calendar: Optional[week_calendar.WeekCalendar] = None,
) -> Optional[str]:
    """``<prefix> - W<n>`` for a tactic on the week containing ``start_date``.

    Purpose: the one place a Weekly Tactic's title is derived, so a merged
             survivor cannot keep a title numbered for a different week — the
             live duplicate's older row is titled ``W8`` for an ISO-W9 week
             (WT-F5), and "keep the oldest" alone would preserve that.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7a2
    Tests:   tests/test_weekly_tactic_dedupe.py::test_wt_m7a2_survivor_title_recanonicalised

    Returns None when there is not enough to build a title with; callers keep
    whatever title they already had rather than inventing one.
    """
    prefix = title_prefix(key_field)
    if not prefix:
        return None
    cal = calendar or week_calendar.WeekCalendar()
    token = cal.token(start_date)
    if not token:
        return None
    return f"{prefix} - {token}"
