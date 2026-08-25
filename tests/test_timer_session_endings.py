"""The three ways a timer session can end, exercised through the real modals.

Purpose: T1 — "Save Related - Close Timer" wrote its work log and left the
         window on screen. Every test in tests/test_reward_protocol_timer.py
         stubs CompletionNoteDialog out, and the modal is the *only* thing that
         differs between Save Related (which failed to close) and Cancel (which
         closed), so the defect had no way to fail a test.
Spec:    docs/implementation_plan_2026-08-25_timer_session_endings.md#acceptance-criteria
Tests:   this file

These build real, mapped windows: grab_set() raises "window not viewable" on
the withdrawn windows the rest of the suite uses, so a withdrawn run cannot
reach the code path under test at all.
"""

from __future__ import annotations

import random

import customtkinter as ctk
import pytest

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem
from src.getmoredone.screens import timer_window as tw
from src.getmoredone.screens.timer_window import TimerWindow
from src.getmoredone.screens.timer_window_dialogs import CompletionNoteDialog

DELIVERABLE = "Draft section 2's opening paragraph"


@pytest.fixture
def root():
    win = ctk.CTk()
    win.withdraw()
    yield win
    win.destroy()


@pytest.fixture
def manager(tmp_path):
    db = DatabaseManager(str(tmp_path / "endings.db"))
    yield db
    db.close()


@pytest.fixture
def hushed(monkeypatch):
    """Silence sound and music only. The dialogs are the thing under test."""
    monkeypatch.setattr(TimerWindow, "_start_music", lambda self: False)
    monkeypatch.setattr(TimerWindow, "_stop_music", lambda self: None)
    monkeypatch.setattr(TimerWindow, "play_sound", lambda self, is_break_start: None)
    monkeypatch.setattr(TimerWindow, "_flash_window", lambda self: None)
    yield


def _item(manager, **kwargs):
    item = ActionItem(who="Self", title="A task", planned_minutes=30,
                      deliverable=DELIVERABLE, **kwargs)
    manager.create_action_item(item)
    return item


def _stopped_timer(root, manager, item):
    """A timer that has run and been stopped — the state the buttons appear in."""
    timer = TimerWindow(root, manager, item, rng=random.Random(1))
    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60
    timer.stop_timer()
    return timer


def _dismiss_the_note_dialog(timer, how="skip"):
    """Press Skip/Save on the CompletionNoteDialog once it exists.

    Scheduled before the button handler runs, because the handler blocks in
    wait_window until the dialog is gone.
    """
    def press():
        for child in timer.winfo_children():
            if isinstance(child, CompletionNoteDialog):
                getattr(child, how)()
                return
        timer.after(20, press)  # not built yet

    timer.after(20, press)


def test_t11_save_related_closes_the_window_after_a_real_modal(
        root, manager, hushed, mapped_windows):
    """T1.1 — the window is gone, not merely told to go.

    The existing test at tests/test_reward_protocol_timer.py:1649 asserts the
    work log and the refresh callback and stops there, so a Save Related that
    saved and stayed on screen passed it.
    """
    item = _item(manager)
    timer = _stopped_timer(root, manager, item)

    _dismiss_the_note_dialog(timer)
    timer.save_and_close_action()

    assert manager.get_work_logs(item.id), "the session was not recorded"
    assert not timer.winfo_exists(), (
        "Save Related recorded the session and left the window on screen"
    )


def test_t11b_save_related_closes_when_launched_from_the_action_item_editor(
        root, manager, hushed, mapped_windows):
    """T1.1 — the same ending, in the configuration the report came from.

    The timer is opened by the editor's Timer button, so its parent is the
    ItemEditorDialog and its on_close is _on_timer_closed — which reloads the
    editor's fields and calls the opener's own callback. The previous test has
    neither, and passes; this one runs what the user ran.
    """
    from src.getmoredone.screens.item_editor import ItemEditorDialog

    item = _item(manager)
    editor = ItemEditorDialog(root, manager, item.id)
    editor.update()

    editor.start_timer()
    timer = next(c for c in editor.winfo_children() if isinstance(c, TimerWindow))
    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60
    timer.stop_timer()

    _dismiss_the_note_dialog(timer)
    timer.save_and_close_action()

    assert manager.get_work_logs(item.id), "the session was not recorded"
    assert not timer.winfo_exists(), (
        "Save Related recorded the session and left the window on screen"
    )
    editor.destroy()


def _really_topmost(window):
    """Set -topmost past conftest's patch, via the Tcl interpreter.

    conftest neuters ``attributes('-topmost', ...)`` on all four window classes
    so a test run cannot throw always-on-top windows over the user's desktop.
    The timer sets -topmost at construction and never drops it, so a run with
    the patch in force is not running the configuration the report came from.
    """
    window.tk.call("wm", "attributes", window._w, "-topmost", True)


def test_t11c_save_related_closes_while_the_timer_is_really_topmost(
        root, manager, hushed, mapped_windows):
    """T1.1 — with the always-on-top flag the app actually runs with."""
    item = _item(manager)
    timer = _stopped_timer(root, manager, item)
    _really_topmost(timer)
    timer.update()

    _dismiss_the_note_dialog(timer)
    timer.save_and_close_action()

    assert manager.get_work_logs(item.id), "the session was not recorded"
    assert not timer.winfo_exists(), (
        "Save Related recorded the session and left the window on screen"
    )


def test_t14_two_timers_on_one_item_reproduce_the_reported_symptom(
        root, manager, hushed, mapped_windows):
    """T1.4 — nothing stops a second timer window opening on the same item.

    Every entry point constructs a TimerWindow unconditionally, and setup_window
    positions all of them at the same saved timer_window_x/y — so a second one
    lands exactly on top of the first and the two are indistinguishable.

    This reproduces the 2026-08-25 database state exactly: a work log at
    08:02:00 from one window, then a completion and a follow-up at 08:07:03
    from the other with no work log at all.
    """
    item = _item(manager)
    first = _stopped_timer(root, manager, item)
    second = TimerWindow(root, manager, item, rng=random.Random(1))

    assert first.geometry().split("+")[1:] == second.geometry().split("+")[1:], (
        "the two windows are not stacked, so this is not the reported shape"
    )

    _dismiss_the_note_dialog(first)
    first.save_and_close_action()

    assert len(manager.get_work_logs(item.id)) == 1, "the first window's session"
    assert not first.winfo_exists(), "the first window did close"
    assert second.winfo_exists(), (
        "a second timer is still on screen, which is what 'the screen doesn't "
        "close' looks like from the user's side"
    )
    assert second.start_timestamp is None, (
        "the surviving window never started, so any ending it reaches records "
        "nothing and says nothing about it"
    )
    second.destroy()


# --- T5 : a modal must not open behind the always-on-top timer ---------------
#
# conftest silences grab_set() and -topmost for the whole run, so the symptom
# itself cannot occur in a test. What these assert is the mechanism that
# prevents it, read back through the Tcl interpreter — past the patch in both
# directions, so the measurement is of the code and not of conftest.

def _topmost_now(window) -> bool:
    return bool(int(window.tk.call("wm", "attributes", window._w, "-topmost")))


def test_t51_a_modal_drops_the_timers_always_on_top(root, manager, hushed,
                                                    mapped_windows):
    """T5.1 — while the note dialog is up, the timer is not on top of it."""
    item = _item(manager)
    timer = _stopped_timer(root, manager, item)
    _really_topmost(timer)
    assert _topmost_now(timer), "the precondition did not take"

    seen = []

    def look():
        for child in timer.winfo_children():
            if isinstance(child, CompletionNoteDialog):
                seen.append(_topmost_now(timer))
                child.skip()
                return
        timer.after(20, look)

    timer.after(20, look)
    timer.save_and_close_action()

    assert seen == [False], (
        f"the timer was still always-on-top while its modal was open: {seen}"
    )


def test_t52_the_timer_is_topmost_again_afterwards(root, manager, hushed,
                                                   mapped_windows):
    """T5.2 — the flag is borrowed for the modal, not thrown away."""
    from src.getmoredone.screens.timer_window_dialogs import suspend_parent_topmost

    item = _item(manager)
    timer = _stopped_timer(root, manager, item)
    _really_topmost(timer)

    dialog = ctk.CTkToplevel(timer)
    suspend_parent_topmost(dialog, timer)
    assert not _topmost_now(timer), "the modal did not drop the parent's flag"

    dialog.destroy()
    timer.update()

    assert _topmost_now(timer), "the timer never got its always-on-top back"
    timer.destroy()


def test_t53_a_parent_that_was_not_topmost_is_left_alone(root, manager, hushed,
                                                         mapped_windows):
    """T5.3 — the helper never *raises* a window, only ever lowers and restores.

    It reaches wm attributes through the Tcl interpreter, past the patch
    conftest uses to keep always-on-top windows off the user's desktop. That is
    only defensible while it cannot turn the flag on for a window that did not
    already have it.
    """
    from src.getmoredone.screens.timer_window_dialogs import suspend_parent_topmost

    item = _item(manager)
    timer = _stopped_timer(root, manager, item)
    assert not _topmost_now(timer), "conftest should have swallowed the timer's own set"

    dialog = ctk.CTkToplevel(timer)
    suspend_parent_topmost(dialog, timer)
    dialog.destroy()
    timer.update()

    assert not _topmost_now(timer), (
        "the helper turned always-on-top ON for a window that did not have it"
    )
    timer.destroy()


def test_t54_every_grabbing_dialog_suspends_the_parents_topmost():
    """T5.4 — no sibling modal left unhardened (P5).

    Parsed, not grepped: a substring search would match the word inside the
    comment that explains it, and would keep matching after the call it is
    meant to find had been deleted.
    """
    import ast
    import pathlib

    from src.getmoredone.screens import timer_window_dialogs as dlg

    tree = ast.parse(pathlib.Path(dlg.__file__).read_text())

    def calls_in(node):
        return {
            n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
            for n in ast.walk(node)
            if isinstance(n, ast.Call)
            and isinstance(n.func, (ast.Attribute, ast.Name))
        }

    grabbing = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names = calls_in(node)
            if "grab_set" in names:
                grabbing[node.name] = names

    assert set(grabbing) == {
        "CompletionNoteDialog", "NextStepsDialog", "DeliverableDialog", "SavorDialog",
    }, f"the set of modal dialogs changed: {sorted(grabbing)}"

    unhardened = [n for n, c in grabbing.items() if "suspend_parent_topmost" not in c]
    assert unhardened == [], (
        f"these hold a grab without dropping the parent's always-on-top: {unhardened}"
    )
