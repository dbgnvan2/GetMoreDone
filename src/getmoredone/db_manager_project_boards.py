"""Project board support mixin for `DatabaseManager`."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import ProjectBoard, ProjectBoardLink, ProjectBoardStatus


class DBManagerProjectBoardsMixin:
    def create_project_board(self, board: ProjectBoard) -> str:
        """Create a new project board."""
        board.updated_at = datetime.now().isoformat()
        if board.display_order is None:
            board.display_order = self._next_project_board_order()
        self.db.conn.execute("""
            INSERT INTO project_boards (
                id, title, annual_plan_element_id, start_date, end_date, importance, next_step, notes,
                display_order, status, completed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            board.id, board.title, board.annual_plan_element_id, board.start_date, board.end_date,
            board.importance,
            board.next_step, board.notes, board.display_order, board.status, board.completed_at,
            board.created_at, board.updated_at
        ))
        self.db.conn.commit()
        return board.id

    def get_project_board(self, board_id: str) -> Optional[ProjectBoard]:
        """Fetch a single project board by ID."""
        row = self.db.conn.execute(
            "SELECT * FROM project_boards WHERE id = ?",
            (board_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_project_board(row)

    def update_project_board(self, board: ProjectBoard):
        """Persist project board changes."""
        board.updated_at = datetime.now().isoformat()
        self.db.conn.execute("""
            UPDATE project_boards SET
                title = ?, annual_plan_element_id = ?, start_date = ?, end_date = ?,
                importance = ?, next_step = ?,
                notes = ?, display_order = ?, status = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
        """, (
            board.title, board.annual_plan_element_id, board.start_date, board.end_date,
            board.importance, board.next_step,
            board.notes, board.display_order, board.status, board.completed_at, board.updated_at, board.id
        ))
        self.db.conn.commit()

    def delete_project_board(self, board_id: str):
        """Delete a project board and its task links."""
        self.db.conn.execute("DELETE FROM project_boards WHERE id = ?", (board_id,))
        self.db.conn.commit()

    def set_project_board_status(self, board_id: str, status: str) -> bool:
        """Update project board status."""
        if status not in {
            ProjectBoardStatus.ACTIVE,
            ProjectBoardStatus.PENDING,
            ProjectBoardStatus.COMPLETED,
        }:
            return False

        completed_at = datetime.now().isoformat() if status == ProjectBoardStatus.COMPLETED else None
        self.db.conn.execute("""
            UPDATE project_boards
            SET status = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
        """, (status, completed_at, datetime.now().isoformat(), board_id))
        self.db.conn.commit()
        return True

    def get_project_boards(
        self,
        show_pending: bool = False,
        show_completed: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return project boards with joined APE metadata and linked-item counts."""
        self._normalize_project_board_order()
        
        # Active boards are ALWAYS shown; show_pending / show_completed each
        # ADD their status on top of active (they don't replace it). Previously
        # passing show_pending=True returned *only* pending boards, so callers
        # like the Scheduler's Projects tab saw zero boards when none were
        # pending.
        statuses = [ProjectBoardStatus.ACTIVE]
        if show_pending:
            statuses.append(ProjectBoardStatus.PENDING)
        if show_completed:
            statuses.append(ProjectBoardStatus.COMPLETED)
            
        placeholders = ",".join("?" for _ in statuses)
        query = f"""
            SELECT
                pb.*,
                ape.year AS ape_year,
                ape.segment_name,
                ape.subsegment_name,
                ape.category_name,
                ape.key_field,
                vc.color_hex AS category_color_hex,
                COUNT(DISTINCT pbi.item_id) AS linked_item_count,
                SUM(CASE WHEN ai.status = 'open' THEN 1 ELSE 0 END) AS open_item_count,
                SUM(CASE WHEN ai.status = 'completed' THEN 1 ELSE 0 END) AS completed_item_count
            FROM project_boards pb
            LEFT JOIN annual_plan_elements ape
              ON ape.id = pb.annual_plan_element_id
            LEFT JOIN vision_categories vc
              ON LOWER(vc.name) = LOWER(ape.category_name)
             AND vc.subsegment_id = (
                SELECT ss.id
                FROM vision_subsegments ss
                JOIN vision_segments s ON s.id = ss.segment_id
                WHERE LOWER(ss.name) = LOWER(ape.subsegment_name)
                  AND LOWER(s.name) = LOWER(ape.segment_name)
                LIMIT 1
             )
            LEFT JOIN project_board_items pbi
              ON pbi.project_board_id = pb.id
            LEFT JOIN action_items ai
              ON ai.id = pbi.item_id
            WHERE pb.status IN ({placeholders})
            GROUP BY 
                pb.id, pb.title, pb.annual_plan_element_id, pb.importance, pb.next_step, pb.notes, pb.display_order, pb.status, pb.completed_at, pb.created_at, pb.updated_at,
                ape.year, ape.segment_name, ape.subsegment_name, ape.category_name, ape.key_field, vc.color_hex
            ORDER BY
                CASE pb.status
                    WHEN 'active' THEN 0
                    WHEN 'pending' THEN 1
                    ELSE 2
                END,
                COALESCE(pb.display_order, 999999) ASC,
                COALESCE(pb.title, '') COLLATE NOCASE ASC
        """
        rows = self.db.conn.execute(query, statuses).fetchall()
        return [dict(row) for row in rows]

    def get_project_board_items(self, board_id: str) -> List[ActionItem]:
        """Return linked action items for one project board."""
        rows = self.db.conn.execute("""
            SELECT ai.*
            FROM action_items ai
            JOIN project_board_items pbi ON pbi.item_id = ai.id
            WHERE pbi.project_board_id = ?
            ORDER BY
                CASE ai.status
                    WHEN 'open' THEN 0
                    WHEN 'completed' THEN 1
                    ELSE 2
                END,
                COALESCE(ai.start_date, ai.due_date, '') ASC,
                ai.priority_score DESC,
                ai.title COLLATE NOCASE ASC
        """, (board_id,)).fetchall()
        return [self._row_to_action_item(row) for row in rows]

    def link_action_item_to_project_board(self, board_id: str, item_id: str):
        """Link an action item to a project board."""
        self.db.conn.execute("""
            INSERT OR IGNORE INTO project_board_items (project_board_id, item_id, created_at)
            VALUES (?, ?, ?)
        """, (board_id, item_id, datetime.now().isoformat()))
        self.db.conn.execute(
            "UPDATE project_boards SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), board_id),
        )
        self.db.conn.commit()

    def link_item_to_project_exclusive(self, board_id: str, item_id: str):
        """Link an action item to exactly one project board, clearing previous project links and syncing APE."""
        self._refuse_if_weekly_tactic(item_id)
        now = datetime.now().isoformat()

        # One transaction: step 1 destroys rows and step 2 recreates them, so a
        # failure between the two would leave the item filed under nothing at
        # all. `with conn` commits on success and rolls back on any exception.
        with self.db.conn:
            # 1. Clear existing project links for this item
            self.db.conn.execute(
                "DELETE FROM project_board_items WHERE item_id = ?",
                (item_id,)
            )

            # 2. Add the new link
            self.db.conn.execute("""
                INSERT INTO project_board_items (project_board_id, item_id, created_at)
                VALUES (?, ?, ?)
            """, (board_id, item_id, now))

            # 3. The board decides the item's Annual Plan Element — including
            # when the board has none. The guard used to be
            # `if board and board.annual_plan_element_id:` with no else, so
            # moving an item onto a board with no APE left the *previous*
            # board's APE on the row: the item claimed a place in the plan
            # belonging to a project it was no longer on, and every reader
            # downstream (the lineage columns, the Scheduler's segment filter,
            # `inherit_project_links`) took that as ground truth. One rule, no
            # stale halves — and `confirm_exclusive_relink` asks first whenever
            # this write would change the item's APE.
            # Tests: tests/test_project_multi_link.py::test_c3_a_board_with_no_plan_element_clears_the_items
            board = self.get_project_board(board_id)
            if board:
                self.db.conn.execute(
                    "UPDATE action_items SET annual_plan_element_id = ?, updated_at = ? WHERE id = ?",
                    (board.annual_plan_element_id, now, item_id)
                )

            # 4. Touch the project board
            self.db.conn.execute(
                "UPDATE project_boards SET updated_at = ? WHERE id = ?",
                (now, board_id),
            )

    def unlink_action_item_from_project_board(self, board_id: str, item_id: str):
        """Unlink an action item from a project board."""
        self.db.conn.execute(
            "DELETE FROM project_board_items WHERE project_board_id = ? AND item_id = ?",
            (board_id, item_id),
        )
        self.db.conn.execute(
            "UPDATE project_boards SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), board_id),
        )
        self.db.conn.commit()

    def clear_item_project_links(self, item_id: str):
        """Remove all project links and clear APE for an action item."""
        now = datetime.now().isoformat()
        self.db.conn.execute("DELETE FROM project_board_items WHERE item_id = ?", (item_id,))
        # A Weekly Tactic must keep its Annual Plan Element — the raw UPDATE
        # here bypasses ``update_action_item``'s validation, so nulling it
        # produced a row the application then refused to save.
        if not self.is_weekly_tactic(item_id):
            self.db.conn.execute(
                "UPDATE action_items SET annual_plan_element_id = NULL, updated_at = ? WHERE id = ?",
                (now, item_id)
            )
        self.db.conn.commit()

    def is_weekly_tactic(self, item_id: str) -> bool:
        """Is this row a Weekly Tactic (``item_type='week'``)?

        The one predicate behind PL6, so the writer that refuses the operation
        and the dialog that describes it cannot disagree about which rows the
        rule covers.
        """
        row = self.db.conn.execute(
            "SELECT item_type FROM action_items WHERE id = ?", (item_id,)
        ).fetchone()
        return bool(row and row["item_type"] == "week")

    def _refuse_if_weekly_tactic(self, item_id: str) -> None:
        """A Weekly Tactic cannot be filed under a Project (PL6).

        Purpose: a tactic's Annual Plan Element is what its canonical title is
                 derived from, and filing re-stamps that APE — so the link is
                 forbidden outright, not merely when it would null the APE.
                 Guarding only the null write closed the loud half of the class
                 (a row ``update_action_item`` then refuses to save) and left
                 the quiet half open: filing a tactic under a board with a
                 *different* plan element silently re-parented it to another
                 lineage, and the result looked perfectly valid (P5, P13).
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1
        Tests:   tests/test_project_multi_link.py::test_f2_filing_never_strips_a_weekly_tactics_plan_element

        Raises ValueError, the way ``update_action_item`` already does for the
        same invariant, so a surface that has not filtered tactics out fails
        loudly rather than corrupting the plan.
        """
        if self.is_weekly_tactic(item_id):
            raise ValueError(
                "A Weekly Tactic cannot be filed under a Project: its Annual "
                "Plan Element is what its title is derived from."
            )

    def inherit_project_links(self, source_id: str, new_id: str) -> int:
        """Copy an item's project links onto an item derived from it.

        Purpose: PL12 — a follow-up (or a complete-and-create) of a project task
                 used to land with no project at all, because both copy paths
                 build the new row through a constructor that never mentions
                 project_board_items.
        Spec:    docs/implementation_plan_2026-08-19_item_editor_project_link.md#pl12
        Tests:   tests/test_item_editor_project_link.py::test_pl12_followup_inherits_project_link

        Exactly **one** link is copied — the source's first. Sweep F2: copying
        every link meant a follow-up of a legacy multi-filed row was itself a
        new multi-filed row, so the count BP2 reports could go *up* while the
        notice beside it promised the number only ever falls. An Action Item
        belongs to exactly one Project, and a copy is an Action Item.

        Returns the number of links copied (0 or 1).
        """
        board_ids = self.get_project_board_ids_for_item(source_id)
        if not board_ids:
            return 0

        if len(board_ids) > 1:
            logging.getLogger(__name__).warning(
                "[project] %s was filed under %d projects; its copy %s inherits "
                "only %s", source_id, len(board_ids), new_id, board_ids[0],
            )
        board_ids = board_ids[:1]
        now = datetime.now().isoformat()
        with self.db.conn:
            for board_id in board_ids:
                self.db.conn.execute("""
                    INSERT OR IGNORE INTO project_board_items (project_board_id, item_id, created_at)
                    VALUES (?, ?, ?)
                """, (board_id, new_id, now))
                self.db.conn.execute(
                    "UPDATE project_boards SET updated_at = ? WHERE id = ?",
                    (now, board_id),
                )

        # Keep the copy's Annual Plan Element consistent with the board it now
        # sits on — but only when nothing else has already set one, so this
        # never overwrites the weekly lineage a follow-up just inherited.
            copy_row = self.db.conn.execute(
                "SELECT annual_plan_element_id FROM action_items WHERE id = ?",
                (new_id,),
            ).fetchone()
            if copy_row is not None and not copy_row["annual_plan_element_id"]:
                board = self.get_project_board(board_ids[0])
                if board and board.annual_plan_element_id:
                    self.db.conn.execute(
                        "UPDATE action_items SET annual_plan_element_id = ?, updated_at = ? WHERE id = ?",
                        (board.annual_plan_element_id, now, new_id),
                    )

        return len(board_ids)

    def get_project_board_ids_for_item(self, item_id: str) -> List[str]:
        """Return all project boards linked to an action item."""
        rows = self.db.conn.execute(
            "SELECT project_board_id FROM project_board_items WHERE item_id = ? ORDER BY created_at",
            (item_id,),
        ).fetchall()
        return [row["project_board_id"] for row in rows]

    def get_items_on_multiple_project_boards(self) -> List[dict]:
        """Action items filed under more than one Project, worst first.

        Purpose: BP2 — filing became exclusive on every surface, but rows
                 created before that can still sit on several boards. They are
                 reported rather than cleaned up behind the user's back: an
                 exclusive re-link deletes the extras, so a silent migration
                 would destroy data nobody was asked about (P2).
        Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp2
        Tests:   tests/test_project_multi_link.py

        Returns one dict per item: ``id``, ``title`` and ``board_count``.
        """
        rows = self.db.conn.execute("""
            SELECT ai.id AS id,
                   ai.title AS title,
                   COUNT(pbi.project_board_id) AS board_count
            FROM action_items ai
            JOIN project_board_items pbi ON pbi.item_id = ai.id
            GROUP BY ai.id
            HAVING COUNT(pbi.project_board_id) > 1
            ORDER BY board_count DESC, ai.title COLLATE NOCASE ASC
        """).fetchall()
        return [
            {"id": row["id"], "title": row["title"], "board_count": row["board_count"]}
            for row in rows
        ]

    # BP5 — the Scheduler's "Unlinked (No Project)" list. A default cap rather
    # than none: the box shows a handful of rows, and the query behind it used
    # to load every open unlinked item in the database to fill it.
    UNLINKED_ITEMS_DEFAULT_LIMIT = 500

    _UNLINKED_FROM = """
            FROM action_items ai
            LEFT JOIN project_board_items pbi ON pbi.item_id = ai.id
            WHERE pbi.project_board_id IS NULL
    """

    def get_unlinked_action_items(
        self,
        status_filter: str = "open",
        limit: Optional[int] = UNLINKED_ITEMS_DEFAULT_LIMIT,
        who_filter: Optional[str] = None,
    ) -> List[ActionItem]:
        """Return action items that are NOT linked to any project board.

        Purpose: BP5 — capped, because the Scheduler renders a fixed number of
                 rows from this list and the uncapped query loaded the whole
                 table to build them.
        Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp5
        Tests:   tests/test_db_project_drag.py::test_bp5_unlinked_items_are_capped_and_the_drop_is_countable

        ``limit=None`` restores the uncapped behaviour. What the cap dropped is
        not silent: :meth:`count_unlinked_action_items` returns the true total,
        and the Scheduler labels the box "showing N of M" (P9).

        ``who_filter`` is here rather than left to the caller because a cap
        applied before a filter drops rows the filter would have kept, and then
        the "showing N of M" describes a different set than the one on screen
        (sweep F3). The count takes the same argument for the same reason.
        """
        query = "SELECT ai.*" + self._UNLINKED_FROM
        params: List[object] = []
        query, params = self._apply_unlinked_filters(query, params, status_filter, who_filter)

        query += " ORDER BY ai.priority_score DESC, ai.title COLLATE NOCASE ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))

        rows = self.db.conn.execute(query, params).fetchall()
        return [self._row_to_action_item(row) for row in rows]

    def _apply_unlinked_filters(self, query, params, status_filter, who_filter):
        """The WHERE clauses the list and the count must share.

        Two queries with two hand-written filter blocks is exactly how a count
        and a list come to disagree (P19), so there is one block.
        """
        if status_filter:
            query += " AND ai.status = ?"
            params.append(status_filter)
        if who_filter is not None:
            # The owner is resolved in Python and matched by exact value,
            # rather than compared with SQL string functions. The gate is
            # ``is not None``, not truthiness: an empty-string filter used to
            # fall past it and drop the filter altogether, so the unlinked list
            # returned *everything* while the project-board branch's
            # ``_matches_who`` returned nothing for the same value (sweep pass
            # 5, P5).
            #
            # ``LOWER(TRIM(ai.who)) = ?`` looked equivalent to the Python
            # predicate this replaced and was not: SQLite's LOWER is ASCII-only
            # and its TRIM strips only U+0020, so a stored "JOSÉ" or a trailing
            # tab stopped matching and the "No Project" box read zero with no
            # signal (P2). Doing it symmetrically in SQL fixes the asymmetry but
            # still cannot fold "JOSÉ" onto "josé" — the comparison has to
            # happen where Python's casing rules apply.
            matches = self._who_values_matching(who_filter)
            if not matches:
                query += " AND 0"
            else:
                query += " AND ai.who IN (%s)" % ",".join("?" for _ in matches)
                params.extend(matches)
        return query, params

    def _who_values_matching(self, who_filter: str) -> List[str]:
        """Stored ``who`` values equal to ``who_filter`` ignoring case and space.

        ``.strip().lower()`` on both sides — exactly the predicate the Scheduler
        applied in Python before the filter moved into the query, so moving it
        changed *when* rows are dropped (before the cap, not after) and not
        *which* ones — with one deliberate exception. The Python form was
        ``item.who and item.who.strip().lower() == ...``, which excluded a row
        with no owner but *did* match a whitespace-only owner against a
        whitespace-only filter. A blank filter matches nothing here instead,
        because "filter by nobody" returning a set of rows is a worse answer
        than returning none; ``DragScheduleScreen._matches_who`` applies the
        same rule on the project-board branch so those two branches cannot
        disagree (sweep pass 4/5).

        Parity is with that branch, not with the whole screen, and the two
        blank forms do not even agree with each other elsewhere:
        ``get_all_items`` / ``get_upcoming_items`` gate on ``if who_filter:``,
        so ``"   "`` reaches their ``LOWER(TRIM(COALESCE(who,'')))`` and
        matches owner-less rows, while ``""`` is falsy and drops the filter
        entirely, returning everything. They are shared with other screens and
        are recorded in BACKLOG.md rather than changed from here.
        """
        target = who_filter.strip().lower()
        if not target:
            return []
        rows = self.db.conn.execute(
            "SELECT DISTINCT who FROM action_items WHERE who IS NOT NULL"
        ).fetchall()
        return [row["who"] for row in rows
                if (row["who"] or "").strip().lower() == target]

    def count_unlinked_action_items(
        self,
        status_filter: str = "open",
        who_filter: Optional[str] = None,
    ) -> int:
        """How many action items are not linked to any project board.

        Purpose: BP5 — the Scheduler wanted the number, not the rows, and was
                 calling ``len(get_unlinked_action_items(...))`` to get it.
        Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp5
        Tests:   tests/test_db_project_drag.py::test_bp5_count_matches_the_uncapped_list
        """
        query = "SELECT COUNT(*) AS n" + self._UNLINKED_FROM
        params: List[object] = []
        query, params = self._apply_unlinked_filters(query, params, status_filter, who_filter)
        row = self.db.conn.execute(query, params).fetchone()
        return int(row["n"]) if row else 0

    def add_project_board_link(self, link: ProjectBoardLink):
        """Add a link to a project board.

        Purpose: Persist a new project-board link (a Project Note), including
                 its initial status.
        Spec:    docs/implementation_plan_2026-06-06_project_notes.md#M1.A.4
        Tests:   tests/test_project_notes.py::test_link_status_roundtrip
        """
        self.db.conn.execute("""
            INSERT INTO project_board_links (id, project_board_id, label, url, link_type, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (link.id, link.project_board_id, link.label, link.url, link.link_type, link.status, link.created_at))
        self.db.conn.commit()

    def get_project_board_links(
        self,
        board_id: str,
        include_completed: bool = True,
    ) -> List[ProjectBoardLink]:
        """Get links for a project board, newest first.

        Purpose: Fetch Project Notes for display. include_completed defaults to
                 True so existing callers (Open Notes dialog, count display)
                 don't change behavior; the new UI passes False when the shared
                 Show Completed toggle is off.
        Spec:    docs/implementation_plan_2026-06-06_project_notes.md#M2.A.3
        Tests:   tests/test_project_notes.py::test_get_links_filters_by_status
                 tests/test_project_notes.py::test_link_status_roundtrip
        """
        if include_completed:
            rows = self.db.conn.execute(
                "SELECT * FROM project_board_links WHERE project_board_id = ? ORDER BY created_at DESC",
                (board_id,),
            ).fetchall()
        else:
            rows = self.db.conn.execute(
                "SELECT * FROM project_board_links "
                "WHERE project_board_id = ? AND status = 'open' "
                "ORDER BY created_at DESC",
                (board_id,),
            ).fetchall()
        return [self._row_to_project_board_link(row) for row in rows]

    def complete_project_note(self, link_id: str) -> bool:
        """Mark a project-board link (Project Note) as completed.

        Purpose: Status change handler for the Project Notes list.
        Spec:    docs/implementation_plan_2026-06-06_project_notes.md#M2.A.1
        Tests:   tests/test_project_notes.py::test_complete_project_note
        Returns: True if a row was updated, False if link_id was unknown.
        """
        cursor = self.db.conn.execute(
            "UPDATE project_board_links SET status = 'completed' WHERE id = ?",
            (link_id,),
        )
        self.db.conn.commit()
        return cursor.rowcount > 0

    def reopen_project_note(self, link_id: str) -> bool:
        """Mark a project-board link (Project Note) as open.

        Purpose: Inverse of complete_project_note — used by the Reopen button.
        Spec:    docs/implementation_plan_2026-06-06_project_notes.md#M2.A.2
        Tests:   tests/test_project_notes.py::test_reopen_project_note
        Returns: True if a row was updated, False if link_id was unknown.
        """
        cursor = self.db.conn.execute(
            "UPDATE project_board_links SET status = 'open' WHERE id = ?",
            (link_id,),
        )
        self.db.conn.commit()
        return cursor.rowcount > 0

    def delete_project_board_link(self, link_id: str):
        """Delete a project board link."""
        self.db.conn.execute("DELETE FROM project_board_links WHERE id = ?", (link_id,))
        self.db.conn.commit()

    def list_annual_plan_element_catalog(self) -> List[Dict[str, Any]]:
        """Return Annual Plan Elements for pickers."""
        rows = self.db.conn.execute("""
            SELECT
                ape.id,
                ape.year,
                ape.segment_name,
                ape.subsegment_name,
                ape.category_name,
                ape.key_field,
                vc.color_hex AS category_color_hex
            FROM annual_plan_elements ape
            LEFT JOIN vision_categories vc
              ON LOWER(vc.name) = LOWER(ape.category_name)
             AND vc.subsegment_id = (
                SELECT ss.id
                FROM vision_subsegments ss
                JOIN vision_segments s ON s.id = ss.segment_id
                WHERE LOWER(ss.name) = LOWER(ape.subsegment_name)
                  AND LOWER(s.name) = LOWER(ape.segment_name)
                LIMIT 1
             )
            ORDER BY ape.year DESC, ape.segment_name COLLATE NOCASE, ape.subsegment_name COLLATE NOCASE, ape.category_name COLLATE NOCASE
        """).fetchall()
        return [dict(row) for row in rows]

    def ensure_project_board_for_ape(self, annual_plan_element_id: str) -> Optional[str]:
        """Create the default project board for an APE if it does not already exist."""
        existing = self.db.conn.execute(
            "SELECT id FROM project_boards WHERE annual_plan_element_id = ?",
            (annual_plan_element_id,),
        ).fetchone()
        if existing:
            return existing["id"]

        row = self.db.conn.execute("""
            SELECT key_field, category_name
            FROM annual_plan_elements
            WHERE id = ?
        """, (annual_plan_element_id,)).fetchone()
        if not row:
            return None

        board = ProjectBoard(
            title=(row["key_field"] or row["category_name"] or "Project").strip(),
            annual_plan_element_id=annual_plan_element_id,
            display_order=self._next_project_board_order(),
        )
        return self.create_project_board(board)

    def ensure_project_boards_for_all_apes(self) -> int:
        """Backfill missing project items for all Annual Plan Elements."""
        rows = self.db.conn.execute("SELECT id FROM annual_plan_elements ORDER BY year ASC, key_field ASC").fetchall()
        created = 0
        for row in rows:
            existing = self.db.conn.execute(
                "SELECT id FROM project_boards WHERE annual_plan_element_id = ?",
                (row["id"],),
            ).fetchone()
            if existing:
                continue
            self.ensure_project_board_for_ape(row["id"])
            created += 1
        return created

    def set_project_board_order(self, ordered_ids: List[str]):
        """Persist a left-to-right, top-to-bottom project note order."""
        now = datetime.now().isoformat()
        for idx, board_id in enumerate(ordered_ids):
            self.db.conn.execute(
                "UPDATE project_boards SET display_order = ?, updated_at = ? WHERE id = ?",
                (idx, now, board_id),
            )
        self.db.conn.commit()

    def _next_project_board_order(self) -> int:
        row = self.db.conn.execute(
            "SELECT COALESCE(MAX(display_order), -1) AS max_order FROM project_boards"
        ).fetchone()
        return int(row["max_order"]) + 1 if row else 0

    def _normalize_project_board_order(self):
        rows = self.db.conn.execute("""
            SELECT id, display_order
            FROM project_boards
            ORDER BY
                CASE WHEN display_order IS NULL THEN 1 ELSE 0 END,
                display_order ASC,
                created_at ASC,
                title COLLATE NOCASE ASC
        """).fetchall()
        needs_update = any(row["display_order"] is None or idx != row["display_order"] for idx, row in enumerate(rows))
        if not needs_update:
            return
        now = datetime.now().isoformat()
        for idx, row in enumerate(rows):
            self.db.conn.execute(
                "UPDATE project_boards SET display_order = ?, updated_at = ? WHERE id = ?",
                (idx, now, row["id"]),
            )
        self.db.conn.commit()


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

        return ProjectBoard(
            id=row["id"],
            title=row["title"],
            annual_plan_element_id=row["annual_plan_element_id"],
            importance=importance,
            next_step=next_step,
            notes=notes,
            display_order=row["display_order"] if "display_order" in row.keys() else None,
            status=row["status"],
            completed_at=completed_at,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_project_board_link(self, row: sqlite3.Row) -> ProjectBoardLink:
        """Convert database row to ProjectBoardLink.

        Purpose: Row hydration. Guards link_type and status with try/except for
                 robustness against in-memory rows missing the column (e.g.,
                 mid-migration partial caches).
        Spec:    docs/implementation_plan_2026-06-06_project_notes.md#M1.A.4
        Tests:   tests/test_project_notes.py::test_link_status_roundtrip
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

