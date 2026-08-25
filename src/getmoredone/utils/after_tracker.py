"""Scheduled callbacks that do not outlive the window they were scheduled on.

Purpose: `self.after(2000, ...)` on a window the user can close in the meantime
         leaves Tk holding a callback against a widget that no longer exists.
         When it fires, Tk raises "invalid command name" into the event loop —
         a traceback the user did not cause and cannot act on.
Spec:    BACKLOG.md, "What else may be leaking"
Tests:   tests/test_after_tracker.py

The same shape as the window leak this came from (P30): a finite thing is
acquired — here a Tk timer registration — and nothing gives it back. The
celebration overlay had already solved it locally; this is that solution made
available to the siblings rather than left as one hardened member of a class.
"""

from __future__ import annotations


class TrackedAfterMixin:
    """Adds ``tracked_after`` and ``cancel_tracked_after`` to a Tk window."""

    def tracked_after(self, delay_ms: int, callback):
        """``after``, but the handle is remembered so it can be cancelled.

        The handle is discarded as the callback runs, so a window that stays
        open for a long time does not accumulate the ids of callbacks that have
        already fired.
        """
        if not hasattr(self, "_tracked_after_ids"):
            self._tracked_after_ids = set()

        pending = self._tracked_after_ids
        handle = None

        def run():
            pending.discard(handle)
            callback()

        handle = self.after(delay_ms, run)
        pending.add(handle)
        return handle

    def cancel_tracked_after(self):
        """Cancel everything still pending. Safe to call twice, and on a
        window that is already half torn down."""
        pending = getattr(self, "_tracked_after_ids", None)
        if not pending:
            return 0
        cancelled = 0
        for handle in list(pending):
            try:
                self.after_cancel(handle)
                cancelled += 1
            except Exception:
                pass
        pending.clear()
        return cancelled

    def destroy(self):
        """Cancel pending callbacks before the widget they target goes away."""
        self.cancel_tracked_after()
        super().destroy()
