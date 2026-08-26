"""
Database manager for GetMoreDone application.
Provides CRUD operations and business logic for all entities.
"""

from contextlib import contextmanager
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Tuple
import logging
import sqlite3
import re

from .database import Database
from .link_integrity import resolve_segment_id_exact
from .db_manager_project_boards import DBManagerProjectBoardsMixin
from .weekly_tactic import tactic_of
from .models import (
    ActionItem, ItemLink, ContactLink, Defaults, RescheduleHistory,
    TimeBlock, WorkLog, Status, Contact, ProjectBoard, ProjectBoardStatus, ProjectBoardLink
)
from .app_settings import AppSettings
from . import week_calendar
from .weekly_tactic_logging import get_weekly_tactic_logger

logger = get_weekly_tactic_logger()


class DatabaseManager(DBManagerProjectBoardsMixin):
    """Manages database operations for GetMoreDone."""

    # Allowed sort columns (security: prevent SQL injection)
    ALLOWED_SORT_COLUMNS = {
        "start_date", "due_date", "priority_score", "importance", "urgency",
        "size", "value", "planned_minutes", "created_at", "updated_at"
    }

    #: WT-M1.C.5 — the last week-boundary collision seen on a save, or None.
    #: Read by callers that want to tell the user why a week did not move.
    last_week_collision: Optional[Dict[str, Any]] = None

    #: WT-M4/WT-M6 — the report from the last re-file, or None. Read by the
    #: surfaces so the user sees what the cascade created (WT-M6.B.5).
    last_cascade_report: Optional[Any] = None

    #: True while a ``transaction()`` block is open. Every commit inside one is
    #: suppressed so the block is genuinely all-or-nothing (WT-M4.D).
    _in_transaction: bool = False

    _weekly_tactic_engine: Optional[Any] = None
    _vps_manager: Optional[Any] = None
    _week_calendar: Optional[Any] = None
    _cascade_batch: Optional[list] = None

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database manager.

        DB selection priority:
        1) explicit `db_path`
        2) env var GETMOREDONE_DB
        3) default per-OS app data dir
        """
        self.db = Database(db_path)
        self.db.connect()
        self.db.initialize_schema()

    @contextmanager
    def transaction(self):
        """WT-M4.D — run a block of writes as one all-or-nothing unit.

        Purpose: the scaffolding cascade creates up to eight rows across eight
                 tables. A failure part-way must leave none of them.
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4d
        Tests:   tests/test_weekly_tactic_cascade.py::test_wt_m4d1_cascade_runs_in_one_transaction

        Every creator on the cascade path takes ``commit=False`` so its own
        ``commit()`` is suppressed inside here. Without both halves the rollback
        is unbuildable: a failure at row 6 of 8 left 5 rows committed, and
        WT-M4.C.5's idempotence then adopted that half-built chain as finished
        (WT-F11).

        Re-entrant: a nested ``with`` joins the outer transaction rather than
        committing early.
        """
        conn = self.db.conn
        if self._in_transaction:
            yield conn
            return

        self._in_transaction = True
        conn.defer_commits()
        try:
            yield conn
        except BaseException:
            # BaseException, not Exception: a Ctrl-C through this block used to
            # leave the commit gate closed for the life of the process while
            # _in_transaction read False. Every later save then looked fine on
            # this connection and was discarded at close() — a green session
            # that persisted nothing.
            conn.rollback()
            raise
        else:
            # force_commit, because `finally` has not reopened the gate yet and
            # this is the one commit the gate exists to let through. Guarded:
            # raised from the `else` arm it is invisible to `except` above, and
            # a locked database would otherwise leave the cascade's writes
            # uncommitted on the connection for the next save to publish.
            try:
                conn.force_commit()
            except BaseException:
                conn.rollback()
                raise
        finally:
            # Always, on every exit path. The gate is process-wide state; it
            # must never outlive the block that closed it.
            conn.resume_commits()
            self._in_transaction = False

    def close(self):
        """Close database connection."""
        self.db.close()

    # ==================== ACTION ITEMS ====================

    def create_action_item(self, item: ActionItem, apply_defaults: bool = True,
                           refile: bool = True, follow_tactic: bool = False) -> str:
        """
        Create a new action item.

        Args:
            item: ActionItem to create
            apply_defaults: Whether to apply system/who defaults
            refile: WT-M3.A — False skips the Weekly Tactic re-file. An item
                created already attached to a tactic is an *attach*, so it is
                stamped and brought into range exactly as one made by attaching
                afterwards. Found by running the real editor: every DB test had
                attached through update_action_item, so the create path was
                never exercised and an item created attached carried no
                original-week stamp at all.

        Returns:
            ID of created item

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m3a
        Tests: tests/test_weekly_tactic_linking.py::test_wt_m3a1_attach_at_create_time_stamps_too
        """
        if apply_defaults:
            self._apply_defaults(item)

        # Stamp segment ID from linked structures when missing
        self._validate_week_item(item)
        self._validate_weekly_tactic_link(item)
        self._stamp_segment_from_relationships(item)
        self._normalize_week_item_dates(item)
        self._normalize_week_item_group(item)

        # Validate and adjust dates
        item.validate_and_adjust_dates()

        # Update priority score
        item.update_priority_score()
        item.updated_at = datetime.now().isoformat()

        if refile and tactic_of(item) and item.item_type != "week":
            # follow_tactic: WT-D1, same as update_action_item. Without it here,
            # picking a Weekly Tactic for a *new* item was silently discarded
            # and the item filed by its own start date — the fix applied to one
            # call of a class and not its sibling (P5).
            target = item.start_date
            if follow_tactic:
                chosen = self.get_action_item(tactic_of(item))
                if chosen is not None:
                    target = chosen.start_date
            with self.transaction():
                self._refile_into_weekly_tactic(item, target)
                return self._insert_action_item(item)
        self.last_cascade_report = None
        return self._insert_action_item(item)

    def _insert_action_item(self, item: ActionItem) -> str:
        """The write half of ``create_action_item``, separated for the hook.

        Raises ``sqlite3.IntegrityError`` when a week item collides on the
        WT-INV5 index. Unlike the update path there is nothing to fall back to —
        a row that does not exist yet cannot keep its previous dates — so the
        error is annotated and re-raised rather than swallowed. Callers on the
        cascade path run inside a transaction, so the whole cascade rolls back
        (WT-M1.C.5's sibling case).
        """
        try:
            return self._write_new_action_item(item)
        except sqlite3.IntegrityError as exc:
            if item.item_type == "week":
                self.last_week_collision = {
                    "item_id": item.id,
                    "kept_start": None,
                    "rejected_start": item.start_date,
                    "error": str(exc),
                }
                logger.warning(
                    "[weekly_tactic] cannot create a Weekly Tactic for %s on %s "
                    "— one already exists for that Annual Plan Element and week",
                    item.annual_plan_element_id, item.start_date,
                )
            raise

    def _write_new_action_item(self, item: ActionItem) -> str:
        self.db.conn.execute("""
            INSERT INTO action_items (
                id, who, contact_id, parent_id, weekly_tactic_id, title, description, next_action, deliverable,
                start_date, due_date,
                original_due_date, is_meeting, meeting_start_time,
                importance, urgency, size, value, priority_score,
                "group", category, planned_minutes, status, completed_at,
                week_action_id, annual_plan_element_id, item_type, segment_description_id, is_habit, percent_complete,
                today_pin_rank, weekly_tactic_start_date,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.id, item.who, item.contact_id, item.parent_id, item.weekly_tactic_id, item.title, item.description,
            item.next_action, item.deliverable,
            item.start_date, item.due_date, item.original_due_date, 1 if item.is_meeting else 0,
            item.meeting_start_time,
            item.importance, item.urgency, item.size, item.value,
            item.priority_score, item.group, item.category,
            item.planned_minutes, item.status, item.completed_at,
            item.week_action_id, item.annual_plan_element_id, item.item_type, item.segment_description_id, 1 if item.is_habit else 0,
            item.percent_complete,
            item.today_pin_rank, item.weekly_tactic_start_date,
            item.created_at, item.updated_at
        ))

        self._commit_unless_in_transaction()
        return item.id

    def get_action_item(self, item_id: str) -> Optional[ActionItem]:
        """Get action item by ID."""
        row = self.db.conn.execute(
            "SELECT * FROM action_items WHERE id = ?",
            (item_id,)
        ).fetchone()

        if row:
            return self._row_to_action_item(row)
        return None

    def update_action_item(self, item: ActionItem, normalize_week_dates: bool = True,
                           refile: bool = True, follow_tactic: bool = False) -> bool:
        """Update an existing action item.

            follow_tactic: WT-D1 — True files the item into the week of the
                Weekly Tactic it now names, rather than the week its own start
                date names, and moves its dates to match. Passed only by the
                "Set Wk Tactic" picker, which is the one place the user says
                which week they want.

                Inferring this from "the in-memory tactic differs from the
                stored one" looked equivalent and was not: the item editor holds
                the ActionItem it opened with, so anything that re-filed the row
                behind an open dialog made the next Save read as a deliberate
                choice and threw away the date the user had just typed.

            refile: WT-D12 — False skips the Weekly Tactic re-file entirely.
                Only the Google Calendar importer passes it: an imported item
                updates its dates without re-filing and without creating any
                plan record, and may sit outside its tactic's week until it is
                touched by hand.

        Returns:
            True when the item was saved as given. False when it was a week item
            whose new week is already taken: the rest of the save landed, the
            week did not move, and ``last_week_collision`` says why.

        Args:
            item: Action item to persist.
            normalize_week_dates: Retained for callers that pass it, but it no
                longer suppresses week-item snapping. A Weekly Tactic's dates
                *are* its week: WT-INV5 and the WT-M1.C unique index are both
                keyed on the week start, and the start-up normaliser snaps any
                stray week item back anyway. Leaving a week item mid-week here
                only meant the migration moved it later, silently. Day-level
                dates on ordinary items are untouched either way — the snapping
                never applied to them.

        Raises:
            ValueError: the item names a Weekly Tactic that is not a week item,
                or is a week item with no Annual Plan Element.
        """
        # Get existing item to preserve original_due_date if it exists
        existing = self.get_action_item(item.id)
        if existing is not None:
            # today_pin_rank is owned exclusively by pin_item_to_today_top (a
            # targeted, column-only update). A full-object save must never
            # change or wipe it — otherwise a stale in-memory copy (e.g. an item
            # editor opened before the item was pinned) would drop the pin on
            # Save. Always inherit the current DB value here.
            item.today_pin_rank = existing.today_pin_rank
        if existing and existing.original_due_date:
            # Preserve original_due_date - it's read-only once set
            item.original_due_date = existing.original_due_date
        else:
            # This is the first time due_date is being set
            item.validate_and_adjust_dates()

        # If due_date already existed, validate it
        if existing and existing.due_date:
            item.validate_and_adjust_dates()

        item.update_priority_score()
        item.updated_at = datetime.now().isoformat()

        self._validate_week_item(item)
        self._validate_weekly_tactic_link(item)
        self._stamp_segment_from_relationships(item)
        # WT-INV5: week items always snap. See the note on normalize_week_dates.
        self._normalize_week_item_dates(item)
        self._normalize_week_item_group(item)

        # WT-M4/WT-M5 — re-file before the write and inside one transaction, so
        # a cascade that fails part-way leaves neither the item nor its new plan
        # records behind (WT-M4.D). The re-file may move the item's dates, so it
        # has to run before they are written.
        if refile:
            target = item.start_date
            if follow_tactic:
                chosen = self.get_action_item(tactic_of(item))
                if chosen is not None:
                    target = chosen.start_date
            with self.transaction():
                self._refile_into_weekly_tactic(item, target)
                return self._save_action_item(item, existing)

        self.last_cascade_report = None
        return self._save_action_item(item, existing)

    def _save_action_item(self, item: ActionItem, existing: Optional[ActionItem]) -> bool:
        """The write half of ``update_action_item``.

        Separated so the re-file can run inside the same transaction, ahead of
        the write it changes.
        """
        # WT-M1.C.5 — cleared on every save, so a stale collision from an
        # earlier save cannot be read as this one's result. The DatabaseManager
        # is long-lived (app.py builds one for the session), so a flag that is
        # only ever set is a flag that is permanently true after the first clash.
        self.last_week_collision = None

        original_dates = (existing.start_date, existing.due_date) if existing else None
        try:
            self._write_action_item(item)
        except sqlite3.IntegrityError as exc:
            self._handle_week_collision(item, original_dates, exc)

        self._commit_unless_in_transaction()
        return self.last_week_collision is None

    def _handle_week_collision(self, item: ActionItem, original_dates, exc):
        """WT-M1.C.5 — a re-snapped week collided with an existing tactic.

        Purpose: changing ``first_day_of_week`` moves every week item's start
                 date (``_normalize_week_item_dates``), which can land two weeks
                 on the same start and violate WT-INV5.
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1c5
        Tests:   tests/test_weekly_tactic_schema.py::test_wt_m1c5_first_day_change_collision_reported

        The collision is *reported*, not raised out of an ordinary save: the
        save proceeds with the item's original dates, and the clash is recorded
        on ``last_week_collision`` and logged so it is never silent (P2). If the
        write still fails with the original dates, the error is genuinely not
        about the week move and is re-raised.

        The caller learns what happened from the return value of
        ``update_action_item``, not only from the log. A week that quietly did
        not move, reported as a clean save, is the silent-drop shape of P2 —
        the user drags a tactic onto an occupied week and nothing says no.
        """
        if item.item_type != "week" or original_dates is None:
            raise exc

        snapped = (item.start_date, item.due_date)
        if snapped == original_dates:
            # The dates did not move, so the clash is not about the week at all.
            raise exc

        item.start_date, item.due_date = original_dates
        try:
            self._write_action_item(item)
        except sqlite3.IntegrityError:
            # The original dates collide too — this was never a re-snap problem.
            item.start_date, item.due_date = snapped
            raise exc

        self.last_week_collision = {
            "item_id": item.id,
            "kept_start": original_dates[0],
            "rejected_start": snapped[0],
            "error": str(exc),
        }
        logger.warning(
            "[weekly_tactic] week item %s could not move to %s — a tactic "
            "already occupies that week for this Annual Plan Element; kept %s",
            item.id, snapped[0], original_dates[0],
        )

    def _write_action_item(self, item: ActionItem):
        """The UPDATE itself, so the collision path can retry it."""
        self.db.conn.execute("""
            UPDATE action_items SET
                who = ?, contact_id = ?, parent_id = ?, weekly_tactic_id = ?, title = ?, description = ?, next_action = ?,
                deliverable = ?,
                start_date = ?, due_date = ?, original_due_date = ?, is_meeting = ?, meeting_start_time = ?,
                importance = ?, urgency = ?, size = ?, value = ?,
                priority_score = ?, "group" = ?, category = ?,
                planned_minutes = ?, status = ?, completed_at = ?,
                week_action_id = ?, annual_plan_element_id = ?, item_type = ?, segment_description_id = ?, is_habit = ?, percent_complete = ?,
                today_pin_rank = ?, weekly_tactic_start_date = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            item.who, item.contact_id, item.parent_id, item.weekly_tactic_id, item.title, item.description, item.next_action,
            item.deliverable,
            item.start_date, item.due_date, item.original_due_date, 1 if item.is_meeting else 0,
            item.meeting_start_time,
            item.importance, item.urgency, item.size, item.value,
            item.priority_score, item.group, item.category,
            item.planned_minutes, item.status, item.completed_at,
            item.week_action_id, item.annual_plan_element_id, item.item_type, item.segment_description_id, 1 if item.is_habit else 0,
            item.percent_complete,
            item.today_pin_rank, item.weekly_tactic_start_date,
            item.updated_at, item.id
        ))

    def attach_vps_manager(self, vps_manager) -> None:
        """Adopt an existing VPSManager for the re-filing engine (WT-M4)."""
        self._vps_manager = vps_manager
        if self._weekly_tactic_engine is not None:
            self._weekly_tactic_engine._vps = vps_manager

    @property
    def weekly_tactic_engine(self):
        """The re-filing engine, built lazily on this connection.

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6
        Tests: tests/test_weekly_tactic_cascade.py
        """
        if self._weekly_tactic_engine is None:
            from .weekly_tactic import WeeklyTacticEngine
            self._weekly_tactic_engine = WeeklyTacticEngine(
                self, self._vps_manager, calendar=self.week_calendar
            )
            return self._weekly_tactic_engine
        # Reading the property is what pushes a changed setting onto the cached
        # engine. Refreshing only when a *week item* was saved meant the first
        # ordinary save after the setting changed still used the old boundary.
        self.week_calendar
        return self._weekly_tactic_engine

    @contextmanager
    def batch_cascade(self):
        """Accumulate cascade reports across a loop into one.

        Purpose: a screen that moves N items in a loop would otherwise show only
                 the last item's report — and because the cascade is idempotent
                 the last item creates nothing.
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6b5
        Tests:   tests/test_weekly_tactic_surfaces.py::test_wt_m6b5_a_batch_reports_every_item
        """
        from .weekly_tactic import CascadeReport

        previous, self._cascade_batch = self._cascade_batch, []
        try:
            yield
        finally:
            collected = self._cascade_batch
            self._cascade_batch = previous
            self.last_cascade_report = CascadeReport.merge(collected)

    def _refile_into_weekly_tactic(self, item: ActionItem, target_date) -> None:
        """WT-M4 — re-file ``item`` for ``target_date`` if it has a tactic.

        Purpose: the single hook. Screens are not individually wired; they all
                 reach this through update/reschedule/bulk (WT-M6).
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6
        Tests:   tests/test_weekly_tactic_surfaces.py

        An item with no Weekly Tactic is left completely alone (WT-INV6) — the
        engine's own predicate decides that, so there is exactly one answer to
        "is this item week-filed" in the codebase.
        """
        from .weekly_tactic import tactic_of

        if item.item_type == "week" or not tactic_of(item):
            self.last_cascade_report = None
            if self._cascade_batch is not None:
                self._cascade_batch.append(None)
            return

        report = self.weekly_tactic_engine.plan_refile(item, target_date)
        self.last_cascade_report = report
        if self._cascade_batch is not None:
            self._cascade_batch.append(report)

    def _commit_unless_in_transaction(self):
        """Commit, unless a ``transaction()`` block owns the unit of work."""
        if not self._in_transaction:
            self.db.conn.commit()

    def delete_action_item(self, item_id: str):
        """Delete action item (cascades to links, logs, etc.)."""
        self.db.conn.execute("DELETE FROM action_items WHERE id = ?", (item_id,))
        self.db.conn.commit()

    def complete_action_item(self, item_id: str) -> bool:
        """
        Mark action item as completed.

        Returns:
            True if the item was found and saved as given. False if it was not
            found, or if it was a week item whose week could not move — see
            ``last_week_collision``.
        """
        # Cleared first: this manager lives for the session, so a report that
        # is only ever set is a report the next save re-shows (P6). The same
        # reasoning already applied to last_week_collision.
        self.last_cascade_report = None

        item = self.get_action_item(item_id)
        if not item:
            return False

        before = self.get_action_item(item_id)
        item.status = Status.COMPLETED
        item.completed_at = datetime.now().isoformat()

        # WT-M5.A — a completed item is re-filed to the week it was completed
        # in, not the week it was planned for. completed_at is a full ISO
        # datetime (see above), so only its date part names a week.
        if tactic_of(item):
            with self.transaction():
                self._refile_into_weekly_tactic(item, item.completed_at[:10])
                # The same preamble the ordinary save runs. Calling
                # _save_action_item directly skipped all of it, so a completed
                # item's updated_at claimed the row had not been touched while
                # its status, completed_at and both dates had changed.
                self._validate_week_item(item)
                self._validate_weekly_tactic_link(item)
                self._stamp_segment_from_relationships(item)
                self._normalize_week_item_group(item)
                item.update_priority_score()
                item.updated_at = datetime.now().isoformat()
                moved = self._save_action_item(item, self.get_action_item(item_id))
                self._record_completion_refile(item_id, before, item)
                return moved

        return self.update_action_item(item, normalize_week_dates=False)

    def _record_completion_refile(self, item_id: str, before: ActionItem,
                                  after: ActionItem) -> None:
        """WT-M5.A.6 — keep the planned start day recoverable after a re-file.

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m5a6
        Tests: tests/test_weekly_tactic_completion.py::test_wt_m5a6_completion_refile_records_history

        Push-out is tracked at the day grain by reschedule_history (WT-F8), and
        completion re-filing moves the start date. Without this row the planned
        day is gone.
        """
        if (before.start_date, before.due_date) == (after.start_date, after.due_date):
            return
        self._record_reschedule(
            item_id, before.start_date, before.due_date,
            after.start_date, after.due_date, "completion_refile",
        )

    def uncomplete_action_item(self, item_id: str) -> bool:
        """
        Reopen a completed action item (mark as open).

        Returns:
            True if item was found and reopened
        """
        item = self.get_action_item(item_id)
        if not item:
            return False

        item.status = Status.OPEN
        # Keep completed_at for historical tracking
        self.update_action_item(item)
        return True

    def bulk_update_action_items(self, item_ids: List[str], start_date: Optional[str] = None, priority: Optional[int] = None):
        """
        Update multiple action items with the same start_date and/or priority.
        Only specified fields are updated; others are preserved.
        If start_date is provided, due_date is set to start_date + 1 day.

        Args:
            item_ids: List of action item IDs to update
            start_date: New start date (ISO format YYYY-MM-DD), or None to skip
            priority: New importance/priority value, or None to skip

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6b2
        Tests: tests/test_weekly_tactic_surfaces.py::test_wt_m6b2_bulk_edit_respects_week_bounds
        """
        with self.batch_cascade():
            self._bulk_update(item_ids, start_date, priority)

    def _bulk_update(self, item_ids, start_date, priority):
        for item_id in item_ids:
            item = self.get_action_item(item_id)
            if not item:
                continue

            # Update fields if provided
            if start_date:
                item.start_date = start_date
                # Auto-calculate due_date as start_date + 1 day, then clamp it
                # into the week when the item is week-filed. WT-M6.B.2: without
                # the clamp, a start on a week's last day guarantees a WT-INV2
                # violation on every bulk edit.
                from datetime import date as date_class
                start = date_class.fromisoformat(start_date)
                due = start + timedelta(days=1)
                if tactic_of(item):
                    week_end = self.week_calendar.end(start)
                    if week_end and due > week_end:
                        due = week_end
                item.due_date = due.isoformat()

            if priority is not None:
                item.importance = priority

            # Persist the item
            self.update_action_item(item, normalize_week_dates=False)

    def duplicate_action_item(self, item_id: str) -> Optional[str]:
        """
        Duplicate an action item (creates new item with same fields and linked notes).

        Returns:
            ID of new item, or None if original not found
        """
        original = self.get_action_item(item_id)
        if not original:
            return None

        # Create new item with same fields
        new_item = ActionItem(
            who=original.who,
            contact_id=original.contact_id,
            title=original.title,
            description=original.description,
            start_date=original.start_date,
            due_date=original.due_date,
            importance=original.importance,
            urgency=original.urgency,
            size=original.size,
            value=original.value,
            group=original.group,
            category=original.category,
            planned_minutes=original.planned_minutes
        )

        new_id = self.create_action_item(new_item, apply_defaults=False)

        # Duplicate linked notes and other links
        if new_id:
            original_links = self.get_item_links(item_id)
            for link in original_links:
                # Create a new link with the same properties but new ID and item_id
                new_link = ItemLink(
                    item_id=new_id,
                    url=link.url,
                    label=link.label,
                    link_type=link.link_type
                )
                self.add_item_link(new_link)

        return new_id

    def _inherit_weekly_lineage(self, source_id: str, new_id: str) -> None:
        """WT-M5.C.1 — carry the week lineage onto an item made from another.

        Purpose: ``create_followup_item`` builds its copy through a constructor
                 that never mentions ``weekly_tactic_id``,
                 ``annual_plan_element_id`` or ``segment_description_id``, so a
                 follow-up silently lost its place in the plan.
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m5c
        Tests:   tests/test_weekly_tactic_completion.py::test_wt_m5c1_create_followup_item_also_inherits

        The copy is then re-filed for its own start date, so it satisfies
        WT-INV1/2 for whichever week it actually lands in.
        """
        source = self.get_action_item(source_id)
        copy = self.get_action_item(new_id)
        if not source or not copy:
            return
        if not tactic_of(source):
            return

        copy.weekly_tactic_id = source.weekly_tactic_id
        copy.annual_plan_element_id = source.annual_plan_element_id
        copy.segment_description_id = source.segment_description_id
        # The stamp belongs to the original item's history, not the copy's.
        copy.weekly_tactic_start_date = None
        self.update_action_item(copy)

    def create_followup_item(self, item_id: str) -> Optional[str]:
        """
        Create a follow-up Action Item linked to the original item.
        Useful when an item isn't completed and needs to be rescheduled.

        The new item will:
        - Inherit properties from the original
        - Be linked via parent_id to the original
        - Have dates shifted forward by 1 day
        - Status set to "open"

        Returns:
            ID of new follow-up item, or None if original not found
        """
        from datetime import datetime, timedelta

        original = self.get_action_item(item_id)
        if not original:
            return None

        # Calculate new dates (shift by 1 day)
        new_start_date = None
        new_due_date = None

        if original.start_date:
            start_dt = datetime.fromisoformat(original.start_date)
            new_start_date = (start_dt + timedelta(days=1)).date().isoformat()

        if original.due_date:
            due_dt = datetime.fromisoformat(original.due_date)
            new_due_date = (due_dt + timedelta(days=1)).date().isoformat()

        # Create new item with same properties
        new_item = ActionItem(
            who=original.who,
            contact_id=original.contact_id,
            title=original.title,
            description=original.description,
            next_action=original.next_action,
            parent_id=item_id,  # Link to original item
            start_date=new_start_date,
            due_date=new_due_date,
            importance=original.importance,
            urgency=original.urgency,
            size=original.size,
            value=original.value,
            group=original.group,
            category=original.category,
            planned_minutes=original.planned_minutes,
            week_action_id=original.week_action_id,
            segment_description_id=original.segment_description_id,
            is_habit=original.is_habit,
            status="open"  # Explicitly set to open
        )

        new_id = self.create_action_item(new_item, apply_defaults=False)
        if new_id:
            self.inherit_derived_item_context(item_id, new_id)

        return new_id

    def inherit_derived_item_context(self, source_id: str, new_id: str) -> None:
        """Carry everything an item made from another one should keep.

        Purpose: B1 — there are two places that build an item out of an
                 existing one, and they disagreed about what "out of" means.
                 ``create_followup_item`` inherited the weekly lineage, the
                 project links and the item links; the timer's
                 Complete & Create Follow Up built its row inline and inherited
                 none of them, so its follow-up landed unfiled from the project
                 it continues. Time that follow-up later and the reward
                 protocol resolves no board — no phase, no counter, no signal.
        Tests:   tests/test_timer_session_endings.py::test_b11_the_followup_stays_filed_under_its_project
                 tests/test_timer_session_endings.py::test_b12_the_followup_keeps_its_weekly_lineage
                 tests/test_timer_session_endings.py::test_b13_the_followup_keeps_its_links
                 tests/test_timer_session_endings.py::test_b14_both_followup_paths_inherit_through_the_same_helper

        One piece of code rather than two lists that drift. They already had:
        ``inherit_project_links``' own docstring names the complete-and-create
        path as a case it covers, and nothing on that path ever called it.

        Deliberately not a fix by routing the timer through
        ``create_followup_item``: that always parents the copy to its source,
        while the timer makes a *sibling* when the source already has a parent.
        Sharing the inheritance keeps that difference intact.
        """
        self._inherit_weekly_lineage(source_id, new_id)
        # PL12 — a copy of a project task stays filed under that project, the
        # way it already keeps its weekly lineage.
        self.inherit_project_links(source_id, new_id)

        for link in self.get_item_links(source_id):
            self.add_item_link(ItemLink(
                item_id=new_id,
                url=link.url,
                label=link.label,
                link_type=link.link_type,
            ))

    # ==================== HIERARCHICAL OPERATIONS ====================

    def get_children(self, parent_id: str) -> List[ActionItem]:
        """
        Get direct children of a parent item.

        Args:
            parent_id: ID of the parent item

        Returns:
            List of child items sorted by priority_score descending
        """
        rows = self.db.conn.execute("""
            SELECT * FROM action_items
            WHERE parent_id = ?
            ORDER BY priority_score DESC, created_at ASC
        """, (parent_id,)).fetchall()

        return [self._row_to_action_item(row) for row in rows]

    def get_subtree(self, item_id: str) -> List[ActionItem]:
        """
        Get full subtree (all descendants) of an item.

        Args:
            item_id: ID of the root item

        Returns:
            List of all descendant items in breadth-first order
        """
        result = []
        queue = [item_id]

        while queue:
            current_id = queue.pop(0)
            children = self.get_children(current_id)
            result.extend(children)
            queue.extend([child.id for child in children])

        return result

    def get_root_items(self, status_filter: Optional[str] = None) -> List[ActionItem]:
        """
        Get all items that have no parent (root items).

        Args:
            status_filter: Optional status filter ('open', 'completed')

        Returns:
            List of root items sorted by priority_score descending
        """
        query = """
            SELECT * FROM action_items
            WHERE parent_id IS NULL
        """
        params = []

        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        query += " ORDER BY priority_score DESC, created_at ASC"

        rows = self.db.conn.execute(query, params).fetchall()
        return [self._row_to_action_item(row) for row in rows]

    # ==================== QUERYING ====================

    def get_upcoming_items(
        self,
        n_days: int = 7,
        who_filter: Optional[str] = None
    ) -> List[ActionItem]:
        """
        Get open items by START date within N days from now (includes ALL overdue starts).

        Shows items that are:
        - Past start date by ANY amount (all overdue starts)
        - Start date within the next N days (default 7)

        Uses start_date if available, falls back to due_date if not.

        Formula: COALESCE(start_date, due_date) <= today + N days

        This ensures NO overdue items are hidden, no matter how old.

        Args:
            n_days: Number of days ahead to look (default 7)
            who_filter: Optional who filter

        Returns:
            List of items sorted by start_date (or due_date if no start), then priority_score
        """
        query = """
            SELECT * FROM action_items
            WHERE status = 'open'
              AND (start_date IS NOT NULL OR due_date IS NOT NULL)
              AND COALESCE(start_date, due_date) <= date('now', '+' || ? || ' days')
        """
        params = [n_days]

        if who_filter:
            query += " AND LOWER(TRIM(COALESCE(who, ''))) = LOWER(TRIM(?))"
            params.append(who_filter)

        query += " ORDER BY COALESCE(start_date, due_date) ASC, priority_score DESC, created_at ASC"

        rows = self.db.conn.execute(query, params).fetchall()
        return [self._row_to_action_item(row) for row in rows]

    def get_all_items(
        self,
        status_filter: Optional[str] = None,
        who_filter: Optional[str] = None,
        group_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        sort_by: str = "start_date",
        sort_desc: bool = False
    ) -> List[ActionItem]:
        """
        Get all action items with optional filtering and sorting.

        Args:
            status_filter: Filter by status (open, completed, canceled)
            who_filter: Filter by who
            group_filter: Filter by group
            category_filter: Filter by category
            sort_by: Column to sort by (must be in ALLOWED_SORT_COLUMNS), default is start_date
            sort_desc: Sort descending if True

        Returns:
            List of filtered/sorted items
        """
        # Validate sort column
        if sort_by not in self.ALLOWED_SORT_COLUMNS:
            sort_by = "start_date"

        query = "SELECT * FROM action_items WHERE 1=1"
        params = []

        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        if who_filter:
            query += " AND LOWER(TRIM(COALESCE(who, ''))) = LOWER(TRIM(?))"
            params.append(who_filter)

        if group_filter:
            query += ' AND "group" = ?'
            params.append(group_filter)

        if category_filter:
            query += " AND category = ?"
            params.append(category_filter)

        direction = "DESC" if sort_desc else "ASC"
        query += f" ORDER BY {sort_by} {direction}"

        rows = self.db.conn.execute(query, params).fetchall()
        return [self._row_to_action_item(row) for row in rows]

    def get_completed_items(
        self,
        days_back: int = 30,
        who_filter: Optional[str] = None
    ) -> List[ActionItem]:
        """Get completed items from last N days."""
        query = """
            SELECT * FROM action_items
            WHERE status = 'completed'
              AND completed_at >= datetime('now', '-' || ? || ' days')
        """
        params = [days_back]

        if who_filter:
            query += " AND LOWER(TRIM(COALESCE(who, ''))) = LOWER(TRIM(?))"
            params.append(who_filter)

        query += " ORDER BY completed_at DESC"

        rows = self.db.conn.execute(query, params).fetchall()
        return [self._row_to_action_item(row) for row in rows]

    def search_items(self, search_text: str) -> List[ActionItem]:
        """Search items by title, description, next_action, or who."""
        query = """
            SELECT * FROM action_items
            WHERE title LIKE ? OR description LIKE ? OR next_action LIKE ? OR who LIKE ?
            ORDER BY priority_score DESC
        """
        pattern = f"%{search_text}%"
        rows = self.db.conn.execute(query, (pattern, pattern, pattern, pattern)).fetchall()
        return [self._row_to_action_item(row) for row in rows]

    # ==================== PROJECT BOARDS ====================

    # ==================== DEFAULTS ====================


    def get_defaults(self, scope_type: str, scope_key: Optional[str] = None) -> Optional[Defaults]:
        """Get defaults for given scope."""
        if scope_type == "system":
            scope_key = None

        # SQLite requires special handling for NULL comparisons
        if scope_key is None:
            row = self.db.conn.execute(
                "SELECT * FROM defaults WHERE scope_type = ? AND scope_key IS NULL",
                (scope_type,)
            ).fetchone()
        else:
            row = self.db.conn.execute(
                "SELECT * FROM defaults WHERE scope_type = ? AND scope_key = ?",
                (scope_type, scope_key)
            ).fetchone()

        if row:
            return self._row_to_defaults(row)
        return None

    def save_defaults(self, defaults: Defaults):
        """Save or update defaults."""
        # SQLite treats NULL != NULL, so INSERT OR REPLACE doesn't work properly
        # with NULL in PRIMARY KEY. We need to DELETE first, then INSERT.

        # Delete any existing row with the same scope
        if defaults.scope_key is None:
            self.db.conn.execute(
                "DELETE FROM defaults WHERE scope_type = ? AND scope_key IS NULL",
                (defaults.scope_type,)
            )
        else:
            self.db.conn.execute(
                "DELETE FROM defaults WHERE scope_type = ? AND scope_key = ?",
                (defaults.scope_type, defaults.scope_key)
            )

        # Insert the new defaults
        self.db.conn.execute("""
            INSERT INTO defaults (
                scope_type, scope_key, contact_id, who, importance, urgency, size, value,
                "group", category, planned_minutes, start_offset_days, due_offset_days,
                near_term_offset_days, long_term_offset_days, next_month_offset_days, next_quarter_offset_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            defaults.scope_type, defaults.scope_key, defaults.contact_id, defaults.who,
            defaults.importance, defaults.urgency, defaults.size, defaults.value,
            defaults.group, defaults.category, defaults.planned_minutes,
            defaults.start_offset_days, defaults.due_offset_days,
            defaults.near_term_offset_days, defaults.long_term_offset_days,
            defaults.next_month_offset_days, defaults.next_quarter_offset_days
        ))
        self.db.conn.commit()

    def get_all_who_defaults(self) -> List[Defaults]:
        """Get all who-specific defaults."""
        rows = self.db.conn.execute(
            "SELECT * FROM defaults WHERE scope_type = 'who' ORDER BY scope_key"
        ).fetchall()
        return [self._row_to_defaults(row) for row in rows]

    def _apply_defaults(self, item: ActionItem):
        """Apply system and who defaults to an action item."""
        # Get system defaults
        system_defaults = self.get_defaults("system")

        # Apply WHO default from system defaults if item.who is empty or None
        if not item.who or not item.who.strip():
            if system_defaults and system_defaults.who:
                item.who = system_defaults.who

        # Get who-specific defaults
        who_defaults = self.get_defaults("who", item.who)

        # Apply defaults with proper precedence: who > system
        # For each field, use: item value > who default > system default

        if item.importance is None:
            if who_defaults and who_defaults.importance is not None:
                item.importance = who_defaults.importance
            elif system_defaults and system_defaults.importance is not None:
                item.importance = system_defaults.importance

        if item.urgency is None:
            if who_defaults and who_defaults.urgency is not None:
                item.urgency = who_defaults.urgency
            elif system_defaults and system_defaults.urgency is not None:
                item.urgency = system_defaults.urgency

        if item.size is None:
            if who_defaults and who_defaults.size is not None:
                item.size = who_defaults.size
            elif system_defaults and system_defaults.size is not None:
                item.size = system_defaults.size

        if item.value is None:
            if who_defaults and who_defaults.value is not None:
                item.value = who_defaults.value
            elif system_defaults and system_defaults.value is not None:
                item.value = system_defaults.value

        if item.group is None:
            if who_defaults and who_defaults.group is not None:
                item.group = who_defaults.group
            elif system_defaults and system_defaults.group is not None:
                item.group = system_defaults.group

        if item.category is None:
            if who_defaults and who_defaults.category is not None:
                item.category = who_defaults.category
            elif system_defaults and system_defaults.category is not None:
                item.category = system_defaults.category

        if item.planned_minutes is None:
            if who_defaults and who_defaults.planned_minutes is not None:
                item.planned_minutes = who_defaults.planned_minutes
            elif system_defaults and system_defaults.planned_minutes is not None:
                item.planned_minutes = system_defaults.planned_minutes

    # ==================== RESCHEDULE ====================

    def reschedule_item(
        self,
        item_id: str,
        new_start: Optional[str],
        new_due: Optional[str],
        reason: Optional[str] = None
    ) -> bool:
        """Reschedule an item and record history.

        Returns:
            True when the item now holds the requested dates. False when it does
            not — the item was a week item whose target week is already taken,
            and ``last_week_collision`` says which.

        The history row is written from the dates the item actually ends up
        with, after the save. Writing it first recorded a date the item never
        held: a week item snaps to its week boundary, so rescheduling one to a
        Wednesday used to leave ``to_start`` claiming that Wednesday while the
        item sat on the Monday.
        """
        self.last_cascade_report = None

        item = self.get_action_item(item_id)
        if not item:
            return False

        from_start, from_due = item.start_date, item.due_date

        # Weekly linked items should update the shared week_action date range.
        if item.item_type == "week" and item.week_action_id:
            target_start = new_start
            target_due = new_due

            wa = self.db.conn.execute(
                "SELECT week_start_date, week_end_date FROM week_actions WHERE id = ?",
                (item.week_action_id,),
            ).fetchone()
            if wa:
                target_start = target_start or wa["week_start_date"]
                target_due = target_due or wa["week_end_date"]

            target_start = target_start or item.start_date
            target_due = target_due or item.due_date
            now = datetime.now().isoformat()

            self.db.conn.execute(
                """
                UPDATE week_actions
                SET week_start_date = ?, week_end_date = ?, updated_at = ?
                WHERE id = ?
                """,
                (target_start, target_due, now, item.week_action_id),
            )
            self.db.conn.execute(
                """
                UPDATE action_items
                SET start_date = ?, due_date = ?, updated_at = ?
                WHERE week_action_id = ? AND item_type = 'week'
                """,
                (target_start, target_due, now, item.week_action_id),
            )
            self._record_reschedule(item_id, from_start, from_due,
                                    target_start, target_due, reason)
            self._commit_unless_in_transaction()
            return True

        # Update item
        item.start_date = new_start
        item.due_date = new_due
        moved = self.update_action_item(item, normalize_week_dates=False)

        saved = self.get_action_item(item_id)
        self._record_reschedule(
            item_id, from_start, from_due,
            saved.start_date if saved else new_start,
            saved.due_date if saved else new_due,
            reason,
        )
        self._commit_unless_in_transaction()
        return moved

    def _record_reschedule(self, item_id, from_start, from_due, to_start, to_due, reason):
        """Write one reschedule_history row.

        Called with the dates the item actually holds, never the ones that were
        merely requested — an audit row that disagrees with the item is worse
        than none (P6).
        """
        history = RescheduleHistory(
            item_id=item_id,
            from_start=from_start,
            from_due=from_due,
            to_start=to_start,
            to_due=to_due,
            reason=reason,
        )
        self.db.conn.execute("""
            INSERT INTO reschedule_history (
                id, item_id, from_start, from_due, to_start, to_due, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            history.id, history.item_id, history.from_start, history.from_due,
            history.to_start, history.to_due, history.reason, history.created_at
        ))

    def pin_item_to_today_top(self, item_id: str) -> bool:
        """Pin an item to the top of the Today list.

        Assigns a ``today_pin_rank`` one greater than the current maximum across
        all open items, so this item sorts above every other Today row (and above
        any previously pinned item). The pin is independent of ``priority_score``
        (which stays equal to importance x urgency x size x value) and survives
        later edits, since it is only ever changed here.

        Returns:
            True if the item was found and pinned.
        """
        row = self.db.conn.execute(
            "SELECT MAX(today_pin_rank) AS max_rank FROM action_items WHERE status = 'open'"
        ).fetchone()
        current_max = row["max_rank"] if row and row["max_rank"] is not None else 0
        new_rank = current_max + 1

        cursor = self.db.conn.execute(
            "UPDATE action_items SET today_pin_rank = ?, updated_at = ? WHERE id = ?",
            (new_rank, datetime.now().isoformat(), item_id),
        )
        self.db.conn.commit()
        return cursor.rowcount > 0

    # ==================== LINKS ====================

    def add_item_link(self, link: ItemLink):
        """Add a link to an action item."""
        self.db.conn.execute("""
            INSERT INTO item_links (id, item_id, label, url, link_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (link.id, link.item_id, link.label, link.url, link.link_type, link.created_at))
        self.db.conn.commit()

    def get_item_links(self, item_id: str) -> List[ItemLink]:
        """Get all links for an action item."""
        rows = self.db.conn.execute(
            "SELECT * FROM item_links WHERE item_id = ? ORDER BY created_at",
            (item_id,)
        ).fetchall()
        return [self._row_to_item_link(row) for row in rows]

    def delete_item_link(self, link_id: str):
        """Delete a link."""
        self.db.conn.execute("DELETE FROM item_links WHERE id = ?", (link_id,))
        self.db.conn.commit()

    # ==================== TIME BLOCKS ====================

    def create_time_block(self, block: TimeBlock) -> str:
        """Create a time block."""
        self.db.conn.execute("""
            INSERT INTO time_blocks (
                id, item_id, block_date, start_time, end_time,
                planned_minutes, label, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            block.id, block.item_id, block.block_date,
            block.start_time, block.end_time, block.planned_minutes,
            block.label, block.created_at, block.updated_at
        ))
        self.db.conn.commit()
        return block.id

    def get_time_blocks(self, block_date: str) -> List[TimeBlock]:
        """Get all time blocks for a specific date."""
        rows = self.db.conn.execute(
            "SELECT * FROM time_blocks WHERE block_date = ? ORDER BY start_time",
            (block_date,)
        ).fetchall()
        return [self._row_to_time_block(row) for row in rows]

    def delete_time_block(self, block_id: str):
        """Delete a time block."""
        self.db.conn.execute("DELETE FROM time_blocks WHERE id = ?", (block_id,))
        self.db.conn.commit()

    # ==================== WORK LOGS ====================

    def create_work_log(self, log: WorkLog) -> str:
        """Create a work log entry.

        Purpose: RP-2.4 — persist the session, including the reward-protocol
                 audit trail when the session ran through the reward path.
        Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#22-work_logs--add-reward-protocol-audit-columns
        Tests:   tests/test_reward_protocol_schema.py::test_rp24_work_log_reward_fields_round_trip
        """
        self.db.conn.execute("""
            INSERT INTO work_logs (
                id, item_id, started_at, ended_at, minutes, note,
                deliverable_snapshot, deliverable_completed, savor_delivered,
                celebration_type, phase,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log.id, log.item_id, log.started_at, log.ended_at,
            log.minutes, log.note,
            log.deliverable_snapshot,
            1 if log.deliverable_completed else 0,
            1 if log.savor_delivered else 0,
            log.celebration_type, log.phase,
            log.created_at
        ))
        self.db.conn.commit()
        return log.id

    def get_work_logs(self, item_id: str) -> List[WorkLog]:
        """Get all work logs for an action item."""
        rows = self.db.conn.execute(
            "SELECT * FROM work_logs WHERE item_id = ? ORDER BY started_at",
            (item_id,)
        ).fetchall()
        return [self._row_to_work_log(row) for row in rows]

    def get_total_actual_minutes(self, item_id: str) -> int:
        """Get total actual minutes logged for an item."""
        result = self.db.conn.execute(
            "SELECT SUM(minutes) FROM work_logs WHERE item_id = ?",
            (item_id,)
        ).fetchone()
        return result[0] or 0

    # ==================== STATS ====================

    def get_planned_vs_actual_stats(self) -> List[Dict[str, Any]]:
        """
        Get planned vs actual statistics for all items with work logs.

        Returns:
            List of dicts with item info, planned minutes, and actual minutes
        """
        query = """
            SELECT
                ai.id,
                ai.title,
                ai.who,
                ai.category,
                ai.size,
                ai.planned_minutes,
                COALESCE(SUM(wl.minutes), 0) as actual_minutes
            FROM action_items ai
            LEFT JOIN work_logs wl ON ai.id = wl.item_id
            WHERE ai.planned_minutes IS NOT NULL
            GROUP BY ai.id
            ORDER BY ai.updated_at DESC
        """
        rows = self.db.conn.execute(query).fetchall()

        stats = []
        for row in rows:
            stats.append({
                "id": row["id"],
                "title": row["title"],
                "who": row["who"],
                "category": row["category"],
                "size": row["size"],
                "planned_minutes": row["planned_minutes"],
                "actual_minutes": row["actual_minutes"],
                "variance": row["actual_minutes"] - (row["planned_minutes"] or 0)
            })

        return stats

    # ==================== UTILITY ====================

    def get_distinct_who_values(self) -> List[str]:
        """Get all distinct 'who' values from action items."""
        rows = self.db.conn.execute(
            "SELECT DISTINCT who FROM action_items ORDER BY who"
        ).fetchall()
        return [row["who"] for row in rows]

    def get_distinct_groups(self) -> List[str]:
        """Get all distinct group values."""
        rows = self.db.conn.execute(
            'SELECT DISTINCT "group" FROM action_items WHERE "group" IS NOT NULL ORDER BY "group"'
        ).fetchall()
        return [row["group"] for row in rows]

    def get_distinct_categories(self) -> List[str]:
        """Get all distinct category values."""
        rows = self.db.conn.execute(
            "SELECT DISTINCT category FROM action_items WHERE category IS NOT NULL ORDER BY category"
        ).fetchall()
        return [row["category"] for row in rows]

    def update_organizational_factor(self, factor_type: str, old_value: str, new_value: str):
        """Update an organizational factor value across all items."""
        if factor_type == "group":
            self.db.conn.execute(
                'UPDATE action_items SET "group" = ? WHERE "group" = ?',
                (new_value, old_value)
            )
        elif factor_type == "category":
            self.db.conn.execute(
                'UPDATE action_items SET category = ? WHERE category = ?',
                (new_value, old_value)
            )
        self.db.conn.commit()

    def delete_organizational_factor(self, factor_type: str, value: str, replacement: Optional[str]):
        """Delete an organizational factor value, optionally replacing with another value."""
        if factor_type == "group":
            if replacement is None:
                # Clear the value
                self.db.conn.execute(
                    'UPDATE action_items SET "group" = NULL WHERE "group" = ?',
                    (value,)
                )
            else:
                # Replace with another value
                self.db.conn.execute(
                    'UPDATE action_items SET "group" = ? WHERE "group" = ?',
                    (replacement, value)
                )
        elif factor_type == "category":
            if replacement is None:
                # Clear the value
                self.db.conn.execute(
                    'UPDATE action_items SET category = NULL WHERE category = ?',
                    (value,)
                )
            else:
                # Replace with another value
                self.db.conn.execute(
                    'UPDATE action_items SET category = ? WHERE category = ?',
                    (replacement, value)
                )
        self.db.conn.commit()

    # ==================== CONTACTS ====================

    def create_contact(self, contact: Contact) -> int:
        """
        Create a new contact.

        Returns:
            ID of created contact
        """
        contact.updated_at = datetime.now().isoformat()

        cursor = self.db.conn.execute("""
            INSERT INTO contacts (
                name, contact_type, email, phone, notes, is_active,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            contact.name, contact.contact_type, contact.email,
            contact.phone, contact.notes, 1 if contact.is_active else 0,
            contact.created_at, contact.updated_at
        ))

        self.db.conn.commit()
        return cursor.lastrowid

    def get_contact(self, contact_id: int) -> Optional[Contact]:
        """Get contact by ID."""
        row = self.db.conn.execute(
            "SELECT * FROM contacts WHERE id = ?",
            (contact_id,)
        ).fetchone()

        if row:
            return self._row_to_contact(row)
        return None

    def get_contact_by_name(self, name: str) -> Optional[Contact]:
        """Get contact by name (case-sensitive exact match)."""
        row = self.db.conn.execute(
            "SELECT * FROM contacts WHERE name = ?",
            (name,)
        ).fetchone()

        if row:
            return self._row_to_contact(row)
        return None

    def get_all_contacts(self, active_only: bool = True) -> List[Contact]:
        """
        Get all contacts.

        Args:
            active_only: If True, only return active contacts

        Returns:
            List of contacts sorted by name
        """
        query = "SELECT * FROM contacts"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY name"

        rows = self.db.conn.execute(query).fetchall()
        return [self._row_to_contact(row) for row in rows]

    # ==================== INTERNAL HELPERS ====================

    def _validate_weekly_tactic_link(self, item: ActionItem):
        """WT-INV4 — a weekly_tactic_id must name an existing item_type='week' row.

        Purpose: keep the tactic link from pointing at an ordinary daily item,
                 which would make "which week is this filed under" unanswerable.
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1d3
        Tests:   tests/test_weekly_tactic_link_migration.py::test_wt_m1d3_tactic_must_be_week_item

        SQLite cannot express this as a CHECK on an existing table, so it is
        enforced here — on every write path, not only the editor.
        """
        if not item.weekly_tactic_id:
            return
        if item.weekly_tactic_id == item.id:
            raise ValueError("An item cannot be its own Weekly Tactic.")
        row = self.db.conn.execute(
            "SELECT item_type FROM action_items WHERE id = ?",
            (item.weekly_tactic_id,),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Weekly Tactic {item.weekly_tactic_id!r} does not exist."
            )
        if row["item_type"] != "week":
            raise ValueError(
                f"Weekly Tactic {item.weekly_tactic_id!r} is not a week item "
                f"(item_type={row['item_type']!r})."
            )

    def _validate_week_item(self, item: ActionItem):
        """WT-M1.C.4 — a week item must name an Annual Plan Element.

        Purpose: SQLite treats NULLs as distinct, so a week item with a NULL APE
                 slips straight past the WT-INV5 unique index. Requiring the APE
                 is what makes the index mean what the invariant says.
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1c4
        Tests:   tests/test_weekly_tactic_schema.py::test_wt_m1c4_week_item_requires_ape
        """
        if item.item_type == "week" and not item.annual_plan_element_id:
            raise ValueError(
                "A Weekly Tactic must belong to an Annual Plan Element "
                "(annual_plan_element_id is required for item_type='week')."
            )

    def _stamp_segment_from_relationships(self, item: ActionItem):
        """Ensure segment_description_id is set based on week action or parent links."""
        if item.segment_description_id:
            return

        segment_id = self._derive_segment_id(
            item.week_action_id, item.parent_id, item.annual_plan_element_id
        )

        if segment_id:
            item.segment_description_id = segment_id

    def _normalize_week_item_dates(self, item: ActionItem):
        """Force weekly items to align with the configured first-day-of-week."""
        if item.item_type != "week":
            return

        bounds = self._compute_week_bounds(item.start_date, item.due_date, self._get_first_day_of_week())
        if not bounds:
            return

        item.start_date, item.due_date = bounds

    def _normalize_week_item_group(self, item: ActionItem):
        """Reserve group label for weekly tactics so they are easy to filter/report."""
        if item.item_type == "week":
            item.group = "Weekly Tactic"

    def _segment_from_week_action(self, week_action_id: Optional[str]) -> Optional[str]:
        if not week_action_id:
            return None
        row = self.db.conn.execute(
            "SELECT segment_description_id FROM week_actions WHERE id = ?",
            (week_action_id,),
        ).fetchone()
        segment_id = row["segment_description_id"] if row else None
        return segment_id

    def _resolve_segment_id_by_name(self, name):
        """First segment description matching this name, or None.

        Used only where nothing is persisted (see _segment_from_annual_plan).
        Link WRITES go through resolve_segment_id_exact, which refuses to guess.
        """
        text = (name or "").strip()
        if not text:
            return None
        row = self.db.conn.execute(
            "SELECT id FROM segment_descriptions WHERE LOWER(name) = LOWER(?) "
            "ORDER BY id",
            (text,),
        ).fetchone()
        return row["id"] if row else None

    def _segment_from_annual_plan(self, annual_plan_element_id: Optional[str]) -> Optional[str]:
        """The APE's segment, by id (RN-M2.B).

        Spec:  docs/spec_2026-08-19_rename_safe_links.md#rn-m2b
        Tests: tests/test_rename_safe_links.py::test_rn_item_segment_follows_the_ape_link_not_its_name

        Runs on every create_action_item, via _derive_segment_id. Its sibling
        _segment_from_week_action already read an id column; this one resolved
        the segment by matching annual_plan_elements.segment_name against
        segment_descriptions.name, so an APE carrying the CORRECT id and a
        drifted name derived None — and the item was stamped with no segment.

        The name is kept as a fallback for a row the migration could not
        resolve, and it goes through resolve_segment_id_exact so it cannot
        guess between two descriptions differing only by case.
        """
        if not annual_plan_element_id:
            return None
        row = self.db.conn.execute(
            "SELECT segment_name, segment_description_id "
            "FROM annual_plan_elements WHERE id = ?",
            (annual_plan_element_id,),
        ).fetchone()
        if not row:
            return None
        if row["segment_description_id"]:
            return row["segment_description_id"]
        exact = resolve_segment_id_exact(self.db.conn, row["segment_name"])
        if exact is not None:
            return exact
        # Nothing is persisted from here, so a by-name answer on an ambiguous
        # name is a display/derivation choice, not a written link. Stamping the
        # item with NO segment would be the worse outcome, and silent.
        return self._resolve_segment_id_by_name(row["segment_name"])

    def _get_first_day_of_week(self) -> int:
        """The configured first day of the week, from the one calendar.

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m2b
        Tests: tests/test_weekly_tactic_cascade.py::test_wt_m4b_week_boundary_has_one_source

        This used to load settings itself while the re-filing engine held a
        calendar built once at startup. Changing "First day of week" mid-session
        then split them: the cascade created a week row on one boundary and the
        save immediately re-snapped it to the other, so the tactic could never
        be found again and the next move into that week hit the WT-INV5 index.
        """
        return self.week_calendar.first_day

    @property
    def week_calendar(self):
        """The week calendar, rebuilt when the setting changes.

        Cheap enough to check every call — ``AppSettings.load()`` is a small
        JSON read, and this replaces a call that already did exactly that.
        """
        from . import week_calendar as _wc

        current = _wc.WeekCalendar.from_settings()
        cached = self._week_calendar
        if (cached is None or cached.first_day != current.first_day
                or cached.rule != current.rule):
            self._week_calendar = current
            if self._weekly_tactic_engine is not None:
                self._weekly_tactic_engine.calendar = current
        return self._week_calendar

    def _derive_segment_id(
        self,
        week_action_id: Optional[str],
        parent_id: Optional[str],
        annual_plan_element_id: Optional[str],
    ) -> Optional[str]:
        segment_id = self._segment_from_week_action(week_action_id)
        if segment_id:
            return segment_id

        if parent_id:
            row = self.db.conn.execute(
                "SELECT segment_description_id, week_action_id, annual_plan_element_id FROM action_items WHERE id = ?",
                (parent_id,),
            ).fetchone()
            if row:
                if row["segment_description_id"]:
                    return row["segment_description_id"]
                segment_id = self._segment_from_week_action(row["week_action_id"])
                if segment_id:
                    return segment_id
                segment_id = self._segment_from_annual_plan(row["annual_plan_element_id"])
                if segment_id:
                    return segment_id

        return self._segment_from_annual_plan(annual_plan_element_id)

    def backfill_action_item_segments(self) -> int:
        """Populate missing segment ids and normalize weekly dates on historical action items."""
        rows = self.db.conn.execute(
            """
            SELECT id, week_action_id, parent_id, annual_plan_element_id,
                   item_type, start_date, due_date, segment_description_id
            FROM action_items
            """
        ).fetchall()

        updated = 0
        now = datetime.now().isoformat()
        first_day = self._get_first_day_of_week()
        for row in rows:
            updates: Dict[str, Any] = {}

            if not row["segment_description_id"]:
                segment_id = self._derive_segment_id(
                    row["week_action_id"],
                    row["parent_id"],
                    row["annual_plan_element_id"],
                )
                if segment_id:
                    updates["segment_description_id"] = segment_id

            if row["item_type"] == "week":
                bounds = self._compute_week_bounds(row["start_date"], row["due_date"], first_day)
                if bounds:
                    start_date, due_date = bounds
                    if start_date != row["start_date"]:
                        updates["start_date"] = start_date
                    if due_date != row["due_date"]:
                        updates["due_date"] = due_date

            if updates:
                updates["updated_at"] = now
                set_clause = ", ".join(f"{key} = ?" for key in updates.keys())
                values = list(updates.values()) + [row["id"]]
                self.db.conn.execute(
                    f"UPDATE action_items SET {set_clause} WHERE id = ?",
                    values,
                )
                updated += 1

        if updated:
            self.db.conn.commit()
        return updated

    def normalize_title_who_fields(self) -> int:
        """Move trailing parenthetical who text into `who` when who is blank.

        Example: ``"Task name (Creative)"`` -> title ``"Task name"``, who ``"Creative"``.
        """
        rows = self.db.conn.execute(
            "SELECT id, title, who FROM action_items"
        ).fetchall()
        updated = 0
        now = datetime.now().isoformat()
        pattern = re.compile(r"^(?P<title>.+?)\s*\((?P<who>[^()]{2,40})\)\s*$")

        for row in rows:
            who = (row["who"] or "").strip()
            if who:
                continue
            title = (row["title"] or "").strip()
            if not title:
                continue
            match = pattern.match(title)
            if not match:
                continue

            clean_title = match.group("title").strip()
            parsed_who = match.group("who").strip()
            if not clean_title or not parsed_who:
                continue

            self.db.conn.execute(
                "UPDATE action_items SET title = ?, who = ?, updated_at = ? WHERE id = ?",
                (clean_title, parsed_who, now, row["id"]),
            )
            updated += 1

        if updated:
            self.db.conn.commit()
        return updated

    def _compute_week_bounds(
        self,
        start_date: Optional[str],
        due_date: Optional[str],
        first_day: int,
    ) -> Optional[Tuple[str, str]]:
        """WT-M2.B — delegates to the one owner of week identity.

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m2b
        Tests: tests/test_week_numbering.py::test_wt_m2b1_no_direct_week_math_callers
        """
        return week_calendar.week_bounds_iso(start_date or due_date, first_day)

    def update_contact(self, contact: Contact):
        """Update an existing contact."""
        contact.updated_at = datetime.now().isoformat()

        self.db.conn.execute("""
            UPDATE contacts SET
                name = ?, contact_type = ?, email = ?, phone = ?,
                notes = ?, is_active = ?, updated_at = ?
            WHERE id = ?
        """, (
            contact.name, contact.contact_type, contact.email, contact.phone,
            contact.notes, 1 if contact.is_active else 0,
            contact.updated_at, contact.id
        ))

        self.db.conn.commit()

    def delete_contact(self, contact_id: int):
        """
        Delete a contact.

        Note: This will fail if there are action items referencing this contact
        due to foreign key constraints. Consider marking as inactive instead.
        """
        self.db.conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        self.db.conn.commit()

    def deactivate_contact(self, contact_id: int):
        """Mark a contact as inactive (soft delete)."""
        self.db.conn.execute(
            "UPDATE contacts SET is_active = 0, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), contact_id)
        )
        self.db.conn.commit()

    def search_contacts(self, search_text: str, active_only: bool = True) -> List[Contact]:
        """Search contacts by name, email, or notes (case-insensitive)."""
        # Return empty list for empty search
        if not search_text or not search_text.strip():
            return []

        query = """
            SELECT * FROM contacts
            WHERE (name LIKE ? COLLATE NOCASE
                   OR email LIKE ? COLLATE NOCASE
                   OR notes LIKE ? COLLATE NOCASE
                   OR phone LIKE ? COLLATE NOCASE)
        """
        search_pattern = f"%{search_text}%"
        params = [search_pattern, search_pattern, search_pattern, search_pattern]

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY name COLLATE NOCASE"

        rows = self.db.conn.execute(query, params).fetchall()
        return [self._row_to_contact(row) for row in rows]

    # ==================== CONTACT LINKS ====================

    def add_contact_link(self, link: ContactLink):
        """Add a link to a contact."""
        self.db.conn.execute("""
            INSERT INTO contact_links (id, contact_id, label, url, link_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (link.id, link.contact_id, link.label, link.url, link.link_type, link.created_at))
        self.db.conn.commit()

    def get_contact_links(self, contact_id: int) -> List[ContactLink]:
        """Get all links for a contact."""
        rows = self.db.conn.execute(
            "SELECT * FROM contact_links WHERE contact_id = ? ORDER BY created_at",
            (contact_id,)
        ).fetchall()
        return [self._row_to_contact_link(row) for row in rows]

    def delete_contact_link(self, link_id: str):
        """Delete a contact link."""
        self.db.conn.execute("DELETE FROM contact_links WHERE id = ?", (link_id,))
        self.db.conn.commit()

    # ==================== ROW CONVERTERS ====================

    def _row_to_action_item(self, row: sqlite3.Row) -> ActionItem:
        """Convert database row to ActionItem."""
        # Handle new columns that may not exist in older databases
        try:
            original_due_date = row["original_due_date"]
        except (KeyError, IndexError):
            original_due_date = None

        try:
            is_meeting = bool(row["is_meeting"])
        except (KeyError, IndexError):
            is_meeting = False

        try:
            meeting_start_time = row["meeting_start_time"]
        except (KeyError, IndexError):
            meeting_start_time = None

        try:
            week_action_id = row["week_action_id"]
        except (KeyError, IndexError):
            week_action_id = None

        try:
            annual_plan_element_id = row["annual_plan_element_id"]
        except (KeyError, IndexError):
            annual_plan_element_id = None

        try:
            item_type = row["item_type"] or "daily"
        except (KeyError, IndexError):
            item_type = "daily"

        try:
            segment_description_id = row["segment_description_id"]
        except (KeyError, IndexError):
            segment_description_id = None

        try:
            is_habit = bool(row["is_habit"])
        except (KeyError, IndexError):
            is_habit = False

        try:
            percent_complete = row["percent_complete"]
        except (KeyError, IndexError):
            percent_complete = 0

        try:
            today_pin_rank = row["today_pin_rank"]
        except (KeyError, IndexError):
            today_pin_rank = None

        try:
            next_action = row["next_action"]
        except (KeyError, IndexError):
            next_action = None

        try:
            weekly_tactic_id = row["weekly_tactic_id"]
        except (KeyError, IndexError):
            weekly_tactic_id = None

        try:
            weekly_tactic_start_date = row["weekly_tactic_start_date"]
        except (KeyError, IndexError):
            weekly_tactic_start_date = None

        try:
            deliverable = row["deliverable"]
        except (KeyError, IndexError):
            deliverable = None

        return ActionItem(
            id=row["id"],
            who=row["who"],
            contact_id=row["contact_id"],
            parent_id=row["parent_id"],
            weekly_tactic_id=weekly_tactic_id,
            weekly_tactic_start_date=weekly_tactic_start_date,
            title=row["title"],
            description=row["description"],
            next_action=next_action,
            deliverable=deliverable,
            start_date=row["start_date"],
            due_date=row["due_date"],
            original_due_date=original_due_date,
            is_meeting=is_meeting,
            meeting_start_time=meeting_start_time,
            importance=row["importance"],
            urgency=row["urgency"],
            size=row["size"],
            value=row["value"],
            priority_score=row["priority_score"],
            group=row["group"],
            category=row["category"],
            planned_minutes=row["planned_minutes"],
            status=row["status"],
            completed_at=row["completed_at"],
            week_action_id=week_action_id,
            annual_plan_element_id=annual_plan_element_id,
            item_type=item_type,
            segment_description_id=segment_description_id,
            is_habit=is_habit,
            percent_complete=percent_complete,
            today_pin_rank=today_pin_rank,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def _row_to_defaults(self, row: sqlite3.Row) -> Defaults:
        """Convert database row to Defaults."""
        # Handle who column which may not exist in older databases
        try:
            who = row["who"]
        except (KeyError, IndexError):
            who = None
        try:
            near_term_offset_days = row["near_term_offset_days"]
        except (KeyError, IndexError):
            near_term_offset_days = None
        try:
            long_term_offset_days = row["long_term_offset_days"]
        except (KeyError, IndexError):
            long_term_offset_days = None
        try:
            next_month_offset_days = row["next_month_offset_days"]
        except (KeyError, IndexError):
            next_month_offset_days = None
        try:
            next_quarter_offset_days = row["next_quarter_offset_days"]
        except (KeyError, IndexError):
            next_quarter_offset_days = None

        return Defaults(
            scope_type=row["scope_type"],
            scope_key=row["scope_key"],
            contact_id=row["contact_id"],
            who=who,
            importance=row["importance"],
            urgency=row["urgency"],
            size=row["size"],
            value=row["value"],
            group=row["group"],
            category=row["category"],
            planned_minutes=row["planned_minutes"],
            start_offset_days=row["start_offset_days"],
            due_offset_days=row["due_offset_days"],
            near_term_offset_days=near_term_offset_days,
            long_term_offset_days=long_term_offset_days,
            next_month_offset_days=next_month_offset_days,
            next_quarter_offset_days=next_quarter_offset_days
        )

    def _row_to_item_link(self, row: sqlite3.Row) -> ItemLink:
        """Convert database row to ItemLink."""
        # Handle link_type column which may not exist in older database rows
        try:
            link_type = row["link_type"]
        except (KeyError, IndexError):
            link_type = "url"  # Default for existing rows

        return ItemLink(
            id=row["id"],
            item_id=row["item_id"],
            label=row["label"],
            url=row["url"],
            link_type=link_type,
            created_at=row["created_at"]
        )

    def _row_to_contact_link(self, row: sqlite3.Row) -> ContactLink:
        """Convert database row to ContactLink."""
        # Handle link_type column which may not exist in older database rows
        try:
            link_type = row["link_type"]
        except (KeyError, IndexError):
            link_type = "url"  # Default for existing rows

        return ContactLink(
            id=row["id"],
            contact_id=row["contact_id"],
            label=row["label"],
            url=row["url"],
            link_type=link_type,
            created_at=row["created_at"]
        )

    def _row_to_project_board(self, row: sqlite3.Row) -> ProjectBoard:
        """Convert database row to ProjectBoard."""
        try:
            importance = row["importance"]
        except (KeyError, IndexError):
            importance = None

        try:
            next_step = row["next_step"]
        except (KeyError, IndexError):
            next_step = None

        try:
            notes = row["notes"]
        except (KeyError, IndexError):
            notes = None

        try:
            completed_at = row["completed_at"]
        except (KeyError, IndexError):
            completed_at = None

        keys = row.keys()
        return ProjectBoard(
            id=row["id"],
            title=row["title"],
            annual_plan_element_id=row["annual_plan_element_id"],
            start_date=row["start_date"] if "start_date" in keys else None,
            end_date=row["end_date"] if "end_date" in keys else None,
            importance=importance,
            next_step=next_step,
            notes=notes,
            display_order=row["display_order"] if "display_order" in row.keys() else None,
            status=row["status"],
            completed_at=completed_at,
            savor_count=row["savor_count"] if "savor_count" in keys else 0,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_project_board_link(self, row: sqlite3.Row) -> ProjectBoardLink:
        """Convert database row to ProjectBoardLink.

        Purpose: Row hydration including the per-link `status` introduced in M1.
        Spec:    docs/implementation_plan_2026-06-06_project_notes.md#M1.A.4
        Tests:   tests/test_project_notes.py::test_link_status_roundtrip
        NOTE:    This method shadows DBManagerProjectBoardsMixin's version of
                 the same name via Python MRO. Both must be kept in sync.
                 (Adjacent issue, flagged in plan §Risks #5 — should be
                 consolidated in a follow-up.)
        """
        try:
            link_type = row["link_type"]
        except (KeyError, IndexError):
            link_type = "url"

        try:
            status = row["status"] or "open"
        except (KeyError, IndexError):
            status = "open"

        return ProjectBoardLink(
            id=row["id"],
            project_board_id=row["project_board_id"],
            label=row["label"],
            url=row["url"],
            link_type=link_type,
            status=status,
            created_at=row["created_at"],
        )

    def _row_to_time_block(self, row: sqlite3.Row) -> TimeBlock:
        """Convert database row to TimeBlock."""
        return TimeBlock(
            id=row["id"],
            item_id=row["item_id"],
            block_date=row["block_date"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            planned_minutes=row["planned_minutes"],
            label=row["label"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def _row_to_work_log(self, row: sqlite3.Row) -> WorkLog:
        """Convert database row to WorkLog.

        The five reward columns are read defensively, in the style the rest of
        this file already uses: a row selected before the migration ran, or by
        a query that does not project them, must not blow up here.

        Spec:  docs/spec_2026-08-23_dopamine_reward_protocol.md#22-work_logs--add-reward-protocol-audit-columns
        Tests: tests/test_reward_protocol_schema.py::test_rp24_work_log_reward_fields_round_trip
        """
        keys = row.keys()

        def optional(name, default=None):
            return row[name] if name in keys else default

        return WorkLog(
            id=row["id"],
            item_id=row["item_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            minutes=row["minutes"],
            note=row["note"],
            deliverable_snapshot=optional("deliverable_snapshot"),
            deliverable_completed=bool(optional("deliverable_completed", 0)),
            savor_delivered=bool(optional("savor_delivered", 0)),
            celebration_type=optional("celebration_type"),
            phase=optional("phase"),
            created_at=row["created_at"]
        )

    def _row_to_contact(self, row: sqlite3.Row) -> Contact:
        """Convert database row to Contact."""
        return Contact(
            id=row["id"],
            name=row["name"],
            contact_type=row["contact_type"],
            email=row["email"],
            phone=row["phone"],
            notes=row["notes"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
