"""Week identity and week numbering — the single owner of both.

Purpose: answer "which week contains this date" and "what is that week called"
         in exactly one place.
Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m2
Tests:   tests/test_week_numbering.py

Before this module the two questions were answered separately and
inconsistently (WT-F2):

* three call sites took ``date.isocalendar().week`` and **discarded the ISO
  year**, so a boundary week's number was ambiguous — 2026-12-28 and 2027-01-01
  are both ISO 2026-W53, and a bare ``53`` cannot say which year;
* week *identity* was settings-driven in one place and hardcoded to Monday in
  two others.

So every public function here returns ``(year, week)``, never a bare week
number, and every week boundary is computed from the configured first day of
the week.

Identity and numbering are related but not the same thing, and this module does
not force them to be. ``week_start``/``week_end`` follow the user's
``first_day_of_week``. The *number* follows ``first_week_of_year_rule``, and
under the ``iso`` rule that number is Monday-anchored by definition — that is
what ISO 8601 means, and it is the behaviour every existing database was
numbered with.
"""

from datetime import date, timedelta
from typing import Optional, Tuple

# WT-M2.A — the three first-week-of-year rules.
RULE_ISO = "iso"
RULE_JAN1 = "jan1"
RULE_FIRST_FULL = "first_full"

WEEK_RULES = (RULE_ISO, RULE_JAN1, RULE_FIRST_FULL)

WEEK_RULE_LABELS = {
    RULE_ISO: "ISO 8601 (week 1 contains the first Thursday)",
    RULE_JAN1: "Week 1 contains January 1",
    RULE_FIRST_FULL: "Week 1 is the first full week of the year",
}

DEFAULT_RULE = RULE_ISO
DEFAULT_FIRST_DAY = 0  # 0 = Monday .. 6 = Sunday


def normalize_rule(value: Optional[str]) -> str:
    """WT-M2.A.2 — coerce any stored value to a known rule.

    Purpose: an unknown or empty setting falls back to ``iso`` rather than
             raising in the middle of an ordinary save.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m2a2
    Tests:   tests/test_week_numbering.py::test_wt_m2a2_unknown_rule_falls_back_to_iso
    """
    if not isinstance(value, str):
        return DEFAULT_RULE
    candidate = value.strip().lower()
    return candidate if candidate in WEEK_RULES else DEFAULT_RULE


def normalize_first_day(value: Optional[int]) -> int:
    """Coerce a stored first-day-of-week to 0..6, defaulting to Monday."""
    try:
        day = int(value)
    except (TypeError, ValueError):
        return DEFAULT_FIRST_DAY
    return day if 0 <= day <= 6 else DEFAULT_FIRST_DAY


def coerce_date(value) -> Optional[date]:
    """Accept a ``date``, an ISO date string, or an ISO datetime string.

    ``completed_at`` is a full ISO datetime (``db_manager.py:191``), so the
    date part is taken rather than letting ``date.fromisoformat`` fail on it.
    Returns None for anything unparseable — callers decide what that means
    rather than having arithmetic run on None (WT-M3.B.4).
    """
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def week_start(value, first_day: int = DEFAULT_FIRST_DAY) -> Optional[date]:
    """The first day of the week containing ``value``."""
    day = coerce_date(value)
    if day is None:
        return None
    first_day = normalize_first_day(first_day)
    return day - timedelta(days=(day.weekday() - first_day) % 7)


def week_end(value, first_day: int = DEFAULT_FIRST_DAY) -> Optional[date]:
    """The last day of the week containing ``value``."""
    start = week_start(value, first_day)
    return None if start is None else start + timedelta(days=6)


def week_bounds(value, first_day: int = DEFAULT_FIRST_DAY):
    """``(start, end)`` of the week containing ``value``, or None."""
    start = week_start(value, first_day)
    return None if start is None else (start, start + timedelta(days=6))


def week_bounds_iso(value, first_day: int = DEFAULT_FIRST_DAY):
    """``(start, end)`` of the week containing ``value`` as ISO strings, or None."""
    found = week_bounds(value, first_day)
    return None if found is None else (found[0].isoformat(), found[1].isoformat())


def month_week_starts(year: int, month: int, first_day: int = DEFAULT_FIRST_DAY):
    """Every week start that falls inside ``year``-``month``.

    Purpose: the one place "which weeks are in this month" is computed.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m2b
    Tests:   tests/test_week_numbering.py::test_wt_m2b1_no_direct_week_math_callers
    """
    from calendar import monthrange

    if month < 1 or month > 12:
        return []
    first_day = normalize_first_day(first_day)
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])

    cursor = week_start(month_start, first_day)
    if cursor < month_start:
        cursor += timedelta(days=7)

    starts = []
    while cursor <= month_end:
        starts.append(cursor)
        cursor += timedelta(days=7)
    return starts


def _first_full_week_start(year: int, first_day: int) -> date:
    """Start of the first week lying entirely inside ``year``."""
    jan1 = date(year, 1, 1)
    start = week_start(jan1, first_day)
    return start if start >= jan1 else start + timedelta(days=7)


def year_and_week(
    value,
    rule: str = DEFAULT_RULE,
    first_day: int = DEFAULT_FIRST_DAY,
) -> Optional[Tuple[int, int]]:
    """WT-M2.A.3 — the (year, week) of the week containing ``value``.

    Purpose: never return a bare week number. 2026-12-28 and 2027-01-01 are
             both ISO 2026-W53; ``53`` alone cannot say which year (WT-F2b).
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m2a
    Tests:   tests/test_week_numbering.py::test_wt_m2a1_rule_table_matches_spec
             tests/test_week_numbering.py::test_wt_m2a3_helper_returns_year_and_week

    Returns None when ``value`` is not a date.
    """
    day = coerce_date(value)
    if day is None:
        return None

    rule = normalize_rule(rule)
    first_day = normalize_first_day(first_day)

    if rule == RULE_ISO:
        iso = day.isocalendar()
        return int(iso[0]), int(iso[1])

    start = week_start(day, first_day)

    if rule == RULE_JAN1:
        # Week 1 is the week containing 1 January of the date's own calendar
        # year, so a week straddling New Year carries two labels — that is the
        # point of a calendar-year-anchored rule.
        anchor = week_start(date(day.year, 1, 1), first_day)
        return day.year, ((start - anchor).days // 7) + 1

    # RULE_FIRST_FULL — week 1 is the first week wholly inside the year, so
    # the stub days before it belong to the previous year's last week.
    year = day.year
    anchor = _first_full_week_start(year, first_day)
    if day < anchor:
        year -= 1
        anchor = _first_full_week_start(year, first_day)
    return year, ((start - anchor).days // 7) + 1


def week_number(
    value,
    rule: str = DEFAULT_RULE,
    first_day: int = DEFAULT_FIRST_DAY,
) -> Optional[int]:
    """Just the week number. Prefer ``year_and_week`` — see WT-F2b."""
    result = year_and_week(value, rule, first_day)
    return None if result is None else result[1]


def week_token(
    value,
    rule: str = DEFAULT_RULE,
    first_day: int = DEFAULT_FIRST_DAY,
) -> Optional[str]:
    """The ``W9``-style token used in Weekly Tactic titles."""
    result = year_and_week(value, rule, first_day)
    return None if result is None else f"W{result[1]}"


class WeekCalendar:
    """A week calendar bound to the user's settings.

    Purpose: give callers one object to ask, instead of each one loading
             settings and doing its own arithmetic (WT-M2.B).
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m2b
    Tests:   tests/test_week_numbering.py::test_wt_m2b1_no_direct_week_math_callers
    """

    def __init__(self, first_day: int = DEFAULT_FIRST_DAY, rule: str = DEFAULT_RULE):
        self.first_day = normalize_first_day(first_day)
        self.rule = normalize_rule(rule)

    @classmethod
    def from_settings(cls, settings=None) -> "WeekCalendar":
        """Build from ``AppSettings``, tolerating a settings file that fails to load."""
        if settings is None:
            try:
                from .app_settings import AppSettings
                settings = AppSettings.load()
            except Exception:
                settings = None
        return cls(
            first_day=getattr(settings, "first_day_of_week", DEFAULT_FIRST_DAY),
            rule=getattr(settings, "first_week_of_year_rule", DEFAULT_RULE),
        )

    def start(self, value) -> Optional[date]:
        return week_start(value, self.first_day)

    def end(self, value) -> Optional[date]:
        return week_end(value, self.first_day)

    def bounds(self, value):
        return week_bounds(value, self.first_day)

    def bounds_iso(self, value):
        """``(start, end)`` as ISO strings, or None."""
        found = week_bounds(value, self.first_day)
        return None if found is None else (found[0].isoformat(), found[1].isoformat())

    def year_and_week(self, value) -> Optional[Tuple[int, int]]:
        return year_and_week(value, self.rule, self.first_day)

    def number(self, value) -> Optional[int]:
        return week_number(value, self.rule, self.first_day)

    def token(self, value) -> Optional[str]:
        return week_token(value, self.rule, self.first_day)

    def contains(self, week_start_value, value) -> bool:
        """True when ``value`` falls inside the week starting ``week_start_value``."""
        start = self.start(week_start_value)
        day = coerce_date(value)
        if start is None or day is None:
            return False
        return start <= day <= start + timedelta(days=6)
