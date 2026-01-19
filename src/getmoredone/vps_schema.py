"""
VPS (Visionary Planning System) Database Schema
Extends GetMoreDone with strategic planning hierarchy.

Based on simplified architecture where:
- Each Segment_Description has its own complete plan hierarchy
- Each level has one parent and can have 0-N children
- Action items can be standalone OR linked to a plan
- Action items can be tasks or habits with daily tracking
"""

import sqlite3
from typing import Optional


class VPSSchema:
    """Manages VPS table creation and migrations."""

    @staticmethod
    def initialize_vps_schema(conn: sqlite3.Connection):
        """Create all VPS tables and extend GMD tables."""

        # ========================================================================
        # SEGMENT DESCRIPTIONS (Life Segments)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS segment_descriptions (
                id               TEXT PRIMARY KEY,
                name             TEXT NOT NULL UNIQUE,
                description      TEXT,
                color_hex        TEXT NOT NULL,
                order_index      INTEGER,
                is_active        INTEGER DEFAULT 1,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            )
        """)

        # ========================================================================
        # TL_VISION (Top Level Vision - typically 5 years)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tl_visions (
                id                   TEXT PRIMARY KEY,
                segment_description_id TEXT NOT NULL REFERENCES segment_descriptions(id) ON DELETE CASCADE,
                start_year           INTEGER NOT NULL,
                end_year             INTEGER NOT NULL,
                title                TEXT,
                vision_statement     TEXT,
                success_metrics      TEXT,  -- JSON array
                is_active            INTEGER DEFAULT 1,
                review_date          TEXT,
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL,
                CHECK (end_year > start_year)
            )
        """)

        # ========================================================================
        # ANNUAL_VISION (One-year vision within TL_Vision)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS annual_visions (
                id                   TEXT PRIMARY KEY,
                tl_vision_id         TEXT NOT NULL REFERENCES tl_visions(id) ON DELETE CASCADE,
                segment_description_id TEXT NOT NULL REFERENCES segment_descriptions(id) ON DELETE CASCADE,
                year                 INTEGER NOT NULL,
                title                TEXT,
                vision_statement     TEXT,
                key_priorities       TEXT,  -- JSON array
                is_active            INTEGER DEFAULT 1,
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL
            )
        """)

        # ========================================================================
        # ANNUAL_PLAN (Executable plan for the year)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS annual_plans (
                id                   TEXT PRIMARY KEY,
                annual_vision_id     TEXT NOT NULL REFERENCES annual_visions(id) ON DELETE CASCADE,
                segment_description_id TEXT NOT NULL REFERENCES segment_descriptions(id) ON DELETE CASCADE,
                year                 INTEGER NOT NULL,
                theme                TEXT,
                objective            TEXT,
                description          TEXT,
                status               TEXT DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'at_risk', 'completed', 'deferred', 'cancelled')),
                target_date          TEXT,
                is_active            INTEGER DEFAULT 1,
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL
            )
        """)

        # ========================================================================
        # QUARTER_INITIATIVE (Quarterly focus areas)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quarter_initiatives (
                id                   TEXT PRIMARY KEY,
                annual_plan_id       TEXT NOT NULL REFERENCES annual_plans(id) ON DELETE CASCADE,
                segment_description_id TEXT NOT NULL REFERENCES segment_descriptions(id) ON DELETE CASCADE,
                quarter              INTEGER NOT NULL CHECK(quarter BETWEEN 1 AND 4),
                year                 INTEGER NOT NULL,
                title                TEXT NOT NULL,
                outcome_statement    TEXT,
                tracking_measures    TEXT,  -- JSON array
                status               TEXT DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'at_risk', 'completed', 'on_hold', 'cancelled')),
                progress_pct         INTEGER DEFAULT 0 CHECK(progress_pct BETWEEN 0 AND 100),
                is_active            INTEGER DEFAULT 1,
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL
            )
        """)

        # ========================================================================
        # MONTH_TACTIC (Monthly execution tactics)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS month_tactics (
                id                   TEXT PRIMARY KEY,
                quarter_initiative_id TEXT NOT NULL REFERENCES quarter_initiatives(id) ON DELETE CASCADE,
                segment_description_id TEXT NOT NULL REFERENCES segment_descriptions(id) ON DELETE CASCADE,
                month                INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
                year                 INTEGER NOT NULL,
                priority_focus       TEXT NOT NULL,
                description          TEXT,
                status               TEXT DEFAULT 'planned' CHECK(status IN ('planned', 'active', 'completed', 'on_hold', 'cancelled')),
                progress_pct         INTEGER DEFAULT 0 CHECK(progress_pct BETWEEN 0 AND 100),
                is_active            INTEGER DEFAULT 1,
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL
            )
        """)

        # ========================================================================
        # WEEK_ACTION (Weekly actionable items)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS week_actions (
                id                   TEXT PRIMARY KEY,
                month_tactic_id      TEXT NOT NULL REFERENCES month_tactics(id) ON DELETE CASCADE,
                segment_description_id TEXT NOT NULL REFERENCES segment_descriptions(id) ON DELETE CASCADE,
                week_start_date      TEXT NOT NULL,
                week_end_date        TEXT NOT NULL,
                title                TEXT NOT NULL,
                description          TEXT,
                outcome_expected     TEXT,
                status               TEXT DEFAULT 'planned' CHECK(status IN ('planned', 'in_progress', 'completed', 'deferred', 'cancelled')),
                order_index          INTEGER,
                is_active            INTEGER DEFAULT 1,
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL,
                step_1               TEXT,
                step_2               TEXT,
                step_3               TEXT,
                step_4               TEXT,
                step_5               TEXT,
                key_result_1         TEXT,
                key_result_2         TEXT,
                key_result_3         TEXT,
                key_result_4         TEXT,
                key_result_5         TEXT
            )
        """)

        # ========================================================================
        # EXTEND ACTION_ITEMS for VPS Integration
        # ========================================================================
        VPSSchema._extend_action_items(conn)

        # ========================================================================
        # EXTEND WEEK_ACTIONS for Step/Key Result fields
        # ========================================================================
        VPSSchema._extend_week_actions(conn)

        # ========================================================================
        # HABIT_TRACKING (Daily completion tracking for habits)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS habit_tracking (
                id              TEXT PRIMARY KEY,
                action_item_id  TEXT NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,
                tracking_date   TEXT NOT NULL,
                is_completed    INTEGER DEFAULT 0,
                notes           TEXT,
                created_at      TEXT NOT NULL,
                UNIQUE(action_item_id, tracking_date)
            )
        """)

        # ========================================================================
        # INDEXES for Performance
        # ========================================================================
        VPSSchema._create_indexes(conn)

        # ========================================================================
        # SEED DATA - Default Life Segments
        # ========================================================================
        VPSSchema._seed_segment_descriptions(conn)

        conn.commit()

    @staticmethod
    def _extend_action_items(conn: sqlite3.Connection):
        """Add VPS-related columns to existing action_items table."""
        # Check which columns already exist
        cursor = conn.execute("PRAGMA table_info(action_items)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'is_habit' not in columns:
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN is_habit INTEGER DEFAULT 0
            """)

        if 'percent_complete' not in columns:
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN percent_complete INTEGER DEFAULT 0 CHECK(percent_complete BETWEEN 0 AND 100)
            """)

        if 'week_action_id' not in columns:
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN week_action_id TEXT REFERENCES week_actions(id) ON DELETE SET NULL
            """)

        if 'segment_description_id' not in columns:
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN segment_description_id TEXT REFERENCES segment_descriptions(id) ON DELETE SET NULL
            """)

    @staticmethod
    def _extend_week_actions(conn: sqlite3.Connection):
        """Add Step and Key Result columns to existing week_actions table."""
        # Check which columns already exist
        cursor = conn.execute("PRAGMA table_info(week_actions)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add Step fields
        for i in range(1, 6):
            field_name = f'step_{i}'
            if field_name not in columns:
                conn.execute(f"""
                    ALTER TABLE week_actions
                    ADD COLUMN {field_name} TEXT
                """)

        # Add Key Result fields
        for i in range(1, 6):
            field_name = f'key_result_{i}'
            if field_name not in columns:
                conn.execute(f"""
                    ALTER TABLE week_actions
                    ADD COLUMN {field_name} TEXT
                """)

    @staticmethod
    def _create_indexes(conn: sqlite3.Connection):
        """Create performance indexes for VPS tables."""

        # Segment descriptions
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_segments_active
            ON segment_descriptions(is_active)
        """)

        # TL Visions
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tl_visions_segment
            ON tl_visions(segment_description_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tl_visions_years
            ON tl_visions(start_year, end_year)
        """)

        # Annual Visions
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_visions_parent
            ON annual_visions(tl_vision_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_visions_segment
            ON annual_visions(segment_description_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_visions_year
            ON annual_visions(year)
        """)

        # Annual Plans
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_plans_parent
            ON annual_plans(annual_vision_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_plans_segment
            ON annual_plans(segment_description_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_plans_year
            ON annual_plans(year)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_plans_status
            ON annual_plans(status)
        """)

        # Quarter Initiatives
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_quarter_initiatives_parent
            ON quarter_initiatives(annual_plan_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_quarter_initiatives_segment
            ON quarter_initiatives(segment_description_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_quarter_initiatives_quarter
            ON quarter_initiatives(quarter, year)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_quarter_initiatives_status
            ON quarter_initiatives(status)
        """)

        # Month Tactics
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_month_tactics_parent
            ON month_tactics(quarter_initiative_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_month_tactics_segment
            ON month_tactics(segment_description_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_month_tactics_month
            ON month_tactics(month, year)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_month_tactics_status
            ON month_tactics(status)
        """)

        # Week Actions
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_week_actions_parent
            ON week_actions(month_tactic_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_week_actions_segment
            ON week_actions(segment_description_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_week_actions_dates
            ON week_actions(week_start_date, week_end_date)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_week_actions_status
            ON week_actions(status)
        """)

        # Action Items VPS extensions
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_action_items_week_action
            ON action_items(week_action_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_action_items_segment
            ON action_items(segment_description_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_action_items_habit
            ON action_items(is_habit) WHERE is_habit = 1
        """)

        # Habit Tracking
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_habit_tracking_item
            ON habit_tracking(action_item_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_habit_tracking_date
            ON habit_tracking(tracking_date)
        """)

    @staticmethod
    def _seed_segment_descriptions(conn: sqlite3.Connection):
        """Insert default life segments if they don't exist."""
        from datetime import datetime
        now = datetime.now().isoformat()

        segments = [
            ('seg-1', 'Health', 'Physical and mental wellbeing', '#4CAF50', 1),
            ('seg-2', 'Purposeful Activity', 'Career, work, and meaningful projects', '#2196F3', 2),
            ('seg-3', 'Skills - Cognitive', 'Learning and intellectual development', '#9C27B0', 3),
            ('seg-4', 'Wealth Creation', 'Financial growth and management', '#FF9800', 4),
            ('seg-5', 'Relationships', 'Personal and professional connections', '#E91E63', 5),
            ('seg-6', 'Recreation', 'Hobbies and leisure activities', '#00BCD4', 6),
            ('seg-7', 'Contribution', 'Giving back and community involvement', '#8BC34A', 7),
            ('seg-8', 'Travel', 'Exploration and adventure', '#FFC107', 8),
            ('seg-9', 'Personal Growth', 'Self-improvement and spirituality', '#673AB7', 9),
        ]

        for seg_id, name, description, color, order in segments:
            conn.execute("""
                INSERT OR IGNORE INTO segment_descriptions
                (id, name, description, color_hex, order_index, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """, (seg_id, name, description, color, order, now, now))
