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
# The one resolver every LINK write uses
# --------------------------------------------------------------------------

def resolve_segment_id_exact(conn: sqlite3.Connection, name) -> "str | None":
    """The segment description with this name, or None if that is not unique.

    Purpose: never write a link the migration would have refused to write.
    Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-inv5
    Tests:   tests/test_rename_safe_links.py::test_rn_ambiguous_name_is_never_resolved_to_a_link

    ``segment_descriptions.name`` is UNIQUE but **case-sensitive**, so ``Health``
    and ``health`` coexist legally. ``resolve_segment_id_by_name`` is a
    ``fetchone()`` with no ambiguity check: it returns whichever row SQLite
    hands back first.

    That mattered because the backfill was careful and its callers were not.
    The migration reported ``ambiguous: [...]`` and left the row NULL — and
    then ``sync_vision_segments_with_settings``, which runs at EVERY manager
    init moments later, wrote a guess into the same row. The logged report was
    false about the database it had just described.

    Returning None on ambiguity is the whole of RN-INV5: a missing link is
    visible in the report, a wrong one is not.
    """
    text = (name or "").strip()
    if not text:
        return None
    rows = conn.execute(
        "SELECT id FROM segment_descriptions WHERE LOWER(name) = LOWER(?)",
        (text,),
    ).fetchall()
    return rows[0]["id"] if len(rows) == 1 else None


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
        resolved = resolve_segment_id_exact(conn, name)
        if resolved is not None:
            conn.execute(
                f"UPDATE {table} SET segment_description_id = ? WHERE id = ?",
                (resolved, row["id"]),
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

def find_initiative_candidates_by_title(
    conn: sqlite3.Connection,
    year: int,
    segment_id: str,
    key_field: str,
) -> List[sqlite3.Row]:
    """Unlinked initiatives whose title still reads as this APE's key field.

    Purpose: one candidate query for the two places that establish the link by
             title — the migration's backfill and the runtime heal.
    Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-m1b1
    Tests:   tests/test_rename_safe_links.py::test_rn_m1b1_backfill_prefers_the_candidate_whose_plan_year_agrees
             tests/test_rename_safe_links.py::test_rn_m2a1_heal_prefers_the_candidate_whose_plan_year_agrees

    **The annual plan's year is a tie-break, not a veto.** Candidates whose
    plan agrees with the APE's year are returned when there are any; the wider
    set is used only when that narrower one is empty.

    Requiring the plan year outright made a correctly-titled initiative on a
    drifted-year plan invisible, so neither caller could link it. Dropping it
    outright was worse in the other direction: a twin on a drifted plan joined
    the candidate set, and being older it won the backfill's ``created_at``
    order and took the link, while the heal — whose contract is "exactly one
    match or refuse" — saw two, refused, and let its caller build a THIRD
    initiative for one plan element.

    Ordering both tiers by ``created_at ASC, id ASC`` keeps the caller's choice
    of ``matches[0]`` deterministic.
    """
    def _matches(require_plan_year: bool) -> List[sqlite3.Row]:
        plan_year = "AND ap.year = ?" if require_plan_year else ""
        params: List[Any] = [int(year), segment_id, key_field]
        if require_plan_year:
            params.append(int(year))
        return conn.execute(
            f"""
            SELECT ai.*
            FROM annual_initiatives ai
            JOIN annual_plans ap ON ap.id = ai.annual_plan_id
            WHERE ai.year = ?
              AND ai.segment_description_id = ?
              AND LOWER(ai.title) = LOWER(?)
              AND ai.annual_plan_element_id IS NULL
              {plan_year}
            ORDER BY ai.created_at ASC, ai.id ASC
            """,
            params,
        ).fetchall()

    return _matches(True) or _matches(False)


def backfill_initiative_ape_links(conn: sqlite3.Connection) -> Dict[str, Any]:
    """RN-M1.B.1 — link each initiative to its APE by the title match, once.

    Spec:  docs/spec_2026-08-19_rename_safe_links.md#rn-m1b1
    Tests: tests/test_rename_safe_links.py::test_rn_m1b1_initiative_ape_link_backfilled_from_title
           tests/test_rename_safe_links.py::test_rn_m1b2_ambiguous_backfill_is_reported
           tests/test_rename_safe_links.py::test_rn_m1b1_backfill_survives_an_annual_plan_year_drift
           tests/test_rename_safe_links.py::test_rn_m1b1_backfill_prefers_the_candidate_whose_plan_year_agrees

    This is the **only** time the title match is used to establish the link. It
    reproduces exactly what ``_heal_annual_initiative_link`` does — same year,
    same segment, ``LOWER(title) = LOWER(key_field)`` — so a database that
    works before the migration links the same way after it. Both call
    ``find_initiative_candidates_by_title``, so the candidate set cannot drift
    between them; what they do with it still differs, and deliberately — the
    heal refuses on more than one, this links the oldest and reports the rest.

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

    for ape in apes:
        segment_id = ape["segment_description_id"]
        if not segment_id:
            # No resolvable segment: the title match alone is not specific
            # enough, since two segments can hold the same key field.
            continue
        matches = find_initiative_candidates_by_title(
            conn, ape["year"], segment_id, ape["key_field"]
        )
        if not matches:
            continue

        winner = matches[0]["id"]
        conn.execute(
            "UPDATE annual_initiatives SET annual_plan_element_id = ? WHERE id = ?",
            (ape["id"], winner),
        )
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
# RN-M5 — report what is already broken
# --------------------------------------------------------------------------

def report_existing_breakage(conn: sqlite3.Connection) -> Dict[str, Any]:
    """What a user who has already renamed has right now (RN-M5.A).

    Spec:  docs/spec_2026-08-19_rename_safe_links.md#rn-m5a
    Tests: tests/test_rename_safe_links.py::test_rn_m5a_existing_breakage_is_reported
           tests/test_rename_safe_links.py::test_rn_m5b_ambiguous_data_is_left_alone

    Counts AND ids, so a human can go and look. Three things:

    * APEs with no resolvable segment — the re-filing cascade is dead for these
      until someone says which segment they belong to.
    * Annual Initiatives with no APE — orphaned by a rename before this change.
    * Duplicate initiatives per (APE, year) — RN-F4's duplicate, which
      accumulates silently because nothing dedupes above the weekly level
      (RN-F6).

    **Nothing here repairs anything** (RN-M5.B, RN-D2). The backfill already
    linked everything it could resolve unambiguously; what is left needs a
    decision no assertion can make — which of two duplicate initiatives holds
    work worth keeping.
    """
    result: Dict[str, Any] = {
        "apes_without_segment": [],
        "initiatives_without_ape": [],
        "duplicate_initiatives": [],
    }
    if not _table_exists(conn, "annual_plan_elements"):
        return result

    if "segment_description_id" in _columns(conn, "annual_plan_elements"):
        result["apes_without_segment"] = [
            {"id": r["id"], "segment_name": r["segment_name"], "year": r["year"]}
            for r in conn.execute(
                "SELECT id, segment_name, year FROM annual_plan_elements "
                "WHERE segment_description_id IS NULL"
            ).fetchall()
        ]

    if (_table_exists(conn, "annual_initiatives")
            and "annual_plan_element_id" in _columns(conn, "annual_initiatives")):
        # Only initiatives whose title still LOOKS derived — the composite
        # `Segment|Subsegment|Category`. An Annual Initiative can be created by
        # hand from the editor with no APE, by design, and reporting every one
        # of those as "orphaned by a rename" made _log_report emit a WARNING
        # per launch forever. A report that cries wolf on normal data trains
        # the reader to ignore it, and this is the log the spec's §10
        # human-review step depends on.
        # EVERY initiative with no APE. RN-INV5 says reported, never silently
        # skipped, and two attempts to filter this list were both wrong:
        #
        #   `title LIKE '%|%|%'` dropped an initiative that WAS derived and was
        #   then retitled by the user — contradicting the hand-edited-title fix
        #   in the same change, and discriminating breakage by a display string,
        #   which RN-INV3 forbids.
        #
        #   A lineage EXISTS() check could not tell a hand-created initiative
        #   from an orphaned one either: both share their segment and year with
        #   a plan element.
        #
        # The noise problem was never the report — it was the LOG. An
        # initiative with no APE is a legitimate, hand-created row as often as
        # it is breakage, so _log_report states it at INFO and reserves WARNING
        # for what genuinely needs a human.
        result["initiatives_without_ape"] = [
            {"id": r["id"], "title": r["title"], "year": r["year"]}
            for r in conn.execute(
                "SELECT id, title, year FROM annual_initiatives "
                "WHERE annual_plan_element_id IS NULL"
            ).fetchall()
        ]
        result["duplicate_initiatives"] = [
            {
                "annual_plan_element_id": r["annual_plan_element_id"],
                "year": r["year"],
                "count": r["n"],
                "ids": r["ids"].split(","),
            }
            for r in conn.execute(
                """
                SELECT annual_plan_element_id, year, COUNT(*) AS n,
                       GROUP_CONCAT(id) AS ids
                FROM annual_initiatives
                WHERE annual_plan_element_id IS NOT NULL
                GROUP BY annual_plan_element_id, year
                HAVING COUNT(*) > 1
                """
            ).fetchall()
        ]

    result["counts"] = {
        key: len(value) for key, value in result.items() if isinstance(value, list)
    }
    return result


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

    # RN-M5.A — after the backfill, so it reports what is STILL broken rather
    # than what the migration was about to fix.
    report["existing_breakage"] = report_existing_breakage(conn)

    _log_report(report)
    return report


def _log_report(report: Dict[str, Any]) -> None:
    """Write what could not be resolved to the audit log (RN-M5.A).

    Only unresolved rows are logged. A migration that links everything cleanly
    says nothing, so a line in this log always means something needs a human.
    """
    breakage = report.get("existing_breakage") or {}
    # An initiative with no plan element is as often a hand-created row as it
    # is breakage, so it is stated, not warned about. A WARNING here fired at
    # every launch forever and trained the reader to ignore the log — which is
    # the log the spec's §10 human-review step depends on.
    informational = {"initiatives_without_ape"}
    for key, rows in breakage.items():
        if key == "counts" or not rows:
            continue
        if key in informational:
            logger.info("link-integrity: %d %s (may be intentional)", len(rows), key)
            continue
        logger.warning(
            "link-integrity: %d %s need a human: %s", len(rows), key, rows
        )

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
