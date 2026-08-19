"""WT-M7.A — merge duplicate Weekly Tactics; WT-M7.B — repair the invariants.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7

The live database holds exactly one duplicate: APE ``ape-f28e63eb``, week
2026-02-23, where the *older* row is titled ``W8`` and holds all five children,
and the *newer* row is titled ``W9`` and holds one reschedule_history row.
2026-02-23 is ISO 2026-W9, so keeping the oldest and its title would preserve a
wrong number (WT-F5). Both halves of that are tested here.
"""

import logging
from datetime import datetime
from uuid import uuid4

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ItemLink, ProjectBoard, TimeBlock, WorkLog
from src.getmoredone.weekly_tactic_maintenance import (
    dedupe_weekly_tactics,
    referencing_tables,
)
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

        kids = [make_daily_item(vps, f"Child {i}", weekly_tactic_id=older.id, refile=False)
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
        make_daily_item(vps, "Child", weekly_tactic_id=older.id, refile=False)

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
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id, refile=False)

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


def test_wt_m7a3_every_referencing_table_is_derived_from_the_schema(tmp_path):
    """The repoint list comes from the schema, not from a list someone maintains.

    The hand-written list shipped two bugs at once: ``time_blocks`` was absent
    and has no ON DELETE clause, so deleting a merged tactic raised FOREIGN KEY
    constraint failed inside schema init — an unrecoverable start-up crash loop;
    and ``habit_tracking`` was absent and *is* ON DELETE CASCADE, so its rows
    vanished while the report said nothing was dropped.
    """
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        derived = {(e["table"], e["column"]): e["on_delete"]
                   for e in referencing_tables(conn)}

        # Every table that actually holds a foreign key into action_items.
        assert ("time_blocks", "item_id") in derived
        assert derived[("time_blocks", "item_id")] == "NO ACTION"
        assert ("habit_tracking", "action_item_id") in derived
        assert derived[("habit_tracking", "action_item_id")] == "CASCADE"
        for table, column in (("reschedule_history", "item_id"),
                              ("item_links", "item_id"),
                              ("work_logs", "item_id"),
                              ("project_board_items", "item_id")):
            assert (table, column) in derived

        # action_items' own self-references are handled explicitly, not here.
        assert not any(table == "action_items" for table, _ in derived)
    finally:
        vps.close()


def test_wt_m7a3_time_block_on_the_loser_does_not_crash_the_merge(tmp_path):
    """time_blocks has no ON DELETE, so an unrepointed row makes DELETE raise.

    This ran inside ``Database.initialize_schema``, so the failure was an app
    that would not start — and would not start on any subsequent launch either,
    because the transaction never committed and the duplicate was still there.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        conn = manager.db.conn
        ape_id = seed_ape(vps)
        survivor = make_week_item(vps, ape_id, title="Keeper")
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id, refile=False)
        _drop_index(vps)
        loser = _raw_week_item(vps, ape_id, "Loser", created_at="2099-01-01T00:00:00")

        manager.create_time_block(TimeBlock(
            item_id=loser, block_date="2026-02-24", start_time="09:00",
            end_time="09:30", planned_minutes=30,
        ))
        before = _count(conn, "time_blocks")
        assert before == 1

        report = dedupe_weekly_tactics(conn)   # must not raise
        conn.commit()

        assert report["merged"] == 1
        assert report["blocked"] == 0
        assert _count(conn, "time_blocks") == before, "the time block must survive"
        moved = conn.execute(
            "SELECT item_id FROM time_blocks"
        ).fetchone()["item_id"]
        assert moved == survivor.id
    finally:
        vps.close()


def test_wt_m7a3_habit_tracking_rows_are_repointed_not_destroyed(tmp_path):
    """habit_tracking is ON DELETE CASCADE — an unrepointed row is destroyed."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        survivor = make_week_item(vps, ape_id, title="Keeper")
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id, refile=False)
        _drop_index(vps)
        loser = _raw_week_item(vps, ape_id, "Loser", created_at="2099-01-01T00:00:00")

        conn.execute(
            """
            INSERT INTO habit_tracking (id, action_item_id, tracking_date,
                                        is_completed, created_at)
            VALUES ('habit-1', ?, '2026-02-24', 1, '2026-02-24T09:00:00')
            """,
            (loser,),
        )
        conn.commit()
        before = _count(conn, "habit_tracking")
        assert before == 1

        report = dedupe_weekly_tactics(conn)
        conn.commit()

        assert _count(conn, "habit_tracking") == before, (
            "the merge destroyed habit rows and reported nothing dropped"
        )
        assert conn.execute(
            "SELECT action_item_id FROM habit_tracking"
        ).fetchone()["action_item_id"] == survivor.id
        assert report["dropped"] == {}
    finally:
        vps.close()


def test_wt_m7a5_dedupe_log_reaches_a_handler(tmp_path):
    """The merge log is the only record of what was deleted — it must land.

    The handler used to be installed by VPSManager, which app.py builds *after*
    the DatabaseManager that runs the migration. So at migration time the logger
    had no handler and every INFO line was discarded.
    """
    from src.getmoredone.weekly_tactic_logging import LOGGER_NAME, get_weekly_tactic_logger

    live = get_weekly_tactic_logger()
    assert live.handlers, "the weekly tactic logger must have a handler"
    assert live.isEnabledFor(logging.INFO)

    vps = make_vps(tmp_path, "logged.db")
    db_path = vps.db_manager.db.db_path
    try:
        ape_id = seed_ape(vps)
        survivor = make_week_item(vps, ape_id, title="Keeper")
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id, refile=False)
        _drop_index(vps)
        loser = _raw_week_item(vps, ape_id, "Loser", created_at="2099-01-01T00:00:00")
    finally:
        vps.close()

    # caplog cannot be used: this logger sets propagate = False, so records
    # never reach the root handler pytest installs. Listen on the logger itself,
    # which is what the app's file handler does.
    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    probe = _Capture(level=logging.INFO)
    live.addHandler(probe)
    try:
        reopened = DatabaseManager(db_path)
        reopened.close()
    finally:
        live.removeHandler(probe)

    text = "\n".join(records)
    assert "merged" in text, f"the merge summary never reached the log: {text!r}"
    assert loser in text, "the deleted row's id must appear in the log"
    assert survivor.id in text, "the surviving row's id must appear in the log"


def _make_blocking_table(vps, loser_id, survivor_id):
    """A table whose FK has no ON DELETE and whose unique key blocks the repoint.

    No table in the shipped schema can reach the blocked branch — time_blocks is
    the only NO ACTION foreign key and it has no unique constraint on item_id,
    so UPDATE OR IGNORE never leaves a row behind. Without this the branch has
    zero coverage, which is how it came to raise from a different line instead
    of the one it replaced.
    """
    conn = vps.db_manager.db.conn
    conn.execute("""
        CREATE TABLE probe_refs (
            item_id TEXT REFERENCES action_items(id),
            tag     TEXT,
            UNIQUE(item_id, tag)
        )
    """)
    conn.execute("INSERT INTO probe_refs (item_id, tag) VALUES (?, 'x')", (survivor_id,))
    conn.execute("INSERT INTO probe_refs (item_id, tag) VALUES (?, 'x')", (loser_id,))
    conn.commit()


def test_wt_m7a_blocked_merge_does_not_stop_the_app_from_starting(tmp_path):
    """A duplicate that cannot be merged must not become a start-up crash loop.

    Skipping the merge only relocated the crash: the group survived, so the
    unique index raised three lines later, out of schema init, on every launch
    forever. The failure is now recorded and logged, and the app opens with
    WT-INV5 unenforced and that fact on the record.
    """
    vps = make_vps(tmp_path, "blocked.db")
    db_path = vps.db_manager.db.db_path
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        survivor = make_week_item(vps, ape_id, title="Keeper")
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id, refile=False)
        _drop_index(vps)
        loser = _raw_week_item(vps, ape_id, "Loser", created_at="2099-01-01T00:00:00")
        _make_blocking_table(vps, loser, survivor.id)
    finally:
        vps.close()

    reopened = DatabaseManager(db_path)   # must not raise
    try:
        report = reopened.db.weekly_tactic_migration_report
        assert report["dedupe"]["blocked"] == 1
        assert report["dedupe"]["merged"] == 0
        assert report["dedupe"]["blocked_rows"] == {"probe_refs.item_id": 1}
        assert report["unique_index_enforced"] is False
        assert report["unique_index_error"] and "duplicate group" in report["unique_index_error"]

        # Nothing was destroyed, and both tactics are still there.
        weeks = reopened.db.conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE item_type = 'week'"
        ).fetchone()["n"]
        assert weeks == 2
        assert reopened.db.conn.execute(
            "SELECT COUNT(*) AS n FROM probe_refs"
        ).fetchone()["n"] == 2
    finally:
        reopened.close()


def test_wt_m7a_blocked_group_is_still_logged(tmp_path):
    """The log is written after every raising step, or it is worth least when it matters."""
    from src.getmoredone.weekly_tactic_logging import get_weekly_tactic_logger

    vps = make_vps(tmp_path, "blocked_log.db")
    db_path = vps.db_manager.db.db_path
    try:
        ape_id = seed_ape(vps)
        survivor = make_week_item(vps, ape_id, title="Keeper")
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id, refile=False)
        _drop_index(vps)
        loser = _raw_week_item(vps, ape_id, "Loser", created_at="2099-01-01T00:00:00")
        _make_blocking_table(vps, loser, survivor.id)
    finally:
        vps.close()

    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    live = get_weekly_tactic_logger()
    probe = _Capture(level=logging.INFO)
    live.addHandler(probe)
    try:
        reopened = DatabaseManager(db_path)
        reopened.close()
    finally:
        live.removeHandler(probe)

    text = "\n".join(records)
    assert "could not be merged" in text, f"the blocked group was never logged: {text!r}"
    assert "is NOT enforced" in text, "an unenforced invariant must be said out loud"


def test_wt_m7a_partial_group_reports_the_deleted_row(tmp_path):
    """One deletable loser and one blocked loser in the same group.

    ``groups`` was not incremented on the blocked path while ``merged`` was, and
    the log gated its per-group detail on ``groups`` — so a row really was
    deleted and its id never appeared anywhere.
    """
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        survivor = make_week_item(vps, ape_id, title="Keeper")
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id, refile=False)
        _drop_index(vps)
        clean_loser = _raw_week_item(vps, ape_id, "Clean", created_at="2098-01-01T00:00:00")
        blocked_loser = _raw_week_item(vps, ape_id, "Blocked", created_at="2099-01-01T00:00:00")
        _make_blocking_table(vps, blocked_loser, survivor.id)

        report = dedupe_weekly_tactics(conn)
        conn.commit()

        assert report["groups"] == 1, "a partly-blocked group is still a group"
        assert report["merged"] == 1
        assert report["blocked"] == 1
        detail = report["details"][0]
        assert detail["deleted_ids"] == [clean_loser]
        assert detail["blocked"] == {"probe_refs.item_id": 1}
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE id = ?", (blocked_loser,)
        ).fetchone()["n"] == 1, "the blocked loser must survive"
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

        make_daily_item(vps, "A", weekly_tactic_id=fewer.id, refile=False)
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
        make_daily_item(vps, "A", weekly_tactic_id=oldest.id, refile=False)
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
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id, refile=False)
        _drop_index(vps)
        # Equal child counts, so the tie breaks on age — make the loser newer.
        loser = _raw_week_item(vps, ape_id, "Loser", created_at="2099-01-01T00:00:00")
        make_daily_item(vps, "Loser child", weekly_tactic_id=loser, refile=False)

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
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id, refile=False)
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
        make_daily_item(vps, "Child", weekly_tactic_id=survivor.id, refile=False)
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


# --------------------------------------------------------------------------
# WT-M7.B — repair the pre-existing invariant violations
# --------------------------------------------------------------------------

def _out_of_range_item(vps, tactic_id, start, due):
    """An item filed on a tactic but sitting outside its week.

    Written straight to the column: every ordinary save now re-files, so the
    violation this repairs cannot be produced through the normal path. It is
    the shape 53 rows on the live database were already in (WT-F10).
    """
    item = make_daily_item(vps, "Out of range", start=start, due=due)
    vps.db_manager.db.conn.execute(
        "UPDATE action_items SET weekly_tactic_id = ? WHERE id = ?",
        (tactic_id, item.id),
    )
    vps.db_manager.db.conn.commit()
    return item


def test_wt_m7b1_existing_violations_repaired(tmp_path):
    """After the repair, no linked item violates WT-INV1 or WT-INV2."""
    from src.getmoredone.weekly_tactic_maintenance import repair_weekly_tactic_invariants

    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")

        before_range = _out_of_range_item(vps, tactic.id, "2026-02-10", "2026-02-11")
        after_range = _out_of_range_item(vps, tactic.id, "2026-03-18", "2026-03-19")
        spanning = _out_of_range_item(vps, tactic.id, "2026-02-25", "2026-03-14")

        report = repair_weekly_tactic_invariants(conn)
        conn.commit()
        assert report["moved"] == 3

        violations = conn.execute("""
            SELECT COUNT(*) AS n
            FROM action_items child
            JOIN action_items week ON week.id = child.weekly_tactic_id
            WHERE child.start_date < week.start_date
               OR child.start_date > week.due_date
               OR child.due_date   < week.start_date
               OR child.due_date   > week.due_date
        """).fetchone()["n"]
        assert violations == 0

        # Weekday preserved where it can be, clamped where it cannot (WT-M3.B).
        moved_before = vps.db_manager.get_action_item(before_range.id)
        assert moved_before.start_date == "2026-02-24", "Tuesday stays a Tuesday"
        moved_span = vps.db_manager.get_action_item(spanning.id)
        assert moved_span.due_date == "2026-03-01", "a spanning item is clamped"
    finally:
        vps.close()


def test_wt_m7b2_repair_reports_what_it_moved(tmp_path):
    """A large silent date rewrite is exactly what P2 warns about."""
    from src.getmoredone.weekly_tactic_maintenance import repair_weekly_tactic_invariants

    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = _out_of_range_item(vps, tactic.id, "2026-02-10", "2026-02-11")

        report = repair_weekly_tactic_invariants(conn)
        conn.commit()

        assert report["checked"] == 1
        assert report["moved"] == 1
        detail = report["details"][0]
        assert detail["item_id"] == item.id
        assert detail["from_start"] == "2026-02-10"
        assert detail["to_start"] == "2026-02-24"
        assert detail["start_shift_days"] == 14, "by how much, not just how many"
        assert detail["week_start"] == "2026-02-23"
    finally:
        vps.close()


def test_wt_m7b3_repair_records_history(tmp_path):
    """Every move is reversible: reason='inv_repair'."""
    from src.getmoredone.weekly_tactic_maintenance import repair_weekly_tactic_invariants

    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = _out_of_range_item(vps, tactic.id, "2026-02-10", "2026-02-11")

        repair_weekly_tactic_invariants(conn)
        conn.commit()

        row = conn.execute(
            "SELECT * FROM reschedule_history WHERE item_id = ? AND reason = 'inv_repair'",
            (item.id,),
        ).fetchone()
        assert row is not None
        assert row["from_start"] == "2026-02-10"
        assert row["to_start"] == "2026-02-24"
        assert row["from_due"] == "2026-02-11"
    finally:
        vps.close()


def test_wt_m7b_repair_idempotent_second_run_moves_nothing(tmp_path):
    """It runs on every app start, so a repaired database must be left alone.

    Not a criterion the spec carries — it became necessary when the repair was
    made automatic rather than a dry-run tool.
    """
    from src.getmoredone.weekly_tactic_maintenance import repair_weekly_tactic_invariants

    vps = make_vps(tmp_path, "repair_twice.db")
    db_path = vps.db_manager.db.db_path
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        _out_of_range_item(vps, tactic.id, "2026-02-10", "2026-02-11")

        first = repair_weekly_tactic_invariants(conn)
        conn.commit()
        assert first["moved"] == 1
        history_after_first = _count(conn, "reschedule_history")

        second = repair_weekly_tactic_invariants(conn)
        conn.commit()
        assert second["moved"] == 0
        assert second["details"] == []
        assert _count(conn, "reschedule_history") == history_after_first, (
            "a clean run must not write history rows"
        )

        snapshot = {r["id"]: tuple(r) for r in conn.execute(
            "SELECT id, start_date, due_date FROM action_items")}
    finally:
        vps.close()

    reopened = DatabaseManager(db_path)
    try:
        assert reopened.db.weekly_tactic_migration_report["invariant_repair"]["moved"] == 0
        after = {r["id"]: tuple(r) for r in reopened.db.conn.execute(
            "SELECT id, start_date, due_date FROM action_items")}
        assert after == snapshot
    finally:
        reopened.close()


def test_wt_m7b_null_due_date_is_not_repaired_every_single_run(tmp_path):
    """A linked item with no due date must not be "repaired" for ever.

    ``bring_into_week`` leaves a NULL due NULL, so requiring one to be in range
    made such a row move on every app start: an identical UPDATE, a fresh
    history row, and a report claiming a change that never happened — the
    inverse of the honesty this routine exists for.
    """
    from src.getmoredone.weekly_tactic_maintenance import repair_weekly_tactic_invariants

    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = make_daily_item(vps, "No due", start="2026-02-25", due="2026-02-25",
                               weekly_tactic_id=tactic.id, refile=False)
        conn.execute("UPDATE action_items SET due_date = NULL WHERE id = ?", (item.id,))
        conn.commit()

        for run in range(3):
            report = repair_weekly_tactic_invariants(conn)
            conn.commit()
            assert report["moved"] == 0, f"run {run + 1} claimed a move that did not happen"

        assert _count(conn, "reschedule_history") == 0, (
            "an unchanged row must not accumulate history on every launch"
        )
        assert vps.db_manager.get_action_item(item.id).due_date is None
    finally:
        vps.close()


def test_wt_m7b_an_unparseable_week_start_is_reported(tmp_path):
    """A child left out of range must appear in the report, not vanish (P2)."""
    from src.getmoredone.weekly_tactic_maintenance import repair_weekly_tactic_invariants

    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = _out_of_range_item(vps, tactic.id, "2026-01-05", "2026-01-06")
        conn.execute("UPDATE action_items SET start_date = 'not a date' WHERE id = ?",
                     (tactic.id,))
        conn.commit()

        report = repair_weekly_tactic_invariants(conn)
        conn.commit()

        assert report["moved"] == 0
        assert report["skipped"] == 1
        assert report["skipped_details"][0]["item_id"] == item.id
        assert "not a date" in report["skipped_details"][0]["reason"]
    finally:
        vps.close()


def test_wt_m7b_the_migration_runs_once_per_launch(tmp_path):
    """VPSManager and DatabaseManager share a Database; the migration is not twice.

    Both call initialize_schema(). Running the whole migration twice doubled the
    repair's history rows and overwrote the first, real report with a no-op one.
    """
    vps = make_vps(tmp_path, "once.db")
    db_path = vps.db_manager.db.db_path
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        _out_of_range_item(vps, tactic.id, "2026-01-05", "2026-01-06")
    finally:
        vps.close()

    from src.getmoredone.vps_manager import VPSManager

    manager = DatabaseManager(db_path)
    first = dict(manager.db.weekly_tactic_migration_report["invariant_repair"])
    assert first["moved"] == 1, "the first pass must be the real one"

    second = VPSManager(db_manager=manager)   # calls initialize_schema again
    try:
        assert manager.db.weekly_tactic_migration_report["invariant_repair"]["moved"] == 1, (
            "the report was overwritten by a second, no-op pass"
        )
        assert _count(manager.db.conn, "reschedule_history") == 1, (
            "the repair ran twice and wrote two history rows for one move"
        )
    finally:
        second.close()


def test_wt_m7b_unrepairable_item_is_reported_not_counted_as_fixed(tmp_path):
    """A tactic that could not snap leaves its children genuinely unrepairable.

    Found by the learning-qa sweep (finding 8): the collision was reported once
    and then never acted on by anything.
    """
    from src.getmoredone.weekly_tactic_maintenance import repair_weekly_tactic_invariants

    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = _out_of_range_item(vps, tactic.id, "2026-02-10", "2026-02-11")

        normalization = {"collisions": [{"id": tactic.id, "from_start": "2026-02-25",
                                         "blocked_start": "2026-02-23", "error": "x"}]}
        report = repair_weekly_tactic_invariants(conn, normalization=normalization)
        conn.commit()

        assert report["moved"] == 0
        assert report["skipped"] == 1
        assert report["skipped_details"][0]["item_id"] == item.id
        assert vps.db_manager.get_action_item(item.id).start_date == "2026-02-10", (
            "an unrepairable item must be left alone, not moved against a bad week"
        )
    finally:
        vps.close()


def test_wt_m7b_an_unfixable_row_is_reported_not_silently_left(tmp_path):
    """A row no move can bring into range must appear in the report.

    Reachable when a tactic's due_date precedes its start_date: the child is out
    of range, but bring_into_week produces the dates it already has. The no-op
    guard added for the NULL-due case would have dropped it from both lists —
    reintroducing the hole the skipped list exists to close (P2).
    """
    from src.getmoredone.weekly_tactic_maintenance import repair_weekly_tactic_invariants

    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = _out_of_range_item(vps, tactic.id, "2026-02-25", "2026-02-25")
        # A tactic whose range is empty: due before start.
        conn.execute("UPDATE action_items SET due_date = '2026-02-16' WHERE id = ?",
                     (tactic.id,))
        conn.execute("UPDATE action_items SET start_date = '2026-02-10', "
                     "due_date = '2026-02-10' WHERE id = ?", (item.id,))
        conn.commit()

        report = repair_weekly_tactic_invariants(conn)
        conn.commit()

        assert report["moved"] == 0
        assert report["skipped"] == 1, (
            "an unfixable row appeared in neither the moved nor the skipped list"
        )
        assert "inverted" in report["skipped_details"][0]["reason"]
        assert _count(conn, "reschedule_history") == 0

        second = repair_weekly_tactic_invariants(conn)
        conn.commit()
        assert (second["moved"], second["skipped"]) == (0, 1), (
            "an unfixable row must report the same on every run, not move once"
        )
    finally:
        vps.close()


# ---------------------------------------------------------------- BC2 (WT-M7.A.7)


def _week_rows(conn, ape_id):
    return conn.execute(
        "SELECT id, start_date, due_date FROM action_items "
        "WHERE item_type = 'week' AND annual_plan_element_id = ? ORDER BY start_date",
        (ape_id,),
    ).fetchall()


def _seed_unsnappable_pair(vps, ape_id):
    """The state the app cannot currently repair.

    One tactic sits on the week start; a second sits mid-week in the SAME week.
    The unique index is on the raw (APE, start_date), so both rows are legal to
    it — the dates differ. ``normalize_week_item_starts`` then cannot snap the
    second onto the first's date, records a collision, and leaves it mid-week.
    """
    from src.getmoredone.weekly_tactic_maintenance import normalize_week_item_starts

    on_boundary = make_week_item(vps, ape_id, title="PW|LS|Blog - W9")
    mid_week = _raw_week_item(vps, ape_id, "PW|LS|Blog - stray",
                              start="2026-02-25", due="2026-02-25")
    conn = vps.db_manager.db.conn
    normalization = normalize_week_item_starts(conn)
    conn.commit()
    return on_boundary, mid_week, normalization


def test_bc2_a_tactic_that_could_not_snap_is_still_deduped(tmp_path):
    """The permanent WT-INV5 violation: same APE, same week, two tactics.

    The dedupe grouped by the raw ``start_date``, so a tactic left mid-week by a
    failed snap formed a group of one and was never merged — the violation
    survived every restart, its only trace a warning in the log.
    """
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        on_boundary, mid_week, normalization = _seed_unsnappable_pair(vps, ape_id)

        assert normalization["collided"] == 1, (
            "the fixture no longer reproduces the collision it exists to seed")
        assert len(_week_rows(conn, ape_id)) == 2

        report = dedupe_weekly_tactics(conn)
        conn.commit()

        rows = _week_rows(conn, ape_id)
        assert len(rows) == 1, (
            f"the mid-week duplicate survived the dedupe: "
            f"{[dict(r) for r in rows]}")
        assert rows[0]["start_date"] == "2026-02-23", (
            "the survivor was left off its week start")
        assert rows[0]["due_date"] == "2026-03-01"
        assert report["groups"] == 1
        assert report["merged"] == 1
        assert report["snapped"] == 1, (
            "the survivor was moved but the report does not say so — that "
            "counter is the only signal this destructive-adjacent write happened")
        assert report["snapped_ids"] == [rows[0]["id"]]
        assert report["deleted_ids"], "the merge deleted a row and did not name it"
    finally:
        vps.close()


def test_bc2_1_children_of_the_unsnappable_tactic_are_repointed(tmp_path):
    """Merging must carry the stray tactic's children onto the survivor."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        on_boundary, mid_week, _ = _seed_unsnappable_pair(vps, ape_id)

        kid = make_daily_item(vps, "Stray child", weekly_tactic_id=mid_week,
                              refile=False)
        keeper = make_daily_item(vps, "Boundary child",
                                 weekly_tactic_id=on_boundary.id, refile=False)

        dedupe_weekly_tactics(conn)
        conn.commit()

        survivor = _week_rows(conn, ape_id)[0]["id"]
        assert vps.db_manager.get_action_item(kid.id).weekly_tactic_id == survivor
        assert vps.db_manager.get_action_item(keeper.id).weekly_tactic_id == survivor
    finally:
        vps.close()


def test_bc2_2_dedupe_stays_idempotent_and_leaves_clean_weeks_alone(tmp_path):
    """Dirty-state (P8): a second run finds nothing, and distinct weeks survive."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        _seed_unsnappable_pair(vps, ape_id)
        # A tactic in a genuinely different week must not be swept up.
        other_week = _raw_week_item(vps, ape_id, "PW|LS|Blog - W10",
                                    start="2026-03-02", due="2026-03-08")

        first = dedupe_weekly_tactics(conn)
        conn.commit()
        second = dedupe_weekly_tactics(conn)
        conn.commit()

        assert first["groups"] == 1
        assert second["groups"] == 0, "the second run found something to do"
        assert second["merged"] == 0

        rows = _week_rows(conn, ape_id)
        assert [r["start_date"] for r in rows] == ["2026-02-23", "2026-03-02"]
        assert other_week in {r["id"] for r in rows}
    finally:
        vps.close()


def test_bc2_3_an_unparseable_start_date_is_still_deduped(tmp_path):
    """A date no calendar can read is still a duplicate of the same bad date.

    The first version of the week-grouping skipped these rows. The unique index
    is on the raw column, so it rejects them regardless — meaning the guard that
    uses this function and the index it protects disagreed, and index creation
    could raise straight out of schema initialisation, which the app cannot
    recover from because nothing commits before that point.
    """
    from src.getmoredone.weekly_tactic_maintenance import find_duplicate_weekly_tactics

    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        _drop_index(vps)
        first = _raw_week_item(vps, ape_id, "Bad one", start="not-a-date",
                               due="not-a-date")
        second = _raw_week_item(vps, ape_id, "Bad two", start="not-a-date",
                                due="not-a-date")

        groups = find_duplicate_weekly_tactics(conn)

        assert len(groups) == 1, f"the unreadable pair was dropped: {groups}"
        assert sorted(groups[0]["member_ids"]) == sorted([first, second])
    finally:
        vps.close()


def test_bc2_4_an_unparseable_pair_does_not_break_schema_init(tmp_path):
    """The whole migration must survive it — this runs at every app start."""
    from src.getmoredone.weekly_tactic_migrations import run_weekly_tactic_migrations

    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        _drop_index(vps)
        _raw_week_item(vps, ape_id, "Bad one", start="not-a-date", due="not-a-date")
        _raw_week_item(vps, ape_id, "Bad two", start="not-a-date", due="not-a-date")

        report = run_weekly_tactic_migrations(conn)

        # `unique_index_enforced or unique_index_error` can never be false — the
        # first is initialised True and only cleared in the branch that sets the
        # second — so it proved nothing beyond "did not raise". Assert the
        # outcome instead: the pair is reported as unmergeable rather than
        # merged, and the index is declined with a reason rather than crashing.
        assert report["dedupe"]["unmergeable"] == 1, report["dedupe"]
        assert report["dedupe"]["merged"] == 0, (
            "two rows sharing an unreadable date were merged — '' and "
            "'not-a-date' mean 'no week', not 'the same week'")
        assert report["unique_index_enforced"] is False
        assert report["unique_index_error"], (
            "the index was declined without saying why")

        rows = conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE item_type = 'week'"
        ).fetchone()["n"]
        assert rows == 2, "a row was deleted on the strength of an unreadable date"
    finally:
        vps.close()


def test_bc2_5_the_repair_does_not_treat_a_snapped_survivor_as_blocked(tmp_path):
    """The collision list handed to the repair must reflect what the dedupe did.

    The repair is given the *pre-dedupe* normalisation report. Once the dedupe
    snaps a collided survivor onto its week start, that tactic is fine — but the
    repair went on skipping its children and writing a warning saying it could
    not be snapped, into the one audit log the user has (P6).
    """
    from src.getmoredone.weekly_tactic_migrations import run_weekly_tactic_migrations

    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        on_boundary, mid_week, _ = _seed_unsnappable_pair(vps, ape_id)
        # The stray holds the children, so it wins the survivor tie-break and is
        # the row that gets snapped. The children sit OUTSIDE the week on
        # purpose: the repair returns early on an in-range child before it ever
        # consults the blocked list, so in-range children cannot tell whether
        # the fix works.
        for index in range(3):
            make_daily_item(vps, f"Stray child {index}", start="2026-03-05",
                            due="2026-03-05", weekly_tactic_id=mid_week,
                            refile=False)

        report = run_weekly_tactic_migrations(conn)

        assert report["dedupe"]["snapped"] >= 1
        assert report["collisions_resolved_by_dedupe"] >= 1, (
            "the repair was handed a collision the dedupe had already resolved")
        assert report["invariant_repair"]["moved"] == 3, (
            f"the children of a tactic the dedupe just fixed were left out of "
            f"range: {report['invariant_repair']}")
        skipped_reasons = [
            entry.get("reason", "")
            for entry in report["invariant_repair"].get("skipped_details", [])
        ]
        assert not any("could not be snapped" in reason for reason in skipped_reasons), (
            f"the repair still calls a fixed tactic unrepairable: {skipped_reasons}")
    finally:
        vps.close()
