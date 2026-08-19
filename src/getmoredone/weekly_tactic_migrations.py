"""Schema migrations for Weekly Tactic scheduling.

Purpose: bring an existing database up to the Weekly Tactic scheduling schema,
         idempotently, reporting every row it touches.
Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1
Tests:   tests/test_weekly_tactic_link_migration.py
         tests/test_weekly_tactic_schema.py

Runs after both the core schema and the VSP schema exist, because the weekly
tactic index is scoped by ``annual_plan_element_id``.

Nothing here is silent: every step returns what it changed, the orchestrator
folds those into one report, and ``Database`` logs it. A migration that moves
49 rows and says nothing is indistinguishable from one that moved none (P2).
"""

import sqlite3
from typing import Any, Dict, List, Set

from .weekly_tactic_logging import get_weekly_tactic_logger

logger = get_weekly_tactic_logger()

# WT-M1.C — the partial unique index enforcing WT-INV5.
WEEKLY_TACTIC_UNIQUE_INDEX = "idx_action_items_weekly_tactic_unique"


class WeeklyTacticMigrationError(RuntimeError):
    """A Weekly Tactic migration could not complete.

    Raised rather than skipping a step, so a database that quietly keeps its
    duplicates cannot pass for a migrated one (WT-M1.C.2).
    """


def _columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    """Column names of ``table``; empty set when the table does not exist."""
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def add_weekly_tactic_link_column(conn: sqlite3.Connection) -> bool:
    """WT-M1.D — add ``action_items.weekly_tactic_id``.

    Purpose: give the tactic link its own column so it stops sharing
             ``parent_id`` with ordinary subtask nesting (WT-D11, WT-F9).
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1d
    Tests:   tests/test_weekly_tactic_link_migration.py::test_wt_m1d1_tactic_links_migrated_nesting_preserved

    Returns True when the column was added by this call.
    """
    if 'weekly_tactic_id' in _columns(conn, 'action_items'):
        return False

    conn.execute("""
        ALTER TABLE action_items
        ADD COLUMN weekly_tactic_id TEXT REFERENCES action_items(id) ON DELETE SET NULL
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_items_weekly_tactic
        ON action_items(weekly_tactic_id)
    """)
    return True


def add_weekly_tactic_start_date_column(conn: sqlite3.Connection) -> bool:
    """WT-M1.A — add ``action_items.weekly_tactic_start_date``.

    Purpose: record the week an item was *originally* meant to start, so
             push-out stays visible after the start date has moved on.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1a
    Tests:   tests/test_weekly_tactic_schema.py::test_wt_m1a1_weekly_tactic_start_date_column_added_null

    Existing rows are left NULL — WT-D10 rules out a backfill, because an item
    that was never week-filed has no original week to claim.
    """
    if 'weekly_tactic_start_date' in _columns(conn, 'action_items'):
        return False
    conn.execute("ALTER TABLE action_items ADD COLUMN weekly_tactic_start_date TEXT")
    return True


def add_project_board_date_columns(conn: sqlite3.Connection) -> List[str]:
    """WT-M1.B — add ``project_boards.start_date`` / ``end_date`` (WT-F4).

    Purpose: give a project the date range it has never had a column for.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1b
    Tests:   tests/test_weekly_tactic_schema.py::test_wt_m1b1_project_board_dates_added_null

    Unvalidated and never auto-derived — WT-D9 makes these informational.
    """
    existing = _columns(conn, 'project_boards')
    if not existing:
        return []
    added: List[str] = []
    for column in ("start_date", "end_date"):
        if column not in existing:
            conn.execute(f"ALTER TABLE project_boards ADD COLUMN {column} TEXT")
            added.append(column)
    return added


def add_rollover_flag_columns(conn: sqlite3.Connection) -> List[str]:
    """WT-M1.E — add ``created_by_rollover`` to the editorial year tables.

    Purpose: mark a row the year-rollover created, so a stub is found by an
             explicit flag rather than inferred from an empty field (WT-D13).
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1e
    Tests:   tests/test_weekly_tactic_schema.py::test_wt_m1e1_rollover_flag_added_default_zero

    Inference from emptiness would report a hand-authored vision with a blank
    statement as a stub — the adversarial case in WT-M4.C.3b.
    """
    added: List[str] = []
    for table in ("annual_visions", "annual_plans"):
        existing = _columns(conn, table)
        if not existing or 'created_by_rollover' in existing:
            continue
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN created_by_rollover INTEGER DEFAULT 0"
        )
        conn.execute(
            f"UPDATE {table} SET created_by_rollover = 0 WHERE created_by_rollover IS NULL"
        )
        added.append(table)
    return added


def migrate_parent_links_to_weekly_tactic(conn: sqlite3.Connection) -> Dict[str, Any]:
    """WT-M1.D.1 / WT-M1.D.4 — move week links off ``parent_id``.

    Purpose: every ``parent_id`` whose parent is a week item becomes a
             ``weekly_tactic_id``; ordinary daily nesting is left alone.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1d1
    Tests:   tests/test_weekly_tactic_link_migration.py::test_wt_m1d1_tactic_links_migrated_nesting_preserved
             tests/test_weekly_tactic_link_migration.py::test_wt_m1d4_link_migration_idempotent

    Idempotent: a second run finds nothing to move and reports zero.
    """
    if 'weekly_tactic_id' not in _columns(conn, 'action_items'):
        return {"moved": 0, "nesting_preserved": 0, "moved_ids": []}

    rows = conn.execute("""
        SELECT child.id AS child_id, parent.id AS tactic_id
        FROM action_items child
        JOIN action_items parent ON parent.id = child.parent_id
        WHERE parent.item_type = 'week'
    """).fetchall()
    moved_ids: List[str] = [row["child_id"] for row in rows]

    for row in rows:
        conn.execute(
            "UPDATE action_items SET weekly_tactic_id = ?, parent_id = NULL WHERE id = ?",
            (row["tactic_id"], row["child_id"]),
        )

    nesting_preserved = conn.execute("""
        SELECT COUNT(*) AS n
        FROM action_items child
        JOIN action_items parent ON parent.id = child.parent_id
        WHERE parent.item_type <> 'week'
    """).fetchone()["n"]

    return {
        "moved": len(moved_ids),
        "nesting_preserved": nesting_preserved,
        "moved_ids": moved_ids,
    }


def create_weekly_tactic_unique_index(conn: sqlite3.Connection) -> bool:
    """WT-M1.C — the unique index enforcing WT-INV5.

    Purpose: at most one Weekly Tactic per (APE, week start).
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1c
    Tests:   tests/test_weekly_tactic_schema.py::test_wt_m1c1_duplicate_weekly_tactic_rejected
             tests/test_weekly_tactic_schema.py::test_wt_m1c2_index_creation_fails_loudly_on_dirty_db

    Fails loudly on a database that still holds duplicates. Skipping the index
    instead would leave the invariant unenforced while every later step assumed
    it held — the silent-drop shape of P2, applied to a constraint.

    Returns True when the index was created by this call.
    """
    from .weekly_tactic_maintenance import find_duplicate_weekly_tactics

    already = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name = ?",
        (WEEKLY_TACTIC_UNIQUE_INDEX,),
    ).fetchone()
    if already:
        return False

    remaining = find_duplicate_weekly_tactics(conn)
    if remaining:
        raise WeeklyTacticMigrationError(
            "Cannot create the Weekly Tactic unique index: "
            f"{len(remaining)} duplicate group(s) remain after dedupe — "
            + ", ".join(
                f"APE {g['ape_id']} week {g['start_date']} x{g['count']}"
                for g in remaining[:5]
            )
        )

    conn.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {WEEKLY_TACTIC_UNIQUE_INDEX}
        ON action_items(annual_plan_element_id, start_date)
        WHERE item_type = 'week'
        """
    )
    return True


def run_weekly_tactic_migrations(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Run every Weekly Tactic migration in dependency order.

    Purpose: single entry point called by ``Database.initialize_schema``.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#8-implementation-order
    Tests:   tests/test_weekly_tactic_link_migration.py
             tests/test_weekly_tactic_schema.py

    Order is load-bearing:
      1. columns — everything below reads them
      2. link migration — the dedupe repoints children onto ``weekly_tactic_id``
      3. dedupe — WT-M1.C's unique index cannot be created until it has run
      4. index
      5. invariant repair — needs the columns and a deduped set of tactics
    """
    report: Dict[str, Any] = {}

    report["link_column_added"] = add_weekly_tactic_link_column(conn)
    report["stamp_column_added"] = add_weekly_tactic_start_date_column(conn)
    report["project_board_columns_added"] = add_project_board_date_columns(conn)
    report["rollover_flag_tables"] = add_rollover_flag_columns(conn)
    report["link_migration"] = migrate_parent_links_to_weekly_tactic(conn)

    from .weekly_tactic_maintenance import (
        audit_stamp_week_starts,
        dedupe_weekly_tactics,
        normalize_week_item_starts,
        repair_weekly_tactic_invariants,
    )

    report["week_start_normalization"] = normalize_week_item_starts(conn)
    report["dedupe"] = dedupe_weekly_tactics(conn)

    # The index cannot be created over duplicates, and a duplicate that could
    # not be merged is not a reason to stop the app from opening. Raising here
    # would have made the previous launch's failure permanent: nothing commits
    # before this point, so the next launch would meet identical state and fail
    # identically, with no way out short of hand-editing the database.
    #
    # So the failure is recorded and logged at ERROR, and the app starts with
    # WT-INV5 unenforced and that fact on the record — loud, not skipped.
    report["unique_index_created"] = False
    report["unique_index_enforced"] = True
    report["unique_index_error"] = None
    try:
        report["unique_index_created"] = create_weekly_tactic_unique_index(conn)
    except WeeklyTacticMigrationError as exc:
        report["unique_index_enforced"] = False
        report["unique_index_error"] = str(exc)

    report["stamp_audit"] = audit_stamp_week_starts(conn)

    # WT-M7.B runs last: it needs the columns, a deduped set of tactics, and the
    # normalisation report, because a tactic that could not snap to its week
    # start makes its children genuinely unrepairable.
    report["invariant_repair"] = repair_weekly_tactic_invariants(
        conn, normalization=report["week_start_normalization"]
    )

    conn.commit()
    # Logged after the commit and outside every raising step, because this is
    # the only record of what happened to the user's rows and it is worth least
    # on the runs that go wrong.
    _log_report(report)
    return report


def _log_report(report: Dict[str, Any]) -> None:
    """Write everything the migration changed to the log.

    An automatic data change that says nothing is indistinguishable from one
    that did nothing (P2). This is the only surface where the user can see
    what happened to their rows.
    """
    moved = report["link_migration"]["moved"]
    if moved:
        logger.info(
            "[weekly_tactic_migration] moved %d tactic link(s) off parent_id; "
            "%d daily nesting link(s) preserved",
            moved,
            report["link_migration"]["nesting_preserved"],
        )

    normalization = report.get("week_start_normalization", {})
    if normalization.get("normalized"):
        logger.info(
            "[weekly_tactic_migration] snapped %d week item(s) onto their week start",
            normalization["normalized"],
        )
    if normalization.get("collided"):
        logger.warning(
            "[weekly_tactic_migration] %d week item(s) could not be snapped — "
            "another tactic already holds that week: %s",
            normalization["collided"],
            [c["id"] for c in normalization["collisions"]],
        )

    audit = report.get("stamp_audit", {})
    if audit.get("misaligned"):
        logger.warning(
            "[weekly_tactic_migration] %d of %d original-week stamp(s) no longer "
            "align to a week start; left unchanged (WT-INV3)",
            audit["misaligned"], audit["checked"],
        )

    dedupe = report.get("dedupe", {})
    if dedupe.get("blocked"):
        logger.error(
            "[weekly_tactic_migration] %d duplicate group(s) had at least one "
            "tactic that could not be merged: rows still reference it through a "
            "foreign key with no ON DELETE clause (%s). Those tactics were left "
            "in place.",
            dedupe["blocked"], dedupe.get("blocked_rows", {}),
        )
    if dedupe.get("dropped"):
        logger.warning(
            "[weekly_tactic_migration] rows removed with merged tactics: %s",
            dedupe["dropped"],
        )
    # Gated on groups, which counts every group processed — including one whose
    # merge was partly blocked. Gating on it while incrementing merged
    # separately once meant a deleted row's id never reached the log.
    if dedupe.get("groups"):
        logger.info(
            "[weekly_tactic_migration] merged %d duplicate tactic(s) across %d group(s); "
            "%d reference(s) repointed; %d title(s) re-canonicalised",
            dedupe["merged"], dedupe["groups"], dedupe["repointed"], dedupe["retitled"],
        )
        for detail in dedupe.get("details", []):
            logger.info(
                "[weekly_tactic_migration]   APE %s week %s: kept %s (%r -> %r), "
                "deleted %s, blocked %s",
                detail["ape_id"], detail["start_date"], detail["survivor_id"],
                detail["title_before"], detail["title_after"],
                detail["deleted_ids"], detail.get("blocked") or {},
            )

    repair = report.get("invariant_repair", {})
    if repair.get("moved"):
        logger.warning(
            "[weekly_tactic_migration] moved %d of %d linked item(s) back inside "
            "their Weekly Tactic's week (WT-INV1/WT-INV2). Every move has a "
            "reschedule_history row with reason='inv_repair'.",
            repair["moved"], repair["checked"],
        )
        for detail in repair.get("details", []):
            logger.warning(
                "[weekly_tactic_migration]   %s: %s..%s -> %s..%s (%+d day(s)) "
                "into week %s",
                detail["item_id"], detail["from_start"], detail["from_due"],
                detail["to_start"], detail["to_due"],
                detail["start_shift_days"] or 0, detail["week_start"],
            )
    if repair.get("skipped"):
        logger.error(
            "[weekly_tactic_migration] %d linked item(s) left out of range "
            "because their tactic could not be snapped to a week start",
            repair["skipped"],
        )

    if not report.get("unique_index_enforced", True):
        logger.error(
            "[weekly_tactic_migration] the WT-INV5 unique index could not be "
            "created, so one Weekly Tactic per (APE, week) is NOT enforced in "
            "this database: %s",
            report.get("unique_index_error"),
        )
