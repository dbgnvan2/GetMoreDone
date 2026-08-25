"""The reward protocol as the timer actually runs it.

Purpose: RP-4 / RP-6 — prove the deliverable is captured before the clock
         starts, that break end no longer completes anything, that "Done" runs
         savor then celebration then persistence, and that the phase changes
         where the spec says it does.
Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#4-ux-flow-hook-points-into-screenstimer_windowpy
Tests:   this file

Real TimerWindow instances on a real DatabaseManager, because the thing worth
proving is that a control reaches the database — which a stub of the window
cannot show. The windows are withdrawn by conftest, so nothing appears on
screen; what is stubbed is only the modal dialogs, since wait_window on a
window nothing will ever destroy does not return.
"""

from __future__ import annotations

import pathlib
import random
from datetime import datetime
from types import SimpleNamespace

import customtkinter as ctk
import pytest

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem, ProjectBoard
from src.getmoredone.reward_protocol import WIRING_THRESHOLD
from src.getmoredone.screens import timer_window as tw
from src.getmoredone.screens import timer_window_dialogs as dialogs
from src.getmoredone.screens import timer_window_reward as twr
from src.getmoredone.screens.timer_window import TimerWindow

DELIVERABLE = "Draft section 2's opening paragraph"

# Every state the timer can be in. Written out rather than derived from the
# implementation, so a state added without a visibility decision fails here.
ALL_TIMER_STATES = ("stopped", "running", "paused", "in_break", "awaiting_choice")

# The modules TimerWindow is composed from. One literal, used by both the state
# scan and the test that pins the family — written twice, changing the scan's
# pattern left the test that exists to catch that green.
TIMER_WINDOW_GLOB = "timer_window*.py"


def _timer_window_modules():
    return sorted(pathlib.Path(tw.__file__).parent.glob(TIMER_WINDOW_GLOB))


class FakeDeliverableDialog:
    """Stands in for the modal. ``result`` is whatever the test wants back."""

    next_result: str | None = DELIVERABLE
    calls: list = []

    def __init__(self, parent, **kwargs):
        FakeDeliverableDialog.calls.append(kwargs)
        self.result = FakeDeliverableDialog.next_result


class FakeSavorDialog:
    shown: list = []

    def __init__(self, parent, snapshot):
        FakeSavorDialog.shown.append(snapshot)
        self.acknowledged = True


class FakeCompletionNoteDialog:
    next_result: str | None = None

    def __init__(self, parent, title):
        self.result = FakeCompletionNoteDialog.next_result


@pytest.fixture
def root():
    win = ctk.CTk()
    win.withdraw()
    yield win
    win.destroy()


@pytest.fixture
def manager(tmp_path):
    db = DatabaseManager(str(tmp_path / "reward.db"))
    yield db
    db.close()


@pytest.fixture
def quiet(monkeypatch):
    """Silence the dialogs, the sound, and the window flash for a whole test."""
    FakeDeliverableDialog.calls = []
    FakeDeliverableDialog.next_result = DELIVERABLE
    FakeSavorDialog.shown = []
    FakeCompletionNoteDialog.next_result = None

    monkeypatch.setattr(twr, "DeliverableDialog", FakeDeliverableDialog)
    monkeypatch.setattr(twr, "SavorDialog", FakeSavorDialog)
    monkeypatch.setattr(tw, "CompletionNoteDialog", FakeCompletionNoteDialog)
    monkeypatch.setattr(TimerWindow, "wait_window", lambda self, window=None: None)
    monkeypatch.setattr(TimerWindow, "_start_music", lambda self: False)
    monkeypatch.setattr(TimerWindow, "_stop_music", lambda self: None)
    monkeypatch.setattr(TimerWindow, "play_sound", lambda self, is_break_start: None)
    monkeypatch.setattr(TimerWindow, "_flash_window", lambda self: None)
    yield


def _item(manager, **kwargs):
    item = ActionItem(who="Self", title="A task", planned_minutes=30, **kwargs)
    manager.create_action_item(item)
    return item


def _linked(manager, savor_count=0, **kwargs):
    """An item filed under a project, with the board at a chosen phase."""
    item = _item(manager, **kwargs)
    board = ProjectBoard(title="Website Rebuild")
    manager.create_project_board(board)
    manager.link_action_item_to_project_board(board.id, item.id)
    for _ in range(savor_count):
        manager.increment_project_savor_count(board.id)
    return item, board


def _timer(root, manager, item, seed=1):
    return TimerWindow(root, manager, item, rng=random.Random(seed))


def _complete_once(timer, note=None):
    """One deliverable, start to persisted, without destroying the window.

    Mirrors done_action's own two lines rather than calling it, because
    done_action ends in finished_action, which closes the window — and a phase
    transition needs fifteen completions in a row.
    """
    assert timer.prepare_reward_session() is True
    timer.start_timestamp = datetime.now()
    timer.work_seconds_elapsed = 25 * 60
    timer._done_pressed = True
    timer._pending_reward = timer.run_reward_sequence()
    timer.save_work_log(note)


def _is_visible(widget) -> bool:
    """grid_remove leaves the widget configured but not mapped."""
    return bool(widget.grid_info())


def _assert_fresh_work_block(timer):
    """A full work block, allowing for the one second the first tick consumes.

    begin_new_focus_cycle resets the countdown and then calls tick(), which
    decrements it immediately — so the value is either the full block or one
    second under it, and never anything else. Both are written out rather than
    asserted as a floor, so a reset that only half-restored the block fails.
    """
    full = timer.work_minutes * 60
    assert timer.work_seconds_remaining in (full, full - 1), (
        f"work_seconds_remaining is {timer.work_seconds_remaining}, expected a "
        f"fresh block of {full}"
    )


# --- RP-4.2 : the deliverable is captured before the clock starts ------------

def test_rp42_linked_start_captures_the_session_deliverable(root, manager, quiet):
    """RP-4.2 — board, phase and snapshot are on the session after Start."""
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        assert timer.prepare_reward_session() is True
        assert timer.session_deliverable == DELIVERABLE
        assert timer.session_board_id == board.id
        assert timer.session_phase == "wiring"
        # And it was persisted onto the item, not just held in memory.
        assert manager.get_action_item(item.id).deliverable == DELIVERABLE
    finally:
        timer.destroy()


def test_rp42_an_item_that_has_a_deliverable_is_not_asked_again(root, manager, quiet):
    """No dialog when there is nothing to ask — the answer is on the window."""
    item, _board = _linked(manager, deliverable="Existing deliverable")
    timer = _timer(root, manager, item)
    try:
        timer.prepare_reward_session()

        assert FakeDeliverableDialog.calls == [], (
            "the user was asked to retype a deliverable the window already shows"
        )
        assert timer.session_deliverable == "Existing deliverable"
        assert timer.deliverable_label.cget("text") == "Existing deliverable"
    finally:
        timer.destroy()


def test_rp42_the_edit_prompt_is_prefilled_and_carries_the_project_context(root, manager, quiet):
    """When it does open, it opens with what is already there."""
    item, _board = _linked(manager, deliverable="Existing deliverable")
    timer = _timer(root, manager, item)
    try:
        timer.edit_deliverable()
        assert FakeDeliverableDialog.calls[0]["deliverable"] == "Existing deliverable"
        assert FakeDeliverableDialog.calls[0]["phase"] == "wiring"
        assert FakeDeliverableDialog.calls[0]["savor_count"] == 0
    finally:
        timer.destroy()


def test_rp42b_cancelling_the_deliverable_dialog_does_not_start_the_timer(root, manager, quiet):
    """RP-4.2b — Cancel means do not start, not start without one."""
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        FakeDeliverableDialog.next_result = None
        timer.start_timer()

        assert timer.timer_state == "stopped"
        assert timer.start_timestamp is None
        assert timer.update_timer_id is None, "a cancelled start still scheduled a tick"
        assert not _is_visible(timer.done_button), "Done is offered for a session that never began"
        assert timer.session_board_id is None
    finally:
        timer.destroy()


def test_rp42b_cancelling_does_not_save_an_edited_time_block(root, manager, quiet):
    """Cancel leaves the item exactly as it was, including planned_minutes.

    The deliverable check runs before the time-block edit is written, so a
    cancelled start cannot leave the item half-updated.
    """
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.time_block_value.delete(0, "end")
        timer.time_block_value.insert(0, "55")
        FakeDeliverableDialog.next_result = None
        timer.start_timer()

        assert manager.get_action_item(item.id).planned_minutes == 30
    finally:
        timer.destroy()


def test_rp42c_unlinked_item_starts_with_no_reward_protocol(root, manager, quiet):
    """RP-4.2c — no project means no phase, no savor and no counter.

    It no longer means no deliverable. Naming what you are about to do is the
    point of starting a timer; the *reward* is what stays project-only.
    """
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        timer.start_timer()

        assert timer.session_board_id is None, "an unlinked item claimed a project"
        assert timer.session_phase is None
        assert timer.session_deliverable == DELIVERABLE
        assert timer.timer_state == "running"
    finally:
        timer._cancel_pending_timer()
        timer.destroy()


# --- RP-4.3 : break end is neutral ------------------------------------------

def _run_to_break_end(timer):
    """Drive the real tick loop to the moment the break runs out."""
    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_remaining = 1
    timer.tick()                    # work hits zero -> in_break
    assert timer.timer_state == "in_break"
    # The handle the in_break tick just scheduled is left in place on purpose:
    # cancelling it here would make "enter_break_choice cancels the tick" true
    # whether or not it does. Nothing fires it — no mainloop runs in the suite.
    timer.break_seconds_remaining = 1
    timer.tick()                    # break hits zero
    # Deliberately NOT cancelled here: enter_break_choice is supposed to do it,
    # and cancelling by hand first makes any assertion about a pending tick
    # true whatever the code does.


def test_rp43_break_end_does_not_auto_stop(root, manager, quiet):
    """RP-4.3 — the ring offers a choice; it does not complete anything."""
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        _run_to_break_end(timer)

        assert timer.timer_state == TimerWindow.AWAITING_CHOICE, (
            f"break end left the timer {timer.timer_state!r}; it must not stop"
        )
        assert _is_visible(timer.break_choice_frame), "the rest/continue choice was not offered"
        assert not _is_visible(timer.completion_frame), (
            "the completion flow opened on the timer ringing — the reward must "
            "never fire on elapsed time"
        )
        assert _is_visible(timer.done_button), "Done is still the way to complete"
        assert timer.update_timer_id is None, (
            "the clock is still scheduled while the timer waits for a choice; the "
            "next tick would re-fire the break-over branch"
        )
        # Disabled, not removed: the rest/continue pair owns the choice while it
        # is open, and offering the same action twice under two names is how a
        # user ends up in a state neither button was written for. The control
        # itself stays, as the UI-regression policy requires.
        assert timer.pause_button.cget("state") == "disabled"
        assert timer.stop_button.cget("state") == "normal", "Stop must still work"
    finally:
        timer.destroy()


def test_rp43a_continue_focus_starts_a_fresh_cycle(root, manager, quiet):
    """RP-4.3a — another block, both countdowns reset, no completion in between."""
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        _run_to_break_end(timer)
        timer.continue_focus_action()
        timer._cancel_pending_timer()

        assert timer.timer_state == "running"
        _assert_fresh_work_block(timer)
        assert timer.break_seconds_remaining == timer.break_minutes * 60
        assert not _is_visible(timer.break_choice_frame)
        assert not _is_visible(timer.completion_frame)
        assert timer.pause_button.cget("state") == "normal", (
            "Pause was left disabled after the choice closed"
        )
        assert timer.pause_button.cget("text") == "⏸  Pause"
    finally:
        timer.destroy()


def test_rp43b_resume_after_rest_does_not_re_enter_a_zero_second_break(root, manager, quiet):
    """RP-4.3b — the loop the old resume rule would have caused.

    At break end both countdowns are zero. "running if work_seconds_remaining
    > 0 else in_break" calls that in_break, and a zero-second break re-fires
    the break-over branch on the next tick, and the next, forever.
    """
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        _run_to_break_end(timer)
        timer.rest_action()
        assert timer.timer_state == "paused"
        assert not _is_visible(timer.break_choice_frame)
        assert timer.pause_button.cget("state") == "normal", (
            "resting left no way to start working again"
        )
        assert timer.pause_button.cget("text") == "▶  Resume"

        timer.pause_timer()             # Resume
        timer._cancel_pending_timer()

        assert timer.timer_state == "running", (
            f"resuming after a rest left the timer {timer.timer_state!r}"
        )
        assert timer.break_seconds_remaining == timer.break_minutes * 60, (
            "resumed into a zero-second break; the next tick would fire break-over again"
        )
        _assert_fresh_work_block(timer)
    finally:
        timer.destroy()


def test_rp43c_stop_and_completion_frame_survive_the_break_change(root, manager, quiet):
    """RP-4.3c — the UI-regression guardrail the spec asks for.

    Stop and Finished/Continue are existing controls. Only the auto-trigger on
    break end changed; pressing Stop must still behave exactly as it did.
    """
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        timer.start_timer()
        timer._cancel_pending_timer()
        assert timer.stop_button.cget("state") == "normal"

        timer.stop_timer()

        assert timer.timer_state == "stopped"
        assert _is_visible(timer.completion_frame), "Stop no longer offers the session actions"
        # Renamed for what they do. "Finished" completed the action item and
        # closed, which from the user's side looked like the button doing
        # nothing: the window went away and the item left Today.
        assert timer.finished_button.cget("text") == "Save Related - Close Timer"
        assert timer.cancel_button.cget("text") == "Cancel Timer"
        assert timer.continue_button.cget("text") == "Complete & Create Follow Up"
        assert timer.start_button.cget("state") == "normal"
        assert not _is_visible(timer.break_choice_frame)
    finally:
        timer.destroy()


# --- RP-4.4 : the Done button -----------------------------------------------

def test_rp44_done_button_visibility_across_every_timer_state(root, manager, quiet):
    """RP-4.4 — visible in every state except stopped, checked in all five."""
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        for state in ALL_TIMER_STATES:
            timer.timer_state = state
            timer._sync_done_button()
            expected = state != "stopped"
            assert _is_visible(timer.done_button) is expected, (
                f"Done button visibility is wrong in state {state!r}: "
                f"expected {'visible' if expected else 'hidden'}"
            )
    finally:
        timer.destroy()


def test_rp44a_done_on_unlinked_item_skips_the_reward_protocol(root, manager, quiet):
    """RP-4.4a — no savor, no celebration, no counter; the ordinary flow runs."""
    item = _item(manager)
    timer = _timer(root, manager, item)
    fired = []
    timer.fire_celebration = lambda kind: fired.append(kind)
    try:
        _complete_once(timer)

        assert FakeSavorDialog.shown == []
        assert fired == []
        log = manager.get_work_logs(item.id)[0]
        assert log.phase is None
        assert log.savor_delivered is False
        assert log.celebration_type is None
        # It has a snapshot now — every session names what it is for — but none
        # of the reward columns, because there is no project to count towards.
        assert log.deliverable_snapshot == DELIVERABLE
        # The user still said it was done, and that is what the column records.
        assert log.deliverable_completed is True
    finally:
        timer.destroy()


# --- RP-4.5 : the reward sequence -------------------------------------------

def test_rp45_savor_precedes_celebration(root, manager, quiet):
    """RP-4.5 — order matters: the surprise lands on top of the savor."""
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    order = []
    try:
        timer.fire_celebration = lambda kind: order.append(("celebration", kind))

        class Recording(FakeSavorDialog):
            def __init__(self, parent, snapshot):
                order.append(("savor", snapshot))
                super().__init__(parent, snapshot)

        # Seeds are cheap; find one that produces both channels so the ordering
        # is actually observable rather than vacuously true.
        for seed in range(200):
            order.clear()
            timer.reward_rng = random.Random(seed)
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(twr, "SavorDialog", Recording)
                timer.prepare_reward_session()
                decision = timer.run_reward_sequence()
            if decision.show_savor and decision.celebration:
                break
        else:
            pytest.fail("no seed in 200 produced both a savor and a celebration")

        assert [kind for kind, _ in order] == ["savor", "celebration"], (
            f"the celebration did not follow the savor: {order}"
        )
    finally:
        timer.destroy()


def test_rp45a_celebration_never_substitutes_for_savor(root, manager, quiet):
    """RP-4.5a — in Phase 1 every completion savors, celebration or not."""
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    celebrated = []
    try:
        timer.fire_celebration = lambda kind: celebrated.append(kind)
        for seed in range(60):
            timer.reward_rng = random.Random(seed)
            timer.prepare_reward_session()
            decision = timer.run_reward_sequence()
            assert decision.show_savor, (
                f"seed {seed}: a Phase 1 completion did not savor"
            )
        assert celebrated, "no celebration fired in 60 draws; the test proves nothing"
        assert len(celebrated) < 60, "a celebration fired every time"
    finally:
        timer.destroy()


def test_rp45b_done_writes_every_reward_column(root, manager, quiet):
    """RP-4.5b — the work_logs row carries the whole audit trail."""
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        _complete_once(timer, note="a completion note")

        log = manager.get_work_logs(item.id)[0]
        assert log.deliverable_snapshot == DELIVERABLE
        assert log.deliverable_completed is True
        assert log.savor_delivered is True          # Phase 1 always savors
        assert log.phase == "wiring"
        assert log.note == "a completion note"
        assert log.celebration_type in (None, "confetti", "balloon", "tada")
        assert manager.get_project_board(board.id).savor_count == 1
    finally:
        timer.destroy()


def test_rp45c_counter_advances_even_when_savor_is_not_shown(root, manager, quiet):
    """RP-4.5c — the prompt is phase-gated; the counter never is."""
    item, board = _linked(manager, savor_count=WIRING_THRESHOLD)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        # A seed whose Phase 2 draw skips the savor, so the two are separable.
        for seed in range(200):
            timer.reward_rng = random.Random(seed)
            timer.prepare_reward_session()
            decision = timer.run_reward_sequence()
            if not decision.show_savor:
                break
        else:
            pytest.fail("no seed in 200 produced a Phase 2 completion without a savor")

        before = manager.get_project_board(board.id).savor_count
        timer.start_timestamp = datetime.now()
        timer._done_pressed = True
        timer._pending_reward = decision
        timer.save_work_log()

        after = manager.get_project_board(board.id).savor_count
        assert after == before + 1, "the counter stalled on a completion that did not savor"
        assert manager.get_work_logs(item.id)[-1].savor_delivered is False
    finally:
        timer.destroy()


def test_rp45d_counter_never_advances_without_a_work_log(root, manager, quiet):
    """RP-4.5d — the two writes happen together or not at all.

    Spec §4.5 advances the counter before saving. Done that way, a session that
    cannot be logged still counts, and nothing afterwards can tell.
    """
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        timer.prepare_reward_session()
        timer._done_pressed = True
        timer._pending_reward = timer.run_reward_sequence()

        timer.start_timestamp = None    # nothing to log
        timer.save_work_log()

        assert manager.get_work_logs(item.id) == []
        assert manager.get_project_board(board.id).savor_count == 0, (
            "a completion was counted although no work log was written"
        )
    finally:
        timer.destroy()


def test_rp45d_a_second_save_does_not_count_the_same_completion_twice(root, manager, quiet):
    """The decision is consumed, so a repeated save cannot double-count."""
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        _complete_once(timer)
        assert manager.get_project_board(board.id).savor_count == 1

        timer.save_work_log()   # e.g. a second call down an error path
        assert manager.get_project_board(board.id).savor_count == 1, (
            "saving twice counted one completion twice"
        )
    finally:
        timer.destroy()


def test_rp45g_snapshot_survives_a_later_edit_of_the_deliverable(root, manager, quiet):
    """RP-4.5g — the log records what this session was for, not what it is now."""
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        assert timer.prepare_reward_session() is True

        # The user edits the item elsewhere while the timer runs. Both the
        # stored row and the timer's own copy of it move, because a test that
        # only moves the row passes even when the snapshot is read from
        # self.item at save time — checked by mutation, and it did.
        fresh = manager.get_action_item(item.id)
        fresh.deliverable = "Something else entirely"
        manager.update_action_item(fresh)
        timer.item.deliverable = "Something else entirely"

        timer.start_timestamp = datetime.now()
        timer._done_pressed = True
        timer._pending_reward = timer.run_reward_sequence()
        timer.save_work_log()

        assert manager.get_work_logs(item.id)[0].deliverable_snapshot == DELIVERABLE
    finally:
        timer.destroy()


def test_rp45_a_deleted_project_completes_without_the_protocol(root, manager, quiet):
    """A project deleted mid-session must not lose the completion."""
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        assert timer.prepare_reward_session() is True
        manager.delete_project_board(board.id)

        timer.start_timestamp = datetime.now()
        timer._done_pressed = True
        timer._pending_reward = timer.run_reward_sequence()
        timer.save_work_log()

        assert timer._pending_reward is None
        log = manager.get_work_logs(item.id)[0]
        assert log.deliverable_completed is True, "the session was still completed"
        assert log.phase is None
    finally:
        timer.destroy()


# --- the whole Done path, once, end to end ----------------------------------

def test_rp44_done_runs_the_reward_sequence_and_then_the_completion_flow(root, manager, quiet):
    """done_action: savor, celebration, work log, counter, item completed, closed."""
    item, board = _linked(manager)
    closed = []
    timer = TimerWindow(root, manager, item, on_close=lambda: closed.append(True),
                        rng=random.Random(1))
    fired = []
    timer.fire_celebration = lambda kind: fired.append(kind)

    timer.start_timer()
    timer.work_seconds_elapsed = 25 * 60

    # No _cancel_pending_timer() here on purpose. It used to sit on this line,
    # which is exactly what production was missing: done_action left the clock
    # running under the modal dialogs. The test was doing the fix's job.
    timer.done_action()

    assert FakeSavorDialog.shown == [DELIVERABLE], "Phase 1 must savor every completion"
    assert manager.get_action_item(item.id).status == "completed"
    assert manager.get_project_board(board.id).savor_count == 1
    log = manager.get_work_logs(item.id)[0]
    assert log.deliverable_completed is True
    assert log.phase == "wiring"
    assert closed == [True]


# --- RP-6 : the phase transition --------------------------------------------

def test_rp61_fifteen_completions_all_savor(root, manager, quiet):
    """RP-6.1 — Phase 1 is continuous reinforcement, all the way to the threshold."""
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        for _ in range(WIRING_THRESHOLD):
            _complete_once(timer)

        logs = manager.get_work_logs(item.id)
        assert len(logs) == WIRING_THRESHOLD
        assert all(log.savor_delivered for log in logs), (
            "a Phase 1 completion skipped the savor step"
        )
        # Reconciled against the dialogs that were really constructed. Asserting
        # the column alone passes when the step is never shown, because the
        # column would just be repeating the decision back — checked by
        # mutation, and it did.
        assert FakeSavorDialog.shown == [DELIVERABLE] * WIRING_THRESHOLD, (
            f"{len(FakeSavorDialog.shown)} savor dialogs were shown for "
            f"{WIRING_THRESHOLD} completions that all record savor_delivered"
        )
        assert all(log.phase == "wiring" for log in logs)
        assert manager.get_project_board(board.id).savor_count == WIRING_THRESHOLD
    finally:
        timer.destroy()


def test_rp62_sixteenth_completion_is_phase_two(root, manager, quiet):
    """RP-6.2 — the completion after the threshold is recorded as maintaining."""
    item, board = _linked(manager, savor_count=WIRING_THRESHOLD)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        _complete_once(timer)

        log = manager.get_work_logs(item.id)[0]
        assert log.phase == "maintaining", (
            f"completion {WIRING_THRESHOLD + 1} recorded phase {log.phase!r}"
        )
        assert manager.get_project_board(board.id).savor_count == WIRING_THRESHOLD + 1
    finally:
        timer.destroy()


def test_rp62_phase_two_savors_sometimes_and_not_always(root, manager, quiet):
    """The point of Phase 2: intermittent, so it stays informative."""
    item, board = _linked(manager, savor_count=WIRING_THRESHOLD)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        for _ in range(40):
            _complete_once(timer)

        savored = [log.savor_delivered for log in manager.get_work_logs(item.id)]
        assert any(savored), "Phase 2 never savored across 40 completions"
        assert not all(savored), "Phase 2 savored every completion; it is meant to be intermittent"
    finally:
        timer.destroy()


# --- the editor picks up what the timer wrote -------------------------------

def test_rp41_editor_picks_up_a_deliverable_written_by_the_timer(root, manager, quiet):
    """An editor open behind the timer must not wipe the deliverable on save.

    _current_timer_field_values decides which fields the editor reloads after
    the timer closes. Leave the deliverable out of it and the editor keeps
    showing its old empty box, and saving from there clears what the timer's
    start dialog just captured.
    """
    from src.getmoredone.screens.item_editor import ItemEditorDialog

    item, _board = _linked(manager)
    editor = ItemEditorDialog(root, manager, item.id)
    try:
        assert editor.deliverable_entry.get() == ""
        editor._pre_timer_field_values = editor._current_timer_field_values()

        timer = _timer(root, manager, item)
        timer.prepare_reward_session()
        timer.destroy()

        editor._reload_editable_notes()
        assert editor.deliverable_entry.get() == DELIVERABLE, (
            "the editor did not pick up the deliverable the timer wrote; saving "
            "from it would wipe it"
        )
    finally:
        editor.destroy()


def test_rp45f_the_timers_cleanup_cancels_a_running_celebration(root, manager, quiet, monkeypatch):
    """The mixin's teardown is reached from the timer's own cleanup.

    Asserting cancel_celebration() works says nothing about whether anything
    calls it. Removing the call from _cleanup_and_destroy left the mixin-level
    test green, which is the wrong layer to be checking — the completion flow
    destroys this window seconds after a celebration starts.
    """
    from src.getmoredone.screens import timer_window_celebration as celebration
    monkeypatch.setattr(celebration, "play_audio_file_async", lambda path: True)

    item = _item(manager)
    timer = _timer(root, manager, item)
    timer.fire_celebration("confetti")
    pending = timer._celebration_after_ids
    assert pending, "the celebration scheduled nothing to cancel"

    timer._cleanup_and_destroy()

    assert pending == set(), (
        "closing the timer left celebration frames scheduled against a window "
        "that no longer exists"
    )


def test_rp45_savor_delivered_records_the_dialog_not_the_decision(root, manager, quiet):
    """work_logs.savor_delivered means "the step was shown", per spec §2.2.

    Derived from decision.show_savor instead, it is a restatement of the
    decision and cannot disagree with it — so it could never reveal a savor
    that was decided on and then not shown.
    """
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        timer.prepare_reward_session()
        decision = timer.run_reward_sequence()
        assert decision.show_savor and timer._savor_shown is True

        # A decision that says savor, with the dialog suppressed: the flag must
        # follow the dialog.
        timer._savor_shown = False
        timer.start_timestamp = datetime.now()
        timer._done_pressed = True
        timer._pending_reward = decision
        timer.save_work_log()

        assert manager.get_work_logs(item.id)[0].savor_delivered is False
    finally:
        timer.destroy()


# --- the awaiting_choice exits, which nothing covered -----------------------

def test_rp43_stopping_at_the_break_choice_puts_the_buttons_away(root, manager, quiet):
    """awaiting_choice -> Stop. Neither reviewer's sequence, and no test's either.

    test_rp43c asserts the same thing after start -> stop, where the frame was
    never shown, so the assertion could not fail. Deleting the grid_remove in
    stop_timer left the whole file green.
    """
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        _run_to_break_end(timer)
        assert _is_visible(timer.break_choice_frame), "precondition: the choice is showing"

        timer.stop_timer()

        assert timer.timer_state == "stopped"
        assert not _is_visible(timer.break_choice_frame), (
            "Stop at the break choice left 'Pause (rest)' and 'Continue focus' on "
            "screen beside Finished/Continue"
        )
        assert _is_visible(timer.completion_frame)
    finally:
        timer.destroy()


def test_rp44_restarting_never_shows_done_beside_finished_and_continue(root, manager, quiet):
    """Start -> Stop -> Start. Three buttons that end the work, two of them wrong.

    Finished and Continue complete the session without the reward protocol:
    no savor, no celebration, no counter, deliverable_completed=0. Offered
    beside Done during a running session, a user reaching for the button they
    already know silently loses the feature.
    """
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.start_timer()
        timer._cancel_pending_timer()
        timer.stop_timer()
        assert _is_visible(timer.completion_frame), "precondition: Stop offers them"

        timer.start_timer()
        timer._cancel_pending_timer()

        assert _is_visible(timer.done_button)
        assert not _is_visible(timer.completion_frame), (
            "a restarted session shows Done, Finished and Continue at once"
        )
    finally:
        timer.destroy()


def test_rp43a_starting_after_a_finished_cycle_gives_a_whole_block(root, manager, quiet):
    """Both countdowns are zero after a full cycle; Start must not replay the ring.

    Without the reset, Start ran a zero-length block: the break alarm and the
    break-over alarm both fire within a second and the user is dumped straight
    back at the choice they just left.
    """
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        _run_to_break_end(timer)
        timer.stop_timer()
        assert (timer.work_seconds_remaining, timer.break_seconds_remaining) == (0, 0)

        timer.start_timer()
        timer._cancel_pending_timer()

        _assert_fresh_work_block(timer)
        assert timer.break_seconds_remaining == timer.break_minutes * 60
        assert timer.timer_state == "running"
        assert not _is_visible(timer.break_choice_frame), (
            "Start left the rest/continue buttons on screen during a running session"
        )
    finally:
        timer.destroy()


def test_rp43_closing_the_window_at_the_break_choice_is_treated_as_stop(root, manager, quiet):
    """on_window_close spelled its states out as a literal list and missed the new one."""
    item = _item(manager)
    timer = _timer(root, manager, item)
    _run_to_break_end(timer)
    assert timer.timer_state == TimerWindow.AWAITING_CHOICE

    stopped = []
    timer.stop_timer = lambda: stopped.append(True)
    timer._cleanup_and_destroy = lambda: None
    timer.save_window_settings = lambda: None

    timer.on_window_close()

    assert stopped == [True], (
        "closing at the break choice skipped stop_timer; on_window_close promises "
        "to treat a close as Stop"
    )
    timer.destroy()


def test_rp44_states_tuple_matches_what_the_code_assigns(root, manager, quiet):
    """TimerWindow.STATES must list every value the module assigns to timer_state.

    Three separate membership tests read this set. AWAITING_CHOICE was added to
    two of them and missed in the third, and nothing noticed. A hand-written
    tuple with a comment claiming it would catch that is not a guard — so this
    parses the modules and reconciles them, and asserts an exact set.
    """
    import ast

    # Every module the class is composed from, not just the two obvious ones.
    # A state assigned in timer_window_celebration.py or a future mixin would be
    # invisible to a hand-listed pair, and `assert assigned` would still pass on
    # the values the scanned modules happen to supply.
    modules = _timer_window_modules()
    assert modules, f"the {TIMER_WINDOW_GLOB} scan found nothing"

    assigned = set()
    for module in modules:
        tree = ast.parse(module.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            targets = [
                x for x in node.targets
                if isinstance(x, ast.Attribute) and x.attr == "timer_state"
            ]
            if not targets:
                continue
            for value in ast.walk(node.value):
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    assigned.add(value.value)
                elif isinstance(value, ast.Attribute) and value.attr.isupper():
                    resolved = getattr(TimerWindow, value.attr, None)
                    assert isinstance(resolved, str), (
                        f"timer_state is assigned TimerWindow.{value.attr}, which is "
                        f"not a string constant"
                    )
                    assigned.add(resolved)

    assert assigned, "found no assignments to timer_state — the scan is broken"
    assert assigned == set(TimerWindow.STATES), (
        f"TimerWindow.STATES is {sorted(TimerWindow.STATES)} but the code assigns "
        f"{sorted(assigned)}. Every membership test over the states reads STATES, so "
        "a value missing from it is a state some guard silently does not cover."
    )
    # ACTIVE_STATES is STATES[1:], which is only correct while STOPPED is first.
    assert TimerWindow.STATES[0] == TimerWindow.STOPPED
    assert set(TimerWindow.ACTIVE_STATES) == set(TimerWindow.STATES) - {TimerWindow.STOPPED}
    assert set(ALL_TIMER_STATES) == set(TimerWindow.STATES), (
        "this file's ALL_TIMER_STATES has drifted from the implementation"
    )


# --- done_action's guarantees ------------------------------------------------

def test_rp44_done_stops_the_clock_before_the_savor_dialog(root, manager, quiet):
    """The alarm must not go off while the savor prompt is asking for five seconds.

    Both dialogs are entered through wait_window, which pumps the Tk event loop,
    so a tick that is still scheduled keeps firing underneath them — the
    break-start sound over the savor moment, and _flash_window's focus_force
    pulling focus off the modal onto the window behind it.
    """
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    timer.fire_celebration = lambda kind: None

    timer.start_timer()
    assert timer.update_timer_id is not None, "precondition: a tick is scheduled"

    state_when_savor_opened = {}

    class Recording(FakeSavorDialog):
        def __init__(self, parent, snapshot):
            state_when_savor_opened["pending_tick"] = timer.update_timer_id
            state_when_savor_opened["state"] = timer.timer_state
            super().__init__(parent, snapshot)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(twr, "SavorDialog", Recording)
        timer.done_action()

    assert state_when_savor_opened["pending_tick"] is None, (
        "the clock was still ticking while the savor dialog was open"
    )
    # Not "stopped": halting for the completion flow deliberately does not dress
    # the window as a finished session (see the sibling test below). What matters
    # is that nothing is counting down, which is what the assertion above says.
    assert state_when_savor_opened["state"] != "running"


def test_rp45_a_failing_reward_sequence_still_records_the_session(root, manager, quiet):
    """The reward is decoration; it may never prevent the work being recorded.

    Unguarded, a TclError from a grab clash or a canvas built on a resizing
    window meant the user pressed Done, saw nothing, and lost the work log, the
    completion and the count together.
    """
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    timer.start_timer()
    timer.work_seconds_elapsed = 25 * 60

    def boom():
        raise RuntimeError("the celebration canvas exploded")

    timer.run_reward_sequence = boom
    timer.done_action()

    assert manager.get_action_item(item.id).status == "completed", (
        "a failure in the reward sequence lost the completion"
    )
    logs = manager.get_work_logs(item.id)
    assert len(logs) == 1, "the session was not recorded"
    assert logs[0].deliverable_completed is True
    # The protocol did not run, so nothing claims it did — and nothing counted.
    assert logs[0].phase is None
    assert manager.get_project_board(board.id).savor_count == 0


def test_rp45d_a_second_save_writes_no_second_work_log(root, manager, quiet):
    """Tightened: the counter was checked, the duplicate row it also writes was not."""
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        _complete_once(timer)
        assert len(manager.get_work_logs(item.id)) == 1
        assert manager.get_project_board(board.id).savor_count == 1

        timer.save_work_log()

        assert len(manager.get_work_logs(item.id)) == 1, (
            "a second save wrote a duplicate session row"
        )
        assert manager.get_project_board(board.id).savor_count == 1
    finally:
        timer.destroy()


def test_rp42_a_database_error_at_start_does_not_block_the_timer(root, manager, quiet):
    """A locked database must not turn Start into a button that does nothing.

    prepare_reward_session is the first statement of start_timer and was
    unguarded, so a transient sqlite error raised into Tk's handler: no dialog,
    no status change, just a traceback on a console the user cannot see.
    """
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.db_manager.get_project_boards_for_item = lambda item_id: (
            _ for _ in ()).throw(RuntimeError("database is locked"))

        timer.start_timer()
        timer._cancel_pending_timer()

        assert timer.timer_state == "running", "a transient DB error blocked the timer"
        assert timer.session_board_id is None, (
            "the session must not claim a project it could not read"
        )
    finally:
        timer.destroy()


# --- Continue records the same session facts as Finished --------------------

def test_rp45_continue_records_the_deliverable_and_carries_it_forward(root, manager, quiet):
    """Continue and Finished are two endings of one session and must agree.

    deliverable_snapshot is not reward-fired: Stop -> Finished writes it with
    deliverable_completed=0. Continue built its own WorkLog inline and dropped
    it, so the identical session recorded nothing about what it was for. The
    duplicate it creates was also missing the field entirely.
    """
    item, board = _linked(manager)
    timer = _timer(root, manager, item)

    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.getmoredone.screens.item_editor.ItemEditorDialog",
                   lambda *a, **k: None)
        timer.continue_action()

    log = manager.get_work_logs(item.id)[0]
    assert log.deliverable_snapshot == DELIVERABLE, (
        "Continue recorded nothing about what the session was for, while the "
        "same session ended with Finished records it"
    )
    # The reward fires on Done, not on Continue — so these stay empty.
    assert log.deliverable_completed is False
    assert log.phase is None
    assert manager.get_project_board(board.id).savor_count == 0

    duplicate = [i for i in manager.get_all_items()
                 if i.id != item.id and i.title == item.title]
    assert duplicate, "Continue did not create the follow-on item"
    assert duplicate[0].deliverable == DELIVERABLE, (
        "the follow-on item lost the deliverable; Continue means the same work "
        "goes on, so what 'done' looks like has not changed"
    )


def test_rp43_starting_a_session_never_leaves_the_break_choice_showing(root, manager, quiet):
    """start_timer hides the rest/continue pair whatever state it was left in.

    Unreachable through the UI today — Start is only enabled once stop_timer has
    run, and that hides the frame too — so the line in start_timer is belt and
    braces and no click sequence can prove it. Driven directly instead, because
    an untested defensive line is indistinguishable from a dead one, and the
    invariant it protects ("a running session never shows the break-end choice")
    is real: it would go wrong the moment Start becomes reachable from
    awaiting_choice.
    """
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        timer.break_choice_frame.grid()
        assert _is_visible(timer.break_choice_frame), "precondition"

        timer.start_timer()
        timer._cancel_pending_timer()

        assert not _is_visible(timer.break_choice_frame)
        assert timer.timer_state == "running"
    finally:
        timer.destroy()


def test_rp45_the_window_behind_the_savor_prompt_is_not_dressed_as_finished(root, manager, quiet):
    """The savor step asks for attention; the window behind it must not fight that.

    done_action used stop_timer to cancel the tick, which also turned the status
    red and read "Stopped", cut the music, hid Done, and put Finished and
    Continue — the two endings this protocol exists to route around — on screen
    beside the prompt. Cancelling the clock never needed any of that.
    """
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    timer.fire_celebration = lambda kind: None
    music = {"stopped": False}
    timer._stop_music = lambda: music.__setitem__("stopped", True)

    seen = {}

    class Recording(FakeSavorDialog):
        def __init__(self, parent, snapshot):
            seen.update(
                completion=_is_visible(timer.completion_frame),
                done=_is_visible(timer.done_button),
                status=timer.status_label.cget("text"),
                pending_tick=timer.update_timer_id,
                music_stopped=music["stopped"],
            )
            super().__init__(parent, snapshot)

    timer.start_timer()
    timer.work_seconds_elapsed = 25 * 60
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(twr, "SavorDialog", Recording)
        timer.done_action()

    assert seen["pending_tick"] is None, "the clock was still ticking — the whole point"
    assert seen["completion"] is False, (
        "Finished and Continue were on screen behind the savor prompt"
    )
    assert seen["status"] != "Stopped", (
        f"the window read {seen['status']!r} behind the savor prompt"
    )
    assert seen["music_stopped"] is False, "the music cut at the savor moment"
    assert seen["done"] is True, (
        "Done vanished, so a completion that then fails has no way to be retried"
    )


def test_rp43a_starting_after_a_stop_during_the_break_gives_a_whole_block(root, manager, quiet):
    """work=0, break=300 — the case the first version of the guard missed.

    It required *both* countdowns to be zero, copied from pause_timer's resume
    rule. Resuming mid-break should re-enter the break; Start should not. Start
    gave a zero-length work block whose first tick fired the BREAK TIME alarm
    and dropped the user back into the break they had just left.
    """
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        timer.start_timer()
        timer._cancel_pending_timer()
        timer.work_seconds_remaining = 1
        timer.tick()                       # into the break
        timer._cancel_pending_timer()
        assert timer.timer_state == "in_break"
        timer.stop_timer()
        assert (timer.work_seconds_remaining, timer.break_seconds_remaining) == (
            0, timer.break_minutes * 60), "precondition: stopped during the break"

        timer.start_timer()
        timer._cancel_pending_timer()

        assert timer.timer_state == "running", (
            f"Start dropped straight back into {timer.timer_state!r}"
        )
        _assert_fresh_work_block(timer)
    finally:
        timer.destroy()


def test_rp45d_a_failed_counter_update_rolls_the_work_log_back(root, manager, quiet):
    """The two writes are one fact, so half of it must never survive.

    The failure test this replaces patched create_work_log, so nothing was
    written and nothing was rolled back — the atomicity the transaction was
    added for had no coverage at all. This is the case that matters: the log
    succeeds, the counter fails, and both must vanish.
    """
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        timer.prepare_reward_session()
        timer.start_timestamp = datetime.now()
        timer.work_seconds_elapsed = 25 * 60
        timer._done_pressed = True
        timer._pending_reward = timer.run_reward_sequence()

        manager.increment_project_savor_count = lambda board_id: (
            _ for _ in ()).throw(RuntimeError("database is locked"))
        with pytest.raises(RuntimeError):
            timer.save_work_log()

        assert manager.get_work_logs(item.id) == [], (
            "the work log survived a failed counter update; the row now claims a "
            "completed deliverable the counter never counted"
        )
        assert manager.get_project_board(board.id).savor_count == 0
    finally:
        timer.destroy()


def test_rp45d_a_failed_save_keeps_the_facts_a_retry_needs(root, manager, quiet):
    """A retry after a failed write must record the completion, not a plain session.

    The flags used to be cleared in a finally. Since the writes are atomic a
    failed attempt leaves nothing behind, so clearing them bought no safety and
    cost the session's facts: the retry wrote the same work with no
    deliverable_completed, no phase, and the counter never advancing.
    """
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        timer.prepare_reward_session()
        timer.start_timestamp = datetime.now()
        timer.work_seconds_elapsed = 25 * 60
        timer._done_pressed = True
        timer._pending_reward = timer.run_reward_sequence()

        real = manager.create_work_log
        calls = []

        def flaky(log):
            calls.append(log)
            if len(calls) == 1:
                raise RuntimeError("database is locked")
            return real(log)

        manager.create_work_log = flaky
        with pytest.raises(RuntimeError):
            timer.save_work_log()

        timer.save_work_log()          # the retry

        logs = manager.get_work_logs(item.id)
        assert len(logs) == 1, "the retry wrote a duplicate, or nothing"
        assert logs[0].deliverable_completed is True, (
            "the retry recorded the completed deliverable as an ordinary session"
        )
        assert logs[0].phase == "wiring"
        assert manager.get_project_board(board.id).savor_count == 1, (
            "the retry left the project's phase permanently short by one"
        )
    finally:
        timer.destroy()


def test_rp45d_a_saved_session_leaves_nothing_behind(root, manager, quiet):
    """After a successful save the session state is fully consumed.

    No click sequence reaches this: finished_action destroys the window on
    success, and prepare_reward_session clears all four at the next Start. So
    the clears are defensive, and a mutation removing the three flags leaves the
    rest of the file green — which is exactly why the invariant is asserted
    directly rather than left looking covered.

    It matters because _pending_reward and _done_pressed are what label a row a
    completed deliverable. Left set on an object that saves again, they would
    stamp a different session with this one's phase and advance the counter for
    work that did not earn it.
    """
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        _complete_once(timer)

        assert timer.start_timestamp is None
        assert timer._pending_reward is None
        assert timer._done_pressed is False
        assert timer._savor_shown is False
    finally:
        timer.destroy()


def test_rp44_the_state_scan_covers_the_whole_timer_window_family():
    """The AST scan's own domain, asserted rather than assumed.

    All five states happen to be assigned in timer_window.py today, so scanning
    only that file still passes — the widened glob is future-proofing and
    catches nothing right now. What can be checked is that the glob resolves to
    the family it claims, so a typo in the pattern fails loudly instead of
    quietly scanning one file.

    It reads TIMER_WINDOW_GLOB rather than repeating the pattern. Written out
    twice, changing the scan's copy left this test — the one that exists to
    catch exactly that — perfectly green. An exact set, not a count floor: a
    floor is what hides the narrowing it was written to catch.
    """
    modules = {m.name for m in _timer_window_modules()}
    assert modules == {
        "timer_window.py",
        "timer_window_reward.py",
        "timer_window_celebration.py",
        "timer_window_dialogs.py",
    }, f"the timer_window family has changed: {sorted(modules)}"


def test_rp45_a_failed_completion_does_not_leave_the_window_claiming_success(root, manager, quiet):
    """The status label outlives the error modal, so it must not assert a lie.

    halt_for_completion runs before anything is persisted. If the save then
    raises, the item is still open and no work log exists, while the timer reads
    a green "Recording..." — the one artefact left on screen after the user
    dismisses the error.
    """
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    errors = []
    try:
        timer.fire_celebration = lambda kind: None
        timer._show_error_dialog = lambda message: errors.append(message)
        timer.db_manager.create_work_log = lambda log: (_ for _ in ()).throw(
            RuntimeError("database is locked"))

        timer.start_timer()
        timer.work_seconds_elapsed = 25 * 60
        timer.done_action()

        assert errors, "the failure was not reported to the user at all"
        assert manager.get_action_item(item.id).status == "open"
        assert manager.get_work_logs(item.id) == []
        assert manager.get_project_board(board.id).savor_count == 0

        status = timer.status_label.cget("text")
        assert "complete" not in status.lower() and "recording" not in status.lower(), (
            f"the window still reads {status!r} for a completion that did not happen"
        )
    finally:
        timer.destroy()


def test_rp45_halting_for_completion_leaves_a_usable_resume_control(root, manager, quiet):
    """PAUSED must look paused, from either route into it.

    The other two transitions into PAUSED both relabel this button. Without it
    the timer sits paused behind a control marked "Pause" that resumes — and
    reached from the break-end choice the button was disabled as well, so a
    completion that failed left no way to carry on.
    """
    item, _board = _linked(manager)

    for enter_from in ("running", "awaiting_choice"):
        timer = _timer(root, manager, item)
        try:
            timer.fire_celebration = lambda kind: None
            if enter_from == "running":
                timer.start_timer()
                timer._cancel_pending_timer()
            else:
                _run_to_break_end(timer)
                assert timer.pause_button.cget("state") == "disabled", "precondition"

            timer.halt_for_completion()

            assert timer.timer_state == "paused"
            assert timer.pause_button.cget("state") == "normal", (
                f"entering from {enter_from}: paused with no resume control"
            )
            assert timer.pause_button.cget("text") == "▶  Resume", (
                f"entering from {enter_from}: the button says "
                f"{timer.pause_button.cget('text')!r} while the timer is paused"
            )
        finally:
            timer.destroy()


def test_rp42_a_cascade_report_failure_does_not_stop_the_timer_starting(root, manager, quiet):
    """The notify is guarded on its own, which is what "two guards" means.

    Left bare, an exception here propagates out of prepare_reward_session and
    out of start_timer, which has no handler — so the Start button does nothing
    and says nothing.
    """
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(twr, "notify_weekly_tactic_changes",
                       lambda *a, **k: (_ for _ in ()).throw(RuntimeError("report failed")))
            timer.start_timer()
            timer._cancel_pending_timer()

        assert timer.timer_state == "running", "a failed cascade report blocked Start"
        # The deliverable write happened before the report, so it must survive.
        assert manager.get_action_item(item.id).deliverable == DELIVERABLE
        assert timer.session_board_id == board.id
    finally:
        timer.destroy()


# --- what the window shows, and who starts the music ------------------------

def test_the_deliverable_is_shown_on_the_timer_window(root, manager, quiet):
    """It was captured in a dialog and then never shown again.

    The one thing the reward is contingent on was the one thing not on screen.
    """
    item, _board = _linked(manager, deliverable="Draft section 2")
    timer = _timer(root, manager, item)
    try:
        # Before Start, straight from the item — the window opens knowing.
        assert timer.deliverable_label.cget("text") == "Draft section 2"

        timer.start_timer()
        timer._cancel_pending_timer()
        assert timer.deliverable_label.cget("text") == "Draft section 2"
    finally:
        timer.destroy()


def test_an_item_with_no_deliverable_says_so_rather_than_showing_nothing(root, manager, quiet):
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        assert timer.deliverable_label.cget("text") == TimerWindow.NO_DELIVERABLE_TEXT
    finally:
        timer.destroy()


def test_a_blank_deliverable_is_prompted_for_on_every_item(root, manager, quiet):
    """Not just project-linked ones. An unlinked session still names its target."""
    item = _item(manager)                      # no project, no deliverable
    timer = _timer(root, manager, item)
    try:
        timer.start_timer()
        timer._cancel_pending_timer()

        assert len(FakeDeliverableDialog.calls) == 1, (
            "an item with no deliverable started a session without being asked"
        )
        assert manager.get_action_item(item.id).deliverable == DELIVERABLE
        assert timer.deliverable_label.cget("text") == DELIVERABLE
    finally:
        timer.destroy()


def test_backing_out_of_the_prompt_does_not_start_an_unlinked_timer(root, manager, quiet):
    """Cancel means do not start, on every item — not only project-linked ones."""
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        FakeDeliverableDialog.next_result = None
        timer.start_timer()

        assert timer.timer_state == "stopped"
        assert timer.update_timer_id is None
    finally:
        timer.destroy()


def test_editing_the_deliverable_updates_the_item_and_the_label(root, manager, quiet):
    item, _board = _linked(manager, deliverable="First idea")
    timer = _timer(root, manager, item)
    try:
        FakeDeliverableDialog.next_result = "Second idea"
        timer.edit_deliverable()

        assert timer.deliverable_label.cget("text") == "Second idea"
        assert manager.get_action_item(item.id).deliverable == "Second idea"
    finally:
        timer.destroy()


def test_backing_out_of_an_edit_changes_nothing(root, manager, quiet):
    item, _board = _linked(manager, deliverable="First idea")
    timer = _timer(root, manager, item)
    try:
        FakeDeliverableDialog.next_result = None
        timer.edit_deliverable()

        assert timer.deliverable_label.cget("text") == "First idea"
        assert manager.get_action_item(item.id).deliverable == "First idea"
    finally:
        timer.destroy()


def test_starting_the_timer_does_not_start_the_music(root, manager, quiet, monkeypatch):
    """Music is the user's to start. It used to begin with every session."""
    item, _board = _linked(manager)
    started = []
    monkeypatch.setattr(TimerWindow, "_start_music",
                        lambda self: started.append(True) or True)
    timer = _timer(root, manager, item)
    try:
        timer.start_timer()
        timer._cancel_pending_timer()

        assert started == [], "starting the timer started the music"

        timer.play_music()
        assert started == [True], "the Play button no longer starts the music"
    finally:
        timer.destroy()


def test_music_information_stays_in_the_music_area(root, manager, quiet):
    """The track used to be appended to the timer's own status line.

    Asserted through _set_music_status, which is the real path — a helper that
    only wrote the same thing a line later was removed rather than left looking
    load-bearing because a test called it directly.
    """
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.current_track_name = "Chief O'Neill's Favourite"
        timer._update_status_label("Working...", "green")

        assert timer.status_label.cget("text") == "Working...", (
            "the timer's status line is carrying music information"
        )

        timer._set_music_status(f"♫ {timer.current_track_name}", "success")
        assert "Chief O'Neill" in timer.music_status_label.cget("text")
        assert timer.status_label.cget("text") == "Working...", (
            "setting the music status leaked into the timer's status line"
        )
    finally:
        timer.destroy()


def test_the_music_buttons_are_labelled_consistently(root, manager, quiet):
    """Nine relabel sites used a different spacing from the constructor."""
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        assert timer.music_play_button.cget("text") == "▶  Play"
        assert timer.music_pause_button.cget("text") == "⏸  Pause"

        # Driven through the real relabel paths, not by configuring the button
        # with the constant and asserting the constant back — which is a test
        # agreeing with itself, and stayed green with all nine relabel sites
        # reverted to their old one-space literals.
        #
        # pygame is stubbed rather than the label logic: pause_music gates on a
        # live mixer, which the suite never initialises.
        import pygame

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(pygame.mixer, "get_init", lambda: True)
            mp.setattr(pygame.mixer.music, "get_busy", lambda: True)
            mp.setattr(pygame.mixer.music, "pause", lambda: None)
            timer.music_is_playing = True
            timer.pause_music()
            assert timer.music_pause_button.cget("text") == "▶  Resume", (
                "a paused music button reads differently from a fresh one"
            )

            mp.setattr(pygame.mixer.music, "get_busy", lambda: False)
            mp.setattr(pygame.mixer.music, "unpause", lambda: None)
            timer.pause_music()
            assert timer.music_pause_button.cget("text") == "⏸  Pause", (
                "a resumed music button reads differently from a fresh one"
            )
    finally:
        timer.destroy()


def test_the_transport_controls_live_inside_the_timer_area(root, manager, quiet):
    """Start, Pause and Stop belong to the timer, not to a frame beside it."""
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        for button, label in ((timer.start_button, "▶  Start"),
                              (timer.pause_button, "⏸  Pause"),
                              (timer.stop_button, "⏹  Stop")):
            assert button.cget("text") == label
            # The transport row's parent is a frame inside the timer frame.
            assert button.master.master is timer.timer_frame, (
                f"{label} is not inside the timer area"
            )
        for widget in (timer.done_button, timer.break_choice_frame,
                       timer.status_label, timer.deliverable_label,
                       timer.time_remaining_label, timer.time_block_value):
            assert widget.master is timer.timer_frame
        # Music, and only music, in the music area.
        assert timer.music_status_label.master is timer.music_play_button.master
        assert timer.music_status_label.master is not timer.timer_frame
    finally:
        timer.destroy()


# --- the session actions ----------------------------------------------------

def test_save_and_close_records_the_session_without_completing_the_item(root, manager, quiet):
    """The timer window is a child record of the action item, not its ending."""
    item, board = _linked(manager)
    closed = []
    timer = TimerWindow(root, manager, item, on_close=lambda: closed.append(True),
                        rng=random.Random(1))
    FakeCompletionNoteDialog.next_result = "got the opening paragraph down"
    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60

    timer.save_and_close_action()

    assert manager.get_action_item(item.id).status == "open", (
        "Save & Close completed the action item; only Done should do that"
    )
    logs = manager.get_work_logs(item.id)
    assert len(logs) == 1
    assert logs[0].minutes == 25
    assert logs[0].note == "got the opening paragraph down"
    assert logs[0].deliverable_snapshot == DELIVERABLE
    assert logs[0].deliverable_completed is False, "no deliverable was declared complete"
    assert manager.get_project_board(board.id).savor_count == 0, (
        "Save & Close advanced the reward counter"
    )
    assert closed == [True], "the opener was not told to refresh"


def test_cancel_timer_records_absolutely_nothing(root, manager, quiet):
    """Cancel means nothing happened — no session, no time, no note, no edit.

    It used to log the elapsed minutes and save the notes box on the reasoning
    that time spent is a fact. True of a session someone meant to have, but not
    what the word Cancel offers. "Save Related - Close Timer" is for keeping it.
    """
    item, board = _linked(manager)
    item.description = "the description as it was"
    manager.update_action_item(item)

    timer = TimerWindow(root, manager, item, rng=random.Random(1))
    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60
    timer.next_steps_text.delete("1.0", "end")
    timer.next_steps_text.insert("1.0", "notes I typed and then abandoned")

    timer.cancel_action()

    assert manager.get_work_logs(item.id) == [], "Cancel Timer recorded a session"
    fresh = manager.get_action_item(item.id)
    assert fresh.status == "open"
    assert fresh.description == "the description as it was", (
        "Cancel Timer saved notes the user abandoned"
    )
    assert manager.get_project_board(board.id).savor_count == 0


def test_cancel_timer_cannot_leak_a_pending_completion(root, manager, quiet):
    """A Done whose save failed must not survive a Cancel into the next session."""
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    timer.fire_celebration = lambda kind: None
    timer._show_error_dialog = lambda message: None
    timer.start_timer()
    timer.work_seconds_elapsed = 25 * 60

    # Fails once, then works. An unconditional raiser left the work-log
    # assertion below unfalsifiable: any write would raise, be swallowed by
    # cancel_action's except, and leave the table empty either way — so it
    # could not tell "Cancel wrote nothing" from "Cancel could not write".
    real = manager.create_work_log
    calls = []

    def flaky(log):
        calls.append(log)
        if len(calls) == 1:
            raise RuntimeError("database is locked")
        return real(log)

    manager.create_work_log = flaky
    timer.done_action()
    assert timer._done_pressed is True, "precondition: the Done is still pending"

    timer.stop_timer()
    timer.cancel_action()

    assert timer._done_pressed is False
    assert timer._pending_reward is None
    assert manager.get_project_board(board.id).savor_count == 0
    assert manager.get_work_logs(item.id) == [], "Cancel Timer wrote a session"


def test_only_done_completes_the_action_item(root, manager, quiet):
    """The three ways out of a session, and which of them ends the work."""
    outcomes = {}
    for label, drive in (
        ("save", lambda t: t.save_and_close_action()),
        ("cancel", lambda t: t.cancel_action()),
        ("done", lambda t: t.done_action()),
    ):
        item, board = _linked(manager)
        timer = TimerWindow(root, manager, item, rng=random.Random(1))
        timer.fire_celebration = lambda kind: None
        timer.start_timer()
        timer._cancel_pending_timer()
        timer.work_seconds_elapsed = 25 * 60
        drive(timer)
        outcomes[label] = (
            manager.get_action_item(item.id).status,
            manager.get_project_board(board.id).savor_count,
        )

    assert outcomes["save"] == ("open", 0)
    assert outcomes["cancel"] == ("open", 0)
    assert outcomes["done"] == ("completed", 1), (
        "Done is the only ending that completes the item and counts it"
    )


def test_editing_the_deliverable_mid_session_updates_the_label(root, manager, quiet):
    """The one state the Edit button is useful in, and the one it was broken in.

    refresh_deliverable_label read `session_deliverable or item.deliverable`,
    and the snapshot is frozen at Start and stays truthy — so after Start every
    edit re-rendered the old text and the button looked broken. The original
    test edited *before* Start, where the snapshot is None and the fallback
    hides it.
    """
    item, _board = _linked(manager, deliverable="First idea")
    timer = _timer(root, manager, item)
    try:
        timer.start_timer()
        timer._cancel_pending_timer()
        assert timer.deliverable_label.cget("text") == "First idea"

        FakeDeliverableDialog.next_result = "Second idea"
        timer.edit_deliverable()
        timer._cancel_pending_timer()

        assert timer.deliverable_label.cget("text") == "Second idea", (
            "the label still shows the old deliverable after an edit"
        )
        assert manager.get_action_item(item.id).deliverable == "Second idea"
        # The snapshot moves too. An explicit edit here redefines what this
        # session is for, and the label, the savor prompt and the work log must
        # not disagree about that. RP-4.5g still holds — it protects against the
        # deliverable being changed *elsewhere*, which does not come through
        # this method (see test_rp45g_snapshot_survives_a_later_edit...).
        assert timer.session_deliverable == "Second idea"
    finally:
        timer.destroy()


def test_editing_the_deliverable_does_not_leave_the_clock_running(root, manager, quiet):
    """The edit modal pumps the event loop, same as the savor dialog does."""
    item, _board = _linked(manager, deliverable="First idea")
    timer = _timer(root, manager, item)
    seen = {}

    class Recording(FakeDeliverableDialog):
        def __init__(self, parent, **kwargs):
            seen["pending_tick"] = timer.update_timer_id
            super().__init__(parent, **kwargs)

    try:
        timer.start_timer()
        assert timer.update_timer_id is not None, "precondition: a tick is scheduled"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(twr, "DeliverableDialog", Recording)
            timer.edit_deliverable()
        timer._cancel_pending_timer()

        assert seen["pending_tick"] is None, (
            "the clock was still ticking while the edit dialog was open"
        )
        assert timer.timer_state == "running", "editing stopped the session"
    finally:
        timer.destroy()


def test_save_and_close_after_a_failed_done_does_not_count_a_completion(root, manager, quiet):
    """A Done whose save failed must not be cashed in by a different ending.

    save_work_log keeps the reward flags on failure so a retry records the
    completion. Save & Close is not that retry: it wrote
    deliverable_completed=1 and advanced the project counter while leaving the
    item open, so the board claimed a completion the item did not record.
    """
    item, board = _linked(manager)
    timer = _timer(root, manager, item)
    try:
        timer.fire_celebration = lambda kind: None
        timer._show_error_dialog = lambda message: None
        timer.start_timer()
        timer.work_seconds_elapsed = 25 * 60

        real = manager.create_work_log
        calls = []

        def flaky(log):
            calls.append(log)
            if len(calls) == 1:
                raise RuntimeError("database is locked")
            return real(log)

        manager.create_work_log = flaky
        timer.done_action()                      # fails; flags stay set
        assert timer._done_pressed is True, "precondition: the Done is still pending"

        timer.stop_timer()
        timer.save_and_close_action()

        assert manager.get_action_item(item.id).status == "open"
        assert manager.get_project_board(board.id).savor_count == 0, (
            "Save & Close counted a completion for an item it left open"
        )
        logs = manager.get_work_logs(item.id)
        assert len(logs) == 1
        assert logs[0].deliverable_completed is False
        assert logs[0].phase is None
    finally:
        timer.destroy()


def test_save_and_close_keeps_the_note_when_the_window_closes_under_it(root, manager, quiet):
    """dialog.result is a plain attribute; it needs no live window to read.

    Guarding it on winfo_exists() threw the typed note away in exactly the case
    where the window had gone — and wrote the log anyway, so nothing signalled
    the loss.
    """
    item, _board = _linked(manager)
    timer = _timer(root, manager, item)

    class ClosesTheWindow:
        def __init__(self, parent, title):
            self.result = "the note I typed"
            parent.destroy()

    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tw, "CompletionNoteDialog", ClosesTheWindow)
        timer.save_and_close_action()

    logs = manager.get_work_logs(item.id)
    assert len(logs) == 1
    assert logs[0].note == "the note I typed", (
        "the note was discarded because the window had already closed"
    )


def test_clearing_the_notes_box_clears_the_description(root, manager, quiet):
    """The one edit the window refused to save was a deletion.

    Driven through Save Related, not Cancel Timer: Cancel now means nothing
    happened, so it saves no edit at all — including a deletion.
    """
    item, _board = _linked(manager)
    item.description = "something I no longer want"
    manager.update_action_item(item)

    timer = TimerWindow(root, manager, item, rng=random.Random(1))
    timer.start_timer()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60
    timer.next_steps_text.delete("1.0", "end")

    timer.save_and_close_action()

    assert manager.get_action_item(item.id).description is None, (
        "blanking the notes box left the old description in place"
    )


def test_editing_the_deliverable_moves_the_savor_prompt_too(root, manager, quiet):
    """Label, savor prompt and work log must all name the same deliverable.

    The label was moved off the frozen snapshot and the savor prompt was not,
    so an edit mid-session left the prompt asking the user to sit with a
    deliverable they had already replaced — the same defect one display site
    over.
    """
    item, _board = _linked(manager, deliverable="First idea")
    timer = _timer(root, manager, item)
    timer.fire_celebration = lambda kind: None

    timer.start_timer()
    FakeDeliverableDialog.next_result = "Second idea"
    timer.edit_deliverable()
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60

    assert timer.deliverable_label.cget("text") == "Second idea"

    timer.done_action()

    assert FakeSavorDialog.shown == ["Second idea"], (
        f"the savor prompt named {FakeSavorDialog.shown} after the user changed "
        "the deliverable to 'Second idea'"
    )
    assert manager.get_work_logs(item.id)[0].deliverable_snapshot == "Second idea"


def test_editing_the_deliverable_restarts_the_clock_afterwards(root, manager, quiet):
    """The cancel half was covered; the restart — the risky half — was not.

    Deleting the whole `finally` body left the file green, so a timer left
    permanently dead (no tick scheduled, state still "running", status still
    reading "Working...") was undetectable.
    """
    item, _board = _linked(manager, deliverable="First idea")
    timer = _timer(root, manager, item)
    try:
        timer.start_timer()
        FakeDeliverableDialog.next_result = "Second idea"

        timer.edit_deliverable()

        assert timer.timer_state == "running"
        assert timer.update_timer_id is not None, (
            "the clock was cancelled for the dialog and never restarted — the "
            "timer looks like it is running and is not"
        )
        timer._cancel_pending_timer()
    finally:
        timer.destroy()


def test_editing_before_the_timer_starts_does_not_offer_to_start_it(root, manager, quiet):
    """Edit is reachable before Start, and it does not start anything."""
    item, _board = _linked(manager, deliverable="First idea")
    timer = _timer(root, manager, item)
    try:
        assert timer.timer_state == "stopped", "precondition: not started"
        FakeDeliverableDialog.next_result = "Second idea"

        timer.edit_deliverable()

        assert FakeDeliverableDialog.calls[-1]["confirm_text"] == "Save", (
            "the Edit dialog offered to 'Start' a session it does not start"
        )
        assert timer.timer_state == "stopped", "editing started the timer"
    finally:
        timer.destroy()


def test_clearing_the_notes_box_clears_it_on_every_ending(root, manager, quiet):
    """Four endings, one answer to what an empty notes box means.

    Cancel and Save & Close cleared the description; Done and Complete & Carry
    Forward kept it, because those two guarded on `if timer_notes:`. Same
    gesture, opposite outcomes, depending on which button you reached for.
    """
    for ending in ("save_and_close_action", "done_action"):
        item, _board = _linked(manager)
        item.description = "something I no longer want"
        manager.update_action_item(item)

        timer = _timer(root, manager, item)
        timer.fire_celebration = lambda kind: None
        timer.start_timer()
        timer._cancel_pending_timer()
        timer.work_seconds_elapsed = 25 * 60
        timer.next_steps_text.delete("1.0", "end")

        getattr(timer, ending)()

        assert manager.get_action_item(item.id).description is None, (
            f"{ending} kept a description the user had cleared"
        )


# --- modals must not open behind the always-on-top timer --------------------

class _StubWindow:
    """A window-shaped object. No Tk, so this test can never reach a screen."""

    def __init__(self, state="normal"):
        self._state = state
        self.calls = []

    def state(self):
        return self._state

    def winfo_ismapped(self):
        return self._state != "withdrawn"

    def attributes(self, *args):
        self.calls.append(("attributes",) + args)

    def lift(self):
        self.calls.append(("lift",))

    def after(self, _ms, fn):
        fn()                      # run the scheduled raise immediately


def test_raise_above_parent_lifts_a_visible_window():
    """The fix for modals opening behind the timer.

    Setting -topmost in __init__ does not stick: measured 0 straight after
    construction while the timer reads 1. The modal then sat behind the timer
    holding grab_set(), invisible and swallowing every click — which is why
    Stop followed by any session button left the window looking dead.
    """
    window = _StubWindow(state="normal")
    dialogs.raise_above_parent(window)

    assert ("attributes", "-topmost", True) in window.calls, (
        "a visible modal did not re-assert itself above the timer"
    )
    assert ("lift",) in window.calls


def test_raise_above_parent_leaves_a_withdrawn_window_alone():
    """Never touch a window that is not on screen.

    The test suite withdraws every window, so without this guard the raise
    fired hundreds of times per run against windows nobody could see, hammering
    the window server and locking up the machine while the suite ran.
    """
    window = _StubWindow(state="withdrawn")
    dialogs.raise_above_parent(window)

    assert window.calls == [], (
        f"a withdrawn window was raised anyway: {window.calls}"
    )


def test_every_timer_modal_raises_itself_above_the_timer(root, manager, quiet, monkeypatch):
    """Every modal the timer opens, not just the one that was reported.

    The timer window is -topmost, so any modal it opens without re-asserting
    itself lands behind it. Checked as a class rather than one dialog at a time,
    because that is how the defect got in.
    """
    raised = []
    monkeypatch.setattr(dialogs, "raise_above_parent",
                        lambda d: raised.append(type(d).__name__))

    item = _item(manager)
    built = [
        dialogs.CompletionNoteDialog(root, "Session Note"),
        dialogs.NextStepsDialog(root),
        dialogs.DeliverableDialog(root, "A task"),
        dialogs.SavorDialog(root, "Draft section 2"),
        dialogs.NextActionWindow(root, manager, item),
    ]
    try:
        assert set(raised) == {
            "CompletionNoteDialog",
            "NextStepsDialog",
            "DeliverableDialog",
            "SavorDialog",
            "NextActionWindow",
        }, f"these modals do not raise themselves above the timer: {raised}"
    finally:
        for w in built:
            try:
                w.destroy()
            except Exception:
                pass
