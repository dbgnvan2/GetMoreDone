"""Tell the user when a Weekly Tactic refused to move.

Purpose: give the collision signal one wording and one place, so every surface
         that can move a week item reports it the same way.
Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1c5
Tests:   tests/test_weekly_tactic_schema.py::test_wt_m1c5_collision_notice_reaches_the_user

``update_action_item`` and ``reschedule_item`` return False when a week item's
target week is already taken, and record the detail on
``db_manager.last_week_collision``. A return value nobody reads is the same
silence as no return value at all (P25) — so this is the reader.
"""

from tkinter import messagebox
from typing import Any, Optional


def describe_week_collision(collision: Optional[dict]) -> Optional[str]:
    """One sentence naming what did not move, or None if nothing collided."""
    if not collision:
        return None
    return (
        "That week already has a Weekly Tactic for this Annual Plan Element, "
        f"so the tactic stayed on {collision.get('kept_start')} instead of "
        f"moving to {collision.get('rejected_start')}. "
        "Only one Weekly Tactic can exist per plan element per week."
    )


def describe_cascade(report: Any) -> Optional[str]:
    """What a re-file created, phrased for a status line. None if nothing was.

    Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6b5
    Tests: tests/test_weekly_tactic_surfaces.py::test_wt_m6b5_created_records_summarised_to_user
    """
    if report is None:
        return None
    status = getattr(report, "status", "refiled")
    if status == "tactic_missing":
        return (
            "This item's Weekly Tactic no longer exists, so the item was saved "
            "without being re-filed and may now sit outside its week."
        )
    if status == "ape_missing":
        return (
            "This item's Weekly Tactic has no Annual Plan Element, so the item "
            "was saved without being re-filed and may now sit outside its week."
        )
    text = report.describe() if hasattr(report, "describe") else ""
    return text or None


def cascade_needs_attention(report: Any) -> bool:
    """Does this report warrant interrupting the user?

    Creating a Weekly Tactic happens on most moves across a week boundary, so
    a modal for every one of those would be noise the user learns to dismiss.
    Two things genuinely need saying:

    * a **year rollover** created blank editorial rows that need the user's own
      words — nobody else can write them, and nothing else will ask;
    * the re-file **failed**, so the item is knowingly outside its week.

    Everything else is in the report and in ``weekly_tactic_debug.log``.
    """
    if report is None:
        return False
    return bool(getattr(report, "failed", False) or getattr(report, "stubs", None))


def notify_cascade(db_manager: Any, parent: Any = None) -> bool:
    """Tell the user when the last save built something needing their attention.

    ``last_cascade_report`` had no reader anywhere in ``src/`` — a save that
    built eight planning rows, blank rollover stubs included, told the user
    nothing (P25).
    """
    report = getattr(db_manager, "last_cascade_report", None)
    if not cascade_needs_attention(report):
        return False
    message = describe_cascade(report)
    if not message:
        return False
    if getattr(report, "failed", False):
        # A failure under a success title with an info icon reads as good news.
        messagebox.showwarning("Item not re-filed", message, parent=parent)
    else:
        messagebox.showinfo("Plan records created", message, parent=parent)
    return True


def notify_weekly_tactic_changes(db_manager: Any, parent: Any = None) -> bool:
    """Report a refused week *and* anything the cascade built. One call site."""
    collided = notify_week_collision(db_manager, parent)
    created = notify_cascade(db_manager, parent)
    return collided or created


def notify_week_collision(db_manager: Any, parent: Any = None) -> bool:
    """Show the collision notice if the last save hit one.

    Returns True when a notice was shown. Safe to call after every save: the
    flag is cleared at the start of each one, so a stale collision cannot be
    reported as this save's result.
    """
    message = describe_week_collision(getattr(db_manager, "last_week_collision", None))
    if not message:
        return False
    messagebox.showwarning("Week Already Taken", message, parent=parent)
    return True
