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
from typing import Optional

from ..models import ProjectBoard
from ..reward_protocol import RewardDecision, decide_reward, phase_for
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

    def prepare_reward_session(self) -> bool:
        """Confirm the deliverable before starting. False means do not start.

        Purpose: RP-4.2 — an item with no project has no board to count
                 towards, so it runs the timer exactly as it always did.
        Tests:   tests/test_reward_protocol_timer.py::test_rp42_linked_start_captures_the_session_deliverable
                 tests/test_reward_protocol_timer.py::test_rp42c_unlinked_item_starts_with_no_reward_protocol
        """
        self.session_deliverable = None
        self.session_board_id = None
        self.session_phase = None
        self._pending_reward = None
        self._done_pressed = False
        self._savor_shown = False

        try:
            board = self.resolve_reward_board()
        except Exception as exc:
            # A transient database error is not a reason to refuse to let
            # someone work (P1). Fall through to an ordinary untracked session
            # rather than leaving Start doing nothing at all.
            logger.exception(
                "[reward_protocol] could not resolve the project for %s; starting "
                "an untracked session: %s", self.item.id, exc,
            )
            return True

        if board is None:
            return True

        phase = phase_for(board.savor_count)
        dialog = DeliverableDialog(
            self,
            item_title=self.item.title,
            deliverable=self.item.deliverable,
            board_title=board.title,
            phase=phase,
            savor_count=board.savor_count,
        )
        self.wait_window(dialog)

        if not dialog.result:
            # Cancelled. Not "start without one": a reward-tracked session with
            # no deliverable has nothing for the reward to be contingent on.
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

        self.session_deliverable = dialog.result
        self.session_board_id = board.id
        # Informational only — what the phase was when the session began. The
        # phase written to the work log is the one decided at Done, which is
        # what the spec's reward sequence specifies.
        self.session_phase = phase
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
