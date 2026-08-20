"""WT-M1.A / WT-M1.B / WT-M1.C / WT-M1.E — schema for Weekly Tactic scheduling.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1
"""

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.getmoredone.app_settings import AppSettings
from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem, ProjectBoard
from src.getmoredone.weekly_tactic_migrations import (
    WEEKLY_TACTIC_UNIQUE_INDEX,
    WeeklyTacticMigrationError,
    create_weekly_tactic_unique_index,
)
from tests.weekly_tactic_fixtures import (
    make_daily_item,
    make_vps,
    make_week_item,
    seed_ape,
)


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


# --------------------------------------------------------------------------
# WT-M1.A — weekly_tactic_start_date
# --------------------------------------------------------------------------

def test_wt_m1a1_weekly_tactic_start_date_column_added_null(tmp_path):
    """The column exists and every existing row reads back NULL (WT-D10)."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        assert "weekly_tactic_start_date" in _columns(conn, "action_items")

        item = make_daily_item(vps, "Pre-existing")
        assert vps.db_manager.get_action_item(item.id).weekly_tactic_start_date is None

        stamped = conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE weekly_tactic_start_date IS NOT NULL"
        ).fetchone()["n"]
        assert stamped == 0, "no backfill: WT-D10 leaves existing rows alone"
    finally:
        vps.close()


def test_wt_m1a2_weekly_tactic_start_date_round_trips(tmp_path):
    """create -> read -> update -> read keeps the value."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        item = ActionItem(who="Self", title="Stamped", start_date="2026-02-25",
                          due_date="2026-02-25", weekly_tactic_start_date="2026-02-16")
        manager.create_action_item(item, apply_defaults=False)

        assert manager.get_action_item(item.id).weekly_tactic_start_date == "2026-02-16"

        stored = manager.get_action_item(item.id)
        stored.weekly_tactic_start_date = "2026-01-05"
        manager.update_action_item(stored)

        assert manager.get_action_item(item.id).weekly_tactic_start_date == "2026-01-05"
    finally:
        vps.close()


# --------------------------------------------------------------------------
# WT-M1.B — project board dates
# --------------------------------------------------------------------------

def test_wt_m1b1_project_board_dates_added_null(tmp_path):
    """WT-F4: project_boards had no date columns. Existing boards read NULL."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        assert {"start_date", "end_date"} <= _columns(conn, "project_boards")

        board = ProjectBoard(title="Plain board")
        vps.db_manager.create_project_board(board)
        stored = vps.db_manager.get_project_board(board.id)
        assert stored.start_date is None
        assert stored.end_date is None
    finally:
        vps.close()


def test_wt_m1b2_project_dates_round_trip_unvalidated(tmp_path):
    """WT-D9 — informational only: an end before a start is stored as given."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        board = ProjectBoard(title="Dated", start_date="2026-03-01", end_date="2026-01-01")
        manager.create_project_board(board)

        stored = manager.get_project_board(board.id)
        assert (stored.start_date, stored.end_date) == ("2026-03-01", "2026-01-01"), (
            "dates must not be validated or reordered (WT-D9)"
        )

        stored.start_date = "2025-12-01"
        stored.end_date = None
        manager.update_project_board(stored)

        again = manager.get_project_board(board.id)
        assert again.start_date == "2025-12-01"
        assert again.end_date is None
    finally:
        vps.close()


# --------------------------------------------------------------------------
# WT-M1.C — the WT-INV5 unique index
# --------------------------------------------------------------------------

def test_wt_m1c1_duplicate_weekly_tactic_rejected(tmp_path):
    """A second tactic for the same APE and week start cannot be written."""
    vps = make_vps(tmp_path)
    try:
        ape_id = seed_ape(vps)
        make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")

        with pytest.raises(sqlite3.IntegrityError):
            make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01",
                           title="Second")

        # A different week for the same APE is fine...
        make_week_item(vps, ape_id, start="2026-03-02", due="2026-03-08", title="Next")
        # ...and so is the same week for a different APE.
        other = seed_ape(vps, subsegment="Other", key_field="Podcast")
        make_week_item(vps, other, start="2026-02-23", due="2026-03-01", title="Other")
    finally:
        vps.close()


def test_wt_m1c2_index_creation_fails_loudly_on_dirty_db(tmp_path):
    """A database still holding duplicates raises; the index is never skipped."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        ape_id = seed_ape(vps)
        make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")

        # Drop the index and force a duplicate in behind it, as an older build
        # would have left one.
        conn.execute(f"DROP INDEX IF EXISTS {WEEKLY_TACTIC_UNIQUE_INDEX}")
        conn.execute(
            """
            INSERT INTO action_items (id, who, title, start_date, due_date, status,
                                      item_type, annual_plan_element_id, priority_score,
                                      created_at, updated_at)
            VALUES ('dupe-1', 'VSP', 'Dupe', '2026-02-23', '2026-03-01', 'open',
                    'week', ?, 0, '2026-02-01T00:00:00', '2026-02-01T00:00:00')
            """,
            (ape_id,),
        )
        conn.commit()

        with pytest.raises(WeeklyTacticMigrationError, match="duplicate group"):
            create_weekly_tactic_unique_index(conn)

        still_missing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name = ?",
            (WEEKLY_TACTIC_UNIQUE_INDEX,),
        ).fetchone()
        assert still_missing is None, "the index must not be created over duplicates"
    finally:
        vps.close()


def test_wt_m1c3_ape_weekly_screen_reports_duplicate_instead_of_crashing(tmp_path):
    """WT-M1.C.3 — the adjacent-month near-miss is reported, not an uncaught error.

    ``get_existing_week_item_starts_for_ape`` guards with a month-prefixed LIKE,
    so asking February for a week starting 2026-03-30 cannot see the March row
    that already exists. Before the index that silently made a duplicate; after
    it, an IntegrityError in a screen with no handler.
    """
    vps = make_vps(tmp_path)
    try:
        ape_id = seed_ape(vps)
        make_week_item(vps, ape_id, start="2026-03-30", due="2026-04-05")

        # Ask March for a week the March-prefixed LIKE *can* see -> skipped.
        seen = vps.create_week_action_items_for_ape(ape_id, 2026, 3, ["2026-03-30"])
        assert seen["created_count"] == 0
        assert seen["skipped_count"] == 1
        assert seen["collided_count"] == 0

        # Ask April for the same week -> the LIKE is blind to it, the index is not.
        blind = vps.create_week_action_items_for_ape(ape_id, 2026, 4, ["2026-03-30"])
        assert blind["created_count"] == 0
        assert blind["skipped_count"] == 0
        assert blind["collided_count"] == 1, "the refusal must be counted, not swallowed"
        assert blind["collisions"][0]["week_start"] == "2026-03-30"
    finally:
        vps.close()


def test_wt_m1c4_week_item_requires_ape(tmp_path):
    """SQLite treats NULLs as distinct, so a NULL-APE week item would bypass the index."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        orphan = ActionItem(who="VSP", title="No APE", item_type="week",
                            start_date="2026-02-23", due_date="2026-03-01")
        with pytest.raises(ValueError, match="Annual Plan Element"):
            manager.create_action_item(orphan, apply_defaults=False)

        # The update path is guarded too — an existing tactic cannot be orphaned.
        tactic = make_week_item(vps, seed_ape(vps))
        stored = manager.get_action_item(tactic.id)
        stored.annual_plan_element_id = None
        with pytest.raises(ValueError, match="Annual Plan Element"):
            manager.update_action_item(stored)
    finally:
        vps.close()


def test_wt_m1c5_first_day_change_collision_reported(tmp_path):
    """A re-snap that lands on an occupied week must report, not raise.

    ``_normalize_week_item_dates`` snaps a week item onto the configured
    first-day-of-week on every save, so a mid-week date — the shape a
    first_day_of_week change leaves behind — can land on a week another tactic
    already holds. That must not raise out of an ordinary save.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        # Two Monday-start weeks a week apart.
        keeper = make_week_item(vps, ape_id, start="2026-02-16", due="2026-02-22",
                                title="Earlier")
        mover = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01",
                               title="Later")

        stored = manager.get_action_item(mover.id)
        stored.start_date = "2026-02-18"   # normalises to 2026-02-16 — taken
        stored.due_date = "2026-02-24"
        stored.next_action = "edited alongside the move"

        moved = manager.update_action_item(stored)  # must not raise
        assert moved is False, (
            "a save that quietly did not move the week must say so to its "
            "caller, not only to the log"
        )

        assert manager.last_week_collision is not None
        assert manager.last_week_collision["item_id"] == mover.id
        assert manager.last_week_collision["rejected_start"] == "2026-02-16"
        assert manager.last_week_collision["kept_start"] == "2026-02-23"

        after = manager.get_action_item(mover.id)
        assert after.start_date == "2026-02-23", "the week must stay where it was"
        assert after.next_action == "edited alongside the move", (
            "the rest of the save must still land"
        )
        assert manager.get_action_item(keeper.id).start_date == "2026-02-16"

        # The flag must not stick: the DatabaseManager lives for the session, so
        # a flag that is only ever set reads as a collision on every later save.
        ordinary = manager.get_action_item(keeper.id)
        ordinary.next_action = "an ordinary save"
        assert manager.update_action_item(ordinary) is True
        assert manager.last_week_collision is None, (
            "a clean save must clear the previous collision"
        )
    finally:
        vps.close()


def test_wt_m1c5_a_genuine_failure_is_not_swallowed_as_a_collision(tmp_path):
    """The revert path only applies when the week actually moved.

    Reverting on *any* IntegrityError from a week item would turn unrelated
    failures into silent no-ops that report success.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        tactic = make_week_item(vps, seed_ape(vps))

        stored = manager.get_action_item(tactic.id)
        stored.weekly_tactic_id = "no-such-tactic"
        with pytest.raises(ValueError):
            manager.update_action_item(stored)

        # Dates unchanged, so nothing to revert to — the error must surface.
        unchanged = manager.get_action_item(tactic.id)
        assert unchanged.start_date == "2026-02-23"
        assert manager.last_week_collision is None
    finally:
        vps.close()


def test_wt_m1c5_reschedule_history_records_where_the_item_landed(tmp_path):
    """The audit row must agree with the item, on the ordinary path too.

    ``reschedule_item`` wrote its history row before the save. A week item snaps
    to its week boundary, so rescheduling one to a Wednesday recorded a start
    date the item never held — a permanently wrong audit row on every week-item
    reschedule to a mid-week date.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        tactic = make_week_item(vps, seed_ape(vps), start="2026-02-23", due="2026-03-01")

        moved = manager.reschedule_item(tactic.id, "2026-03-04", "2026-03-06",
                                        reason="test")
        assert moved is True

        stored = manager.get_action_item(tactic.id)
        assert stored.start_date == "2026-03-02", "a week item snaps to its week"

        row = manager.db.conn.execute(
            "SELECT from_start, to_start, to_due FROM reschedule_history "
            "WHERE item_id = ? ORDER BY created_at DESC LIMIT 1",
            (tactic.id,),
        ).fetchone()
        assert row["from_start"] == "2026-02-23"
        assert row["to_start"] == stored.start_date, (
            "history recorded a date the item never held"
        )
        assert row["to_due"] == stored.due_date
    finally:
        vps.close()


def test_wt_m1c5_reschedule_reports_a_refused_move(tmp_path):
    """A collision must reach the caller, not only the log."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        make_week_item(vps, ape_id, start="2026-02-16", due="2026-02-22", title="Earlier")
        mover = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01",
                               title="Later")

        moved = manager.reschedule_item(mover.id, "2026-02-18", "2026-02-20",
                                        reason="test")
        assert moved is False, "the caller must be told the week did not move"
        assert manager.last_week_collision is not None

        stored = manager.get_action_item(mover.id)
        assert stored.start_date == "2026-02-23"

        row = manager.db.conn.execute(
            "SELECT to_start FROM reschedule_history WHERE item_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (mover.id,),
        ).fetchone()
        assert row["to_start"] == "2026-02-23", (
            "history must record where the item actually is, not where it was asked to go"
        )
    finally:
        vps.close()


def test_wt_m1c5_collision_notice_reaches_the_user(tmp_path):
    """A return value nobody reads is the same silence as no return value (P25)."""
    from src.getmoredone.screens.week_collision_notice import describe_week_collision

    assert describe_week_collision(None) is None
    assert describe_week_collision({}) is None

    notice = describe_week_collision({
        "item_id": "x", "kept_start": "2026-02-23",
        "rejected_start": "2026-02-16", "error": "UNIQUE constraint failed",
    })
    assert "2026-02-23" in notice and "2026-02-16" in notice
    assert "already has a Weekly Tactic" in notice

    # And the surfaces that can move a week item actually call it.
    screens = Path(__file__).resolve().parents[1] / "src" / "getmoredone" / "screens"
    for name in ("today.py", "upcoming.py", "all_items.py"):
        text = (screens / name).read_text(encoding="utf-8")
        assert "notify_weekly_tactic_changes(self.db_manager, self)" in text, (
            f"{name} moves dates but never reports a refused week"
        )


def test_wt_m1c3_both_creation_paths_report_collisions(tmp_path):
    """WT-M1.C.3 — the drag path reports a refusal, not just the button (P5).

    ``_finish_row_drag`` used to refresh only when something was created, so a
    drag that collided produced no refresh, no status and no visible sign at
    all. Both callers now describe the outcome through one helper.
    """
    from src.getmoredone.screens.weekly_items import WeeklyItemsScreen

    describe = WeeklyItemsScreen._describe_week_creation
    quiet = describe(2, 1, 0)
    assert "Created 2" in quiet and "skipped 1" in quiet
    assert "already existed" not in quiet

    loud = describe(0, 0, 1)
    assert "already existed" in loud, (
        "a refused week must be named, not left as a silently smaller count"
    )

    # And the drag path must actually reach it — asserting the wording without
    # asserting the wiring would not have caught the original defect (P25).
    calls = []
    stub = SimpleNamespace(
        dragged_row={"id": "ape-1"},
        winfo_toplevel=lambda: SimpleNamespace(unbind=lambda _e: None),
        winfo_pointerxy=lambda: (0, 0),
        right_list=object(),
        winfo_containing=lambda *_: "target",
        _is_descendant=lambda *_: True,
        _selected_week_context=lambda: ("2026-02-23", 2026, 1, 2),
        vps_manager=SimpleNamespace(
            create_week_action_items_for_ape=lambda *_a, **_k: {
                "created_count": 0, "skipped_count": 0, "collided_count": 1,
            }
        ),
        refresh=lambda: calls.append("refresh"),
        status_label=SimpleNamespace(configure=lambda **kw: calls.append(kw["text"])),
        _describe_week_creation=describe,
    )
    WeeklyItemsScreen._finish_row_drag(stub, SimpleNamespace(x_root=0, y_root=0))

    assert "refresh" in calls, "a collided drag must still refresh"
    assert any("already existed" in c for c in calls if isinstance(c, str)), (
        f"the drag path never reported the collision: {calls}"
    )


def test_wt_m1c3_drag_without_a_week_selected_says_so(tmp_path):
    """The button path warns; the drag path used to do nothing at all."""
    from src.getmoredone.screens.weekly_items import WeeklyItemsScreen

    said = []
    stub = SimpleNamespace(
        dragged_row={"id": "ape-1"},
        winfo_toplevel=lambda: SimpleNamespace(unbind=lambda _e: None),
        winfo_pointerxy=lambda: (0, 0),
        right_list=object(),
        winfo_containing=lambda *_: "target",
        _is_descendant=lambda *_: True,
        _selected_week_context=lambda: None,
        refresh=lambda: said.append("refresh"),
        status_label=SimpleNamespace(configure=lambda **kw: said.append(kw["text"])),
    )
    WeeklyItemsScreen._finish_row_drag(stub, SimpleNamespace(x_root=0, y_root=0))
    assert any("Select a Week Start" in s for s in said if isinstance(s, str)), said


def test_wt_m1c3_drag_reports_a_stale_ape_instead_of_a_traceback(tmp_path):
    """create_week_action_items_for_ape raises on a stale APE; a Tk binding must not."""
    from src.getmoredone.screens.weekly_items import WeeklyItemsScreen

    said = []

    def _raise(*_a, **_k):
        raise ValueError("Annual Plan Element not found")

    stub = SimpleNamespace(
        dragged_row={"id": "ape-gone"},
        winfo_toplevel=lambda: SimpleNamespace(unbind=lambda _e: None),
        winfo_pointerxy=lambda: (0, 0),
        right_list=object(),
        winfo_containing=lambda *_: "target",
        _is_descendant=lambda *_: True,
        _selected_week_context=lambda: ("2026-02-23", 2026, 1, 2),
        vps_manager=SimpleNamespace(create_week_action_items_for_ape=_raise),
        refresh=lambda: said.append("refresh"),
        status_label=SimpleNamespace(configure=lambda **kw: said.append(kw["text"])),
    )
    WeeklyItemsScreen._finish_row_drag(stub, SimpleNamespace(x_root=0, y_root=0))
    assert any("Could not create" in s for s in said if isinstance(s, str)), said


# --------------------------------------------------------------------------
# WT-M1.E — created_by_rollover
# --------------------------------------------------------------------------

def test_wt_m1e1_rollover_flag_added_default_zero(tmp_path):
    """WT-D13 — an explicit flag, defaulting to 0 on every existing row."""
    vps = make_vps(tmp_path)
    try:
        conn = vps.db_manager.db.conn
        for table in ("annual_visions", "annual_plans"):
            assert "created_by_rollover" in _columns(conn, table)

        seed_ape(vps)  # builds a real annual_visions / annual_plans lineage
        for table in ("annual_visions", "annual_plans"):
            flagged = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE COALESCE(created_by_rollover, 0) <> 0"
            ).fetchone()["n"]
            assert flagged == 0, f"{table} rows created by hand must not read as stubs"
    finally:
        vps.close()


# --------------------------------------------------------------------------
# Dirty state (P8) — the interesting run is the second one
# --------------------------------------------------------------------------

def test_wt_m1_migrations_on_populated_db_run_two(tmp_path):
    """Reopening a populated database adds no columns and moves no rows."""
    vps = make_vps(tmp_path, "populated.db")
    db_path = vps.db_manager.db.db_path
    try:
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id)
        make_daily_item(vps, "Linked", weekly_tactic_id=tactic.id)
        before = {
            row["id"]: tuple(row)
            for row in vps.db_manager.db.conn.execute(
                "SELECT id, start_date, due_date, weekly_tactic_id, title FROM action_items"
            )
        }
    finally:
        vps.close()

    reopened = DatabaseManager(db_path)
    try:
        report = reopened.db.weekly_tactic_migration_report
        assert report["link_column_added"] is False
        assert report["stamp_column_added"] is False
        assert report["project_board_columns_added"] == []
        assert report["rollover_flag_tables"] == []
        assert report["unique_index_created"] is False
        assert report["dedupe"]["merged"] == 0
        assert report["week_start_normalization"]["normalized"] == 0

        after = {
            row["id"]: tuple(row)
            for row in reopened.db.conn.execute(
                "SELECT id, start_date, due_date, weekly_tactic_id, title FROM action_items"
            )
        }
        assert after == before, f"run #2 altered data: {before} -> {after}"
    finally:
        reopened.close()


def test_wt_m1_migration_report_is_available_to_callers(tmp_path):
    """The report is the only place a large automatic change is visible (P2)."""
    vps = make_vps(tmp_path)
    try:
        report = vps.db_manager.db.weekly_tactic_migration_report
        assert report is not None
        assert set(report) >= {
            "link_column_added", "stamp_column_added", "project_board_columns_added",
            "rollover_flag_tables", "link_migration", "week_start_normalization",
            "dedupe", "unique_index_created",
        }
    finally:
        vps.close()
