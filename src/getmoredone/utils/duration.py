"""Render a count of minutes the way a person reads it.

Purpose: PT2 — a project's total time is stored as minutes and "750" reads
         worse than "12h 30m" everywhere it is shown.
Tests:   tests/test_project_time_totals.py::test_pt21_minutes_render_the_way_a_person_reads_them
"""

from __future__ import annotations

from typing import Optional


def format_minutes(minutes: Optional[int]) -> str:
    """``None``/0 -> "0m"; under an hour -> "45m"; otherwise "2h" or "2h 30m"."""
    total = int(minutes or 0)
    if total < 0:
        total = 0
    hours, rest = divmod(total, 60)
    if not hours:
        return f"{rest}m"
    if not rest:
        return f"{hours}h"
    return f"{hours}h {rest}m"
