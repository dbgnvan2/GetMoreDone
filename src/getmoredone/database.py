"""
Database module for GetMoreDone application.
Handles SQLite schema creation and connection management.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from .vps_schema import VPSSchema


class Database:
    """Manages SQLite database connection and schema."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses default data/getmoredone.db
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "getmoredone.db"
        else:
            db_path = Path(db_path)

        # Ensure data directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = str(db_path)
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Open database connection and enable foreign keys."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
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

        # Initialize VPS (Visionary Planning System) schema
        VPSSchema.initialize_vps_schema(conn)

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
            # Make who nullable for existing items
            # (SQLite doesn't support ALTER COLUMN, handled by new schema)

        if 'parent_id' not in columns:
            # Add parent_id column to action_items for hierarchical relationships
            conn.execute("""
                ALTER TABLE action_items
                ADD COLUMN parent_id TEXT REFERENCES action_items(id) ON DELETE SET NULL
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
