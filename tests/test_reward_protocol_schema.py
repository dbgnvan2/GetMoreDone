"""Schema, migration, and persistence for the reward protocol.

Purpose: RP-2 — prove the three tables gain their columns on a fresh database
         *and* on one created before the protocol existed, that re-running the
         migration is harmless, and that every field survives a round trip.
Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#2-data-model-changes
Tests:   this file

Every DatabaseManager here is handed an explicit tmp_path database. The default
path resolves to the user's real application database and __init__ runs
migrations against it.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.getmoredone.database import Database
from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem, ProjectBoard, WorkLog

# The work_logs columns the protocol adds, with the definition the spec gives.
WORK_LOG_REWARD_COLUMNS = {
    "deliverable_snapshot": ("TEXT", None),
    "deliverable_completed": ("INTEGER", "0"),
    "savor_delivered": ("INTEGER", "0"),
    "celebration_type": ("TEXT", None),
    "phase": ("TEXT", None),
}

# The schema of these three tables as it stood immediately before this feature,
# copied from database.py at commit de5c809. A legacy database is built from
# these rather than by dropping columns from a current one, so the migration is
# exercised against the shape it will really meet in the wild.
LEGACY_ACTION_ITEMS = """
    CREATE TABLE action_items (
        id TEXT PRIMARY KEY, who TEXT, contact_id INTEGER, parent_id TEXT,
        title TEXT NOT NULL, description TEXT, next_action TEXT,
        start_date TEXT, due_date TEXT, original_due_date TEXT,
        is_meeting INTEGER DEFAULT 0, meeting_start_time TEXT,
        importance INTEGER, urgency INTEGER, size INTEGER, value INTEGER,
        priority_score INTEGER NOT NULL DEFAULT 0,
        "group" TEXT, category TEXT, planned_minutes INTEGER,
        status TEXT NOT NULL DEFAULT 'open', completed_at TEXT,
        item_type TEXT NOT NULL DEFAULT 'daily', annual_plan_element_id TEXT,
        today_pin_rank INTEGER,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )
"""

LEGACY_WORK_LOGS = """
    CREATE TABLE work_logs (
        id TEXT PRIMARY KEY, item_id TEXT NOT NULL,
        started_at TEXT NOT NULL, ended_at TEXT, minutes INTEGER NOT NULL,
        note TEXT, created_at TEXT NOT NULL
    )
"""

LEGACY_PROJECT_BOARDS = """
    CREATE TABLE project_boards (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, annual_plan_element_id TEXT,
        importance INTEGER, next_step TEXT, notes TEXT, display_order INTEGER,
        status TEXT NOT NULL DEFAULT 'active', completed_at TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )
"""


def _columns(conn, table) -> dict:
    """{name: (declared_type, default)} for one table."""
    return {
        row[1]: (row[2].upper(), row[4])
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _legacy_db(tmp_path):
    """A database file carrying the pre-protocol schema and one row per table."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute(LEGACY_ACTION_ITEMS)
    conn.execute(LEGACY_WORK_LOGS)
    conn.execute(LEGACY_PROJECT_BOARDS)
    conn.execute(
        "INSERT INTO action_items (id, who, title, priority_score, status, item_type,"
        " created_at, updated_at) VALUES ('old-item', 'me', 'Old task', 0, 'open',"
        " 'daily', '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO work_logs (id, item_id, started_at, minutes, created_at)"
        " VALUES ('old-log', 'old-item', '2026-01-01T09:00:00', 25, '2026-01-01T09:25:00')"
    )
    conn.execute(
        "INSERT INTO project_boards (id, title, status, created_at, updated_at)"
        " VALUES ('old-board', 'Old board', 'active', '2026-01-01T00:00:00',"
        " '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def manager(tmp_path):
    db = DatabaseManager(str(tmp_path / "fresh.db"))
    yield db
    db.close()


# --- RP-2.x : the CREATE TABLE half, on its own -----------------------------

def test_rp2_create_table_alone_declares_every_new_column(tmp_path, monkeypatch):
    """The spec requires each column in *both* the CREATE TABLE and the migration.

    Every other test here would pass with the CREATE TABLE half missing, because
    initialize_schema runs the migrations straight afterwards and they add the
    column to a brand-new database just as readily as to an old one. Checked by
    mutation: deleting `deliverable TEXT` from the CREATE TABLE left the
    fresh-database tests green.

    So the migrations are switched off and the CREATE TABLE statements are made
    to stand on their own. Behavioural, not a grep of the source: sqlite_master
    cannot be used for this either, since ALTER TABLE ADD COLUMN rewrites the
    stored CREATE TABLE text to include the new column.
    """
    monkeypatch.setattr(Database, "_run_migrations", lambda self, conn: None)

    db = Database(str(tmp_path / "no_migrations.db"))
    db.initialize_schema()
    try:
        assert "deliverable" in _columns(db.conn, "action_items"), (
            "action_items.deliverable comes only from the migration; a fresh "
            "database should get it from the CREATE TABLE"
        )
        missing = set(WORK_LOG_REWARD_COLUMNS) - set(_columns(db.conn, "work_logs"))
        assert not missing, f"work_logs CREATE TABLE does not declare {sorted(missing)}"
        assert "savor_count" in _columns(db.conn, "project_boards"), (
            "project_boards.savor_count comes only from the migration"
        )
    finally:
        db.close()


# --- RP-2.1 / RP-2.1a : action_items.deliverable ----------------------------

def test_rp21_fresh_db_has_deliverable_column(manager):
    """RP-2.1 — a database created today has the column from its CREATE TABLE."""
    columns = _columns(manager.db.conn, "action_items")
    assert "deliverable" in columns, (
        "action_items.deliverable is missing from the CREATE TABLE definition; a "
        "brand-new database would only get it if the migration happened to run"
    )
    assert columns["deliverable"][0] == "TEXT"


def test_rp21a_migration_adds_deliverable_to_legacy_db_and_is_idempotent(tmp_path):
    """RP-2.1a — the column arrives on an upgrading DB, and re-running is harmless."""
    path = _legacy_db(tmp_path)

    db = Database(str(path))
    db.initialize_schema()
    assert "deliverable" in _columns(db.conn, "action_items")
    # An existing row gets NULL, not a fabricated deliverable.
    assert db.conn.execute(
        "SELECT deliverable FROM action_items WHERE id = 'old-item'"
    ).fetchone()[0] is None

    db.initialize_schema()  # second run: must not raise "duplicate column name"
    assert "deliverable" in _columns(db.conn, "action_items")
    assert db.conn.execute("SELECT COUNT(*) FROM action_items").fetchone()[0] == 1
    db.close()


# --- RP-2.2 / RP-2.2a : work_logs audit columns -----------------------------

def test_rp22_fresh_db_has_all_five_work_log_reward_columns(manager):
    """RP-2.2 — all five, with the spec's types and defaults, on a fresh DB.

    Asserted as an exact set rather than "at least the ones I remembered": a
    column silently dropped from the CREATE TABLE has to fail here.
    """
    columns = _columns(manager.db.conn, "work_logs")
    missing = set(WORK_LOG_REWARD_COLUMNS) - set(columns)
    assert not missing, f"work_logs is missing {sorted(missing)}"

    for name, (declared_type, default) in WORK_LOG_REWARD_COLUMNS.items():
        assert columns[name][0] == declared_type, (
            f"work_logs.{name} is {columns[name][0]}, spec says {declared_type}"
        )
        assert columns[name][1] == default, (
            f"work_logs.{name} defaults to {columns[name][1]!r}, spec says {default!r}"
        )


def test_rp22a_migration_backfills_work_log_defaults_on_existing_rows(tmp_path):
    """RP-2.2a — an existing row reads 0, not NULL, for the two counted flags.

    NOT NULL DEFAULT 0 on an ALTER TABLE is what makes this true; without the
    default SQLite refuses the statement outright, and with a nullable column
    the pre-protocol rows would read None and every consumer would have to
    special-case them.
    """
    path = _legacy_db(tmp_path)
    db = Database(str(path))
    db.initialize_schema()

    columns = _columns(db.conn, "work_logs")
    missing = set(WORK_LOG_REWARD_COLUMNS) - set(columns)
    assert not missing, f"migration did not add {sorted(missing)}"

    row = db.conn.execute(
        "SELECT deliverable_snapshot, deliverable_completed, savor_delivered,"
        " celebration_type, phase FROM work_logs WHERE id = 'old-log'"
    ).fetchone()
    assert row[0] is None
    assert row[1] == 0, "a pre-protocol session must not read as a completed deliverable"
    assert row[2] == 0, "a pre-protocol session must not read as having been savored"
    assert row[3] is None
    assert row[4] is None

    db.initialize_schema()
    assert db.conn.execute("SELECT COUNT(*) FROM work_logs").fetchone()[0] == 1
    db.close()


def test_rp22a_a_half_migrated_db_gets_the_rest_of_the_columns(tmp_path):
    """Each ALTER is guarded on its own, so an interrupted upgrade can finish.

    A single "have any of these?" guard would look correct and would skip the
    four remaining columns forever on a database where one had already landed.
    """
    path = _legacy_db(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute("ALTER TABLE work_logs ADD COLUMN deliverable_snapshot TEXT")
    conn.commit()
    conn.close()

    db = Database(str(path))
    db.initialize_schema()
    missing = set(WORK_LOG_REWARD_COLUMNS) - set(_columns(db.conn, "work_logs"))
    assert not missing, (
        f"a half-migrated database was left without {sorted(missing)} — the "
        "column guards are not independent"
    )
    db.close()


# --- RP-2.3 : project_boards.savor_count ------------------------------------

def test_rp23_savor_count_column_and_migration(tmp_path, manager):
    """RP-2.3 — present on a fresh DB, added to a legacy one, idempotent."""
    fresh = _columns(manager.db.conn, "project_boards")
    assert "savor_count" in fresh, "project_boards.savor_count missing on a fresh database"
    assert fresh["savor_count"] == ("INTEGER", "0")

    path = _legacy_db(tmp_path)
    db = Database(str(path))
    db.initialize_schema()
    assert "savor_count" in _columns(db.conn, "project_boards")
    assert db.conn.execute(
        "SELECT savor_count FROM project_boards WHERE id = 'old-board'"
    ).fetchone()[0] == 0, "an existing project must start Phase 1 at zero, not part-way in"
    db.initialize_schema()
    assert db.conn.execute("SELECT COUNT(*) FROM project_boards").fetchone()[0] == 1
    db.close()


def test_rp23a_savor_count_round_trips_through_get_project_board(manager):
    """RP-2.3a — the counter survives the mapper, and the increment is real."""
    board = ProjectBoard(title="Round trip")
    manager.create_project_board(board)
    assert manager.get_project_board(board.id).savor_count == 0

    assert manager.increment_project_savor_count(board.id) == 1
    assert manager.increment_project_savor_count(board.id) == 2
    assert manager.get_project_board(board.id).savor_count == 2, (
        "the increment did not survive a reload — the mapper is dropping savor_count"
    )


def test_rp23a_increment_reports_an_unknown_board_instead_of_pretending(manager):
    """A stale board id returns None rather than silently reporting success."""
    assert manager.increment_project_savor_count("no-such-board") is None


def test_rp23b_update_project_board_cannot_clobber_savor_count(manager):
    """RP-2.3b — saving a board loaded before an increment must not roll it back.

    Not in the spec. It is here because update_project_board rewrites every
    column it knows about, and a board object held by an open editor is exactly
    the stale reader that would undo a completion.
    """
    board = ProjectBoard(title="Editing while working")
    manager.create_project_board(board)

    stale = manager.get_project_board(board.id)   # savor_count == 0, as an open editor would hold
    manager.increment_project_savor_count(board.id)
    manager.increment_project_savor_count(board.id)

    stale.title = "Renamed in the editor"
    manager.update_project_board(stale)

    reloaded = manager.get_project_board(board.id)
    assert reloaded.title == "Renamed in the editor", "the edit itself should still save"
    assert reloaded.savor_count == 2, (
        f"saving a stale board rolled savor_count back to {reloaded.savor_count}; "
        "update_project_board must not write that column"
    )


# --- RP-2.4 / RP-2.5 : persistence round trips ------------------------------

def test_rp24_work_log_reward_fields_round_trip(manager):
    """RP-2.4 — every one of the five fields comes back as it went in."""
    item = ActionItem(who="me", title="Task")
    manager.create_action_item(item)

    manager.create_work_log(WorkLog(
        item_id=item.id,
        started_at="2026-08-24T09:00:00",
        ended_at="2026-08-24T09:25:00",
        minutes=25,
        note="a note",
        deliverable_snapshot="Draft section 2's opening paragraph",
        deliverable_completed=True,
        savor_delivered=True,
        celebration_type="confetti",
        phase="wiring",
    ))

    log = manager.get_work_logs(item.id)[0]
    assert log.deliverable_snapshot == "Draft section 2's opening paragraph"
    assert log.deliverable_completed is True
    assert log.savor_delivered is True
    assert log.celebration_type == "confetti"
    assert log.phase == "wiring"


def test_rp24_a_plain_session_records_no_reward(manager):
    """A work log written by the ordinary Stop -> Finished path claims nothing."""
    item = ActionItem(who="me", title="Task")
    manager.create_action_item(item)
    manager.create_work_log(WorkLog(item_id=item.id, started_at="2026-08-24T09:00:00", minutes=25))

    log = manager.get_work_logs(item.id)[0]
    assert log.deliverable_completed is False
    assert log.savor_delivered is False
    assert log.celebration_type is None
    assert log.phase is None
    assert log.deliverable_snapshot is None


def test_rp25_deliverable_round_trips_on_create_and_update(manager):
    """RP-2.5 — both write paths carry it; a create-only fix would look identical here."""
    written = "Draft section 2's opening paragraph"
    item = ActionItem(who="me", title="Task", deliverable=written)
    manager.create_action_item(item)
    assert manager.get_action_item(item.id).deliverable == written

    reloaded = manager.get_action_item(item.id)
    reloaded.deliverable = "Send the draft to Sam"
    manager.update_action_item(reloaded)
    assert manager.get_action_item(item.id).deliverable == "Send the draft to Sam"

    reloaded.deliverable = None
    manager.update_action_item(reloaded)
    assert manager.get_action_item(item.id).deliverable is None, (
        "clearing the deliverable must actually clear it"
    )


# --- RP-6.3 : the multi-board rule ------------------------------------------

def test_rp63_first_linked_board_by_created_at_wins(manager):
    """RP-6.3 — spec §7.1 MVP: an item on several boards uses the oldest link."""
    item = ActionItem(who="me", title="On two boards")
    manager.create_action_item(item)

    second = ProjectBoard(title="Linked later")
    first = ProjectBoard(title="Linked first")
    manager.create_project_board(second)
    manager.create_project_board(first)

    # Written directly so the two links have distinguishable timestamps; the
    # helper stamps datetime.now() and both would land in the same millisecond.
    manager.db.conn.execute(
        "INSERT INTO project_board_items (project_board_id, item_id, created_at)"
        " VALUES (?, ?, '2026-08-01T10:00:00')", (first.id, item.id))
    manager.db.conn.execute(
        "INSERT INTO project_board_items (project_board_id, item_id, created_at)"
        " VALUES (?, ?, '2026-08-20T10:00:00')", (second.id, item.id))
    manager.db.conn.commit()

    boards = manager.get_project_boards_for_item(item.id)
    assert [b.title for b in boards] == ["Linked first", "Linked later"], (
        "get_project_boards_for_item must order by link created_at, oldest first"
    )


def test_rp63_an_unlinked_item_has_no_boards(manager):
    """The unlinked case is the one that must skip the reward protocol entirely."""
    item = ActionItem(who="me", title="Unlinked")
    manager.create_action_item(item)
    assert manager.get_project_boards_for_item(item.id) == []
