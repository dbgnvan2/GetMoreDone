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

import random
from datetime import datetime
from types import SimpleNamespace

import customtkinter as ctk
import pytest

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem, ProjectBoard
from src.getmoredone.reward_protocol import WIRING_THRESHOLD
from src.getmoredone.screens import timer_window as tw
from src.getmoredone.screens import timer_window_reward as twr
from src.getmoredone.screens.timer_window import TimerWindow

DELIVERABLE = "Draft section 2's opening paragraph"

# Every state the timer can be in. Written out rather than derived from the
# implementation, so a state added without a visibility decision fails here.
ALL_TIMER_STATES = ("stopped", "running", "paused", "in_break", "awaiting_choice")


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


def test_rp42_the_dialog_is_prefilled_from_the_item(root, manager, quiet):
    """An item that already has a deliverable does not make the user retype it."""
    item, _board = _linked(manager, deliverable="Existing deliverable")
    timer = _timer(root, manager, item)
    try:
        timer.prepare_reward_session()
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
    """RP-4.2c — no project means no dialog and no protocol; the timer is unchanged."""
    item = _item(manager)
    timer = _timer(root, manager, item)
    try:
        timer.start_timer()

        assert FakeDeliverableDialog.calls == [], "an unlinked item was asked for a deliverable"
        assert timer.session_board_id is None
        assert timer.session_deliverable is None
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
    timer._cancel_pending_timer()
    timer.break_seconds_remaining = 1
    timer.tick()                    # break hits zero
    timer._cancel_pending_timer()


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
        assert timer.pause_button.cget("text") == "Pause"
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
        assert timer.pause_button.cget("text") == "Resume"

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
        assert _is_visible(timer.completion_frame), "Stop no longer offers Finished/Continue"
        assert timer.finished_button.cget("text") == "Finished"
        assert timer.continue_button.cget("text") == "Continue"
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
        assert log.deliverable_snapshot is None
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
    timer._cancel_pending_timer()
    timer.work_seconds_elapsed = 25 * 60

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
