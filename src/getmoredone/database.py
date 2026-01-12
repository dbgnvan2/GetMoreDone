"""
Database module for GetMoreDone application.
Handles SQLite schema creation and connection management.
"""

import sqlite3
from pathlib import Path
from typing import Optional


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

        # Action items table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS action_items (
                id               TEXT PRIMARY KEY,
                who              TEXT NOT NULL,
                title            TEXT NOT NULL,
                description      TEXT,

                start_date        TEXT,
                due_date          TEXT,

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
                created_at   TEXT NOT NULL
            )
        """)

        # Defaults table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS defaults (
                scope_type        TEXT NOT NULL,
                scope_key         TEXT,

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

        conn.commit()

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
