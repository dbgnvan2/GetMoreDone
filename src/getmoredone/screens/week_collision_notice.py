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
