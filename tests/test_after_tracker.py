"""Scheduled callbacks must not outlive the window they target.

Purpose: `self.after(2000, ...)` on a window the user can close first leaves Tk
         holding a callback against a widget that no longer exists; when it
         fires, Tk raises "invalid command name" into the event loop.
Spec:    BACKLOG.md, "What else may be leaking"
Tests:   this file

The same shape as the window leak (P30): something finite is taken — a Tk timer
registration — and nothing gives it back.
"""

from __future__ import annotations

import pathlib
import sys

# Self-contained path bootstrap. test_rm3d imports every test file with the
# repo root stripped from sys.path, and this file sorts first — so it cannot
# rely on an earlier file having put the root back, which is the only reason
# the other files that import `conftest` survive that probe.
_ROOT = pathlib.Path(__file__).resolve().parents[1]
for _entry in (str(_ROOT), str(_ROOT / "src")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import customtkinter as ctk  # noqa: E402
import pytest  # noqa: E402

from src.getmoredone.utils.after_tracker import TrackedAfterMixin  # noqa: E402


class _Window(TrackedAfterMixin, ctk.CTkToplevel):
    pass


@pytest.fixture
def root():
    win = ctk.CTk()
    yield win
    win.destroy()


def test_a_tracked_callback_is_cancelled_when_the_window_closes(root):
    """The point of the whole thing."""
    window = _Window(root)
    fired = []
    window.tracked_after(50_000, lambda: fired.append(True))
    assert window._tracked_after_ids, "the handle was not remembered"

    pending = window._tracked_after_ids
    window.destroy()

    assert pending == set(), (
        "closing the window left a callback scheduled against a dead widget"
    )
    assert fired == []


def test_cancel_is_safe_twice_and_on_a_window_with_nothing_pending(root):
    window = _Window(root)
    assert window.cancel_tracked_after() == 0      # nothing scheduled yet
    window.tracked_after(50_000, lambda: None)
    assert window.cancel_tracked_after() == 1
    assert window.cancel_tracked_after() == 0      # already cleared
    window.destroy()


def test_a_fired_callback_stops_being_tracked(root):
    """A long-lived window must not accumulate the ids of callbacks that ran."""
    window = _Window(root)
    fired = []
    window.tracked_after(1, lambda: fired.append(True))
    for _ in range(50):
        window.update()
        if fired:
            break
    assert fired == [True], "the callback never ran"
    assert window._tracked_after_ids == set(), (
        "a callback that has already fired is still being tracked"
    )
    window.destroy()


def test_the_windows_that_schedule_long_callbacks_use_the_tracker():
    """WL — the sites the backlog named, asserted rather than assumed.

    Each of these schedules a callback measured in seconds on a window the user
    can close in the meantime. Parsed, not grepped: a bare `self.after(` inside
    a comment explaining the tracker would satisfy a substring search.
    """
    import ast
    import pathlib

    src_root = pathlib.Path(__file__).resolve().parents[1] / "src" / "getmoredone"
    offenders = []
    for name in ("screens/timer_window.py", "screens/timer_window_dialogs.py",
                 "screens/item_editor.py"):
        path = src_root / name
        for node in ast.walk(ast.parse(path.read_text())):
            # A bare expression statement: the handle is thrown away, so
            # nothing can ever cancel it. `self.update_timer_id = self.after(...)`
            # keeps its handle and is cancelled by _cancel_pending_timer, which
            # is a different mechanism doing the same job — the delay is not
            # the signal, the discarded handle is.
            if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                continue
            call = node.value
            fn = call.func
            if not (isinstance(fn, ast.Attribute) and fn.attr == "after"):
                continue
            if not (isinstance(fn.value, ast.Name) and fn.value.id == "self"):
                continue
            delay = call.args[0] if call.args else None
            if isinstance(delay, ast.Constant) and isinstance(delay.value, int) \
                    and delay.value >= 1000:
                offenders.append(f"{name}:{node.lineno} self.after({delay.value})")

    assert not offenders, (
        "these schedule a callback seconds into the future without tracking it, "
        f"so closing the window leaves it pointing at a dead widget: {offenders}"
    )
