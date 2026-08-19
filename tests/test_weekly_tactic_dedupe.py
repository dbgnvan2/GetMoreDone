"""WT-M7.A — merge duplicate Weekly Tactics; WT-M7.B — repair the invariants.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7

The live database holds exactly one duplicate: APE ``ape-f28e63eb``, week
2026-02-23, where the *older* row is titled ``W8`` and holds all five children,
and the *newer* row is titled ``W9`` and holds one reschedule_history row.
2026-02-23 is ISO 2026-W9, so keeping the oldest and its title would preserve a
wrong number (WT-F5). Both halves of that are tested here.
"""

from datetime import datetime
from uuid import uuid4

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ItemLink, ProjectBoard, WorkLog
from src.getmoredone.weekly_tactic_maintenance import dedupe_weekly_tactics
from src.getmoredone.weekly_tactic_migrations import WEEKLY_TACTIC_UNIQUE_INDEX
from tests.weekly_tactic_fixtures import (
    make_daily_item,
    make_vps,
    make_week_item,
    seed_ape,
)


def _drop_index(vps):
    """Let a test build the dirty state the dedupe exists to clean up."""
    vps.db_manager.db.conn.execute(f"DROP INDEX IF EXISTS {WEEKLY_TACTIC_UNIQUE_INDEX}")
    vps.db_manager.db.conn.commit()


def _raw_week_item(vps, ape_id, title, start="2026-02-23", due="2026-03-01",
                   created_at="2026-02-18T20:27:05"):
    """Insert a week item directly, bypassing the guards, to seed a duplicate."""
    item_id = f"week-{uuid4().hex[:8]}"
    vps.db_manager.db.conn.execute(
        """
        INSERT INTO action_items (id, who, title, start_date, due_date, status,
                                  item_type, annual_plan_element_id, priority_score,
                                  "group", created_at, updated_at)
        VALUES (?, 'VSP', ?, ?, ?, 'open', 'week', ?, 0, 'Weekly Tactic', ?, ?)
        """,
        (item_id, title, start, due, ape_id, created_at, created_at),
    )
    vps.db_manager.db.conn.commit()
    return item_id


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]


def test_wt_m7a1_duplicates_merged_children_repointed(tmp_path):
    """One survivor; every child ends up on it."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        older = make_week_item(vps, ape_id, title="PW|LS|Blog - W8")
        _drop_index(vps)
        newer = _raw_week_item(vps, ape_id, "PW|LS|Blog - W9 (2026-02-23)")

        kids = [make_daily_item(vps, f"Child {i}", weekly_tactic_id=older.id)
                for i in range(5)]

        report = dedupe_weekly_tactics(conn)
        conn.commit()

        assert report["groups"] == 1
        assert report["merged"] == 1

        survivors = conn.execute(
            "SELECT id FROM action_items WHERE item_type = 'week'"
        ).fetchall()
        assert len(survivors) == 1
        assert survivors[0]["id"] == older.id, "most children wins the tie-break"
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE id = ?", (newer,)
        ).fetchone()["n"] == 0

        for kid in kids:
            assert vps.db_manager.get_action_item(kid.id).weekly_tactic_id == older.id
    finally:
        vps.close()


def test_wt_m7a2_survivor_title_recanonicalised(tmp_path):
    """The merge must not preserve a title numbered for the wrong week (WT-F5)."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps, key_field="Blog")
        key_field = conn.execute(
            "SELECT key_field FROM annual_plan_elements WHERE id = ?", (ape_id,)
        ).fetchone()["key_field"]

        older = make_week_item(vps, ape_id, title="Wrong - W8")
        _drop_index(vps)
        _raw_week_item(vps, ape_id, "Also wrong")
        make_daily_item(vps, "Child", weekly_tactic_id=older.id)

        report = dedupe_weekly_tactics(conn)
        conn.commit()

        assert report["retitled"] == 1
        title = vps.db_manager.get_action_item(older.id).title
        # 2026-02-23 is ISO 2026-W9, whatever the old title claimed.
        assert title.endswith(" - W9"), title
        assert title.startswith(vps.shorten_pipe_prefix(key_field).split(" - ")[0][:2])
    finally:
        vps.close()


def test_wt_m7a3_no_cascade_data_lost(tmp_path):
    """All four ON DELETE CASCADE tables are repointed before the loser goes."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        conn = manager.db.conn
        ape_id = seed_ape(vps)
        survivor = make_week_item(vps, ape_id, title="Keeper")
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id)

        _drop_index(vps)
        loser = _raw_week_item(vps, ape_id, "Loser")

        # One row in each cascade table, all hanging off the loser.
        manager.reschedule_item(loser, "2026-02-23", "2026-03-01", reason="test")
        manager.add_item_link(ItemLink(item_id=loser, url="https://example.test",
                                       label="note"))
        manager.create_work_log(WorkLog(item_id=loser, started_at=datetime.now().isoformat(),
                                        minutes=30))
        board = ProjectBoard(title="Board")
        manager.create_project_board(board)
        conn.execute(
            "INSERT INTO project_board_items (project_board_id, item_id, created_at) VALUES (?, ?, ?)",
            (board.id, loser, datetime.now().isoformat()),
        )
        conn.commit()

        before = {t: _count(conn, t) for t in
                  ("reschedule_history", "item_links", "work_logs", "project_board_items")}
        assert all(n >= 1 for n in before.values())

        dedupe_weekly_tactics(conn)
        conn.commit()

        after = {t: _count(conn, t) for t in before}
        assert after == before, f"cascade rows lost in the merge: {before} -> {after}"

        for table in before:
            orphaned = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE item_id = ?", (loser,)
            ).fetchone()["n"]
            assert orphaned == 0
            moved = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE item_id = ?", (survivor.id,)
            ).fetchone()["n"]
            assert moved >= 1, f"{table} was not repointed onto the survivor"
    finally:
        vps.close()


def test_wt_m7a4_tiebreak_when_both_have_children(tmp_path):
    """Most children wins; an equal count breaks on oldest created_at.

    The live duplicate does not exercise this — only one of its two rows has
    children — so the fixture is built rather than sampled.
    """
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        fewer = make_week_item(vps, ape_id, title="Fewer")
        _drop_index(vps)
        more = _raw_week_item(vps, ape_id, "More", created_at="2099-01-01T00:00:00")

        make_daily_item(vps, "A", weekly_tactic_id=fewer.id)
        for i in range(3):
            conn.execute(
                "UPDATE action_items SET weekly_tactic_id = ? WHERE id = ?",
                (more, make_daily_item(vps, f"B{i}").id),
            )
        conn.commit()

        dedupe_weekly_tactics(conn)
        conn.commit()

        remaining = [r["id"] for r in conn.execute(
            "SELECT id FROM action_items WHERE item_type = 'week'")]
        assert remaining == [more], (
            "the newest row wins when it holds more children — count beats age"
        )
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE weekly_tactic_id = ?", (more,)
        ).fetchone()["n"] == 4
    finally:
        vps.close()


def test_wt_m7a4_tiebreak_equal_children_prefers_oldest(tmp_path):
    """Equal child counts fall back to created_at, deterministically."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        oldest = make_week_item(vps, ape_id, title="Oldest")
        conn.execute("UPDATE action_items SET created_at = ? WHERE id = ?",
                     ("2020-01-01T00:00:00", oldest.id))
        _drop_index(vps)
        newer = _raw_week_item(vps, ape_id, "Newer", created_at="2030-01-01T00:00:00")
        make_daily_item(vps, "A", weekly_tactic_id=oldest.id)
        conn.execute("UPDATE action_items SET weekly_tactic_id = ? WHERE id = ?",
                     (newer, make_daily_item(vps, "B").id))
        conn.commit()

        dedupe_weekly_tactics(conn)
        conn.commit()

        remaining = [r["id"] for r in conn.execute(
            "SELECT id FROM action_items WHERE item_type = 'week'")]
        assert remaining == [oldest.id]
    finally:
        vps.close()


def test_wt_m7a5_dedupe_reports_counts(tmp_path):
    """Never a silent pass: the report names what was merged and repointed (P2)."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        survivor = make_week_item(vps, ape_id, title="Keeper")
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id)
        _drop_index(vps)
        # Equal child counts, so the tie breaks on age — make the loser newer.
        loser = _raw_week_item(vps, ape_id, "Loser", created_at="2099-01-01T00:00:00")
        make_daily_item(vps, "Loser child", weekly_tactic_id=loser)

        report = dedupe_weekly_tactics(conn)
        conn.commit()

        assert report["groups"] == 1
        assert report["merged"] == 1
        assert report["repointed"] >= 1
        detail = report["details"][0]
        assert detail["survivor_id"] == survivor.id
        assert detail["deleted_ids"] == [loser]
        assert detail["ape_id"] == ape_id
        assert detail["start_date"] == "2026-02-23"
        assert "title_before" in detail and "title_after" in detail
    finally:
        vps.close()


def test_wt_m7a6_dedupe_idempotent_and_dirty_state(tmp_path):
    """A second run finds nothing; reopening a merged database changes nothing (P8)."""
    vps = make_vps(tmp_path, "dirty.db")
    db_path = vps.db_manager.db.db_path
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        survivor = make_week_item(vps, ape_id, title="Keeper")
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id)
        _drop_index(vps)
        _raw_week_item(vps, ape_id, "Loser")

        first = dedupe_weekly_tactics(conn)
        conn.commit()
        assert first["merged"] == 1

        second = dedupe_weekly_tactics(conn)
        conn.commit()
        assert second["groups"] == 0
        assert second["merged"] == 0
        assert second["details"] == []

        snapshot = {r["id"]: tuple(r) for r in conn.execute(
            "SELECT id, title, start_date, weekly_tactic_id FROM action_items")}
    finally:
        vps.close()

    reopened = DatabaseManager(db_path)
    try:
        assert reopened.db.weekly_tactic_migration_report["dedupe"]["merged"] == 0
        after = {r["id"]: tuple(r) for r in reopened.db.conn.execute(
            "SELECT id, title, start_date, weekly_tactic_id FROM action_items")}
        assert after == snapshot
    finally:
        reopened.close()


def test_wt_m7a_migration_dedupes_and_then_indexes(tmp_path):
    """End to end: a dirty database opens clean, indexed, and reported.

    The wiring test — the dedupe existing is not the same as the migration
    running it (P21).
    """
    vps = make_vps(tmp_path, "endtoend.db")
    db_path = vps.db_manager.db.db_path
    try:
        ape_id = seed_ape(vps)
        survivor = make_week_item(vps, ape_id, title="Keeper")
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id)
        _drop_index(vps)
        _raw_week_item(vps, ape_id, "Loser")
    finally:
        vps.close()

    reopened = DatabaseManager(db_path)
    try:
        report = reopened.db.weekly_tactic_migration_report
        assert report["dedupe"]["merged"] == 1
        assert report["unique_index_created"] is True

        weeks = reopened.db.conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE item_type = 'week'"
        ).fetchone()["n"]
        assert weeks == 1
    finally:
        reopened.close()
