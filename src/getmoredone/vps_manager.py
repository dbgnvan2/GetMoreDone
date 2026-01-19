"""
VPS (Visionary Planning System) Database Manager
Provides CRUD operations for all VPS entities.
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from .database import Database


class VPSManager:
    """Manages all VPS database operations."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize VPS manager with database connection."""
        self.db = Database(db_path)
        self.db.connect()
        self.db.initialize_schema()

    def close(self):
        """Close database connection."""
        self.db.close()

    # ========================================================================
    # SEGMENT DESCRIPTIONS
    # ========================================================================

    def get_all_segments(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all life segments."""
        query = "SELECT * FROM segment_descriptions"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY order_index"

        cursor = self.db.conn.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_segment(self, segment_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific segment by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM segment_descriptions WHERE id = ?",
            (segment_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_segment(self, name: str, description: str, color_hex: str,
                      order_index: int) -> str:
        """Create a new life segment."""
        segment_id = f"seg-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO segment_descriptions
            (id, name, description, color_hex, order_index, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (segment_id, name, description, color_hex, order_index, now, now))

        self.db.conn.commit()
        return segment_id

    def update_segment(self, segment_id: str, **kwargs) -> bool:
        """Update a segment's fields."""
        allowed_fields = {'name', 'description', 'color_hex', 'order_index', 'is_active'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [segment_id]

        self.db.conn.execute(
            f"UPDATE segment_descriptions SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # TL_VISIONS (Top Level Visions)
    # ========================================================================

    def get_tl_visions(self, segment_id: Optional[str] = None,
                       active_only: bool = True) -> List[Dict[str, Any]]:
        """Get TL visions, optionally filtered by segment."""
        query = "SELECT * FROM tl_visions WHERE 1=1"
        params = []

        if segment_id:
            query += " AND segment_description_id = ?"
            params.append(segment_id)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY start_year DESC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_tl_vision(self, vision_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific TL vision by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM tl_visions WHERE id = ?",
            (vision_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_tl_vision(self, segment_description_id: str, start_year: int,
                        end_year: int, title: str, vision_statement: str = "",
                        success_metrics: str = "[]") -> str:
        """Create a new TL vision."""
        vision_id = f"tlv-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO tl_visions
            (id, segment_description_id, start_year, end_year, title, vision_statement,
             success_metrics, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (vision_id, segment_description_id, start_year, end_year, title,
              vision_statement, success_metrics, now, now))

        self.db.conn.commit()
        return vision_id

    def update_tl_vision(self, vision_id: str, **kwargs) -> bool:
        """Update a TL vision's fields."""
        allowed_fields = {'title', 'vision_statement', 'success_metrics',
                         'review_date', 'is_active', 'start_year', 'end_year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [vision_id]

        self.db.conn.execute(
            f"UPDATE tl_visions SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # ANNUAL_VISIONS
    # ========================================================================

    def get_annual_visions(self, tl_vision_id: Optional[str] = None,
                          year: Optional[int] = None,
                          active_only: bool = True) -> List[Dict[str, Any]]:
        """Get annual visions, optionally filtered."""
        query = "SELECT * FROM annual_visions WHERE 1=1"
        params = []

        if tl_vision_id:
            query += " AND tl_vision_id = ?"
            params.append(tl_vision_id)

        if year:
            query += " AND year = ?"
            params.append(year)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY year DESC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_annual_vision(self, vision_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific annual vision by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM annual_visions WHERE id = ?",
            (vision_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_annual_vision(self, tl_vision_id: str, segment_description_id: str,
                           year: int, title: str, vision_statement: str = "",
                           key_priorities: str = "[]") -> str:
        """Create a new annual vision."""
        vision_id = f"av-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO annual_visions
            (id, tl_vision_id, segment_description_id, year, title, vision_statement,
             key_priorities, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (vision_id, tl_vision_id, segment_description_id, year, title,
              vision_statement, key_priorities, now, now))

        self.db.conn.commit()
        return vision_id

    def update_annual_vision(self, vision_id: str, **kwargs) -> bool:
        """Update an annual vision's fields."""
        allowed_fields = {'title', 'vision_statement', 'key_priorities', 'is_active', 'year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [vision_id]

        self.db.conn.execute(
            f"UPDATE annual_visions SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # ANNUAL_PLANS
    # ========================================================================

    def get_annual_plans(self, annual_vision_id: Optional[str] = None,
                        year: Optional[int] = None,
                        active_only: bool = True) -> List[Dict[str, Any]]:
        """Get annual plans, optionally filtered."""
        query = "SELECT * FROM annual_plans WHERE 1=1"
        params = []

        if annual_vision_id:
            query += " AND annual_vision_id = ?"
            params.append(annual_vision_id)

        if year:
            query += " AND year = ?"
            params.append(year)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY year DESC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_annual_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific annual plan by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM annual_plans WHERE id = ?",
            (plan_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_annual_plan(self, annual_vision_id: str, segment_description_id: str,
                          year: int, theme: str, objective: str = "",
                          description: str = "") -> str:
        """Create a new annual plan."""
        plan_id = f"ap-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO annual_plans
            (id, annual_vision_id, segment_description_id, year, theme, objective,
             description, status, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started', 1, ?, ?)
        """, (plan_id, annual_vision_id, segment_description_id, year, theme,
              objective, description, now, now))

        self.db.conn.commit()
        return plan_id

    def update_annual_plan(self, plan_id: str, **kwargs) -> bool:
        """Update an annual plan's fields."""
        allowed_fields = {'theme', 'objective', 'description', 'status',
                         'target_date', 'is_active', 'year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [plan_id]

        self.db.conn.execute(
            f"UPDATE annual_plans SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # QUARTER_INITIATIVES
    # ========================================================================

    def get_quarter_initiatives(self, annual_plan_id: Optional[str] = None,
                               quarter: Optional[int] = None,
                               year: Optional[int] = None,
                               active_only: bool = True) -> List[Dict[str, Any]]:
        """Get quarter initiatives, optionally filtered."""
        query = "SELECT * FROM quarter_initiatives WHERE 1=1"
        params = []

        if annual_plan_id:
            query += " AND annual_plan_id = ?"
            params.append(annual_plan_id)

        if quarter:
            query += " AND quarter = ?"
            params.append(quarter)

        if year:
            query += " AND year = ?"
            params.append(year)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY year DESC, quarter DESC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_quarter_initiative(self, initiative_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific quarter initiative by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM quarter_initiatives WHERE id = ?",
            (initiative_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_quarter_initiative(self, annual_plan_id: str, segment_description_id: str,
                                 quarter: int, year: int, title: str,
                                 outcome_statement: str = "",
                                 tracking_measures: str = "[]") -> str:
        """Create a new quarter initiative."""
        initiative_id = f"qi-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO quarter_initiatives
            (id, annual_plan_id, segment_description_id, quarter, year, title,
             outcome_statement, tracking_measures, status, progress_pct, is_active,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'not_started', 0, 1, ?, ?)
        """, (initiative_id, annual_plan_id, segment_description_id, quarter, year,
              title, outcome_statement, tracking_measures, now, now))

        self.db.conn.commit()
        return initiative_id

    def update_quarter_initiative(self, initiative_id: str, **kwargs) -> bool:
        """Update a quarter initiative's fields."""
        allowed_fields = {'title', 'outcome_statement', 'tracking_measures',
                         'status', 'progress_pct', 'is_active', 'quarter', 'year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [initiative_id]

        self.db.conn.execute(
            f"UPDATE quarter_initiatives SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # MONTH_TACTICS
    # ========================================================================

    def get_month_tactics(self, quarter_initiative_id: Optional[str] = None,
                         month: Optional[int] = None,
                         year: Optional[int] = None,
                         active_only: bool = True) -> List[Dict[str, Any]]:
        """Get month tactics, optionally filtered."""
        query = "SELECT * FROM month_tactics WHERE 1=1"
        params = []

        if quarter_initiative_id:
            query += " AND quarter_initiative_id = ?"
            params.append(quarter_initiative_id)

        if month:
            query += " AND month = ?"
            params.append(month)

        if year:
            query += " AND year = ?"
            params.append(year)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY year DESC, month DESC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_month_tactic(self, tactic_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific month tactic by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM month_tactics WHERE id = ?",
            (tactic_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_month_tactic(self, quarter_initiative_id: str, segment_description_id: str,
                           month: int, year: int, priority_focus: str,
                           description: str = "") -> str:
        """Create a new month tactic."""
        tactic_id = f"mt-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO month_tactics
            (id, quarter_initiative_id, segment_description_id, month, year,
             priority_focus, description, status, progress_pct, is_active,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'planned', 0, 1, ?, ?)
        """, (tactic_id, quarter_initiative_id, segment_description_id, month, year,
              priority_focus, description, now, now))

        self.db.conn.commit()
        return tactic_id

    def update_month_tactic(self, tactic_id: str, **kwargs) -> bool:
        """Update a month tactic's fields."""
        allowed_fields = {'priority_focus', 'description', 'status',
                         'progress_pct', 'is_active', 'month', 'year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [tactic_id]

        self.db.conn.execute(
            f"UPDATE month_tactics SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # WEEK_ACTIONS
    # ========================================================================

    def get_week_actions(self, month_tactic_id: Optional[str] = None,
                        week_start_date: Optional[str] = None,
                        active_only: bool = True) -> List[Dict[str, Any]]:
        """Get week actions, optionally filtered."""
        query = "SELECT * FROM week_actions WHERE 1=1"
        params = []

        if month_tactic_id:
            query += " AND month_tactic_id = ?"
            params.append(month_tactic_id)

        if week_start_date:
            query += " AND week_start_date = ?"
            params.append(week_start_date)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY week_start_date DESC, order_index"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_week_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific week action by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM week_actions WHERE id = ?",
            (action_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_week_action(self, month_tactic_id: str, segment_description_id: str,
                          week_start_date: str, week_end_date: str, title: str,
                          description: str = "", outcome_expected: str = "",
                          step_1: str = "", step_2: str = "", step_3: str = "",
                          step_4: str = "", step_5: str = "",
                          key_result_1: str = "", key_result_2: str = "", key_result_3: str = "",
                          key_result_4: str = "", key_result_5: str = "") -> str:
        """Create a new week action."""
        action_id = f"wa-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO week_actions
            (id, month_tactic_id, segment_description_id, week_start_date, week_end_date,
             title, description, outcome_expected, status, is_active, created_at, updated_at,
             step_1, step_2, step_3, step_4, step_5,
             key_result_1, key_result_2, key_result_3, key_result_4, key_result_5)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planned', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (action_id, month_tactic_id, segment_description_id, week_start_date,
              week_end_date, title, description, outcome_expected, now, now,
              step_1, step_2, step_3, step_4, step_5,
              key_result_1, key_result_2, key_result_3, key_result_4, key_result_5))

        self.db.conn.commit()
        return action_id

    def update_week_action(self, action_id: str, **kwargs) -> bool:
        """Update a week action's fields."""
        allowed_fields = {'title', 'description', 'outcome_expected', 'status',
                         'order_index', 'is_active', 'week_start_date', 'week_end_date',
                         'step_1', 'step_2', 'step_3', 'step_4', 'step_5',
                         'key_result_1', 'key_result_2', 'key_result_3', 'key_result_4', 'key_result_5'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [action_id]

        self.db.conn.execute(
            f"UPDATE week_actions SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    def auto_create_action_items_from_steps(self, week_action_id: str) -> List[str]:
        """
        Auto-create Action Items from non-blank Step fields in a Week Action.
        Returns list of created action item IDs.
        """
        from datetime import timedelta
        from .models import ActionItem

        # Get the week action
        week_action = self.get_week_action(week_action_id)
        if not week_action:
            return []

        week_start_date = week_action['week_start_date']
        segment_id = week_action['segment_description_id']
        created_item_ids = []

        # Process each step field
        day_offset = 0
        for i in range(1, 6):
            step_field = f'step_{i}'
            key_result_field = f'key_result_{i}'

            step_value = week_action.get(step_field, '').strip() if week_action.get(step_field) else ''
            key_result_value = week_action.get(key_result_field, '').strip() if week_action.get(key_result_field) else ''

            # Only create Action Item if Step is non-blank
            if step_value:
                # Calculate start date (week_start + day_offset)
                from datetime import datetime
                start_dt = datetime.fromisoformat(week_start_date)
                item_start_date = (start_dt + timedelta(days=day_offset)).date().isoformat()

                # Build description from Step and Key Result
                description = f"Step {i}: {step_value}"
                if key_result_value:
                    description += f"\nKey Result: {key_result_value}"

                # Create Action Item using db_manager
                action_item = ActionItem(
                    who="",  # Will be filled by system defaults
                    title=step_value[:100],  # Use step as title (limit to reasonable length)
                    description=description,
                    start_date=item_start_date,
                    week_action_id=week_action_id,
                    segment_description_id=segment_id
                )

                # Create the item (apply_defaults=True will use system defaults)
                item_id = self.db.create_action_item(action_item, apply_defaults=True)
                created_item_ids.append(item_id)

                # Increment day offset for next action item
                day_offset += 1

        return created_item_ids

    # ========================================================================
    # ACTION ITEMS (VPS Extensions)
    # ========================================================================

    def link_action_item_to_week_action(self, action_item_id: str,
                                       week_action_id: str,
                                       segment_description_id: str) -> bool:
        """Link an action item to a week action."""
        self.db.conn.execute("""
            UPDATE action_items
            SET week_action_id = ?, segment_description_id = ?, updated_at = ?
            WHERE id = ?
        """, (week_action_id, segment_description_id, datetime.now().isoformat(),
              action_item_id))

        self.db.conn.commit()
        return True

    def get_action_items_for_week_action(self, week_action_id: str) -> List[Dict[str, Any]]:
        """Get all action items linked to a week action."""
        cursor = self.db.conn.execute("""
            SELECT * FROM action_items
            WHERE week_action_id = ?
            ORDER BY start_date, title
        """, (week_action_id,))

        return [dict(row) for row in cursor.fetchall()]

    def get_action_item(self, action_item_id: str) -> Optional[Dict[str, Any]]:
        """Get a single action item by ID."""
        cursor = self.db.conn.execute("""
            SELECT * FROM action_items
            WHERE id = ?
        """, (action_item_id,))

        row = cursor.fetchone()
        return dict(row) if row else None

    def update_action_item(self, action_item_id: str, **kwargs) -> bool:
        """Update an action item with provided fields."""
        if not kwargs:
            return False

        # Build update query dynamically
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)

        # Add updated_at timestamp
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(action_item_id)

        query = f"""
            UPDATE action_items
            SET {', '.join(fields)}
            WHERE id = ?
        """

        self.db.conn.execute(query, values)
        self.db.conn.commit()
        return True

    # ========================================================================
    # HABIT TRACKING
    # ========================================================================

    def create_habit_tracking_days(self, action_item_id: str, start_date: str,
                                   end_date: str) -> int:
        """Create habit tracking records for each day in date range."""
        from datetime import datetime, timedelta

        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        count = 0
        current = start
        while current <= end:
            tracking_id = f"ht-{uuid4().hex[:8]}"
            now = datetime.now().isoformat()

            try:
                self.db.conn.execute("""
                    INSERT INTO habit_tracking
                    (id, action_item_id, tracking_date, is_completed, created_at)
                    VALUES (?, ?, ?, 0, ?)
                """, (tracking_id, action_item_id, current.date().isoformat(), now))
                count += 1
            except sqlite3.IntegrityError:
                # Day already exists, skip
                pass

            current += timedelta(days=1)

        self.db.conn.commit()
        return count

    def toggle_habit_day(self, action_item_id: str, tracking_date: str,
                        is_completed: bool, notes: str = "") -> bool:
        """Toggle habit completion for a specific day."""
        self.db.conn.execute("""
            UPDATE habit_tracking
            SET is_completed = ?, notes = ?
            WHERE action_item_id = ? AND tracking_date = ?
        """, (1 if is_completed else 0, notes, action_item_id, tracking_date))

        self.db.conn.commit()

        # Recalculate percent_complete
        self._update_habit_percent_complete(action_item_id)
        return True

    def get_habit_tracking(self, action_item_id: str) -> List[Dict[str, Any]]:
        """Get all habit tracking records for an action item."""
        cursor = self.db.conn.execute("""
            SELECT * FROM habit_tracking
            WHERE action_item_id = ?
            ORDER BY tracking_date
        """, (action_item_id,))

        return [dict(row) for row in cursor.fetchall()]

    def _update_habit_percent_complete(self, action_item_id: str):
        """Recalculate and update percent_complete for a habit."""
        cursor = self.db.conn.execute("""
            SELECT
                COUNT(*) as total_days,
                SUM(is_completed) as completed_days
            FROM habit_tracking
            WHERE action_item_id = ?
        """, (action_item_id,))

        row = cursor.fetchone()
        total = row['total_days']
        completed = row['completed_days'] or 0

        percent = int((completed / total) * 100) if total > 0 else 0

        self.db.conn.execute("""
            UPDATE action_items
            SET percent_complete = ?, updated_at = ?
            WHERE id = ?
        """, (percent, datetime.now().isoformat(), action_item_id))

        self.db.conn.commit()

    # ========================================================================
    # HIERARCHY NAVIGATION
    # ========================================================================

    def get_full_hierarchy_for_segment(self, segment_id: str) -> Dict[str, Any]:
        """Get complete planning hierarchy for a segment."""
        segment = self.get_segment(segment_id)
        if not segment:
            return {}

        tl_visions = self.get_tl_visions(segment_id=segment_id)

        for tl_vision in tl_visions:
            tl_vision['annual_visions'] = self.get_annual_visions(
                tl_vision_id=tl_vision['id']
            )

            for annual_vision in tl_vision['annual_visions']:
                annual_vision['annual_plans'] = self.get_annual_plans(
                    annual_vision_id=annual_vision['id']
                )

                for annual_plan in annual_vision['annual_plans']:
                    annual_plan['quarter_initiatives'] = self.get_quarter_initiatives(
                        annual_plan_id=annual_plan['id']
                    )

                    for quarter_initiative in annual_plan['quarter_initiatives']:
                        quarter_initiative['month_tactics'] = self.get_month_tactics(
                            quarter_initiative_id=quarter_initiative['id']
                        )

                        for month_tactic in quarter_initiative['month_tactics']:
                            month_tactic['week_actions'] = self.get_week_actions(
                                month_tactic_id=month_tactic['id']
                            )

                            for week_action in month_tactic['week_actions']:
                                week_action['action_items'] = self.get_action_items_for_week_action(
                                    week_action['id']
                                )

        return {
            'segment': segment,
            'tl_visions': tl_visions
        }

    def get_hierarchy_breadcrumb(self, entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
        """Get breadcrumb trail from segment down to specific entity."""
        breadcrumb = []

        if entity_type == 'week_action':
            week_action = self.get_week_action(entity_id)
            if week_action:
                breadcrumb.insert(0, {'type': 'week_action', 'data': week_action})
                entity_type = 'month_tactic'
                entity_id = week_action['month_tactic_id']

        if entity_type == 'month_tactic':
            month_tactic = self.get_month_tactic(entity_id)
            if month_tactic:
                breadcrumb.insert(0, {'type': 'month_tactic', 'data': month_tactic})
                entity_type = 'quarter_initiative'
                entity_id = month_tactic['quarter_initiative_id']

        if entity_type == 'quarter_initiative':
            quarter_initiative = self.get_quarter_initiative(entity_id)
            if quarter_initiative:
                breadcrumb.insert(0, {'type': 'quarter_initiative', 'data': quarter_initiative})
                entity_type = 'annual_plan'
                entity_id = quarter_initiative['annual_plan_id']

        if entity_type == 'annual_plan':
            annual_plan = self.get_annual_plan(entity_id)
            if annual_plan:
                breadcrumb.insert(0, {'type': 'annual_plan', 'data': annual_plan})
                entity_type = 'annual_vision'
                entity_id = annual_plan['annual_vision_id']

        if entity_type == 'annual_vision':
            annual_vision = self.get_annual_vision(entity_id)
            if annual_vision:
                breadcrumb.insert(0, {'type': 'annual_vision', 'data': annual_vision})
                entity_type = 'tl_vision'
                entity_id = annual_vision['tl_vision_id']

        if entity_type == 'tl_vision':
            tl_vision = self.get_tl_vision(entity_id)
            if tl_vision:
                breadcrumb.insert(0, {'type': 'tl_vision', 'data': tl_vision})
                segment = self.get_segment(tl_vision['segment_description_id'])
                if segment:
                    breadcrumb.insert(0, {'type': 'segment', 'data': segment})

        return breadcrumb

    # ========================================================================
    # DELETE METHODS (WITH CHILD RECORD PROTECTION)
    # ========================================================================

    def _has_children(self, table: str, parent_id_column: str, parent_id: str) -> bool:
        """Check if a record has child records."""
        cursor = self.db.conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {parent_id_column} = ?",
            (parent_id,)
        )
        count = cursor.fetchone()[0]
        return count > 0

    def delete_tl_vision(self, vision_id: str) -> bool:
        """
        Delete a TL Vision if it has no child records.
        Returns True if deleted, False if children exist.
        """
        # Check for annual visions
        if self._has_children('annual_visions', 'tl_vision_id', vision_id):
            return False

        self.db.conn.execute(
            "DELETE FROM tl_visions WHERE id = ?",
            (vision_id,)
        )
        self.db.conn.commit()
        return True

    def delete_annual_vision(self, vision_id: str) -> bool:
        """
        Delete an Annual Vision if it has no child records.
        Returns True if deleted, False if children exist.
        """
        # Check for annual plans
        if self._has_children('annual_plans', 'annual_vision_id', vision_id):
            return False

        self.db.conn.execute(
            "DELETE FROM annual_visions WHERE id = ?",
            (vision_id,)
        )
        self.db.conn.commit()
        return True

    def delete_annual_plan(self, plan_id: str) -> bool:
        """
        Delete an Annual Plan if it has no child records.
        Returns True if deleted, False if children exist.
        """
        # Check for quarter initiatives
        if self._has_children('quarter_initiatives', 'annual_plan_id', plan_id):
            return False

        self.db.conn.execute(
            "DELETE FROM annual_plans WHERE id = ?",
            (plan_id,)
        )
        self.db.conn.commit()
        return True

    def delete_quarter_initiative(self, initiative_id: str) -> bool:
        """
        Delete a Quarter Initiative if it has no child records.
        Returns True if deleted, False if children exist.
        """
        # Check for month tactics
        if self._has_children('month_tactics', 'quarter_initiative_id', initiative_id):
            return False

        self.db.conn.execute(
            "DELETE FROM quarter_initiatives WHERE id = ?",
            (initiative_id,)
        )
        self.db.conn.commit()
        return True

    def delete_month_tactic(self, tactic_id: str) -> bool:
        """
        Delete a Month Tactic if it has no child records.
        Returns True if deleted, False if children exist.
        """
        # Check for week actions
        if self._has_children('week_actions', 'month_tactic_id', tactic_id):
            return False

        self.db.conn.execute(
            "DELETE FROM month_tactics WHERE id = ?",
            (tactic_id,)
        )
        self.db.conn.commit()
        return True

    def delete_week_action(self, action_id: str) -> bool:
        """
        Delete a Week Action if it has no child records.
        Returns True if deleted, False if children exist.
        """
        # Check for linked action items
        if self._has_children('action_items', 'week_action_id', action_id):
            return False

        self.db.conn.execute(
            "DELETE FROM week_actions WHERE id = ?",
            (action_id,)
        )
        self.db.conn.commit()
        return True

    def delete_segment(self, segment_id: str) -> bool:
        """
        Delete a Segment if it has no child records.
        Returns True if deleted, False if children exist.
        """
        # Check for TL visions
        if self._has_children('tl_visions', 'segment_description_id', segment_id):
            return False

        self.db.conn.execute(
            "DELETE FROM segment_descriptions WHERE id = ?",
            (segment_id,)
        )
        self.db.conn.commit()
        return True
