"""Weekly Tactic data cleanup — dedupe and invariant repair.

Purpose: bring an existing database into line with WT-INV1/2/5, reporting
         every row it changes.
Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7
Tests:   tests/test_weekly_tactic_dedupe.py

Both routines run automatically from the migration. That makes reporting the
whole safety story: a merge that destroys a child link, or a repair that
rewrites 53 dates, must never be indistinguishable from a no-op (P2). Every
function here returns what it did, and the migration logs it in full.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from . import week_calendar
from .weekly_tactic_titles import canonical_weekly_tactic_title

logger = logging.getLogger("getmoredone.weekly_tactic")

# Tables that reference action_items(id) with ON DELETE CASCADE. Every one must
# be repointed onto the survivor *before* a loser is deleted, or the merge
# silently destroys rows the user cannot get back (WT-M7.A.3).
CASCADE_CHILD_TABLES = (
    ("reschedule_history", "item_id"),
    ("item_links", "item_id"),
    ("work_logs", "item_id"),
    ("project_board_items", "item_id"),
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def normalize_week_item_starts(
    conn: sqlite3.Connection,
    calendar: Optional[week_calendar.WeekCalendar] = None,
) -> Dict[str, Any]:
    """Snap every week item onto its week's real boundaries.

    Purpose: WT-M1.C's unique index is on the raw ``start_date`` column, so it
             only enforces WT-INV5 once every week item's start date *is* its
             week start. Normalising first is what makes the index mean what
             WT-INV5 says.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1c
    Tests:   tests/test_weekly_tactic_dedupe.py::test_wt_m7a6_dedupe_idempotent_and_dirty_state

    Normalising can itself collide two weeks onto one start date — that is
    WT-M1.C.5's scenario, and it is why this runs before the dedupe, not after.
    On a database that *already* has the unique index (every run after the
    first), such a collision would otherwise raise straight out of schema
    initialisation and stop the app from opening. The row is left where it is
    and the clash is reported instead.
    """
    cal = calendar or week_calendar.WeekCalendar.from_settings()
    now = datetime.now().isoformat()
    moved: List[Dict[str, str]] = []
    collisions: List[Dict[str, str]] = []

    rows = conn.execute(
        "SELECT id, start_date, due_date FROM action_items WHERE item_type = 'week'"
    ).fetchall()
    for row in rows:
        source = row["start_date"] or row["due_date"]
        bounds = cal.bounds_iso(source)
        if bounds is None:
            continue
        start, end = bounds
        if row["start_date"] == start and row["due_date"] == end:
            continue
        try:
            conn.execute(
                "UPDATE action_items SET start_date = ?, due_date = ?, updated_at = ? WHERE id = ?",
                (start, end, now, row["id"]),
            )
        except sqlite3.IntegrityError as exc:
            collisions.append({
                "id": row["id"],
                "from_start": row["start_date"],
                "blocked_start": start,
                "error": str(exc),
            })
            logger.warning(
                "[weekly_tactic] week item %s cannot snap from %s to %s — a "
                "tactic already occupies that week: %s",
                row["id"], row["start_date"], start, exc,
            )
            continue
        moved.append({
            "id": row["id"],
            "from_start": row["start_date"],
            "to_start": start,
        })

    return {
        "normalized": len(moved),
        "details": moved,
        "collided": len(collisions),
        "collisions": collisions,
    }


def audit_stamp_week_starts(
    conn: sqlite3.Connection,
    calendar: Optional[week_calendar.WeekCalendar] = None,
) -> Dict[str, Any]:
    """WT-M2.B.3 — report stamps that no longer sit on a week start.

    Purpose: changing ``first_day_of_week`` moves where weeks begin, but
             WT-INV3 forbids any automatic path from moving a
             ``weekly_tactic_start_date``. So a stamp taken under the old
             setting can end up mid-week.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m2b3
    Tests:   tests/test_week_numbering.py::test_wt_m2b3_first_day_change_on_populated_db

    Reports them rather than repairing them: rewriting the stamp is exactly
    what WT-INV3 rules out, and a silent rewrite would destroy the only record
    of when the item was originally meant to start.
    """
    cal = calendar or week_calendar.WeekCalendar.from_settings()
    misaligned: List[Dict[str, str]] = []

    rows = conn.execute("""
        SELECT id, weekly_tactic_start_date
        FROM action_items
        WHERE weekly_tactic_start_date IS NOT NULL
          AND weekly_tactic_start_date <> ''
    """).fetchall()
    for row in rows:
        stamp = row["weekly_tactic_start_date"]
        aligned = cal.start(stamp)
        if aligned is None or aligned.isoformat() != stamp:
            misaligned.append({
                "id": row["id"],
                "stamp": stamp,
                "week_start_now": aligned.isoformat() if aligned else None,
            })

    if misaligned:
        logger.warning(
            "[weekly_tactic] %d original-week stamp(s) no longer sit on a week "
            "start under the current first-day-of-week; left unchanged per "
            "WT-INV3: %s",
            len(misaligned), [m["id"] for m in misaligned],
        )

    return {"checked": len(rows), "misaligned": len(misaligned), "details": misaligned}


def find_duplicate_weekly_tactics(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Groups of week items sharing one (APE, week start).

    Week items with no APE are skipped: SQLite treats NULLs as distinct, so
    they could not be deduped by key anyway (WT-M1.C.4 stops new ones).
    """
    rows = conn.execute("""
        SELECT annual_plan_element_id AS ape_id, start_date, COUNT(*) AS n
        FROM action_items
        WHERE item_type = 'week'
          AND annual_plan_element_id IS NOT NULL
          AND start_date IS NOT NULL
        GROUP BY annual_plan_element_id, start_date
        HAVING COUNT(*) > 1
        ORDER BY annual_plan_element_id, start_date
    """).fetchall()
    return [
        {"ape_id": row["ape_id"], "start_date": row["start_date"], "count": row["n"]}
        for row in rows
    ]


def _child_count(conn: sqlite3.Connection, tactic_id: str) -> int:
    return conn.execute(
        """
        SELECT COUNT(*) AS n FROM action_items
        WHERE weekly_tactic_id = ? OR parent_id = ?
        """,
        (tactic_id, tactic_id),
    ).fetchone()["n"]


def _choose_survivor(conn: sqlite3.Connection, rows: List[sqlite3.Row]) -> sqlite3.Row:
    """WT-M7.A.4 — most children wins; ties break on oldest ``created_at``.

    Stated rather than left to whatever sorts first, because the choice decides
    which links survive. On the live duplicate this picks the older ``W8`` row,
    which holds all five children — and whose title is then corrected.
    """
    return sorted(
        rows,
        key=lambda row: (-_child_count(conn, row["id"]), row["created_at"] or "", row["id"]),
    )[0]


def _repoint_children(conn: sqlite3.Connection, loser_id: str, survivor_id: str):
    """Move every reference off the loser before it is deleted.

    All four cascade tables are ON DELETE CASCADE, so anything still pointing at
    the loser when it goes is destroyed with it (WT-M7.A.3). The updates run
    first, and whatever a uniqueness constraint refuses to move is counted and
    reported rather than disappearing quietly.
    """
    counts: Dict[str, int] = {}
    dropped: Dict[str, int] = {}

    cursor = conn.execute(
        "UPDATE action_items SET weekly_tactic_id = ? WHERE weekly_tactic_id = ?",
        (survivor_id, loser_id),
    )
    counts["action_items.weekly_tactic_id"] = cursor.rowcount

    # Stragglers that never went through the WT-M1.D migration (a week parent
    # written by an older build between migration and dedupe).
    cursor = conn.execute(
        "UPDATE action_items SET weekly_tactic_id = ?, parent_id = NULL WHERE parent_id = ?",
        (survivor_id, loser_id),
    )
    counts["action_items.parent_id"] = cursor.rowcount

    for table, column in CASCADE_CHILD_TABLES:
        if not _table_exists(conn, table):
            continue
        # OR IGNORE: project_board_items is keyed (board, item), so a loser and
        # survivor already on the same board would collide. That row is a real
        # duplicate once merged — but it is still a row about to be cascaded
        # away, so it is counted below rather than lost in silence.
        cursor = conn.execute(
            f"UPDATE OR IGNORE {table} SET {column} = ? WHERE {column} = ?",
            (survivor_id, loser_id),
        )
        counts[f"{table}.{column}"] = cursor.rowcount

        left = conn.execute(
            f"SELECT COUNT(*) AS n FROM {table} WHERE {column} = ?", (loser_id,)
        ).fetchone()["n"]
        if left:
            dropped[f"{table}.{column}"] = left
            logger.warning(
                "[weekly_tactic] %d %s row(s) could not move from %s to %s and "
                "will be removed with the merged tactic",
                left, table, loser_id, survivor_id,
            )

    return counts, dropped


def _ape_key_field(conn: sqlite3.Connection, ape_id: Optional[str]) -> Optional[str]:
    if not ape_id:
        return None
    row = conn.execute(
        "SELECT key_field FROM annual_plan_elements WHERE id = ?", (ape_id,)
    ).fetchone()
    return row["key_field"] if row else None


def dedupe_weekly_tactics(
    conn: sqlite3.Connection,
    calendar: Optional[week_calendar.WeekCalendar] = None,
) -> Dict[str, Any]:
    """WT-M7.A — one Weekly Tactic per (APE, week).

    Purpose: merge duplicates, repoint every child onto the survivor, and
             re-canonicalise the survivor's title.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7a
    Tests:   tests/test_weekly_tactic_dedupe.py::test_wt_m7a1_duplicates_merged_children_repointed
             tests/test_weekly_tactic_dedupe.py::test_wt_m7a3_no_cascade_data_lost

    Idempotent: a second run finds no groups and reports zeros.
    """
    cal = calendar or week_calendar.WeekCalendar.from_settings()
    now = datetime.now().isoformat()

    report: Dict[str, Any] = {
        "groups": 0,
        "merged": 0,
        "repointed": 0,
        "retitled": 0,
        "dropped": {},
        "details": [],
    }

    for group in find_duplicate_weekly_tactics(conn):
        rows = conn.execute(
            """
            SELECT * FROM action_items
            WHERE item_type = 'week'
              AND annual_plan_element_id = ?
              AND start_date = ?
            ORDER BY created_at ASC, id ASC
            """,
            (group["ape_id"], group["start_date"]),
        ).fetchall()
        if len(rows) < 2:
            continue

        survivor = _choose_survivor(conn, rows)
        losers = [row for row in rows if row["id"] != survivor["id"]]

        repointed = 0
        dropped_total: Dict[str, int] = {}
        for loser in losers:
            counts, dropped = _repoint_children(conn, loser["id"], survivor["id"])
            repointed += sum(counts.values())
            for key, value in dropped.items():
                dropped_total[key] = dropped_total.get(key, 0) + value
            conn.execute("DELETE FROM action_items WHERE id = ?", (loser["id"],))

        canonical = canonical_weekly_tactic_title(
            _ape_key_field(conn, group["ape_id"]), survivor["start_date"], cal
        )
        retitled = False
        if canonical and canonical != survivor["title"]:
            conn.execute(
                "UPDATE action_items SET title = ?, updated_at = ? WHERE id = ?",
                (canonical, now, survivor["id"]),
            )
            retitled = True

        report["groups"] += 1
        report["merged"] += len(losers)
        report["repointed"] += repointed
        report["retitled"] += 1 if retitled else 0
        for key, value in dropped_total.items():
            report["dropped"][key] = report["dropped"].get(key, 0) + value
        report["details"].append({
            "ape_id": group["ape_id"],
            "start_date": group["start_date"],
            "survivor_id": survivor["id"],
            "deleted_ids": [row["id"] for row in losers],
            "title_before": survivor["title"],
            "title_after": canonical if retitled else survivor["title"],
            "repointed": repointed,
            "dropped": dropped_total,
        })

    return report
