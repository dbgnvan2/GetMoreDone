"""
VSP (Vision Strategy Plan) Database Schema
Extends GetMoreDone with strategic planning hierarchy.

Based on simplified architecture where:
- Each Segment_Description has its own complete plan hierarchy
- Each level has one parent and can have 0-N children
- Action items can be standalone OR linked to a plan
- Action items can be tasks or habits with daily tracking
"""

import sqlite3
from typing import List, Optional, Tuple


class VPSSchema:
    """Manages VSP table creation and migrations."""

    @staticmethod
    def initialize_vps_schema(conn: sqlite3.Connection):
        """Create all VSP tables and extend GMD tables."""
        legacy_assignment_tables = VPSSchema._prepare_legacy_vision_schema_migration(conn)

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
        VPSSchema._migrate_legacy_vision_schema_data(conn, legacy_assignment_tables)

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
        # EXTEND ACTION_ITEMS for VSP Integration
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
    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table_name: str) -> List[str]:
        if not VPSSchema._table_exists(conn, table_name):
            return []
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [row[1] for row in rows]

    @staticmethod
    def _prepare_legacy_vision_schema_migration(conn: sqlite3.Connection) -> List[Tuple[str, str]]:
        """
        Detect and rename the old Vision Segment schema so modern tables can be created.

        Legacy shape:
        - vision_segments(id, segment_id, subsegment, category, order_index, created_at, updated_at)
        - annual_vision_segment_items(vision_segment_id, year, ...)
        """
        columns = VPSSchema._table_columns(conn, "vision_segments")
        if not columns:
            return []

        is_legacy_segments = (
            "name" not in columns and {"segment_id", "subsegment", "category"}.issubset(set(columns))
        )
        if not is_legacy_segments:
            return []

        conn.execute("ALTER TABLE vision_segments RENAME TO vision_segments_legacy")
        assignment_tables: List[Tuple[str, str]] = []
        for table_name in ("annual_vision_segment_items", "annual_vision_segments"):
            if not VPSSchema._table_exists(conn, table_name):
                continue
            table_cols = set(VPSSchema._table_columns(conn, table_name))
            if "year" not in table_cols:
                continue
            id_column = (
                "vision_segment_id" if "vision_segment_id" in table_cols
                else ("vision_element_id" if "vision_element_id" in table_cols else "")
            )
            if not id_column:
                continue
            legacy_name = f"{table_name}_legacy"
            if not VPSSchema._table_exists(conn, legacy_name):
                conn.execute(f"ALTER TABLE {table_name} RENAME TO {legacy_name}")
            assignment_tables.append((legacy_name, id_column))
        return assignment_tables

    @staticmethod
    def _migrate_legacy_vision_schema_data(
        conn: sqlite3.Connection,
        legacy_assignment_tables: List[Tuple[str, str]],
    ):
        """Migrate legacy Vision Segment rows into current Vision Element tables."""
        if not VPSSchema._table_exists(conn, "vision_segments_legacy"):
            return

        from datetime import datetime
        from uuid import uuid4

        # RN-M1.C — the column has to exist before this can stamp it. The VSP
        # schema's CREATE TABLE does not declare it; link_integrity adds it,
        # and that runs AFTER initialize_vps_schema. Calling the adder here is
        # not a second definition of the column — it is the same idempotent
        # one, called earlier. run_link_integrity_migrations still calls it for
        # every other table and finds this one already present.
        from .link_integrity import add_segment_description_id_columns

        add_segment_description_id_columns(conn)

        now = datetime.now().isoformat()
        legacy_rows = conn.execute(
            """
            SELECT
                l.id AS legacy_id,
                l.segment_id AS legacy_segment_id,
                -- The description this row actually points AT, not a name to
                -- look one up by. NULL exactly when the legacy segment_id is
                -- dangling or absent, which is the 'Uncategorized' case below.
                sd.id AS description_id,
                COALESCE(sd.name, '') AS segment_name,
                l.subsegment,
                l.category,
                COALESCE(l.created_at, ?) AS created_at,
                COALESCE(l.updated_at, ?) AS updated_at
            FROM vision_segments_legacy l
            LEFT JOIN segment_descriptions sd ON sd.id = l.segment_id
            ORDER BY COALESCE(l.order_index, 0), l.created_at, l.id
            """,
            (now, now),
        ).fetchall()

        # RN-M1.C / RN-INV5 — which description each collapsed segment means,
        # or nothing when the legacy rows disagree.
        #
        # segment_cache below is keyed by LOWERED name, so two legacy rows
        # pointing at two descriptions whose names differ only by case collapse
        # into ONE new vision_segments row. Stamping the first row's id onto it
        # asserts a link that is false for the other row's work — its
        # sub-segment and category would sit under a life segment they never
        # belonged to, and the backfill's ambiguity report, which used to name
        # both candidates, would come back clean. A wrong link is worse than a
        # missing one precisely because the missing one is visible.
        descriptions_by_segment_name: dict = {}
        for legacy in legacy_rows:
            key = ((legacy["segment_name"] or "").strip() or "Uncategorized").lower()
            if legacy["description_id"]:
                descriptions_by_segment_name.setdefault(key, set()).add(
                    legacy["description_id"]
                )

        def _agreed_description_id(name: str):
            """The one description every legacy row under this name meant."""
            candidates = descriptions_by_segment_name.get(name.lower(), set())
            return next(iter(candidates)) if len(candidates) == 1 else None

        segment_cache = {}
        subsegment_cache = {}
        category_cache = {}
        legacy_to_element = {}

        for row in legacy_rows:
            segment_name = (row["segment_name"] or "").strip() or "Uncategorized"
            subsegment_name = (row["subsegment"] or "").strip() or "General"
            category_name = (row["category"] or "").strip() or "General"
            created_at = (row["created_at"] or now).strip()
            updated_at = (row["updated_at"] or now).strip()

            segment_key = segment_name.lower()
            segment_id = segment_cache.get(segment_key)
            if not segment_id:
                segment_row = conn.execute(
                    "SELECT id FROM vision_segments WHERE LOWER(name) = LOWER(?)",
                    (segment_name,),
                ).fetchone()
                if segment_row:
                    segment_id = segment_row["id"]
                else:
                    segment_id = f"vsg-{uuid4().hex[:8]}"
                    # RN-M1.C — the fourth and last INSERT INTO vision_segments
                    # to stamp the id. Its three siblings resolve the id from
                    # the name because that is all they have; this one is
                    # handed the real id by the legacy row and used to throw it
                    # away, insert by name, and let the backfill re-derive it.
                    # With two descriptions differing only by case the name
                    # resolves to neither, so a link the data already knew came
                    # out NULL and was reported as needing a human.
                    #
                    # sd.id, NOT l.segment_id: the LEFT JOIN is what makes a
                    # dangling legacy id come out NULL instead of being written
                    # verbatim as a reference to a row that is not there --
                    # which raises FOREIGN KEY constraint failed here, inside
                    # schema init. The 'Uncategorized' fallback is the same
                    # case seen from the name side, so it needs no branch.
                    #
                    # Through _agreed_description_id, so a name two legacy rows
                    # disagree about is left NULL and reported rather than
                    # silently resolved in favour of whichever row sorted
                    # first.
                    conn.execute(
                        """
                        INSERT INTO vision_segments
                            (id, name, vision_text, segment_description_id,
                             created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (segment_id, segment_name, "",
                         _agreed_description_id(segment_name),
                         created_at, updated_at),
                    )
                segment_cache[segment_key] = segment_id

            subsegment_key = (segment_id, subsegment_name.lower())
            subsegment_id = subsegment_cache.get(subsegment_key)
            if not subsegment_id:
                subsegment_row = conn.execute(
                    """
                    SELECT id FROM vision_subsegments
                    WHERE segment_id = ? AND LOWER(name) = LOWER(?)
                    """,
                    (segment_id, subsegment_name),
                ).fetchone()
                if subsegment_row:
                    subsegment_id = subsegment_row["id"]
                else:
                    subsegment_id = f"vss-{uuid4().hex[:8]}"
                    conn.execute(
                        """
                        INSERT INTO vision_subsegments
                        (id, segment_id, name, color_hex, description, vision_text, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (subsegment_id, segment_id, subsegment_name, None, "", "", created_at, updated_at),
                    )
                subsegment_cache[subsegment_key] = subsegment_id

            category_key = (subsegment_id, category_name.lower())
            category_id = category_cache.get(category_key)
            if not category_id:
                category_row = conn.execute(
                    """
                    SELECT id FROM vision_categories
                    WHERE subsegment_id = ? AND LOWER(name) = LOWER(?)
                    """,
                    (subsegment_id, category_name),
                ).fetchone()
                if category_row:
                    category_id = category_row["id"]
                else:
                    category_id = f"vct-{uuid4().hex[:8]}"
                    conn.execute(
                        """
                        INSERT INTO vision_categories
                        (id, subsegment_id, name, color_hex, description, vision_text, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (category_id, subsegment_id, category_name, None, "", "", created_at, updated_at),
                    )
                category_cache[category_key] = category_id

            key_field = f"{segment_name}|{subsegment_name}|{category_name}"
            existing_element = conn.execute(
                """
                SELECT id, key_field FROM vision_elements
                WHERE category_id = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (category_id,),
            ).fetchone()
            if existing_element:
                vision_element_id = existing_element["id"]
                if (existing_element["key_field"] or "") != key_field:
                    conflict = conn.execute(
                        "SELECT id FROM vision_elements WHERE key_field = ? AND id <> ?",
                        (key_field, vision_element_id),
                    ).fetchone()
                    if not conflict:
                        conn.execute(
                            """
                            UPDATE vision_elements
                            SET segment_id = ?, subsegment_id = ?, category_id = ?, key_field = ?, updated_at = ?
                            WHERE id = ?
                            """,
                            (segment_id, subsegment_id, category_id, key_field, updated_at, vision_element_id),
                        )
            else:
                vision_element_id = f"ve-{uuid4().hex[:8]}"
                conn.execute(
                    """
                    INSERT INTO vision_elements
                    (id, segment_id, subsegment_id, category_id, key_field, vision_text, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (vision_element_id, segment_id, subsegment_id, category_id, key_field, "", created_at, updated_at),
                )

            legacy_to_element[row["legacy_id"]] = {
                "vision_element_id": vision_element_id,
                "segment_name": segment_name,
                "subsegment_name": subsegment_name,
                "category_name": category_name,
                "key_field": key_field,
            }

        for table_name, id_column in legacy_assignment_tables:
            if not VPSSchema._table_exists(conn, table_name):
                continue
            assignment_rows = conn.execute(
                f"""
                SELECT year, {id_column} AS source_id, COALESCE(created_at, ?) AS created_at
                FROM {table_name}
                """,
                (now,),
            ).fetchall()
            for row in assignment_rows:
                source_id = row["source_id"]
                mapped = legacy_to_element.get(source_id)
                if not mapped and id_column == "vision_element_id":
                    ve_row = conn.execute(
                        """
                        SELECT
                            ve.id AS vision_element_id,
                            s.name AS segment_name,
                            ss.name AS subsegment_name,
                            c.name AS category_name,
                            ve.key_field AS key_field
                        FROM vision_elements ve
                        JOIN vision_segments s ON s.id = ve.segment_id
                        JOIN vision_subsegments ss ON ss.id = ve.subsegment_id
                        JOIN vision_categories c ON c.id = ve.category_id
                        WHERE ve.id = ?
                        """,
                        (source_id,),
                    ).fetchone()
                    if ve_row:
                        mapped = dict(ve_row)
                if not mapped:
                    continue

                exists = conn.execute(
                    """
                    SELECT id FROM annual_vision_elements
                    WHERE year = ? AND vision_element_id = ?
                    """,
                    (row["year"], mapped["vision_element_id"]),
                ).fetchone()
                if exists:
                    continue

                created_at = (row["created_at"] or now).strip()
                conn.execute(
                    """
                    INSERT INTO annual_vision_elements
                    (id, year, vision_element_id, segment_name, subsegment_name, category_name, key_field, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"ave-{uuid4().hex[:8]}",
                        row["year"],
                        mapped["vision_element_id"],
                        mapped["segment_name"],
                        mapped["subsegment_name"],
                        mapped["category_name"],
                        mapped["key_field"],
                        created_at,
                        created_at,
                    ),
                )

        for table_name, _id_column in legacy_assignment_tables:
            if VPSSchema._table_exists(conn, table_name):
                conn.execute(f"DROP TABLE {table_name}")
        conn.execute("DROP TABLE vision_segments_legacy")

    @staticmethod
    def _extend_action_items(conn: sqlite3.Connection):
        """Add VSP-related columns to existing action_items table."""
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
        """Create performance indexes for VSP tables."""

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

        # Action Items VSP extensions
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
