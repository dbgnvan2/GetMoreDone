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


def test_t14_two_timers_on_one_item_are_not_yet_prevented(
        root, manager, hushed):
    """T1.4 — nothing stops a second timer window opening on the same item.

    Every entry point constructs a TimerWindow unconditionally, and setup_window
    positions all of them at the same saved timer_window_x/y — so a second one
    lands exactly on top of the first and the two are indistinguishable.

    This reproduces the 2026-08-25 database state exactly: a work log at
    08:02:00 from one window, then a completion and a follow-up at 08:07:03
    from the other with no work log at all.

    NOTE FOR WHOEVER SEES THIS GO RED: that is good news, not a regression.
    It pins a defect recorded in BACKLOG.md as deliberately unfixed. When the
    second window is prevented, delete this test rather than repairing it.
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
        "CompletionNoteDialog", "NextStepsDialog", "DeliverableDialog", "SavorDialog",
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
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in SHOW)

    all_sites, guarded, unparented = set(), set(), set()
    for mod in (twin, dlg):
        name = pathlib.Path(mod.__file__).name
        tree = ast.parse(pathlib.Path(mod.__file__).read_text())
        for node in ast.walk(tree):
            if _is_show(node):
                # Identified by (file, line): one re-parse produces different
                # node objects, so identity cannot be used across two walks.
                all_sites.add((name, node.lineno))
                if not any(k.arg == "parent" for k in node.keywords):
                    unparented.add((name, node.lineno))
            if isinstance(node, ast.With):
                names = {n.func.id for n in ast.walk(node)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
                if "parent_topmost_suspended" in names:
                    guarded |= {(name, i.lineno) for i in ast.walk(node) if _is_show(i)}

    assert len(all_sites) == 4, (
        f"the set of messagebox calls changed: {sorted(all_sites)}. A new one "
        "must be wrapped in parent_topmost_suspended and counted here."
    )
    assert all_sites - guarded == set(), (
        "these messagebox calls open behind the always-on-top timer holding a "
        f"grab: {sorted(all_sites - guarded)}"
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


def test_t31_the_next_steps_dialog_is_gone(root, manager, hushed,
                                           monkeypatch):
    """T3.1 — the ending builds no NextStepsDialog.

    Asserted by intercepting the class, not by reading the source: the import
    could be removed while a call survived under another name, and a source
    grep would call that clean.
    """
    from src.getmoredone.screens import item_editor as ie
    from src.getmoredone.screens import timer_window_dialogs as dlg
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    built = []

    def caught(*a, **k):
        built.append(a)
        raise AssertionError("the ending still opens a Next Steps dialog")

    # Both modules. The original defect resolved the name through
    # timer_window's OWN globals (a module-level import, called bare), so
    # rebinding it on timer_window_dialogs alone intercepts nothing and the
    # assertion below is true by construction. This test was green against a
    # verbatim restoration of the defect until the csdp sweep proved it.
    # raising=False because timer_window no longer has the attribute at all —
    # which is the point, and is why it has to be created to be watched.
    monkeypatch.setattr(tw, "NextStepsDialog", caught, raising=False)
    monkeypatch.setattr(dlg, "NextStepsDialog", caught)

    item = _item(manager)
    _continue_from(root, manager, item)
    assert built == []


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


def test_t71_the_followup_is_marked_in_its_title(root, manager, hushed,
                                                 monkeypatch):
    """T7.1 — the follow-up is recognisable as one in any list."""
    from src.getmoredone.screens import item_editor as ie
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    item = _item(manager)
    _continue_from(root, manager, item)

    assert _child_of(manager, item).title == "A task - Followup"


def test_t72_a_followup_of_a_followup_is_not_marked_twice(root, manager, hushed,
                                                          monkeypatch):
    """T7.2 — Continue is for work that runs over days, so it repeats.

    Unconditional appending gives "A task - Followup - Followup - Followup" by
    the third day.
    """
    from src.getmoredone.screens import item_editor as ie
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: None)

    item = _item(manager)
    _continue_from(root, manager, item)
    day_two = _child_of(manager, item)

    _continue_from(root, manager, day_two)

    # The second follow-up is a *sibling* of the first, not its child: an item
    # that already has a parent gives the new one the same parent.
    titles = sorted(c.title for c in manager.get_children(item.id))
    assert titles == ["A task - Followup", "A task - Followup"], (
        f"the suffix stacked on a follow-up of a follow-up: {titles}"
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
