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
        # ANNUAL_INITIATIVE (Annual outcomes under an Annual Plan)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS annual_initiatives (
                id                   TEXT PRIMARY KEY,
                annual_plan_id       TEXT NOT NULL REFERENCES annual_plans(id) ON DELETE CASCADE,
                segment_description_id TEXT NOT NULL REFERENCES segment_descriptions(id) ON DELETE CASCADE,
                year                 INTEGER NOT NULL,
                title                TEXT NOT NULL,
                description          TEXT,
                outcome_statement    TEXT,
                status               TEXT DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'at_risk', 'completed', 'on_hold', 'cancelled')),
                progress_pct         INTEGER DEFAULT 0 CHECK(progress_pct BETWEEN 0 AND 100),
                is_active            INTEGER DEFAULT 1,
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL
            )
        """)

        # ========================================================================
        # VISION ELEMENT MASTER DATA (Segment > SubSegment > Category)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vision_segments (
                id               TEXT PRIMARY KEY,
                name             TEXT NOT NULL UNIQUE,
                vision_text      TEXT,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS vision_subsegments (
                id               TEXT PRIMARY KEY,
                segment_id       TEXT NOT NULL REFERENCES vision_segments(id) ON DELETE CASCADE,
                name             TEXT NOT NULL,
                color_hex        TEXT,
                description      TEXT,
                vision_text      TEXT,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL,
                UNIQUE(segment_id, name)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS vision_categories (
                id               TEXT PRIMARY KEY,
                subsegment_id    TEXT NOT NULL REFERENCES vision_subsegments(id) ON DELETE CASCADE,
                name             TEXT NOT NULL,
                color_hex        TEXT,
                description      TEXT,
                vision_text      TEXT,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL,
                UNIQUE(subsegment_id, name)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS vision_elements (
                id               TEXT PRIMARY KEY,
                segment_id       TEXT NOT NULL REFERENCES vision_segments(id) ON DELETE CASCADE,
                subsegment_id    TEXT NOT NULL REFERENCES vision_subsegments(id) ON DELETE CASCADE,
                category_id      TEXT NOT NULL REFERENCES vision_categories(id) ON DELETE CASCADE,
                key_field        TEXT NOT NULL UNIQUE,
                vision_text      TEXT,
                is_active        INTEGER DEFAULT 1,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            )
        """)

        # ========================================================================
        # ANNUAL VISION / PLAN ELEMENTS (created from Vision Elements)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS annual_vision_elements (
                id               TEXT PRIMARY KEY,
                year             INTEGER NOT NULL,
                vision_element_id TEXT NOT NULL REFERENCES vision_elements(id) ON DELETE CASCADE,
                segment_name     TEXT NOT NULL,
                subsegment_name  TEXT NOT NULL,
                category_name    TEXT NOT NULL,
                key_field        TEXT NOT NULL,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL,
                UNIQUE(year, vision_element_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS annual_plan_elements (
                id               TEXT PRIMARY KEY,
                year             INTEGER NOT NULL,
                vision_element_id TEXT NOT NULL REFERENCES vision_elements(id) ON DELETE CASCADE,
                annual_vision_element_id TEXT NOT NULL REFERENCES annual_vision_elements(id) ON DELETE CASCADE,
                segment_name     TEXT NOT NULL,
                subsegment_name  TEXT NOT NULL,
                category_name    TEXT NOT NULL,
                key_field        TEXT NOT NULL,
                q1               INTEGER DEFAULT 0,
                q2               INTEGER DEFAULT 0,
                q3               INTEGER DEFAULT 0,
                q4               INTEGER DEFAULT 0,
                m1               INTEGER DEFAULT 0,
                m2               INTEGER DEFAULT 0,
                m3               INTEGER DEFAULT 0,
                m4               INTEGER DEFAULT 0,
                m5               INTEGER DEFAULT 0,
                m6               INTEGER DEFAULT 0,
                m7               INTEGER DEFAULT 0,
                m8               INTEGER DEFAULT 0,
                m9               INTEGER DEFAULT 0,
                m10              INTEGER DEFAULT 0,
                m11              INTEGER DEFAULT 0,
                m12              INTEGER DEFAULT 0,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL,
                UNIQUE(year, vision_element_id)
            )
        """)

        # ========================================================================
        # QUARTER_INITIATIVE (Quarterly focus areas)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quarter_initiatives (
                id                   TEXT PRIMARY KEY,
                annual_plan_id       TEXT NOT NULL REFERENCES annual_plans(id) ON DELETE CASCADE,
                annual_initiative_id TEXT REFERENCES annual_initiatives(id) ON DELETE CASCADE,
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
        # EXTEND QUARTER_INITIATIVES for annual initiative linkage
        # ========================================================================
        VPSSchema._extend_quarter_initiatives(conn)

        # ========================================================================
        # EXTEND ANNUAL_PLAN_ELEMENTS for period assignment flags
        # ========================================================================
        VPSSchema._extend_annual_plan_elements(conn)

        # ========================================================================
        # EXTEND VISION_SUBSEGMENTS for color support
        # ========================================================================
        VPSSchema._extend_vision_subsegments(conn)

        # ========================================================================
        # EXTEND VISION_ELEMENTS for editable vision text
        # ========================================================================
        VPSSchema._extend_vision_elements(conn)
        VPSSchema._extend_vision_master_text_fields(conn)
        VPSSchema._extend_vision_master_metadata(conn)

        # ========================================================================
        # EXTEND WEEK_ACTIONS for Step/Key Result fields
        # ========================================================================
        VPSSchema._extend_week_actions(conn)

        # ========================================================================
        # VISION_SEGMENTS (Master list: Segment/SubSegment/Category elements)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vision_segments (
                id          TEXT PRIMARY KEY,
                segment_id  TEXT REFERENCES segment_descriptions(id) ON DELETE CASCADE,
                subsegment  TEXT NOT NULL,
                category    TEXT NOT NULL,
                order_index INTEGER DEFAULT 0,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)

        # ========================================================================
        # ANNUAL_VISION_SEGMENT_ITEMS (Which vision segments are assigned to a year)
        # ========================================================================
        conn.execute("""
            CREATE TABLE IF NOT EXISTS annual_vision_segment_items (
                id                TEXT PRIMARY KEY,
                vision_segment_id TEXT NOT NULL REFERENCES vision_segments(id) ON DELETE CASCADE,
                year              INTEGER NOT NULL,
                created_at        TEXT NOT NULL,
                UNIQUE(vision_segment_id, year)
            )
        """)

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

        if 'item_type' not in columns:
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN item_type TEXT NOT NULL DEFAULT 'daily'
            """)

        if 'annual_plan_element_id' not in columns:
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN annual_plan_element_id TEXT
            """)

    @staticmethod
    def _extend_quarter_initiatives(conn: sqlite3.Connection):
        """Add annual initiative linkage to existing quarter_initiatives tables."""
        cursor = conn.execute("PRAGMA table_info(quarter_initiatives)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'annual_initiative_id' not in columns:
            conn.execute("""
                ALTER TABLE quarter_initiatives
                ADD COLUMN annual_initiative_id TEXT REFERENCES annual_initiatives(id) ON DELETE CASCADE
            """)

    @staticmethod
    def _extend_annual_plan_elements(conn: sqlite3.Connection):
        """Add quarter/month assignment flags to annual_plan_elements."""
        cursor = conn.execute("PRAGMA table_info(annual_plan_elements)")
        columns = [row[1] for row in cursor.fetchall()]

        for i in range(1, 5):
            col = f"q{i}"
            if col not in columns:
                conn.execute(f"ALTER TABLE annual_plan_elements ADD COLUMN {col} INTEGER DEFAULT 0")

        for i in range(1, 13):
            col = f"m{i}"
            if col not in columns:
                conn.execute(f"ALTER TABLE annual_plan_elements ADD COLUMN {col} INTEGER DEFAULT 0")

    @staticmethod
    def _extend_vision_subsegments(conn: sqlite3.Connection):
        """Add optional color to vision_subsegments."""
        cursor = conn.execute("PRAGMA table_info(vision_subsegments)")
        columns = [row[1] for row in cursor.fetchall()]

        if "color_hex" not in columns:
            conn.execute("""
                ALTER TABLE vision_subsegments
                ADD COLUMN color_hex TEXT
            """)

    @staticmethod
    def _extend_vision_elements(conn: sqlite3.Connection):
        """Add optional vision text to vision_elements."""
        cursor = conn.execute("PRAGMA table_info(vision_elements)")
        columns = [row[1] for row in cursor.fetchall()]

        if "vision_text" not in columns:
            conn.execute("""
                ALTER TABLE vision_elements
                ADD COLUMN vision_text TEXT
            """)

    @staticmethod
    def _extend_vision_master_text_fields(conn: sqlite3.Connection):
        """Add vision_text columns to segment/subsegment/category master tables."""
        for table in ("vision_segments", "vision_subsegments", "vision_categories"):
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]
            if "vision_text" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN vision_text TEXT")

    @staticmethod
    def _extend_vision_master_metadata(conn: sqlite3.Connection):
        """Add optional metadata fields for subsegment/category management."""
        table_columns = {}
        for table in ("vision_subsegments", "vision_categories"):
            cursor = conn.execute(f"PRAGMA table_info({table})")
            table_columns[table] = [row[1] for row in cursor.fetchall()]

        if "description" not in table_columns["vision_subsegments"]:
            conn.execute("ALTER TABLE vision_subsegments ADD COLUMN description TEXT")

        if "description" not in table_columns["vision_categories"]:
            conn.execute("ALTER TABLE vision_categories ADD COLUMN description TEXT")
        if "color_hex" not in table_columns["vision_categories"]:
            conn.execute("ALTER TABLE vision_categories ADD COLUMN color_hex TEXT")

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

        # Annual Initiatives
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_initiatives_parent
            ON annual_initiatives(annual_plan_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_initiatives_segment
            ON annual_initiatives(segment_description_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_initiatives_year
            ON annual_initiatives(year)
        """)

        # Vision Element hierarchy
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vision_subsegments_segment
            ON vision_subsegments(segment_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vision_categories_subsegment
            ON vision_categories(subsegment_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vision_elements_segment
            ON vision_elements(segment_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vision_elements_subsegment
            ON vision_elements(subsegment_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vision_elements_category
            ON vision_elements(category_id)
        """)

        # Annual element records
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_vision_elements_year
            ON annual_vision_elements(year)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_plan_elements_year
            ON annual_plan_elements(year)
        """)

        # Quarter Initiatives
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_quarter_initiatives_parent
            ON quarter_initiatives(annual_plan_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_quarter_initiatives_annual_initiative
            ON quarter_initiatives(annual_initiative_id)
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_action_items_type
            ON action_items(item_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_action_items_annual_plan_element
            ON action_items(annual_plan_element_id)
        """)

        # Vision Segments
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vision_segments_segment
            ON vision_segments(segment_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vision_segments_order
            ON vision_segments(order_index)
        """)

        # Annual Vision Segment Items
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_vision_segment_items_year
            ON annual_vision_segment_items(year)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_vision_segment_items_vs
            ON annual_vision_segment_items(vision_segment_id)
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
