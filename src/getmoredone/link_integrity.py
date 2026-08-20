"""Id columns for links that are currently resolved by name.

Purpose: give every link a real id, so renaming a thing never moves it.
Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-m1
Tests:   tests/test_rename_safe_links.py

A name is a label. Today three links are held together by one instead:

* ``annual_plan_elements`` / ``annual_vision_elements`` carry ``segment_name``
  and no id, so the re-filing cascade resolves the segment by name — and
  renaming one makes an ordinary date change on a filed Action Item **raise**
  (spec §2).
* ``annual_initiatives`` is matched to its APE by
  ``LOWER(ai.title) = LOWER(ape.key_field)``, so a rename makes the next
  assignment build a *second* initiative (RN-F4).
* ``vision_segments`` and ``segment_descriptions`` describe one concept in two
  tables with no key between them, joined on ``LOWER(name)`` in three places
  (RN-F2).

**The backfill never guesses.** It matches the *current* name exactly, once,
case-insensitively, and writes the id. A row that matches nothing — or matches
ambiguously — is left NULL and **reported** (RN-INV5, RN-D2). A wrong link is
worse than a missing one: a missing one is visible in the report, and a wrong
one silently attaches a user's work to someone else's plan element.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, List

from .weekly_tactic_logging import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)


def _columns(conn: sqlite3.Connection, table: str) -> List[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone() is not None


# --------------------------------------------------------------------------
# RN-M1.A / RN-M1.C — the id columns
# --------------------------------------------------------------------------

SEGMENT_ID_TABLES = ("annual_plan_elements", "annual_vision_elements", "vision_segments")


def add_segment_description_id_columns(conn: sqlite3.Connection) -> Dict[str, bool]:
    """RN-M1.A.1 / RN-M1.C.1 — add ``segment_description_id``, idempotently.

    Nullable and unconstrained on purpose: pre-existing rows must migrate
    rather than block, and a row the backfill cannot resolve stays NULL so the
    report can name it (RN-D3, RN-INV5).

    Returns ``{table: True}`` where this call added the column.
    """
    added: Dict[str, bool] = {}
    for table in SEGMENT_ID_TABLES:
        if not _table_exists(conn, table):
            added[table] = False
            continue
        if "segment_description_id" in _columns(conn, table):
            added[table] = False
            continue
        conn.execute(
            f"ALTER TABLE {table} "
            "ADD COLUMN segment_description_id TEXT "
            # ON DELETE SET NULL, not a bare reference: deleting a life segment
            # must null the link, not fail with FOREIGN KEY constraint failed.
            # A plain REFERENCES made delete_segment raise for a segment with
            # no children at all, because sync_vision_segments_with_settings
            # had created a vision_segments row pointing at it.
            "REFERENCES segment_descriptions(id) ON DELETE SET NULL"
        )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_segment_description "
            f"ON {table}(segment_description_id)"
        )
        added[table] = True
    return added


def add_initiative_ape_column(conn: sqlite3.Connection) -> bool:
    """RN-M1.B — ``annual_initiatives.annual_plan_element_id`` (RN-D3).

    The link lives on the initiative rather than the APE because an initiative
    is created lazily *for* an APE, and an APE may legitimately have none yet.
    """
    if not _table_exists(conn, "annual_initiatives"):
        return False
    if "annual_plan_element_id" in _columns(conn, "annual_initiatives"):
        return False
    conn.execute(
        "ALTER TABLE annual_initiatives "
        "ADD COLUMN annual_plan_element_id TEXT "
        "REFERENCES annual_plan_elements(id) ON DELETE SET NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_annual_initiatives_ape "
        "ON annual_initiatives(annual_plan_element_id)"
    )
    return True


# --------------------------------------------------------------------------
# RN-M1.A.2 / RN-M1.C.1 — backfill the segment id, or report the row
# --------------------------------------------------------------------------

def backfill_segment_ids(conn: sqlite3.Connection, table: str) -> Dict[str, Any]:
    """Match ``<table>.<name column>`` to a segment description, exactly, once.

    Spec:  docs/spec_2026-08-19_rename_safe_links.md#rn-m1a2
    Tests: tests/test_rename_safe_links.py::test_rn_m1a2_unmatched_segment_is_reported_not_guessed

    Case-insensitive **exact** match, nothing fuzzy. Only rows whose id is
    still NULL are touched, so this is a no-op on the second run (RN-M1.D) and
    it never overwrites a link that resolution has since healed.

    Two segments with the same name case-insensitively would make the match
    ambiguous. That is reported and left NULL rather than resolved by picking
    one — the whole point of RN-INV5.
    """
    if not _table_exists(conn, table):
        return {"linked": 0, "unmatched": [], "ambiguous": []}

    name_column = "name" if table == "vision_segments" else "segment_name"
    if "segment_description_id" not in _columns(conn, table):
        return {"linked": 0, "unmatched": [], "ambiguous": []}

    rows = conn.execute(
        f"SELECT id, {name_column} AS nm FROM {table} "
        "WHERE segment_description_id IS NULL"
    ).fetchall()

    linked = 0
    unmatched: List[Dict[str, Any]] = []
    ambiguous: List[Dict[str, Any]] = []

    for row in rows:
        name = (row["nm"] or "").strip()
        if not name:
            unmatched.append({"id": row["id"], "name": row["nm"]})
            continue
        matches = conn.execute(
            "SELECT id FROM segment_descriptions WHERE LOWER(name) = LOWER(?)",
            (name,),
        ).fetchall()
        if len(matches) == 1:
            conn.execute(
                f"UPDATE {table} SET segment_description_id = ? WHERE id = ?",
                (matches[0]["id"], row["id"]),
            )
            linked += 1
        elif not matches:
            unmatched.append({"id": row["id"], "name": name})
        else:
            # Two segments share a name. Guessing here would attach the row to
            # an arbitrary one of them, silently.
            ambiguous.append(
                {"id": row["id"], "name": name,
                 "candidates": [m["id"] for m in matches]}
            )

    return {"linked": linked, "unmatched": unmatched, "ambiguous": ambiguous}


# --------------------------------------------------------------------------
# RN-M1.B.1 / RN-M1.B.2 — backfill the initiative ↔ APE link
# --------------------------------------------------------------------------

def backfill_initiative_ape_links(conn: sqlite3.Connection) -> Dict[str, Any]:
    """RN-M1.B.1 — link each initiative to its APE by the title match, once.

    Spec:  docs/spec_2026-08-19_rename_safe_links.md#rn-m1b1
    Tests: tests/test_rename_safe_links.py::test_rn_m1b1_initiative_ape_link_backfilled_from_title
           tests/test_rename_safe_links.py::test_rn_m1b2_ambiguous_backfill_is_reported

    This is the **only** time the title match is used to establish the link. It
    reproduces exactly what ``_find_annual_initiative_for_ape`` does today —
    same year, same segment, ``LOWER(title) = LOWER(key_field)`` — so a
    database that works before the migration links the same way after it.

    RN-M1.B.2: a user who has already renamed may have TWO initiatives matching
    one APE (that is RN-F4's duplicate). The oldest by ``created_at`` is
    linked, the other is left NULL, and **both are reported**. Dropping or
    merging the second is a tie-break decision this migration does not own
    (spec §9).
    """
    if not (_table_exists(conn, "annual_initiatives")
            and _table_exists(conn, "annual_plan_elements")):
        return {"linked": 0, "unmatched": [], "ambiguous": []}
    if "annual_plan_element_id" not in _columns(conn, "annual_initiatives"):
        return {"linked": 0, "unmatched": [], "ambiguous": []}

    apes = conn.execute(
        "SELECT id, year, key_field, segment_description_id, segment_name "
        "FROM annual_plan_elements"
    ).fetchall()

    linked = 0
    ambiguous: List[Dict[str, Any]] = []
    claimed: set[str] = set()

    for ape in apes:
        segment_id = ape["segment_description_id"]
        if not segment_id:
            # No resolvable segment: the title match alone is not specific
            # enough, since two segments can hold the same key field.
            continue
        matches = conn.execute(
            """
            SELECT ai.id
            FROM annual_initiatives ai
            JOIN annual_plans ap ON ap.id = ai.annual_plan_id
            WHERE ai.year = ?
              AND ai.segment_description_id = ?
              AND LOWER(ai.title) = LOWER(?)
              AND ap.year = ?
              AND ai.annual_plan_element_id IS NULL
            ORDER BY ai.created_at ASC, ai.id ASC
            """,
            (int(ape["year"]), segment_id, ape["key_field"], int(ape["year"])),
        ).fetchall()
        if not matches:
            continue

        winner = matches[0]["id"]
        conn.execute(
            "UPDATE annual_initiatives SET annual_plan_element_id = ? WHERE id = ?",
            (ape["id"], winner),
        )
        claimed.add(winner)
        linked += 1

        if len(matches) > 1:
            ambiguous.append({
                "annual_plan_element_id": ape["id"],
                "key_field": ape["key_field"],
                "year": ape["year"],
                "linked": winner,
                "left_null": [m["id"] for m in matches[1:]],
            })

    unmatched = [
        {"id": row["id"], "title": row["title"], "year": row["year"]}
        for row in conn.execute(
            "SELECT id, title, year FROM annual_initiatives "
            "WHERE annual_plan_element_id IS NULL"
        ).fetchall()
    ]

    return {"linked": linked, "unmatched": unmatched, "ambiguous": ambiguous}


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def run_link_integrity_migrations(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Every RN-M1 migration, in dependency order.

    Purpose: single entry point called by ``Database.initialize_schema``.
    Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-m1
    Tests:   tests/test_rename_safe_links.py::test_rn_m1d_migration_on_populated_db_run_two

    Order is load-bearing: the initiative backfill reads
    ``annual_plan_elements.segment_description_id``, so the segment backfill
    must have run first. Getting this wrong does not error — it silently links
    nothing, which is why the order is stated rather than assumed.
    """
    report: Dict[str, Any] = {}

    report["columns_added"] = add_segment_description_id_columns(conn)
    report["initiative_column_added"] = add_initiative_ape_column(conn)

    for table in SEGMENT_ID_TABLES:
        report[f"backfill_{table}"] = backfill_segment_ids(conn, table)

    report["backfill_initiative_ape"] = backfill_initiative_ape_links(conn)

    _log_report(report)
    return report


def _log_report(report: Dict[str, Any]) -> None:
    """Write what could not be resolved to the audit log (RN-M5.A).

    Only unresolved rows are logged. A migration that links everything cleanly
    says nothing, so a line in this log always means something needs a human.
    """
    for key, value in report.items():
        if not isinstance(value, dict) or "unmatched" not in value:
            continue
        if value["linked"]:
            logger.info("link-integrity: %s linked %d row(s)", key, value["linked"])
        for row in value["unmatched"]:
            logger.warning(
                "link-integrity: %s could not resolve %s — left NULL, not guessed",
                key, row,
            )
        for row in value["ambiguous"]:
            logger.warning(
                "link-integrity: %s is AMBIGUOUS %s — left NULL, needs a human",
                key, row,
            )
