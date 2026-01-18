"""
Database manager for GetMoreDone application.
Provides CRUD operations and business logic for all entities.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import sqlite3

from .database import Database
from .models import (
    ActionItem, ItemLink, ContactLink, Defaults, RescheduleHistory,
    TimeBlock, WorkLog, Status, Contact
)


class DatabaseManager:
    """Manages database operations for GetMoreDone."""

    # Allowed sort columns (security: prevent SQL injection)
    ALLOWED_SORT_COLUMNS = {
        "start_date", "due_date", "priority_score", "importance", "urgency",
        "size", "value", "planned_minutes", "created_at", "updated_at"
    }

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database manager."""
        self.db = Database(db_path)
        self.db.connect()
        self.db.initialize_schema()

    def close(self):
        """Close database connection."""
        self.db.close()

    # ==================== ACTION ITEMS ====================

    def create_action_item(self, item: ActionItem, apply_defaults: bool = True) -> str:
        """
        Create a new action item.

        Args:
            item: ActionItem to create
            apply_defaults: Whether to apply system/who defaults

        Returns:
            ID of created item
        """
        if apply_defaults:
            self._apply_defaults(item)

        # Validate and adjust dates
        item.validate_and_adjust_dates()

        # Update priority score
        item.update_priority_score()
        item.updated_at = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO action_items (
                id, who, contact_id, parent_id, title, description, next_action, start_date, due_date,
                original_due_date, is_meeting, meeting_start_time,
                importance, urgency, size, value, priority_score,
                "group", category, planned_minutes, status, completed_at,
                week_action_id, segment_description_id, is_habit, percent_complete,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.id, item.who, item.contact_id, item.parent_id, item.title, item.description,
            item.next_action,
            item.start_date, item.due_date, item.original_due_date, 1 if item.is_meeting else 0,
            item.meeting_start_time,
            item.importance, item.urgency, item.size, item.value,
            item.priority_score, item.group, item.category,
            item.planned_minutes, item.status, item.completed_at,
            item.week_action_id, item.segment_description_id, 1 if item.is_habit else 0,
            item.percent_complete,
            item.created_at, item.updated_at
        ))

        self.db.conn.commit()
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

    def update_action_item(self, item: ActionItem):
        """Update an existing action item."""
        # Get existing item to preserve original_due_date if it exists
        existing = self.get_action_item(item.id)
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

        self.db.conn.execute("""
            UPDATE action_items SET
                who = ?, contact_id = ?, parent_id = ?, title = ?, description = ?, next_action = ?,
                start_date = ?, due_date = ?, original_due_date = ?, is_meeting = ?, meeting_start_time = ?,
                importance = ?, urgency = ?, size = ?, value = ?,
                priority_score = ?, "group" = ?, category = ?,
                planned_minutes = ?, status = ?, completed_at = ?,
                week_action_id = ?, segment_description_id = ?, is_habit = ?, percent_complete = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            item.who, item.contact_id, item.parent_id, item.title, item.description, item.next_action,
            item.start_date, item.due_date, item.original_due_date, 1 if item.is_meeting else 0,
            item.meeting_start_time,
            item.importance, item.urgency, item.size, item.value,
            item.priority_score, item.group, item.category,
            item.planned_minutes, item.status, item.completed_at,
            item.week_action_id, item.segment_description_id, 1 if item.is_habit else 0,
            item.percent_complete,
            item.updated_at, item.id
        ))

        self.db.conn.commit()

    def delete_action_item(self, item_id: str):
        """Delete action item (cascades to links, logs, etc.)."""
        self.db.conn.execute("DELETE FROM action_items WHERE id = ?", (item_id,))
        self.db.conn.commit()

    def complete_action_item(self, item_id: str) -> bool:
        """
        Mark action item as completed.

        Returns:
            True if item was found and completed
        """
        item = self.get_action_item(item_id)
        if not item:
            return False

        item.status = Status.COMPLETED
        item.completed_at = datetime.now().isoformat()
        self.update_action_item(item)
        return True

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

    def duplicate_action_item(self, item_id: str) -> Optional[str]:
        """
        Duplicate an action item (creates new item with same fields).

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

        return self.create_action_item(new_item, apply_defaults=False)

    def complete_and_create(self, item_id: str) -> Optional[str]:
        """
        Complete item and create a new one seeded from it.

        Returns:
            ID of new item, or None if original not found
        """
        if not self.complete_action_item(item_id):
            return None

        return self.duplicate_action_item(item_id)

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
            query += " AND who = ?"
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
            query += " AND who = ?"
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
            query += " AND who = ?"
            params.append(who_filter)

        query += " ORDER BY completed_at DESC"

        rows = self.db.conn.execute(query, params).fetchall()
        return [self._row_to_action_item(row) for row in rows]

    def search_items(self, search_text: str) -> List[ActionItem]:
        """Search items by title or description."""
        query = """
            SELECT * FROM action_items
            WHERE title LIKE ? OR description LIKE ?
            ORDER BY priority_score DESC
        """
        pattern = f"%{search_text}%"
        rows = self.db.conn.execute(query, (pattern, pattern)).fetchall()
        return [self._row_to_action_item(row) for row in rows]

    # ==================== DEFAULTS ====================

    def get_defaults(self, scope_type: str, scope_key: Optional[str] = None) -> Optional[Defaults]:
        """Get defaults for given scope."""
        if scope_type == "system":
            scope_key = None

        row = self.db.conn.execute(
            "SELECT * FROM defaults WHERE scope_type = ? AND scope_key IS ?",
            (scope_type, scope_key)
        ).fetchone()

        if row:
            return self._row_to_defaults(row)
        return None

    def save_defaults(self, defaults: Defaults):
        """Save or update defaults."""
        self.db.conn.execute("""
            INSERT OR REPLACE INTO defaults (
                scope_type, scope_key, contact_id, who, importance, urgency, size, value,
                "group", category, planned_minutes, start_offset_days, due_offset_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            defaults.scope_type, defaults.scope_key, defaults.contact_id, defaults.who,
            defaults.importance, defaults.urgency, defaults.size, defaults.value,
            defaults.group, defaults.category, defaults.planned_minutes,
            defaults.start_offset_days, defaults.due_offset_days
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
    ):
        """Reschedule an item and record history."""
        item = self.get_action_item(item_id)
        if not item:
            return

        # Record history
        history = RescheduleHistory(
            item_id=item_id,
            from_start=item.start_date,
            from_due=item.due_date,
            to_start=new_start,
            to_due=new_due,
            reason=reason
        )

        self.db.conn.execute("""
            INSERT INTO reschedule_history (
                id, item_id, from_start, from_due, to_start, to_due, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            history.id, history.item_id, history.from_start, history.from_due,
            history.to_start, history.to_due, history.reason, history.created_at
        ))

        # Update item
        item.start_date = new_start
        item.due_date = new_due
        self.update_action_item(item)

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
        """Create a work log entry."""
        self.db.conn.execute("""
            INSERT INTO work_logs (
                id, item_id, started_at, ended_at, minutes, note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            log.id, log.item_id, log.started_at, log.ended_at,
            log.minutes, log.note, log.created_at
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
            next_action = row["next_action"]
        except (KeyError, IndexError):
            next_action = None

        return ActionItem(
            id=row["id"],
            who=row["who"],
            contact_id=row["contact_id"],
            parent_id=row["parent_id"],
            title=row["title"],
            description=row["description"],
            next_action=next_action,
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
            segment_description_id=segment_description_id,
            is_habit=is_habit,
            percent_complete=percent_complete,
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
            due_offset_days=row["due_offset_days"]
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
        """Convert database row to WorkLog."""
        return WorkLog(
            id=row["id"],
            item_id=row["item_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            minutes=row["minutes"],
            note=row["note"],
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
