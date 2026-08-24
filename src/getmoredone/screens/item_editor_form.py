"""The one place the item editor turns its form into an ActionItem.

Purpose: BP3 — ``save_item`` and ``save_item_if_needed`` both create a new
         Action Item, and both used to assemble its fields from scratch. They
         drifted twice in a single session (the Project link, then the order in
         which the Annual Plan Element is written), so whichever button the user
         happened to press decided what got stored.
Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp3
Tests:   tests/test_item_editor_new_item_builder.py

Everything both paths share lives here: the field assembly, the new-item-only
fields, the validation, and the insert sequence. The two callers keep only what
is genuinely their own — ``save_item`` also updates an existing row, and
``save_item_if_needed`` also refreshes the Notes tab afterwards.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from ..models import ActionItem
from ..validation import Validator
from .week_collision_notice import notify_weekly_tactic_changes


class ItemEditorFormMixin:
    """Form → ActionItem, shared by both of the editor's save paths."""

    def build_item_from_form(self, item: Optional[ActionItem] = None) -> ActionItem:
        """Write every form field onto ``item`` (a fresh one when omitted).

        Field order matters and is the order ``save_item`` used: the Weekly
        Tactic title is canonicalised from the item's *stored* start date,
        before the form's start date overwrites it.
        """
        if item is None:
            item = ActionItem(who="", title="")

        item.who = self.who_var.get().strip()
        item.contact_id = self.selected_contact_id
        item.title = self.title_entry.get().strip()
        if item.item_type == "week":
            item.title = self._canonical_weekly_tactic_title(
                item.title,
                item.annual_plan_element_id,
                item.start_date,
            )
        item.description = self.description_text.get("1.0", "end").strip() or None
        item.next_action = self.next_action_text.get("1.0", "end").strip() or None
        # RP-4.1 — read back through the same builder both save paths use, so
        # the field cannot reach one of them and not the other.
        # Tests: tests/test_item_editor_new_item_builder.py::test_rp41_deliverable_from_form_reaches_the_saved_item
        item.deliverable = self.deliverable_entry.get().strip() or None
        item.start_date = self.start_date_entry.get().strip() or None
        item.due_date = self.due_date_entry.get().strip() or None
        item.is_meeting = self.is_meeting_var.get()

        # Priority factors
        item.importance = self.extract_factor_value(self.importance_var.get())
        item.urgency = self.extract_factor_value(self.urgency_var.get())
        item.size = self.extract_factor_value(self.size_var.get())
        item.value = self.extract_factor_value(self.value_var.get())

        # Organization
        item.group = self.group_var.get().strip() or None
        item.category = self.category_var.get().strip() or None

        # Planned minutes
        planned_text = self.planned_minutes_entry.get().strip()
        item.planned_minutes = int(planned_text) if planned_text else None

        # WT-M6.A.3 — the hand-edited original-week stamp (WT-D3). Blank clears
        # it; anything unparseable is left as it was rather than writing a date
        # the user did not mean.
        stamp = self.weekly_tactic_start_var.get().strip()
        if stamp:
            try:
                date.fromisoformat(stamp)
                item.weekly_tactic_start_date = stamp
            except ValueError:
                self._warn(
                    "[save] ignoring unparseable weekly_tactic_start_date %r", stamp
                )
        else:
            item.weekly_tactic_start_date = None

        return item

    def apply_new_item_fields(self, item: ActionItem) -> None:
        """The fields that only a brand-new row gets, on both insert paths.

        ``week_action_id`` is the dead legacy FK (WT-F6): NULL on every row and
        pointing at an empty table. It is carried here rather than retired —
        that is its own change (spec section 9) — but it is carried on *both*
        paths now, so the two cannot disagree about it.
        """
        item.week_action_id = getattr(self, "week_action_id", None)
        if getattr(self, "pending_weekly_tactic_id", None):
            item.weekly_tactic_id = self.pending_weekly_tactic_id
            self._follow_chosen_tactic = True
        item.segment_description_id = getattr(self, "segment_description_id", None)

    def validate_item_for_save(self, item: ActionItem) -> Optional[str]:
        """Return the first blocking problem with ``item``, or None."""
        # Due date must be >= start date.
        if item.start_date and item.due_date:
            try:
                start = datetime.strptime(item.start_date, "%Y-%m-%d").date()
                due = datetime.strptime(item.due_date, "%Y-%m-%d").date()
                if due < start:
                    return "Error: Due date cannot be before Start date"
            except ValueError:
                # Let the validator handle invalid date formats
                pass

        errors = Validator.validate_action_item(item)
        if errors:
            return errors[0].message
        return None

    def insert_new_item(self, item: ActionItem) -> None:
        """Create the row, then apply everything that needs its id.

        Order is load-bearing and is why this is one function: the Weekly
        Tactic re-file writes its own Annual Plan Element onto the row, so the
        Project link goes LAST or the stored APE depends on which button was
        pressed (P5 — the two insert paths disagreeing is exactly what BP3 is
        about).
        """
        follow = bool(getattr(self, "_follow_chosen_tactic", False))
        self.db_manager.create_action_item(
            item, apply_defaults=True, follow_tactic=follow,
        )
        self._follow_chosen_tactic = False
        self.pending_weekly_tactic_id = None
        self.item_id = item.id
        self.item = item
        if follow:
            # follow_tactic moves the item's dates, so the in-memory copy is
            # already stale; re-read rather than display what we sent.
            self.item = self.db_manager.get_action_item(item.id) or item
        # WT-M6.B.5 — say what the cascade built, on every insert path (P25).
        notify_weekly_tactic_changes(self.db_manager, self)

        # PL3/PL4 — the Project link, last, and on both paths.
        if self._apply_project_link(item.id):
            # Linking writes the board's Annual Plan Element onto the row, so
            # re-read rather than keep a stale in-memory copy.
            self.item = self.db_manager.get_action_item(item.id) or self.item
        self.refresh_project_display()

    def _warn(self, message: str, *args) -> None:
        """Log a warning if this editor has a logger; never fail the save for it."""
        logger = getattr(self, "logger", None)
        if logger is not None:
            logger.warning(message, *args)
