"""Tests for the Project Notes feature.

Spec: docs/implementation_plan_2026-06-06_project_notes.md

GUI tests skip cleanly when customtkinter / a display is unavailable.
Run under the project venv:
    ./venv/bin/python -m pytest tests/test_project_notes.py -v
"""
from __future__ import annotations

import sqlite3
import pytest

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ProjectBoard, ProjectBoardLink


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_manager(tmp_path):
    db_path = str(tmp_path / "project_notes.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


@pytest.fixture
def board_id(db_manager):
    board = ProjectBoard(title="Notes Board")
    return db_manager.create_project_board(board)


# ============================================================================
# M1 — Data model
# ============================================================================

class TestM1DataModel:
    """M1: ProjectBoardLink has a `status` field, table has the column, and
    the migration adds it to existing DBs without data loss."""

    def test_project_board_link_has_status_field(self):
        """M1.A.1: ProjectBoardLink dataclass has a `status` field, default 'open'."""
        link = ProjectBoardLink(project_board_id="b1", url="http://x")
        assert hasattr(link, "status")
        assert link.status == "open"

    def test_project_board_links_table_has_status_column(self, db_manager):
        """M1.A.2: project_board_links table has a `status` column with default 'open'."""
        cursor = db_manager.db.conn.execute("PRAGMA table_info(project_board_links)")
        cols = {row[1]: row for row in cursor.fetchall()}
        assert "status" in cols, "status column missing"
        # row schema: cid, name, type, notnull, dflt_value, pk
        assert cols["status"][2].upper() == "TEXT"
        assert cols["status"][3] == 1  # NOT NULL
        # default may be wrapped in quotes by SQLite
        dflt = cols["status"][4]
        assert dflt is not None and "open" in str(dflt)

    def test_migration_adds_status_to_existing_db(self, tmp_path):
        """M1.A.3: Existing DB without status column gets the column added on init,
        and pre-existing rows default to 'open'."""
        db_path = str(tmp_path / "legacy.db")

        # Manually create a LEGACY project_board_links table (no status column)
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE project_boards (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    annual_plan_element_id TEXT, importance INTEGER,
                    next_step TEXT, notes TEXT, display_order INTEGER,
                    status TEXT NOT NULL DEFAULT 'active', completed_at TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE project_board_links (
                    id TEXT PRIMARY KEY,
                    project_board_id TEXT NOT NULL,
                    label TEXT,
                    url TEXT NOT NULL,
                    link_type TEXT DEFAULT 'url',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "INSERT INTO project_boards (id, title, status, created_at, updated_at) "
                "VALUES ('b1', 'B', 'active', '2020-01-01', '2020-01-01')"
            )
            conn.execute(
                "INSERT INTO project_board_links (id, project_board_id, url, created_at) "
                "VALUES ('legacy-link', 'b1', 'note://legacy', '2020-01-01')"
            )
            conn.commit()

        # Now open the DB through the manager — migration must add the column
        manager = DatabaseManager(db_path)
        try:
            cursor = manager.db.conn.execute("PRAGMA table_info(project_board_links)")
            cols = [row[1] for row in cursor.fetchall()]
            assert "status" in cols

            row = manager.db.conn.execute(
                "SELECT status FROM project_board_links WHERE id = ?", ("legacy-link",)
            ).fetchone()
            assert row["status"] == "open"
        finally:
            manager.close()

    def test_link_status_roundtrip(self, db_manager, board_id):
        """M1.A.4: add_project_board_link / get_project_board_links round-trip status."""
        link_open = ProjectBoardLink(project_board_id=board_id, url="o://", label="open one")
        link_done = ProjectBoardLink(
            project_board_id=board_id, url="c://", label="done one", status="completed"
        )
        db_manager.add_project_board_link(link_open)
        db_manager.add_project_board_link(link_done)

        rows = db_manager.get_project_board_links(board_id)
        by_label = {r.label: r for r in rows}
        assert by_label["open one"].status == "open"
        assert by_label["done one"].status == "completed"


# ============================================================================
# M2 — DB methods: complete / reopen / filtered get
# ============================================================================

class TestM2DBMethods:
    """M2: complete_project_note, reopen_project_note, include_completed filter."""

    def test_complete_project_note(self, db_manager, board_id):
        """M2.A.1: complete_project_note sets status='completed'."""
        link = ProjectBoardLink(project_board_id=board_id, url="x://", label="todo")
        db_manager.add_project_board_link(link)

        ok = db_manager.complete_project_note(link.id)
        assert ok is True
        refreshed = db_manager.get_project_board_links(board_id)
        assert refreshed[0].status == "completed"

    def test_reopen_project_note(self, db_manager, board_id):
        """M2.A.2: reopen_project_note sets status='open'."""
        link = ProjectBoardLink(
            project_board_id=board_id, url="x://", label="t", status="completed"
        )
        db_manager.add_project_board_link(link)

        ok = db_manager.reopen_project_note(link.id)
        assert ok is True
        refreshed = db_manager.get_project_board_links(board_id)
        assert refreshed[0].status == "open"

    def test_complete_reopen_unknown_id_returns_false(self, db_manager):
        """Status mutators return False when the ID is unknown."""
        assert db_manager.complete_project_note("no-such-id") is False
        assert db_manager.reopen_project_note("no-such-id") is False

    def test_get_links_filters_by_status(self, db_manager, board_id):
        """M2.A.3: include_completed=False returns only open notes."""
        db_manager.add_project_board_link(
            ProjectBoardLink(project_board_id=board_id, url="o://", label="open A")
        )
        db_manager.add_project_board_link(
            ProjectBoardLink(
                project_board_id=board_id, url="c://", label="done B", status="completed"
            )
        )
        db_manager.add_project_board_link(
            ProjectBoardLink(project_board_id=board_id, url="o2://", label="open C")
        )

        all_links = db_manager.get_project_board_links(board_id, include_completed=True)
        open_only = db_manager.get_project_board_links(board_id, include_completed=False)

        assert len(all_links) == 3
        assert {l.label for l in open_only} == {"open A", "open C"}
        assert all(l.status == "open" for l in open_only)

    def test_get_links_ordered_newest_first(self, db_manager, board_id):
        """Sort decision: get_project_board_links returns most-recent first."""
        # Insert with explicit, non-default created_at so order is unambiguous.
        for label, ts in [("oldest", "2020-01-01T00:00:00"),
                          ("middle", "2022-06-15T12:00:00"),
                          ("newest", "2026-06-06T09:00:00")]:
            db_manager.add_project_board_link(
                ProjectBoardLink(
                    project_board_id=board_id, url=f"{label}://",
                    label=label, created_at=ts,
                )
            )
        rows = db_manager.get_project_board_links(board_id)
        assert [r.label for r in rows] == ["newest", "middle", "oldest"]
