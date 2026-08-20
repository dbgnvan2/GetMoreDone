"""
Database module for GetMoreDone application.
Handles SQLite schema creation and connection management.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from .paths import resolve_db_path
from .vps_schema import VPSSchema
from .link_integrity import run_link_integrity_migrations
from .weekly_tactic_migrations import run_weekly_tactic_migrations


class _DeferredCommitConnection:
    """A connection whose ``commit()`` is suppressed inside a transaction.

    Purpose: WT-M4.D — make the scaffolding cascade genuinely all-or-nothing.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4d
    Tests:   tests/test_weekly_tactic_cascade.py::test_wt_m4d1_cascade_runs_in_one_transaction

    Roughly thirty places call ``self.db.conn.commit()`` directly, and the
    cascade nests four creators deep. Threading a ``commit=False`` argument
    through all of them is possible but not *checkable*: one missed site
    silently defeats the rollback, and the failure only shows up as half a
    lineage committed on an error path nobody exercises.

    A gate on the connection cannot be missed. Every commit on this connection
    goes through here, whoever makes it and however deep — including ``with
    conn:``, whose ``__exit__`` is overridden below rather than delegated,
    because sqlite3's own would commit the raw connection.

    One consequence worth knowing: ``isinstance(db.conn, sqlite3.Connection)``
    is False. Nothing in this codebase tests for it, and everything else passes
    through by ``__getattr__``.
    """

    __slots__ = ("_conn", "_defer_depth")

    def __init__(self, conn: sqlite3.Connection):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_defer_depth", 0)

    # -- the gate ---------------------------------------------------------

    def defer_commits(self) -> None:
        object.__setattr__(self, "_defer_depth", self._defer_depth + 1)

    def resume_commits(self) -> None:
        object.__setattr__(self, "_defer_depth", max(0, self._defer_depth - 1))

    @property
    def commits_deferred(self) -> bool:
        return self._defer_depth > 0

    def commit(self):
        if self._defer_depth > 0:
            return None
        return self._conn.commit()

    def force_commit(self):
        """Commit regardless of the gate — for the owner of the transaction."""
        return self._conn.commit()

    # -- everything else passes straight through --------------------------

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        if name in self.__slots__:
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def __enter__(self):
        # Deliberately not delegated: sqlite3's own context manager commits on
        # the raw connection, which would step straight past the gate the class
        # docstring promises. Yielding self keeps every commit inside the block
        # going through commit() above.
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
            return False
        self._conn.rollback()
        return False


class Database:
    """Manages SQLite database connection and schema."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses default data/getmoredone.db
        """
        resolved_db_path = resolve_db_path(db_path)
        self.db_uri = False

        if isinstance(resolved_db_path, Path):
            # Ensure parent directory exists for file-backed databases.
            resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(resolved_db_path)
        else:
            # Keep SQLite memory targets / URIs untouched.
            self.db_path = resolved_db_path
            self.db_uri = resolved_db_path.startswith("file:")
        self.conn: Optional[sqlite3.Connection] = None
        # Report from the last run of the Weekly Tactic migrations. Read by
        # tests and by the app so a large data change is never silent (P2).
        # Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1
        self.weekly_tactic_migration_report: Optional[dict] = None
        # RN-M1. Same once-per-Database guard: two managers share one
        # Database, and an unguarded call runs the backfill twice per
        # launch, overwriting the first (real) report with a no-op one.
        self.link_integrity_report: Optional[dict] = None

    def connect(self) -> sqlite3.Connection:
        """Open database connection and enable foreign keys."""
        if self.conn is None:
            raw = sqlite3.connect(self.db_path, uri=self.db_uri)
            raw.row_factory = sqlite3.Row
            raw.execute("PRAGMA foreign_keys = ON")
            # Wrapped so a transaction can suppress every commit on this
            # connection at once, however deep the caller (WT-M4.D).
            self.conn = _DeferredCommitConnection(raw)
        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def initialize_schema(self):
        """Create all tables and indexes if they don't exist."""
        conn = self.connect()

        # Contacts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL UNIQUE,
                contact_type    TEXT CHECK(contact_type IN ('Client', 'Contact', 'Personal')) DEFAULT 'Contact',
                email           TEXT,
                phone           TEXT,
                notes           TEXT,
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """)

        # Action items table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS action_items (
                id               TEXT PRIMARY KEY,
                who              TEXT,
                contact_id       INTEGER REFERENCES contacts(id),
                parent_id        TEXT REFERENCES action_items(id) ON DELETE SET NULL,
                title            TEXT NOT NULL,
                description      TEXT,
                next_action      TEXT,

                start_date        TEXT,
                due_date          TEXT,
                original_due_date TEXT,
                is_meeting        INTEGER DEFAULT 0,
                meeting_start_time TEXT,

                importance        INTEGER,
                urgency           INTEGER,
                size              INTEGER,
                value             INTEGER,
                priority_score    INTEGER NOT NULL DEFAULT 0,

                "group"           TEXT,
                category          TEXT,

                planned_minutes   INTEGER,
                status            TEXT NOT NULL DEFAULT 'open',
                completed_at      TEXT,
                item_type         TEXT NOT NULL DEFAULT 'daily',
                annual_plan_element_id TEXT,
                today_pin_rank    INTEGER,

                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL
            )
        """)

        # Links/attachments table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS item_links (
                id           TEXT PRIMARY KEY,
                item_id      TEXT NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,
                label        TEXT,
                url          TEXT NOT NULL,
                link_type    TEXT DEFAULT 'url',
                created_at   TEXT NOT NULL
            )
        """)

        # Contact links table (for Obsidian notes, etc.)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contact_links (
                id           TEXT PRIMARY KEY,
                contact_id   INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                label        TEXT,
                url          TEXT NOT NULL,
                link_type    TEXT DEFAULT 'url',
                created_at   TEXT NOT NULL
            )
        """)

        # Defaults table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS defaults (
                scope_type        TEXT NOT NULL,
                scope_key         TEXT,
                contact_id        INTEGER REFERENCES contacts(id),

                who               TEXT,
                importance        INTEGER,
                urgency           INTEGER,
                size              INTEGER,
                value             INTEGER,

                "group"           TEXT,
                category          TEXT,
                planned_minutes   INTEGER,

                start_offset_days INTEGER,
                due_offset_days   INTEGER,
                near_term_offset_days INTEGER,
                long_term_offset_days INTEGER,
                next_month_offset_days INTEGER,
                next_quarter_offset_days INTEGER,

                PRIMARY KEY (scope_type, scope_key)
            )
        """)

        # Reschedule history table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reschedule_history (
                id           TEXT PRIMARY KEY,
                item_id      TEXT NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,
                from_start   TEXT,
                from_due     TEXT,
                to_start     TEXT,
                to_due       TEXT,
                reason       TEXT,
                created_at   TEXT NOT NULL
            )
        """)

        # Time blocks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS time_blocks (
                id           TEXT PRIMARY KEY,
                item_id      TEXT REFERENCES action_items(id),
                block_date   TEXT NOT NULL,
                start_time   TEXT NOT NULL,
                end_time     TEXT NOT NULL,
                planned_minutes INTEGER NOT NULL,
                label        TEXT,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )
        """)

        # Work logs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS work_logs (
                id           TEXT PRIMARY KEY,
                item_id      TEXT NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,
                started_at   TEXT NOT NULL,
                ended_at     TEXT,
                minutes      INTEGER NOT NULL,
                note         TEXT,
                created_at   TEXT NOT NULL
            )
        """)

        # Create indexes
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contacts_name
            ON contacts(name)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contacts_active
            ON contacts(is_active)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_status_due
            ON action_items(status, due_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_who
            ON action_items(who)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_blocks_date
            ON time_blocks(block_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_item
            ON work_logs(item_id)
        """)

        # Run migrations for existing databases
        self._run_migrations(conn)

        # Create indexes for migrated columns (must happen after migrations)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_contact
            ON action_items(contact_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_parent
            ON action_items(parent_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contact_links_contact
            ON contact_links(contact_id)
        """)

        # Initialize VSP (Vision Strategy Plan) schema
        VPSSchema.initialize_vps_schema(conn)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_boards (
                id                     TEXT PRIMARY KEY,
                title                  TEXT NOT NULL,
                annual_plan_element_id TEXT REFERENCES annual_plan_elements(id) ON DELETE RESTRICT,
                importance             INTEGER,
                next_step              TEXT,
                notes                  TEXT,
                display_order          INTEGER,
                status                 TEXT NOT NULL DEFAULT 'active'
                                        CHECK(status IN ('active', 'pending', 'completed')),
                completed_at           TEXT,
                created_at             TEXT NOT NULL,
                updated_at             TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_board_items (
                project_board_id       TEXT NOT NULL REFERENCES project_boards(id) ON DELETE CASCADE,
                item_id                TEXT NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,
                created_at             TEXT NOT NULL,
                PRIMARY KEY (project_board_id, item_id)
            )
        """)

        # M1.A.2 — project_board_links includes a `status` column (open/completed)
        # so a linked Obsidian note carries a per-project status.
        # Spec: docs/implementation_plan_2026-06-06_project_notes.md#M1.A.2
        # Tests: tests/test_project_notes.py::test_project_board_links_table_has_status_column
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_board_links (
                id                     TEXT PRIMARY KEY,
                project_board_id       TEXT NOT NULL REFERENCES project_boards(id) ON DELETE CASCADE,
                label                  TEXT,
                url                    TEXT NOT NULL,
                link_type              TEXT DEFAULT 'url',
                status                 TEXT NOT NULL DEFAULT 'open',
                created_at             TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_boards_status
            ON project_boards(status, updated_at)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_boards_ape
            ON project_boards(annual_plan_element_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_board_items_board
            ON project_board_items(project_board_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_board_items_item
            ON project_board_items(item_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_board_links_board
            ON project_board_links(project_board_id)
        """)

        # NOTE: project_boards.annual_plan_element_id is intentionally NOT unique.
        # Multiple projects may share one APE (e.g. a catch-all "Contribution -
        # Projects - Projects" default), so only the regular lookup index above
        # (idx_project_boards_ape) is used. Older DBs that created a UNIQUE index
        # are relaxed in _run_migrations (drop idx_project_boards_unique_ape).

        # Weekly Tactic scheduling migrations. Must run last: they are scoped by
        # annual_plan_element_id (VSP schema) and touch project_boards, both of
        # which are only guaranteed to exist by this point.
        # Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#8-implementation-order
        # Once per Database, not once per manager. VPSManager and
        # DatabaseManager now share one Database and both call
        # initialize_schema(), so this ran twice per launch — doubling the
        # repair's history rows and overwriting the first (real) report with a
        # second, no-op one.
        if self.weekly_tactic_migration_report is None:
            self.weekly_tactic_migration_report = run_weekly_tactic_migrations(conn)

        # RN-M1. After the weekly-tactic migrations on purpose: the backfill
        # reads annual_plan_elements, which the VSP schema above creates.
        # Guarded the same way and for the same reason — two managers share one
        # Database, so an unguarded call runs twice per launch.
        if self.link_integrity_report is None:
            self.link_integrity_report = run_link_integrity_migrations(conn)

        conn.commit()

    def _run_migrations(self, conn: sqlite3.Connection):
        """Run migrations for existing databases."""
        # Check if contact_id column exists in action_items
        cursor = conn.execute("PRAGMA table_info(action_items)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'contact_id' not in columns:
            # Add contact_id column to action_items
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN contact_id INTEGER REFERENCES contacts(id)
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
            # Make who nullable for existing items
            # (SQLite doesn't support ALTER COLUMN, handled by new schema)

        if 'parent_id' not in columns:
            # Add parent_id column to action_items for hierarchical relationships
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN parent_id TEXT REFERENCES action_items(id) ON DELETE SET NULL
            """)

        # Keep weekly tactics grouped consistently for filtering/reporting.
        conn.execute("""
            UPDATE action_items
            SET "group" = 'Weekly Tactic'
            WHERE item_type = 'week'
              AND COALESCE("group", '') <> 'Weekly Tactic'
        """)

        # Check if contact_id column exists in defaults
        cursor = conn.execute("PRAGMA table_info(defaults)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'contact_id' not in columns:
            # Add contact_id column to defaults
            conn.execute("""
                ALTER TABLE defaults
                ADD COLUMN contact_id INTEGER REFERENCES contacts(id)
            """)

        if 'who' not in columns:
            # Add who column to defaults
            conn.execute("""
                ALTER TABLE defaults
                ADD COLUMN who TEXT
            """)

        # Add future date option columns to defaults
        if 'near_term_offset_days' not in columns:
            conn.execute("""
                ALTER TABLE defaults
                ADD COLUMN near_term_offset_days INTEGER
            """)
        if 'long_term_offset_days' not in columns:
            conn.execute("""
                ALTER TABLE defaults
                ADD COLUMN long_term_offset_days INTEGER
            """)
        if 'next_month_offset_days' not in columns:
            conn.execute("""
                ALTER TABLE defaults
                ADD COLUMN next_month_offset_days INTEGER
            """)
        if 'next_quarter_offset_days' not in columns:
            conn.execute("""
                ALTER TABLE defaults
                ADD COLUMN next_quarter_offset_days INTEGER
            """)

        # Check if link_type column exists in item_links
        cursor = conn.execute("PRAGMA table_info(item_links)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'link_type' not in columns:
            # Add link_type column to item_links
            conn.execute("""
                ALTER TABLE item_links
                ADD COLUMN link_type TEXT DEFAULT 'url'
            """)

        # Check if is_meeting and original_due_date columns exist in action_items
        cursor = conn.execute("PRAGMA table_info(action_items)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'is_meeting' not in columns:
            # Add is_meeting column to action_items
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN is_meeting INTEGER DEFAULT 0
            """)

        if 'original_due_date' not in columns:
            # Add original_due_date column to action_items
            # Populate it with current due_date for existing items
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN original_due_date TEXT
            """)
            # Set original_due_date to due_date for existing items that have a due date
            conn.execute("""
                UPDATE action_items
                SET original_due_date = due_date
                WHERE due_date IS NOT NULL AND original_due_date IS NULL
            """)

        if 'meeting_start_time' not in columns:
            # Add meeting_start_time column to action_items
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN meeting_start_time TEXT
            """)

        if 'next_action' not in columns:
            # Add next_action column to action_items
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN next_action TEXT
            """)

        if 'today_pin_rank' not in columns:
            # Add today_pin_rank column to action_items. Nullable manual pin used
            # by the Today list: higher rank sorts nearer the top; NULL = unpinned.
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN today_pin_rank INTEGER
            """)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'project_boards'"
        )
        if cursor.fetchone():
            columns = [row[1] for row in conn.execute("PRAGMA table_info(project_boards)").fetchall()]

            if 'importance' not in columns:
                conn.execute("""
                    ALTER TABLE project_boards
                    ADD COLUMN importance INTEGER
                """)

            if 'next_step' not in columns:
                conn.execute("""
                    ALTER TABLE project_boards
                    ADD COLUMN next_step TEXT
                """)

            if 'notes' not in columns:
                conn.execute("""
                    ALTER TABLE project_boards
                    ADD COLUMN notes TEXT
                """)

            if 'status' not in columns:
                conn.execute("""
                    ALTER TABLE project_boards
                    ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
                """)

            if 'display_order' not in columns:
                conn.execute("""
                    ALTER TABLE project_boards
                    ADD COLUMN display_order INTEGER
                """)

            if 'completed_at' not in columns:
                conn.execute("""
                    ALTER TABLE project_boards
                    ADD COLUMN completed_at TEXT
                """)

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'project_board_links'")
        if not cursor.fetchone():
            # First-time create on an upgrading DB — include `status` from day one.
            # Spec: docs/implementation_plan_2026-06-06_project_notes.md#M1.A.3
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_board_links (
                    id                     TEXT PRIMARY KEY,
                    project_board_id       TEXT NOT NULL REFERENCES project_boards(id) ON DELETE CASCADE,
                    label                  TEXT,
                    url                    TEXT NOT NULL,
                    link_type              TEXT DEFAULT 'url',
                    status                 TEXT NOT NULL DEFAULT 'open',
                    created_at             TEXT NOT NULL
                )
            """)
        else:
            # M1.A.3 — Existing project_board_links from an older DB might not
            # have the `status` column yet. Add it idempotently with default 'open'
            # so existing rows are non-null.
            # Spec: docs/implementation_plan_2026-06-06_project_notes.md#M1.A.3
            # Tests: tests/test_project_notes.py::test_migration_adds_status_to_existing_db
            cursor = conn.execute("PRAGMA table_info(project_board_links)")
            link_columns = [row[1] for row in cursor.fetchall()]
            if 'status' not in link_columns:
                conn.execute("""
                    ALTER TABLE project_board_links
                    ADD COLUMN status TEXT NOT NULL DEFAULT 'open'
                """)

        # Relax the old 1:1 APE<->project constraint. Earlier schema versions
        # created UNIQUE INDEX idx_project_boards_unique_ape, which blocked
        # linking more than one project to the same Annual Plan Element (and made
        # the project editor's Save silently fail with a UNIQUE constraint error).
        # Multiple projects may now share one APE; drop the unique index if present.
        # The regular idx_project_boards_ape lookup index is retained.
        conn.execute("DROP INDEX IF EXISTS idx_project_boards_unique_ape")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.close()
