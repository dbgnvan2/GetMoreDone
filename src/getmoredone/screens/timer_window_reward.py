"""The reward protocol as the timer window uses it.

Purpose: RP-4.2 / RP-4.4 / RP-4.5 — capture the deliverable before the clock
         starts, and on "Done" run savor, then celebration, then persistence.
Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#4-ux-flow-hook-points-into-screenstimer_windowpy
Tests:   tests/test_reward_protocol_timer.py

Kept out of timer_window.py, which is already past the size where this repo's
policy calls a file a refactor candidate. The timer keeps the widgets and the
clock; this keeps the protocol.

Two places deliberately differ from the literal sequence in spec §4.5.

The counter is advanced inside ``save_work_log``, next to the row it belongs
with, rather than as its own step before it. Written as the spec lists it, a
window closed between the two would leave a board claiming a completion that
nothing recorded.

The work log is written once. Spec step 4 saves it and step 5 hands over to
"the existing completion flow" — but that flow already saves one, so following
both literally writes two rows for one session.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Optional

from ..models import ProjectBoard
from ..reward_protocol import RewardDecision, decide_reward, phase_for
from ..theme import status_text_color
from .timer_window_celebration import TimerCelebrationMixin
from .timer_window_dialogs import DeliverableDialog, SavorDialog
from .week_collision_notice import notify_weekly_tactic_changes

logger = logging.getLogger(__name__)


class TimerRewardMixin(TimerCelebrationMixin):
    """Reward-protocol behaviour for ``TimerWindow``."""

    def init_reward_session(self, rng: Optional[random.Random] = None) -> None:
        """Reset the per-session reward state. Called once from __init__."""
        # Injectable so a test can pin the decision. Not seeded here: an
        # unseeded Random is what the protocol wants in real use.
        self.reward_rng = rng if rng is not None else random.Random()
        self.session_deliverable: Optional[str] = None
        self.session_board_id: Optional[str] = None
        self.session_phase: Optional[str] = None
        # Set only by done_action, read only by save_work_log. Its presence
        # means the reward protocol ran; its absence means it did not.
        self._pending_reward: Optional[RewardDecision] = None
        # Whether the savor dialog was really put on screen. Read rather than
        # re-derived from the decision: work_logs.savor_delivered is meant to
        # say the step was *shown*, and a flag that merely repeats the decision
        # cannot tell anyone whether it was.
        self._savor_shown = False
        # Separate from the decision on purpose. "The user said this is done"
        # and "the protocol ran" are different facts, and an unlinked item can
        # be the first without ever being the second. Folding them into one
        # flag would make work_logs.deliverable_completed mean "was on a
        # project", which is not what the spec says it records.
        self._done_pressed = False

    # -- start ---------------------------------------------------------------

    def resolve_reward_board(self) -> Optional[ProjectBoard]:
        """The board this item's completions count towards, if any.

        Spec §7.1 MVP: an item filed under several boards uses the first by
        link date. The choice is made here, in one place, rather than left to
        whichever caller happens to index the list.
        """
        boards = self.db_manager.get_project_boards_for_item(self.item.id)
        if not boards:
            return None
        if len(boards) > 1:
            logger.info(
                "[reward_protocol] %s is filed under %d projects; counting towards %r "
                "(the oldest link)", self.item.id, len(boards), boards[0].title,
            )
        return boards[0]

    def refresh_deliverable_label(self):
        """Show what this session is for, on the window it is for.

        Purpose: the deliverable was captured in a dialog and then never shown
                 again, so the one thing the reward is contingent on was the one
                 thing not on screen.
        Tests:   tests/test_reward_protocol_timer.py::test_the_deliverable_is_shown_on_the_timer_window
        """
        # item.deliverable, never session_deliverable. The snapshot is frozen
        # at Start and stays truthy for the rest of the session, so reading it
        # first meant every mid-session edit re-rendered the old text and the
        # Edit button looked broken in the one state it is useful in. The
        # snapshot's job is work_logs.deliverable_snapshot, not the display.
        text = self.item.deliverable
        if text:
            self.deliverable_label.configure(
                text=text, text_color=status_text_color("body"))
        else:
            self.deliverable_label.configure(
                text=self.NO_DELIVERABLE_TEXT, text_color=status_text_color("muted"))

    def edit_deliverable(self):
        """Change what this session is for, from the timer itself.

        Tests: tests/test_reward_protocol_timer.py::test_editing_the_deliverable_updates_the_item_and_the_label

        Editing mid-session does not rewrite what the session was started for:
        work_logs.deliverable_snapshot is frozen at start (RP-4.5g). It changes
        the item, and the label, from here on.
        """
        # The clock stops while the modal is open. wait_window pumps the Tk
        # event loop, so a still-scheduled tick fires underneath it — the same
        # hazard done_action documents and solves, at a sibling call site that
        # did not have the guard (P5).
        resume = self.timer_state in (self.RUNNING, self.IN_BREAK)
        if resume:
            self._cancel_pending_timer()
        try:
            if not self.ask_for_deliverable():
                return
        finally:
            if resume and self.timer_state in (self.RUNNING, self.IN_BREAK):
                self.last_tick_time = datetime.now()
                self.tick()
        self.refresh_deliverable_label()

    def ask_for_deliverable(self) -> bool:
        """Prompt for the deliverable. False means the user backed out.

        Purpose: RP-4.2 — one prompt, used both at Start when there is nothing
                 to run a session against and by the Edit button.
        Tests:   tests/test_reward_protocol_timer.py::test_a_blank_deliverable_is_prompted_for_on_every_item
        """
        board = self.resolve_reward_board_safely()
        dialog = DeliverableDialog(
            self,
            item_title=self.item.title,
            deliverable=self.item.deliverable,
            board_title=board.title if board else None,
            phase=phase_for(board.savor_count) if board else None,
            savor_count=board.savor_count if board else None,
            # Reached from Edit, the session is already running, and offering
            # to "Start" one is an answer to a question nobody asked.
            confirm_text="Start" if self.timer_state == self.STOPPED else "Save",
        )
        self.wait_window(dialog)

        if not dialog.result:
            return False

        if dialog.result != (self.item.deliverable or None):
            self.item.deliverable = dialog.result
            # Two guards, not one, and both of them real.
            #
            # A shared except made a failed cascade report come out as "could
            # not save the deliverable" — one message for two unrelated facts
            # (P13). But splitting them and leaving the notify bare is not two
            # guards either: an exception there propagates out of start_timer,
            # which has no handler, and the timer silently fails to start.
            #
            # The comments live up here rather than inside the block because
            # tests/test_weekly_tactic_surfaces.py requires the notify within
            # twelve lines of the call it reports on, and prose counts.
            try:
                self.db_manager.update_action_item(self.item)
            except Exception as exc:
                logger.exception(
                    "[reward_protocol] could not save the deliverable on %s; the "
                    "session still records it: %s", self.item.id, exc,
                )
            else:
                try:
                    notify_weekly_tactic_changes(self.db_manager, self)
                except Exception as exc:
                    logger.exception(
                        "[reward_protocol] the deliverable saved, but reporting "
                        "the weekly-tactic cascade failed: %s", exc,
                    )
        return True

    def resolve_reward_board_safely(self):
        """resolve_reward_board, but a database hiccup is not fatal.

        A transient error is not a reason to refuse to let someone work (P1);
        the session runs untracked instead.
        """
        try:
            return self.resolve_reward_board()
        except Exception as exc:
            logger.exception(
                "[reward_protocol] could not resolve the project for %s; treating "
                "the session as untracked: %s", self.item.id, exc,
            )
            return None

    def prepare_reward_session(self) -> bool:
        """Settle what this session is for before the clock starts.

        Purpose: RP-4.2 — every session has a deliverable, and one that has
                 already been named is not asked for again; it is on screen.
        Tests:   tests/test_reward_protocol_timer.py::test_rp42_linked_start_captures_the_session_deliverable
                 tests/test_reward_protocol_timer.py::test_a_blank_deliverable_is_prompted_for_on_every_item

        False means do not start. Reward *counting* is still project-only — an
        item with no project gets a deliverable and no phase, no savor and no
        counter — but naming what you are about to do is not the reward
        protocol, it is the point of starting a timer at all.
        """
        self.session_deliverable = None
        self.session_board_id = None
        self.session_phase = None
        self._pending_reward = None
        self._done_pressed = False
        self._savor_shown = False

        if not self.item.deliverable:
            # Only when there is nothing to run a session against. Asking every
            # time re-types an answer the user can already see on the window.
            if not self.ask_for_deliverable():
                return False

        self.session_deliverable = self.item.deliverable
        board = self.resolve_reward_board_safely()
        if board is not None:
            self.session_board_id = board.id
            # Informational only — what the phase was when the session began.
            # The phase written to the work log is the one decided at Done.
            self.session_phase = phase_for(board.savor_count)

        self.refresh_deliverable_label()
        return True

    # -- done ----------------------------------------------------------------

    def done_action(self):
        """Deliverable complete: savor, celebrate, then the completion flow.

        Purpose: RP-4.4 / RP-4.5 — the reward fires on completion, at whatever
                 moment the user says it is done, never on the timer ringing.
        Tests:   tests/test_reward_protocol_timer.py::test_rp45_savor_precedes_celebration
                 tests/test_reward_protocol_timer.py::test_rp44a_done_on_unlinked_item_skips_the_reward_protocol
        """
        # Halt the clock first. Both dialogs below are entered through
        # wait_window, which pumps the Tk event loop, so the tick kept running
        # underneath them: the break alarm would sound over the savor prompt and
        # _flash_window's focus_force would pull focus off it. Every pre-existing
        # route into finished_action came through stop_timer, so this
        # combination could not arise before Done existed.
        #
        # halt_for_completion and not stop_timer: the latter also dresses the
        # window as a finished session — red "Stopped", music cut, Finished and
        # Continue on screen — behind a prompt asking the user to sit with what
        # they just made.
        if self.timer_state != self.STOPPED:
            self.halt_for_completion()

        self._done_pressed = True

        # Guarded, because everything in the reward sequence is decoration —
        # a dialog, a canvas, an audio player — and none of it may be allowed
        # to prevent the session being recorded. Unguarded, a TclError from a
        # grab clash meant the user pressed Done, saw nothing happen, and lost
        # the work log, the completion and the count.
        try:
            self._pending_reward = self.run_reward_sequence()
        except Exception as exc:
            self._pending_reward = None
            logger.exception(
                "[reward_protocol] the reward sequence failed; completing the "
                "session without it: %s", exc,
            )

        self.finished_action()

    def run_reward_sequence(self) -> Optional[RewardDecision]:
        """Savor then celebration, in that order. None when there is no board.

        The celebration is a bonus on top of the savor and never a replacement
        for it, which is why it is fired after and only after.
        """
        if not self.session_board_id:
            return None

        board = self.db_manager.get_project_board(self.session_board_id)
        if board is None:
            # Deleted while the timer was open. Say so rather than silently
            # dropping a completion the user just earned.
            logger.warning(
                "[reward_protocol] project %s vanished during the session; "
                "completing without the reward protocol", self.session_board_id,
            )
            return None

        decision = decide_reward(board.savor_count, self.reward_rng)

        self._savor_shown = False
        if decision.show_savor and self.session_deliverable:
            dialog = SavorDialog(self, self.session_deliverable)
            self.wait_window(dialog)
            self._savor_shown = True

        if decision.celebration:
            self.fire_celebration(decision.celebration)

        return decision
