"""The three ways a timer session can end, exercised through the real modals.

Purpose: T1 — "Save Related - Close Timer" wrote its work log and left the
         window on screen. Every test in tests/test_reward_protocol_timer.py
         stubs CompletionNoteDialog out, and the modal is the *only* thing that
         differs between Save Related (which failed to close) and Cancel (which
         closed), so the defect had no way to fail a test.
Spec:    docs/implementation_plan_2026-08-25_timer_session_endings.md#acceptance-criteria
Tests:   this file

These build real TimerWindows on a real DatabaseManager, withdrawn like every
other window in the suite. They were written against the ``mapped_windows``
fixture on the assumption that grab_set() needs a viewable window — it does,
but conftest silences grab_set() for the whole run, so nothing here ever
called it. Sixteen tests that skip on the machine people iterate on is a poor
trade for a precondition that was never required; measured by removing the
fixture and re-running every mutation.

-topmost is read and written through ``window.tk.call`` rather than
``window.attributes``, past the patch conftest uses to keep always-on-top
windows off the user's desktop — otherwise these would be measuring conftest.
"""

from __future__ import annotations

import random

import customtkinter as ctk
import pytest
import tkinter as tk

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


@pytest.fixture(autouse=True)
def _empty_timer_registry():
    """B2 — the registry is module-level, so it leaks between tests.

    Found the hard way: a mutation that made open_for hand back ANY live timer
    instead of this item's passed the whole file and failed when its test ran
    alone. Dead entries left by earlier tests were being reused, so the wrong
    behaviour looked right (P8 — the second run sees state the first left).
    """
    tw._LIVE_TIMERS.clear()
    yield
    tw._LIVE_TIMERS.clear()


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
        root, manager, hushed):
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
        root, manager, hushed):
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
        root, manager, hushed):
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


# --- T5 : a modal must not open behind the always-on-top timer ---------------
#
# conftest silences grab_set() and -topmost for the whole run, so the symptom
# itself cannot occur in a test. What these assert is the mechanism that
# prevents it, read back through the Tcl interpreter — past the patch in both
# directions, so the measurement is of the code and not of conftest.

def _topmost_now(window) -> bool:
    return bool(int(window.tk.call("wm", "attributes", window._w, "-topmost")))


def test_t51_a_modal_drops_the_timers_always_on_top(root, manager, hushed,):
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


def test_t52_the_timer_is_topmost_again_afterwards(root, manager, hushed):
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


def test_t53_a_parent_that_was_not_topmost_is_left_alone(root, manager, hushed):
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
        "CompletionNoteDialog", "DeliverableDialog", "SavorDialog",
    }, f"the set of modal dialogs changed: {sorted(grabbing)}"

    unhardened = [n for n, c in grabbing.items() if "suspend_parent_topmost" not in c]
    assert unhardened == [], (
        f"these hold a grab without dropping the parent's always-on-top: {unhardened}"
    )


def test_t55_every_messagebox_over_the_timer_suspends_its_topmost():
    """T5.5 — the sibling class the first sweep stopped short of (P5).

    tkinter.messagebox builds its own Toplevel and grabs it, so it belongs to
    the same class as the four dialogs — but it lives in a different file and
    the AST guard above, whose docstring says "no sibling modal left
    unhardened", could not see it. Three of these four sites are the except
    handler of a timer ending, which is the worst place to put an invisible
    modal: something has already gone wrong and the user is told nothing.

    Anchored to whole call expressions via the AST, not grepped: the words
    appear in the comments explaining them.
    """
    import ast
    import pathlib

    from src.getmoredone.screens import timer_window as twin
    from src.getmoredone.screens import timer_window_dialogs as dlg

    SHOW = ("showerror", "showwarning", "showinfo", "askyesno")

    def _is_show(node):
        """A messagebox call under either spelling.

        Attribute AND Name: `from tkinter.messagebox import showerror` then a
        bare `showerror(...)` is a real site, and matching only the dotted form
        let one through — proved by mutation during the csdp re-sweep. It is
        the same name-resolution shape as the t31 defect two commits earlier.
        """
        if not isinstance(node, ast.Call):
            return False
        fn = node.func
        if isinstance(fn, ast.Attribute):
            return fn.attr in SHOW
        return isinstance(fn, ast.Name) and fn.id in SHOW

    def _walk_here(node):
        """Walk a subtree WITHOUT descending into nested callables.

        ast.walk crosses function boundaries, so a showerror moved into a
        `def later():` scheduled with after() inside the `with` counted as
        guarded while running, at runtime, after the context manager had
        exited and given the flag back. Also proved by mutation.
        """
        stack = list(ast.iter_child_nodes(node))
        while stack:
            cur = stack.pop()
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            yield cur
            stack.extend(ast.iter_child_nodes(cur))

    all_sites, guarded, unparented = set(), set(), set()
    for mod in (twin, dlg):
        name = pathlib.Path(mod.__file__).name
        tree = ast.parse(pathlib.Path(mod.__file__).read_text())
        for node in ast.walk(tree):
            if _is_show(node):
                # Keyed by (file, line): a second parse makes new node objects,
                # so identity cannot be used across two walks.
                all_sites.add((name, node.lineno))
                if not any(k.arg == "parent" for k in node.keywords):
                    unparented.add((name, node.lineno))
            if not isinstance(node, ast.With):
                continue
            suspended = {
                ast.unparse(item.context_expr.args[0])
                for item in node.items
                if isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Name)
                and item.context_expr.func.id == "parent_topmost_suspended"
                and item.context_expr.args
            }
            if not suspended:
                continue
            for inner in _walk_here(node):
                if not _is_show(inner):
                    continue
                # The window suspended must be the window the box is attached
                # to. One site suspended the timer while parenting the box to a
                # different always-on-top window, and this guard called it
                # covered because it never compared the two.
                target = next((ast.unparse(k.value) for k in inner.keywords
                               if k.arg == "parent"), None)
                if target is not None and target in suspended:
                    guarded.add((name, inner.lineno))

    assert len(all_sites) == 4, (
        f"the set of messagebox calls changed: {sorted(all_sites)}. A new one "
        "must be wrapped in parent_topmost_suspended and counted here."
    )
    assert all_sites - guarded == set(), (
        "these messagebox calls open behind an always-on-top window holding a "
        f"grab, or suspend a window other than the one they attach to: "
        f"{sorted(all_sites - guarded)}"
    )
    assert unparented == set(), (
        f"these messagebox calls pass no parent=, so Tk attaches them to the "
        f"default root rather than the timer: {sorted(unparented)}"
    )


def test_t56_a_second_modal_does_not_hand_the_flag_back_early():
    """T5.6 — nesting. The first modal's restore must not outrank the second.

    Without a depth count, modal B opens over an already-suspended parent,
    reads -topmost as False, decides there is nothing to do and registers no
    restore. Then A closes and raises the parent back over B, which is still
    holding grab_set() — the reported bug, rebuilt out of its own fix.
    """
    from src.getmoredone.screens.timer_window_dialogs import (
        _resume_topmost, _suspend_topmost)

    parent = ctk.CTk()
    parent.withdraw()
    try:
        _really_topmost(parent)
        assert _topmost_now(parent), "precondition"

        assert _suspend_topmost(parent) is True          # modal A
        assert _suspend_topmost(parent) is True          # modal B, over A
        assert not _topmost_now(parent)

        _resume_topmost(parent)                          # A closes first
        assert not _topmost_now(parent), (
            "the parent was raised back over a modal that is still open"
        )

        _resume_topmost(parent)                          # B closes
        assert _topmost_now(parent), "the flag was never given back"
    finally:
        parent.destroy()


def test_t57_an_unbalanced_resume_does_not_break_the_next_modal():
    """T5.7 — a stray resume must not drive the count below zero.

    The counter is state on a long-lived window, so an extra resume — a
    mis-bound <Destroy>, a dialog torn down twice — is reachable. Left
    unclamped it makes the count negative, and then the NEXT modal sees a
    non-zero depth, concludes the flag is already suspended, and opens with
    the parent still on top of it. The damage is not in the stray call; it is
    in the modal after it, which is what this asserts.

    The first version of this test asserted only that a stray resume did not
    raise the flag. It could not fail: nothing had been saved, so the write
    was skipped for a reason unrelated to the guard.
    """
    from src.getmoredone.screens.timer_window_dialogs import (
        _resume_topmost, _suspend_topmost)

    parent = ctk.CTk()
    parent.withdraw()
    try:
        _really_topmost(parent)
        _suspend_topmost(parent)
        _resume_topmost(parent)
        assert _topmost_now(parent), "precondition: back to where we started"

        _resume_topmost(parent)          # the stray one

        assert _suspend_topmost(parent) is True
        assert not _topmost_now(parent), (
            "the modal after a stray resume opened with the parent still "
            "always-on-top — the reported bug, via the counter"
        )
    finally:
        parent.destroy()


# --- T2 / T3 / T6 : Complete & Create Follow Up ------------------------------

def _continue_from(root, manager, item, vps_manager=None):
    """Run the ending, with the two dialogs it still opens driven for us."""
    timer = TimerWindow(root, manager, item, rng=random.Random(1),
                        vps_manager=vps_manager)
    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60
    timer.stop_timer()
    _dismiss_the_note_dialog(timer)
    timer.continue_action()
    return timer


def _child_of(manager, item):
    kids = manager.get_children(item.id)
    assert len(kids) == 1, f"expected one follow-up, found {len(kids)}"
    return kids[0]


def test_t21_the_followup_keeps_the_items_dates(root, manager, hushed,
                                                monkeypatch):
    """T2.1 — no +1 shift. The follow-up continues the same day's work."""
    from src.getmoredone.screens import item_editor as ie
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    item = _item(manager, start_date="2026-08-24", due_date="2026-08-27")
    _continue_from(root, manager, item)

    child = _child_of(manager, item)
    assert (child.start_date, child.due_date) == ("2026-08-24", "2026-08-27"), (
        f"the follow-up was re-dated to {child.start_date}/{child.due_date}"
    )


def test_t22_a_past_dated_item_yields_a_past_dated_followup(
        root, manager, hushed, monkeypatch):
    """T2.2 — inheriting the dates means a late item begets a late follow-up.

    Confirmed as intended when it was raised. Pinned so a later pass does not
    read it as a bug and quietly re-introduce a shift.
    """
    from src.getmoredone.screens import item_editor as ie
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    item = _item(manager, start_date="2020-01-06", due_date="2020-01-06")
    _continue_from(root, manager, item)

    child = _child_of(manager, item)
    assert (child.start_date, child.due_date) == ("2020-01-06", "2020-01-06")


def test_t23_the_followup_description_is_the_prompt(
        root, manager, hushed, monkeypatch):
    """T2.3 — a prompt to fill in, not a copy of the finished item's notes."""
    from src.getmoredone.screens import item_editor as ie
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    item = _item(manager, description="everything I already did today")
    _continue_from(root, manager, item)

    child = _child_of(manager, item)
    assert child.description == tw.FOLLOW_UP_PROMPT, (
        f"the follow-up opened saying {child.description!r}"
    )


def test_b41_the_dead_dialog_is_gone():
    """B4 — NextStepsDialog had no caller, so the class itself is deleted.

    This replaces test_t31, which patched the name on both modules to catch the
    ending building one. That test existed because the class still did; with it
    gone, its absence is the guarantee and nothing can call it by any spelling.
    """
    from src.getmoredone.screens import timer_window as twin
    from src.getmoredone.screens import timer_window_dialogs as dlg

    assert not hasattr(dlg, "NextStepsDialog"), (
        "the dead dialog is back; it had no caller and its removal is what "
        "stops the ending re-acquiring one"
    )
    assert not hasattr(twin, "NextStepsDialog")


def test_t32_the_followup_editor_opens_with_a_vps_manager(
        root, manager, hushed, monkeypatch):
    """T3.2 — the follow-up is what the flow ends on, and it is not crippled.

    Captures the boundary call's kwargs rather than checking the widget was
    built: a vps_manager the editor is never handed is the same as none (P25).
    """
    from src.getmoredone.screens import item_editor as ie

    opened = {}

    def fake_editor(parent, db, item_id, **kwargs):
        opened["item_id"] = item_id
        opened.update(kwargs)

    monkeypatch.setattr(ie, "ItemEditorDialog", fake_editor)

    sentinel = object()
    item = _item(manager)
    _continue_from(root, manager, item, vps_manager=sentinel)

    child = _child_of(manager, item)
    assert opened.get("item_id") == child.id, (
        "the flow did not end on the follow-up's editor"
    )
    assert opened.get("vps_manager") is sentinel, (
        "the follow-up's editor was opened without a vps_manager"
    )


def test_t33_continue_records_the_session_and_leaves_the_item_open(
        root, manager, hushed, monkeypatch):
    """T3.3 — the session is what ends. The Action Item is not.

    "Complete" in this button's name is the timer record, not the task. The
    ending used to call complete_action_item; it does not, and only "Done"
    closes an Action Item.
    """
    from src.getmoredone.screens import item_editor as ie
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    item = _item(manager)
    _continue_from(root, manager, item)

    logs = manager.get_work_logs(item.id)
    assert len(logs) == 1, "the session was not recorded"
    assert logs[0].minutes == 25
    assert manager.get_action_item(item.id).status == "open", (
        "the ending closed the Action Item; only Done does that"
    )
    assert _child_of(manager, item).status == "open"


def test_t41_a_silent_ending_says_so(root, manager, hushed,
                                     capsys):
    """T4.1 — an ending that records nothing must not do it quietly.

    This is the diagnostic whose absence made the original report take four
    attempts to read: a completion and a follow-up existed in the database
    with no work log, and nothing anywhere said why.
    """
    item = _item(manager)
    timer = TimerWindow(root, manager, item, rng=random.Random(1))
    assert timer.start_timestamp is None, "this window never started"

    timer.save_work_log("a note nobody will see")

    assert manager.get_work_logs(item.id) == []
    assert "no session to log" in capsys.readouterr().out, (
        "an ending recorded nothing and said nothing about it"
    )
    timer.destroy()


def test_t61_the_button_says_what_it_does(root, manager, hushed):
    """T6.1 — it creates a follow-up; it no longer opens a Next Steps dialog."""
    item = _item(manager)
    timer = TimerWindow(root, manager, item, rng=random.Random(1))

    assert timer.continue_button.cget("text") == "Complete & Create Follow Up"
    timer.destroy()


def test_t12_a_failed_destroy_is_reported_not_swallowed(root, manager, hushed,
                                                        monkeypatch, capsys):
    """T1.2 — a window that did not close must not be reported as closed.

    The handler read "Window destruction completed with minor error (safe to
    ignore)" and carried on whatever had failed. That is a success decided from
    the reassuring half of the story: the window was still on screen, still
    taking clicks, and nothing said so. It was not this bug — chasing it cost
    an afternoon precisely because it could not be ruled out.
    """
    item = _item(manager)
    timer = TimerWindow(root, manager, item, rng=random.Random(1))

    monkeypatch.setattr(TimerWindow, "destroy",
                        lambda self: (_ for _ in ()).throw(RuntimeError("nope")))
    timer._cleanup_and_destroy()

    out = capsys.readouterr().out
    assert "still on screen after destroy()" in out, (
        "the window survived and the log did not say so"
    )
    assert "safe to ignore" not in out
    monkeypatch.undo()
    timer.destroy()


def test_b01_the_followup_title_carries_the_day_it_was_made(root, manager,
                                                            hushed, monkeypatch):
    """B0.1 — the created date is the only thing that differs between them."""
    from datetime import date as _date

    from src.getmoredone.screens import item_editor as ie
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    item = _item(manager)
    _continue_from(root, manager, item)

    today = _date.today().strftime("%m-%d")
    assert _child_of(manager, item).title == f"A task - Follow up {today}"


def test_b02_the_dated_suffix_does_not_stack():
    """B0.2 — a follow-up of a follow-up replaces the stamp, never appends.

    Driven directly rather than through two endings: the point is the string
    rule, and going through the flow twice on one day cannot produce two
    different dates to tell apart.
    """
    from datetime import date as _date

    first = tw.follow_up_title("Draft the report", _date(2026, 8, 26))
    assert first == "Draft the report - Follow up 08-26"

    second = tw.follow_up_title(first, _date(2026, 8, 27))
    assert second == "Draft the report - Follow up 08-27", (
        f"the stamp stacked instead of being replaced: {second!r}"
    )


def test_b03_a_title_that_merely_mentions_a_follow_up_is_left_alone():
    """B0.2 — the strip is anchored, so a real task name survives it.

    "Follow up 08-26 with Legal" is a legitimate action item. An unanchored
    replace would eat the words out of the middle of someone's title.
    """
    from datetime import date as _date

    # An INTERIOR " - Follow up MM-DD". The first version of this used
    # "Follow up 08-26 with Legal", which has no " - " at all — so it was saved
    # by the prefix, not by the anchor the docstring names, and deleting the
    # anchor left the test green. Measured by the csdp sweep.
    out = tw.follow_up_title("Call Bob - Follow up 08-26 about the invoice",
                             _date(2026, 8, 27))
    assert out == "Call Bob - Follow up 08-26 about the invoice - Follow up 08-27", (
        f"the strip ate words out of the middle of a real title: {out!r}"
    )

    # And the prefix-less form, which was the only case before.
    plain = tw.follow_up_title("Follow up 08-26 with Legal", _date(2026, 8, 27))
    assert plain == "Follow up 08-26 with Legal - Follow up 08-27"


def test_b04_consecutive_days_are_distinguishable():
    """B0.3 — the point of the whole change, stated as the outcome."""
    from datetime import date as _date

    monday = tw.follow_up_title("A task", _date(2026, 8, 24))
    tuesday = tw.follow_up_title(monday, _date(2026, 8, 25))
    wednesday = tw.follow_up_title(tuesday, _date(2026, 8, 26))

    assert len({monday, tuesday, wednesday}) == 3, (
        f"three days produced fewer than three distinct titles: "
        f"{[monday, tuesday, wednesday]}"
    )


def test_t73_a_failed_done_is_not_counted_by_this_ending(root, manager, hushed,
                                                         monkeypatch):
    """T7.3 — the ending no longer completes the item, so it must not count one.

    Done sets the reward flags and they survive a failed save on purpose, so a
    retry records the completion. This ending is not that retry any more:
    carrying them would write deliverable_completed=1 and advance the project
    counter while the Action Item stayed open, and the board would claim a
    completion the item does not record.
    """
    from src.getmoredone.screens import item_editor as ie
    from src.getmoredone.models import ProjectBoard
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    item = _item(manager)
    board = ProjectBoard(title="Website Rebuild")
    manager.create_project_board(board)
    manager.link_action_item_to_project_board(board.id, item.id)

    timer = TimerWindow(root, manager, item, rng=random.Random(1))
    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60
    timer.stop_timer()
    # All three, not just the two flags. save_work_log increments the counter
    # only `if decision is not None and self.session_board_id`, and decision is
    # self._pending_reward — so without this the savor_count assertion below
    # passes whether or not the discard happens, which the csdp sweep proved.
    from src.getmoredone.reward_protocol import RewardDecision
    timer._done_pressed = True          # a Done whose save failed
    timer._savor_shown = True
    timer._pending_reward = RewardDecision(
        phase="wiring", show_savor=True, celebration=None)

    _dismiss_the_note_dialog(timer)
    timer.continue_action()

    log = manager.get_work_logs(item.id)[0]
    assert log.deliverable_completed is False, (
        "an ending that leaves the item open recorded a completed deliverable"
    )
    assert manager.get_project_board(board.id).savor_count == 0, (
        "the project counter advanced for a task that is still open"
    )


# --- B1 : the follow-up keeps the context of the work it continues -----------

def _linked_to_a_board(manager, item):
    from src.getmoredone.models import ProjectBoard
    board = ProjectBoard(title="Website Rebuild")
    manager.create_project_board(board)
    manager.link_action_item_to_project_board(board.id, item.id)
    return board


def test_b11_the_followup_stays_filed_under_its_project(root, manager, hushed,
                                                        monkeypatch):
    """B1.1 — an unfiled follow-up has no reward protocol, and says nothing.

    The ending built its row inline and never called inherit_project_links,
    whose own docstring names this path. The follow-up's editor is where the
    flow now ends, so the user is dropped straight into the unfiled item.
    """
    from src.getmoredone.screens import item_editor as ie
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    item = _item(manager)
    board = _linked_to_a_board(manager, item)
    _continue_from(root, manager, item)

    child = _child_of(manager, item)
    filed = manager.get_project_boards_for_item(child.id)
    assert [b.id for b in filed] == [board.id], (
        "the follow-up landed with no project, so timing it later would "
        "resolve no board: no phase, no counter, no signal"
    )


def test_b13_the_followup_keeps_its_links(root, manager, hushed, monkeypatch):
    """B1.3 — the reference material comes with the work that continues."""
    from src.getmoredone.models import ItemLink
    from src.getmoredone.screens import item_editor as ie
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    item = _item(manager)
    manager.add_item_link(ItemLink(item_id=item.id, url="https://example.test/spec",
                                   label="The spec", link_type="url"))
    _continue_from(root, manager, item)

    child_links = manager.get_item_links(_child_of(manager, item).id)
    assert [(l.url, l.label) for l in child_links] == [
        ("https://example.test/spec", "The spec")], (
        "the follow-up lost the links of the work it continues"
    )


def test_b14_both_followup_paths_inherit_through_the_same_helper():
    """B1.4 — one piece of code, not two field lists that drift.

    They already had drifted: inherit_project_links names the
    complete-and-create path in its docstring and nothing on that path called
    it. Asserted by call site, via the AST, because the failure mode is one
    path quietly growing its own copy again.
    """
    import ast
    import pathlib

    from src.getmoredone import db_manager as dbm
    from src.getmoredone.screens import timer_window as twin

    def calls_in(path, funcname=None):
        tree = ast.parse(pathlib.Path(path).read_text())
        if funcname:
            tree = next(n for n in ast.walk(tree)
                        if isinstance(n, ast.FunctionDef) and n.name == funcname)
        return {n.func.attr for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    followup = calls_in(dbm.__file__, "create_followup_item")
    ending = calls_in(twin.__file__, "continue_action")

    assert "inherit_derived_item_context" in followup, (
        "create_followup_item stopped using the shared helper"
    )
    assert "inherit_derived_item_context" in ending, (
        "the timer ending stopped using the shared helper"
    )
    # Neither may reach past it to the pieces — that is how they drifted before.
    for name, seen in (("create_followup_item", followup), ("continue_action", ending)):
        leaked = seen & {"inherit_project_links", "_inherit_weekly_lineage"}
        assert leaked == set(), (
            f"{name} calls {sorted(leaked)} directly instead of going through "
            "the shared helper, which is how the two paths drifted before"
        )


# --- B3 : a window that did not close must change what happens next ---------

def test_b31_cleanup_reports_whether_it_closed(root, manager, hushed, monkeypatch):
    """B3.1 — the answer is returned, not only logged."""
    item = _item(manager)

    good = TimerWindow(root, manager, item, rng=random.Random(1))
    assert good._cleanup_and_destroy() is True

    stuck = TimerWindow(root, manager, item, rng=random.Random(1))
    monkeypatch.setattr(TimerWindow, "destroy",
                        lambda self: (_ for _ in ()).throw(RuntimeError("nope")))
    assert stuck._cleanup_and_destroy() is False, (
        "a window still on screen was reported as closed"
    )
    monkeypatch.undo()
    stuck.destroy()


def test_b32_the_editor_is_raised_over_a_timer_that_did_not_close(
        root, manager, hushed, monkeypatch):
    """B3.2 — otherwise the flow ends on an editor nobody can see.

    continue_action exists to land the user on the follow-up. A timer that
    survived its destroy() is still always-on-top, so without this the editor
    opens underneath it and the ending looks like it did nothing — which is
    where this whole batch started.
    """
    from src.getmoredone.screens import item_editor as ie
    from src.getmoredone.screens import timer_window_dialogs as dlg

    rescued = []
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: "the-editor")
    monkeypatch.setattr(dlg, "raise_over_a_stuck_timer",
                        lambda window, timer: rescued.append(window))
    monkeypatch.setattr(tw, "raise_over_a_stuck_timer",
                        lambda window, timer: rescued.append(window))
    monkeypatch.setattr(TimerWindow, "_cleanup_and_destroy", lambda self: False)

    item = _item(manager)
    timer = TimerWindow(root, manager, item, rng=random.Random(1))
    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60
    timer.stop_timer()
    _dismiss_the_note_dialog(timer)
    timer.continue_action()

    assert rescued == ["the-editor"], (
        "the follow-up's editor was left under a timer that did not close"
    )
    monkeypatch.undo()
    timer.destroy()


def test_b33_a_timer_that_closed_normally_needs_no_rescue(
        root, manager, hushed, monkeypatch):
    """B3.2 — and the rescue does not fire on the ordinary path.

    Without this the previous test passes just as well against a version that
    raises the editor every time, which would lower a timer that is not there.
    """
    from src.getmoredone.screens import item_editor as ie

    rescued = []
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: "the-editor")
    monkeypatch.setattr(tw, "raise_over_a_stuck_timer",
                        lambda window, timer: rescued.append(window))

    item = _item(manager)
    _continue_from(root, manager, item)

    assert rescued == [], "the rescue fired on a timer that closed cleanly"


# --- B2 : one timer per item, from every entry point ------------------------

def test_b21_a_second_timer_returns_the_first(root, manager, hushed):
    """B2.1 — the defect test_t14 used to pin, now prevented.

    Every timer opens at the same saved coordinates, so a second one landed
    exactly on the first and the two were indistinguishable. Each could write
    its own work log for the same stretch of clock, and an ending pressed on
    the top one revealed an identical window underneath — which is what "no
    related record and the screen doesn't close" looked like.
    """
    item = _item(manager)
    first = TimerWindow.open_for(root, manager, item, rng=random.Random(1))
    second = TimerWindow.open_for(root, manager, item, rng=random.Random(1))

    assert second is first, "a second timer window was opened on the same item"
    first.destroy()


def test_b22_a_different_item_still_gets_its_own_timer(root, manager, hushed):
    """B2.1 — the guard is per item, not a global one-timer rule.

    Without this, `return the first window whatever was asked for` passes the
    test above.
    """
    one = _item(manager)
    two = _item(manager)
    a = TimerWindow.open_for(root, manager, one, rng=random.Random(1))
    b = TimerWindow.open_for(root, manager, two, rng=random.Random(1))

    assert a is not b, "two different items were given the same timer window"
    a.destroy()
    b.destroy()


def test_b23_closing_a_timer_frees_the_item(root, manager, hushed):
    """B2.3 — otherwise the item can never be timed again this session."""
    item = _item(manager)
    first = TimerWindow.open_for(root, manager, item, rng=random.Random(1))
    assert tw._LIVE_TIMERS.get(item.id) is first, "precondition: it was claimed"

    first._cleanup_and_destroy()

    # The registry entry itself, not just the observable outcome: the liveness
    # check downstream would hide a missing release, so a behavioural
    # assertion here passes whether or not the item was ever freed.
    assert item.id not in tw._LIVE_TIMERS, (
        "the item was never released, so the entry lingers until a collection"
    )
    second = TimerWindow.open_for(root, manager, item, rng=random.Random(1))
    assert second is not first
    second.destroy()


def test_b24_a_destroyed_window_is_not_handed_back(root, manager, hushed):
    """B2.3 — a window destroyed without going through cleanup, too.

    The registry is weak so it clears eventually, but "eventually" means after
    a collection, and pressing Timer again straight away is the common case.
    """
    item = _item(manager)
    first = TimerWindow.open_for(root, manager, item, rng=random.Random(1))
    first.destroy()          # not _cleanup_and_destroy

    second = TimerWindow.open_for(root, manager, item, rng=random.Random(1))
    assert second is not first
    assert second.winfo_exists()
    second.destroy()


def test_b25_every_screen_opens_through_the_registry():
    """B2.2 — four entry points, and a guard on one of them is not a guard.

    Parsed rather than grepped, and asserted as an exact set: a fifth opener
    added without going through open_for fails here rather than silently
    reintroducing the second window (P25, P29).
    """
    import ast
    import pathlib

    from src.getmoredone.screens import all_items, item_editor, today, upcoming

    direct, through = set(), set()
    for mod in (today, upcoming, all_items, item_editor):
        name = pathlib.Path(mod.__file__).name
        for node in ast.walk(ast.parse(pathlib.Path(mod.__file__).read_text())):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "TimerWindow":
                direct.add((name, node.lineno))
            elif (isinstance(fn, ast.Attribute) and fn.attr == "open_for"
                  and isinstance(fn.value, ast.Name)
                  and fn.value.id == "TimerWindow"):
                through.add(name)

    assert direct == set(), (
        f"these build a TimerWindow directly instead of going through "
        f"open_for, so they can open a second one on an item: {sorted(direct)}"
    )
    assert through == {"today.py", "upcoming.py", "all_items.py", "item_editor.py"}, (
        f"the set of timer entry points changed: {sorted(through)}"
    )


# --- csdp sweep findings ----------------------------------------------------

def test_f11_a_timer_that_did_not_close_keeps_its_claim_on_the_item(
        root, manager, hushed, monkeypatch):
    """F1 — releasing before the destroy undid B2 on B3's own path.

    The entry was dropped four lines before destroy() was even attempted and
    never put back, so a window still on screen left its item free and the next
    Timer press built a second one at the same coordinates. Both fixes shipped
    in one batch and one defeated the other on the single path where both are
    live.
    """
    item = _item(manager)
    stuck = TimerWindow.open_for(root, manager, item, rng=random.Random(1))
    monkeypatch.setattr(TimerWindow, "destroy",
                        lambda self: (_ for _ in ()).throw(RuntimeError("nope")))

    assert stuck._cleanup_and_destroy() is False

    assert tw._LIVE_TIMERS.get(item.id) is stuck, (
        "the registry released an item whose timer is still on screen"
    )
    monkeypatch.undo()

    again = TimerWindow.open_for(root, manager, item, rng=random.Random(1))
    assert again is stuck, (
        "a second timer was opened on an item that already has one on screen"
    )
    stuck.destroy()


def test_f21_reusing_a_timer_keeps_the_new_openers_callback(root, manager,
                                                            hushed):
    """F2 — open_for returned the live window and dropped everything passed.

    The editor's on_close is what reloads its fields when the timer closes.
    Dropped, the editor keeps stale values and saving from it overwrites what
    the timer just wrote — the clobber _current_timer_field_values exists to
    prevent.
    """
    item = _item(manager)
    first, second = [], []

    live = TimerWindow.open_for(root, manager, item, rng=random.Random(1),
                                on_close=lambda: first.append(1))
    again = TimerWindow.open_for(root, manager, item, rng=random.Random(1),
                                 on_close=lambda: second.append(1))
    assert again is live, "precondition: the window was reused"

    # _close_and_return, not _cleanup_and_destroy: the callback is invoked by
    # the shared ending helper, not by the teardown underneath it.
    live._close_and_return()

    assert first == [1], "the original opener stopped being told"
    assert second == [1], (
        "the second opener's callback was dropped, so whatever it refreshes "
        "never hears that the timer closed"
    )


def test_f22_reusing_a_timer_refreshes_the_item(root, manager, hushed):
    """F2 — the live window held the item as it was when it first opened.

    Both openers save before opening the timer, so the row is current and the
    live window's copy is the stale one.

    What this asserts is the data object, and only that. The clock is NOT
    re-read: time_block_minutes and work_seconds_remaining are set in __init__
    and a reuse leaves them on the old duration. That gap is real and recorded
    in BACKLOG.md rather than claimed here — the earlier version of this
    docstring said the window "acted on" the stale item, which was more than
    the assertion below shows.
    """
    item = _item(manager)
    live = TimerWindow.open_for(root, manager, item, rng=random.Random(1))

    stored = manager.get_action_item(item.id)
    stored.title = "A task, renamed in the editor"
    stored.planned_minutes = 90
    manager.update_action_item(stored)

    again = TimerWindow.open_for(root, manager, stored, rng=random.Random(1))

    assert again.item.title == "A task, renamed in the editor", (
        "the reused timer is still holding the item as it was when it opened"
    )
    assert again.item.planned_minutes == 90
    live.destroy()


def test_f31_a_timer_that_cannot_be_raised_is_replaced_not_kept(
        root, manager, hushed, monkeypatch):
    """F3 — an unguarded raise turned one TclError into a dead button forever.

    The entry survived the failure, so every later press took the same failing
    path for the life of the process, with no way back (P1).
    """
    item = _item(manager)
    live = TimerWindow.open_for(root, manager, item, rng=random.Random(1))
    monkeypatch.setattr(type(live), "lift",
                        lambda self: (_ for _ in ()).throw(tk.TclError("boom")))

    replacement = TimerWindow.open_for(root, manager, item, rng=random.Random(1))

    assert replacement is not live, (
        "the timer that could not be raised was handed back again, so the "
        "button is dead for the rest of the session"
    )
    monkeypatch.undo()
    live.destroy()
    replacement.destroy()


def test_f51_a_follow_up_that_cannot_be_created_does_not_lose_the_session(
        root, manager, hushed, monkeypatch):
    """F5 — the inheritance ran before the work log and after an unchecked insert.

    Three DB writes, one of which re-files a week-attached item, sat ahead of
    the only record here that cannot be recreated. A raise in any of them lost
    the log for work the user had just finished.
    """
    from src.getmoredone.screens import item_editor as ie
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    inherited = []
    monkeypatch.setattr(type(manager), "inherit_derived_item_context",
                        lambda self, s, n: (inherited.append((s, n)),
                                            (_ for _ in ()).throw(
                                                RuntimeError("boom")))[0])

    item = _item(manager)
    _continue_from(root, manager, item)

    assert inherited, "precondition: the inheritance was attempted"
    assert len(manager.get_work_logs(item.id)) == 1, (
        "a failure in the inheritance lost the work log for a finished session"
    )


def test_g11_reusing_a_timer_does_not_revert_the_editors_notes(root, manager,
                                                               hushed):
    """Sweep finding 1 — the fix for one clobber installed its mirror image.

    The notes box is filled once at __init__. Refreshing self.item without it
    left _save_notes_to_item comparing a fresh description against a stale box,
    so every ending wrote the old text back over what the editor had just
    saved. With both stale they had matched and nothing was written.
    """
    item = _item(manager, description="the original note")
    live = TimerWindow.open_for(root, manager, item, rng=random.Random(1))

    stored = manager.get_action_item(item.id)
    stored.description = "what the editor saved while the timer was open"
    manager.update_action_item(stored)

    TimerWindow.open_for(root, manager, stored, rng=random.Random(1))
    live._save_notes_to_item()

    assert manager.get_action_item(item.id).description == (
        "what the editor saved while the timer was open"), (
        "the ending wrote the timer's stale notes back over the editor's save"
    )
    live.destroy()


def test_g12_a_note_typed_into_the_timer_survives_a_reuse(root, manager, hushed):
    """Sweep finding 1 — and the refresh must not throw away unsaved work.

    Without this, "always refresh the box" passes the test above while
    discarding whatever the user had typed into the timer and not yet saved.
    """
    item = _item(manager, description="the original note")
    live = TimerWindow.open_for(root, manager, item, rng=random.Random(1))

    live.next_steps_text.delete("1.0", "end")
    live.next_steps_text.insert("1.0", "what I typed into the timer")

    stored = manager.get_action_item(item.id)
    stored.description = "what the editor saved"
    manager.update_action_item(stored)
    TimerWindow.open_for(root, manager, stored, rng=random.Random(1))

    assert live.next_steps_text.get("1.0", "end-1c").strip() == (
        "what I typed into the timer"), (
        "the reuse discarded a note the user had typed and not yet saved"
    )
    live.destroy()


def test_g13_the_pop_out_notes_window_keeps_pointing_at_the_same_item(
        root, manager, hushed):
    """Sweep finding 4 — NextActionWindow writes through self.item by reference.

    Rebinding self.item on a reuse left the pop-out holding the old object, so
    saving from it wrote a whole stale row back — title, dates, deliverable,
    not just the note. The fields are copied into the existing object instead.
    """
    item = _item(manager)
    live = TimerWindow.open_for(root, manager, item, rng=random.Random(1))
    aliased = live.item                      # what the pop-out would hold

    stored = manager.get_action_item(item.id)
    stored.title = "renamed in the editor"
    manager.update_action_item(stored)
    TimerWindow.open_for(root, manager, stored, rng=random.Random(1))

    assert live.item is aliased, (
        "self.item was rebound, so anything holding the old object writes a "
        "stale row through it"
    )
    assert aliased.title == "renamed in the editor", (
        "the alias was preserved but never refreshed"
    )
    live.destroy()


def test_g14_the_callback_chain_does_not_grow_on_every_reopen(root, manager,
                                                              hushed):
    """Sweep finding 2 — `is` never matches a bound method.

    All four openers pass one, and attribute access builds a fresh bound-method
    object each time, so the dedupe was inert: five presses ran that screen's
    refresh five times on close.
    """
    item = _item(manager)
    calls = []

    class Screen:
        def refresh(self):
            calls.append(1)

    screen = Screen()
    live = TimerWindow.open_for(root, manager, item, rng=random.Random(1),
                                on_close=screen.refresh)
    for _ in range(4):
        TimerWindow.open_for(root, manager, item, rng=random.Random(1),
                             on_close=screen.refresh)

    live._close_and_return()

    assert calls == [1], (
        f"the opener's refresh ran {len(calls)} times for one close; the "
        "chain grows on every re-open"
    )


def test_g15_a_failing_refresh_does_not_swallow_the_ending(root, manager,
                                                           hushed):
    """Sweep finding 5 — the guard existed on the adopted path only.

    Unguarded, a list refresh that raises skipped _cleanup_and_destroy, left
    the window on screen, and reported "Failed to save the session" for one
    that had already been written.
    """
    def explode():
        raise RuntimeError("the list could not be rebuilt")

    item = _item(manager)
    timer = TimerWindow(root, manager, item, rng=random.Random(1),
                        on_close=explode)

    timer._close_and_return()

    assert not timer.winfo_exists(), (
        "a failing opener refresh stopped the timer from closing"
    )
