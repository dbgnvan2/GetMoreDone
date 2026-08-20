"""BP4 — code retired because nothing in the app called it.

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#bp4

``complete_and_create`` and ``RescheduleDialog`` each had no caller in ``src/``.
Both had been kept alive by their own tests, which is how an unreachable path
goes on collecting maintenance — the weekly-lineage work hardened
``complete_and_create`` twice for a path no user could reach.

These assertions exist so the names cannot quietly return without a caller: a
grep, because the point is the absence of a definition, and no behavioural test
can assert that.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "getmoredone"


def _python_files():
    return sorted(SRC.rglob("*.py"))


@pytest.mark.parametrize("name", ["complete_and_create", "RescheduleDialog"])
def test_bp4_retired_names_do_not_return(name):
    """No definition and no call site anywhere under src/."""
    offenders = [
        str(path.relative_to(REPO))
        for path in _python_files()
        if name in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"{name} was retired in BP4 because nothing called it; it is back in "
        f"{offenders}. If it is wanted again, wire it to a real surface and "
        "delete this assertion — do not re-add it with tests as its only caller."
    )


def test_bp4_the_reschedule_dialog_module_is_gone():
    assert not (SRC / "screens" / "reschedule_dialog.py").exists()


def test_bp4_this_guard_can_actually_fire():
    """Guards the guard (P24): the search really does look at file contents."""
    assert any(
        "create_followup_item" in path.read_text(encoding="utf-8")
        for path in _python_files()
    ), "the file sweep found nothing at all — it is not reading src/"
