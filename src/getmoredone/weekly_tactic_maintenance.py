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

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from . import week_calendar
from .models import ActionItem
from .weekly_tactic import bring_into_week
from .weekly_tactic_logging import get_weekly_tactic_logger
from .weekly_tactic_titles import canonical_weekly_tactic_title

logger = get_weekly_tactic_logger()

# The (table, column) pairs this schema is known to declare against
# action_items. The derived list below is the source of truth, but every table
# here is created with CREATE TABLE IF NOT EXISTS — so a database made before a
# REFERENCES clause was added keeps the old, FK-free definition forever (SQLite
# cannot add a constraint by ALTER TABLE). On such a database the table is
# invisible to PRAGMA and its rows would be orphaned silently. This floor turns
# that into a warning instead of an absence.
EXPECTED_REFERENCES = {
    ("reschedule_history", "item_id"),
    ("item_links", "item_id"),
    ("work_logs", "item_id"),
    ("time_blocks", "item_id"),
    ("project_board_items", "item_id"),
    ("habit_tracking", "action_item_id"),
}


def referencing_tables(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Every (table, column) holding a foreign key into ``action_items``.

    Purpose: derive the repoint list from the schema instead of maintaining it
             by hand.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7a3
    Tests:   tests/test_weekly_tactic_dedupe.py::test_wt_m7a3_every_referencing_table_is_derived_from_the_schema

    A hand-written list shipped two bugs at once: ``time_blocks`` was missing and
    has no ON DELETE clause, so deleting a merged tactic raised FOREIGN KEY
    constraint failed during schema init — an unrecoverable start-up crash loop;
    and ``habit_tracking`` was missing and *is* ON DELETE CASCADE, so its rows
    were destroyed while the report said nothing was dropped. Both are the same
    root cause, and the next table added to the schema would have reopened them.

    ``on_delete`` is carried through because it decides what a leftover row
    means: CASCADE leftovers are destroyed by the delete (report them), while
    NO ACTION / RESTRICT leftovers make the delete fail (skip the merge).
    """
    found: List[Dict[str, Any]] = []
    tables = [
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    for table in tables:
        if table == "action_items":
            continue  # parent_id / weekly_tactic_id are handled explicitly
        try:
            fks = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        except sqlite3.Error:
            continue
        for fk in fks:
            if fk["table"] != "action_items":
                continue
            found.append({
                "table": table,
                "column": fk["from"],
                "on_delete": (fk["on_delete"] or "NO ACTION").upper(),
            })

    live = {(entry["table"], entry["column"]) for entry in found}
    existing = set(tables)
    for table, column in sorted(EXPECTED_REFERENCES - live):
        if table not in existing:
            continue  # the table itself is absent; nothing to orphan
        found.append({"table": table, "column": column, "on_delete": "NO ACTION"})
        logger.warning(
            "[weekly_tactic] %s.%s does not declare its foreign key to "
            "action_items in this database (created before the clause was "
            "added); repointing it anyway so its rows are not orphaned",
            table, column,
        )

    return sorted(found, key=lambda entry: (entry["table"], entry["column"]))


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
    blocking: Dict[str, int] = {}

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

    for entry in referencing_tables(conn):
        table, column = entry["table"], entry["column"]
        # OR IGNORE: some of these carry a uniqueness constraint —
        # project_board_items is keyed (board, item), habit_tracking is keyed
        # (item, date) — so a loser and survivor already sharing that key would
        # collide. Such a row is a genuine duplicate once merged, but it is
        # still a row about to disappear, so it is counted rather than lost.
        cursor = conn.execute(
            f"UPDATE OR IGNORE {table} SET {column} = ? WHERE {column} = ?",
            (survivor_id, loser_id),
        )
        counts[f"{table}.{column}"] = cursor.rowcount

        left = conn.execute(
            f"SELECT COUNT(*) AS n FROM {table} WHERE {column} = ?", (loser_id,)
        ).fetchone()["n"]
        if not left:
            continue

        key = f"{table}.{column}"
        if entry["on_delete"] == "CASCADE":
            dropped[key] = left
            logger.warning(
                "[weekly_tactic] %d %s row(s) could not move from %s to %s and "
                "will be removed with the merged tactic",
                left, table, loser_id, survivor_id,
            )
        else:
            # No ON DELETE clause: the delete would fail with FOREIGN KEY
            # constraint failed, which at migration time is an app that will
            # not start. Refuse the merge instead.
            blocking[key] = left
            logger.error(
                "[weekly_tactic] %d %s row(s) still reference %s and cannot be "
                "moved to %s; the merge is skipped rather than crashing",
                left, table, loser_id, survivor_id,
            )

    return counts, dropped, blocking


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
        "blocked": 0,
        "blocked_rows": {},
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
        blocked_total: Dict[str, int] = {}
        deleted_ids: List[str] = []
        for loser in losers:
            counts, dropped, blocking = _repoint_children(
                conn, loser["id"], survivor["id"]
            )
            if blocking:
                # This loser stays. Its leftovers were not destroyed, so they
                # must not be counted as dropped — nor may the rows that *did*
                # move for it be reported as repointed onto a merge that never
                # happened.
                for key, value in blocking.items():
                    blocked_total[key] = blocked_total.get(key, 0) + value
                continue

            repointed += sum(counts.values())
            for key, value in dropped.items():
                dropped_total[key] = dropped_total.get(key, 0) + value
            conn.execute("DELETE FROM action_items WHERE id = ?", (loser["id"],))
            deleted_ids.append(loser["id"])

        if blocked_total:
            report["blocked"] += 1

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
        report["merged"] += len(deleted_ids)
        report["repointed"] += repointed
        report["retitled"] += 1 if retitled else 0
        for key, value in dropped_total.items():
            report["dropped"][key] = report["dropped"].get(key, 0) + value
        for key, value in blocked_total.items():
            report["blocked_rows"][key] = report["blocked_rows"].get(key, 0) + value
        report["details"].append({
            "ape_id": group["ape_id"],
            "start_date": group["start_date"],
            "survivor_id": survivor["id"],
            "deleted_ids": deleted_ids,
            "title_before": survivor["title"],
            "title_after": canonical if retitled else survivor["title"],
            "repointed": repointed,
            "dropped": dropped_total,
            "blocked": blocked_total,
        })

    return report


def repair_weekly_tactic_invariants(
    conn: sqlite3.Connection,
    calendar: Optional[week_calendar.WeekCalendar] = None,
    normalization: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """WT-M7.B — bring every linked item's dates inside its tactic's week.

    Purpose: repair the WT-INV1 / WT-INV2 violations that pre-date this feature
             — 24 start dates and 29 due dates on the live database (WT-F10).
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7b
    Tests:   tests/test_weekly_tactic_dedupe.py::test_wt_m7b1_existing_violations_repaired
             tests/test_weekly_tactic_dedupe.py::test_wt_m7b2_repair_reports_what_it_moved

    Runs automatically inside the migration, so three things carry the weight
    that a dry-run gate would otherwise have carried:

    * the full per-item before/after list is returned and logged, not a count —
      53 dates rewritten with nothing to show for it is the silent-drop shape
      of P2;
    * every move writes a ``reschedule_history`` row with
      ``reason='inv_repair'``, so a wrong one is reversible;
    * it is a no-op on an already-clean database, because it runs on every app
      start rather than once.

    ``normalization`` is the report from :func:`normalize_week_item_starts`.
    A week item that could not snap to its boundary leaves its children
    genuinely unrepairable — the week itself is in the wrong place — so those
    are reported here rather than silently counted as repaired.
    """
    cal = calendar or week_calendar.WeekCalendar.from_settings()
    now = datetime.now().isoformat()

    blocked_tactics = {
        entry["id"] for entry in (normalization or {}).get("collisions", [])
    }

    moved: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    rows = conn.execute("""
        SELECT child.id           AS item_id,
               child.start_date   AS start_date,
               child.due_date     AS due_date,
               week.id            AS tactic_id,
               week.start_date    AS week_start,
               week.due_date      AS week_end
        FROM action_items child
        JOIN action_items week ON week.id = child.weekly_tactic_id
        WHERE week.item_type = 'week'
          AND week.start_date IS NOT NULL
        ORDER BY child.id
    """).fetchall()

    for row in rows:
        week_start = week_calendar.coerce_date(row["week_start"])
        if week_start is None:
            # Reported, not skipped in silence: an item left out of range that
            # appears in neither list makes the report unable to show it (P2).
            skipped.append({
                "item_id": row["item_id"],
                "tactic_id": row["tactic_id"],
                "reason": f"tactic start date {row['week_start']!r} is not a date",
            })
            continue
        week_end = week_calendar.coerce_date(row["week_end"]) or (
            week_start + timedelta(days=6))

        start = week_calendar.coerce_date(row["start_date"])
        due = week_calendar.coerce_date(row["due_date"])
        # A NULL due date is not a violation: bring_into_week leaves it NULL, so
        # requiring one here made such a row "repaired" on every single app
        # start — an identical UPDATE plus a fresh history row, for ever, while
        # the report claimed a move that never happened.
        start_ok = start is not None and week_start <= start <= week_end
        due_ok = due is None or (week_start <= due <= week_end)
        if start_ok and due_ok:
            continue

        if row["tactic_id"] in blocked_tactics:
            # The tactic itself is sitting on the wrong week start, so moving
            # its children would file them against a boundary that is about to
            # change. Report rather than repair.
            skipped.append({
                "item_id": row["item_id"],
                "tactic_id": row["tactic_id"],
                "reason": "tactic could not be snapped to its week start",
            })
            logger.warning(
                "[weekly_tactic] item %s left out of range: its tactic %s could "
                "not be snapped to a week start",
                row["item_id"], row["tactic_id"],
            )
            continue

        item = ActionItem(who="", title="", start_date=row["start_date"],
                          due_date=row["due_date"])
        change = bring_into_week(item, week_start, week_end)

        if (change["from_start"], change["from_due"]) == (change["to_start"], change["to_due"]):
            # Nothing actually moved. Writing an identical UPDATE and a history
            # row anyway would report a change that did not happen.
            continue

        conn.execute(
            "UPDATE action_items SET start_date = ?, due_date = ?, updated_at = ? WHERE id = ?",
            (item.start_date, item.due_date, now, row["item_id"]),
        )
        conn.execute(
            """
            INSERT INTO reschedule_history (
                id, item_id, from_start, from_due, to_start, to_due, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'inv_repair', ?)
            """,
            (f"rh-{uuid4().hex[:12]}", row["item_id"], change["from_start"],
             change["from_due"], change["to_start"], change["to_due"], now),
        )
        moved.append({
            "item_id": row["item_id"],
            "tactic_id": row["tactic_id"],
            "week_start": row["week_start"],
            **change,
            "start_shift_days": _day_delta(change["from_start"], change["to_start"]),
        })

    return {
        "checked": len(rows),
        "moved": len(moved),
        "skipped": len(skipped),
        "details": moved,
        "skipped_details": skipped,
    }


def _day_delta(from_date: Optional[str], to_date: Optional[str]) -> Optional[int]:
    """How far a date moved, in days — the "by how much" WT-M7.B.2 asks for."""
    start = week_calendar.coerce_date(from_date)
    end = week_calendar.coerce_date(to_date)
    if start is None or end is None:
        return None
    return (end - start).days
