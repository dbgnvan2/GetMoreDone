"""Project board support mixin for `DatabaseManager`."""

from __future__ import annotations

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
                id, title, annual_plan_element_id, importance, next_step, notes,
                display_order, status, completed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            board.id, board.title, board.annual_plan_element_id, board.importance,
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
                title = ?, annual_plan_element_id = ?, importance = ?, next_step = ?,
                notes = ?, display_order = ?, status = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
        """, (
            board.title, board.annual_plan_element_id, board.importance, board.next_step,
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
        
        statuses = []
        if show_pending:
            statuses.append(ProjectBoardStatus.PENDING)
        if show_completed:
            statuses.append(ProjectBoardStatus.COMPLETED)
            
        # If no filters are selected, show only active projects
        if not statuses:
            statuses = [ProjectBoardStatus.ACTIVE]
            
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
                pb.id, pb.title, pb.importance, pb.next_step, pb.notes, pb.display_order, pb.status, pb.completed_at, pb.created_at, pb.updated_at,
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
        now = datetime.now().isoformat()
        
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
        
        # 3. Fetch board's APE ID to sync
        board = self.get_project_board(board_id)
        if board and board.annual_plan_element_id:
            self.db.conn.execute(
                "UPDATE action_items SET annual_plan_element_id = ?, updated_at = ? WHERE id = ?",
                (board.annual_plan_element_id, now, item_id)
            )
            
        # 4. Touch the project board
        self.db.conn.execute(
            "UPDATE project_boards SET updated_at = ? WHERE id = ?",
            (now, board_id),
        )
        self.db.conn.commit()

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
        self.db.conn.execute(
            "UPDATE action_items SET annual_plan_element_id = NULL, updated_at = ? WHERE id = ?",
            (now, item_id)
        )
        self.db.conn.commit()

    def get_project_board_ids_for_item(self, item_id: str) -> List[str]:
        """Return all project boards linked to an action item."""
        rows = self.db.conn.execute(
            "SELECT project_board_id FROM project_board_items WHERE item_id = ? ORDER BY created_at",
            (item_id,),
        ).fetchall()
        return [row["project_board_id"] for row in rows]

    def get_unlinked_action_items(self, status_filter: str = "open") -> List[ActionItem]:
        """Return action items that are NOT linked to any project board."""
        query = """
            SELECT ai.*
            FROM action_items ai
            LEFT JOIN project_board_items pbi ON pbi.item_id = ai.id
            WHERE pbi.project_board_id IS NULL
        """
        params = []
        if status_filter:
            query += " AND ai.status = ?"
            params.append(status_filter)
            
        query += " ORDER BY ai.priority_score DESC, ai.title COLLATE NOCASE ASC"
        
        rows = self.db.conn.execute(query, params).fetchall()
        return [self._row_to_action_item(row) for row in rows]

    def add_project_board_link(self, link: ProjectBoardLink):
        """Add a link to a project board."""
        self.db.conn.execute("""
            INSERT INTO project_board_links (id, project_board_id, label, url, link_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (link.id, link.project_board_id, link.label, link.url, link.link_type, link.created_at))
        self.db.conn.commit()

    def get_project_board_links(self, board_id: str) -> List[ProjectBoardLink]:
        """Get all links for a project board."""
        rows = self.db.conn.execute(
            "SELECT * FROM project_board_links WHERE project_board_id = ? ORDER BY created_at",
            (board_id,),
        ).fetchall()
        return [self._row_to_project_board_link(row) for row in rows]

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
        """Convert database row to ProjectBoardLink."""
        try:
            link_type = row["link_type"]
        except (KeyError, IndexError):
            link_type = "url"

        return ProjectBoardLink(
            id=row["id"],
            project_board_id=row["project_board_id"],
            label=row["label"],
            url=row["url"],
            link_type=link_type,
            created_at=row["created_at"],
        )

