"""Renaming must never break a link.

Purpose: a name is a label, never the thing that holds two rows together.
Spec:    docs/spec_2026-08-19_rename_safe_links.md
Plan:    docs/implementation_plan_2026-08-19_rename_safe_links.md
Tests:   this file

RN-M2.D is the whole spec as one test and is written **first**, red. It fails
today at three of six rename levels. That is the acceptance criterion for the
change, not a bug in the test — do not weaken it to get an early green.

The failure it encodes, measured (spec §2): renaming a segment makes an
ordinary date change on a filed Action Item **raise**, and the item silently
does not move, because the re-filing cascade resolves the segment by name.
"""

from __future__ import annotations

import ast
import collections
import logging
import re
from datetime import date
from pathlib import Path

import pytest

from src.getmoredone.link_integrity import (
    SEGMENT_ID_TABLES,
    report_existing_breakage,
    run_link_integrity_migrations,
)
from src.getmoredone.models import ProjectBoard
from tests.weekly_tactic_fixtures import make_daily_item, make_vps, make_week_item


# --------------------------------------------------------------------------
# Chain construction
# --------------------------------------------------------------------------

def _build_full_chain(vps, year: int = 2026):
    """Segment → sub-segment → category → vision element → AVE/APE →
    annual initiative → quarter → month → Weekly Tactic → Action Item.

    Built through the real creators, not raw INSERTs, so the rows are the ones
    the app makes. Returns a dict of ids — every link is snapshotted **by id**,
    because snapshotting by name is the mistake under test.
    """
    segment_name = vps.get_all_segments(active_only=False)[0]["name"]
    segment_row = next(
        s for s in vps.get_all_segments(active_only=False)
        if s["name"] == segment_name
    )

    subsegment = "Living Systems"
    key_field = "Blog"
    vps.create_vision_subsegment(segment_name, subsegment)
    vision_element_id = vps.create_or_get_vision_element(
        segment_name, subsegment, key_field
    )
    created = vps.create_annual_records_from_vision_element(year, vision_element_id)
    ape_id = created["annual_plan_element_id"]

    # Drive the real assignment path so the annual/quarter/month initiatives
    # exist exactly as the app creates them.
    vps.assign_ape_to_month(ape_id, quarter=2, month=5)

    ape = vps._get_annual_plan_element_row(ape_id)
    initiative = vps._find_annual_initiative_for_ape(ape)

    vision_segment = next(
        row for row in vps.get_vision_segments()
        if row["name"].lower() == segment_name.lower()
    )
    subsegment_row = next(
        row for row in vps.get_vision_subsegments(segment_name)
        if row["name"].lower() == subsegment.lower()
    )
    category_row = next(
        row for row in vps.get_vision_categories(segment_name, subsegment)
        if row["name"].lower() == key_field.lower()
    )

    # RN-F5's two already-safe links, so the matrix covers all six levels and
    # a future refactor to name-matching fails here rather than in real data.
    tactic = make_week_item(vps, ape_id, title="Weekly Tactic")
    # An ordinary Action Item under the tactic. NOT the tactic itself: a Weekly
    # Tactic cannot be filed under a Project — its APE is what its title
    # derives from — and db_manager raises on the attempt.
    item = make_daily_item(vps, title="Task", weekly_tactic_id=tactic.id)
    board = ProjectBoard(title="Original Project", annual_plan_element_id=ape_id)
    project_board_id = vps.db_manager.create_project_board(board)
    vps.db_manager.link_item_to_project_exclusive(project_board_id, item.id)

    return {
        "year": year,
        "segment_description_id": segment_row["id"],
        "project_board_id": project_board_id,
        "weekly_tactic_id": tactic.id,
        "action_item_id": item.id,
        "segment_name": segment_name,
        "vision_segment_id": vision_segment["id"],
        "subsegment_id": subsegment_row["id"],
        "category_id": category_row["id"],
        "vision_element_id": vision_element_id,
        "ape_id": ape_id,
        "annual_initiative_id": initiative["id"] if initiative else None,
        "key_field": key_field,
    }


# --------------------------------------------------------------------------
# The links, each resolved the way the app resolves it
# --------------------------------------------------------------------------


RENAMED_TO = {
    "segment": "Health Renamed",
    "subsegment": "Living Systems Renamed",
    "category": "Blog Renamed",
    "vision_element_key_field": "Blog Renamed Key",
    "project": "Renamed Project",
    "weekly_tactic": "Weekly Tactic Renamed",
}


def _assert_the_rename_happened(vps, chain, level):
    """Post-condition: the new name is actually stored.

    Without this the matrix passes trivially when the rename did nothing —
    before == after because neither moved. Verified by mutation: making
    rename_vision_segment / _subsegment / _category and update_vision_element
    into no-ops left ALL SIX parametrisations green.

    "The links survived" is only meaningful if something was renamed.
    """
    expected = RENAMED_TO[level]
    queries = {
        "segment": ("SELECT name AS v FROM vision_segments WHERE id = ?",
                    chain["vision_segment_id"]),
        "subsegment": ("SELECT name AS v FROM vision_subsegments WHERE id = ?",
                       chain["subsegment_id"]),
        "category": ("SELECT name AS v FROM vision_categories WHERE id = ?",
                     chain["category_id"]),
        "vision_element_key_field": (
            "SELECT key_field AS v FROM annual_plan_elements WHERE id = ?",
            chain["ape_id"]),
        "project": ("SELECT title AS v FROM project_boards WHERE id = ?",
                    chain["project_board_id"]),
        "weekly_tactic": ("SELECT title AS v FROM action_items WHERE id = ?",
                          chain["weekly_tactic_id"]),
    }
    sql, key = queries[level]
    value = vps.db.conn.execute(sql, (key,)).fetchone()["v"]
    assert expected in (value or ""), (
        f"the {level} rename did not happen: stored value is {value!r}, "
        f"expected it to contain {expected!r}. The link comparison below would "
        "pass trivially."
    )


def _resolve_links(vps, chain):
    """Every link in the chain, resolved now, as ids.

    Compared against the snapshot taken before the rename. A link that returns
    None, or a different id, is broken.
    """
    ape = vps._get_annual_plan_element_row(chain["ape_id"])
    initiative = vps._find_annual_initiative_for_ape(ape) if ape else None

    # The vision_segments <-> segment_descriptions link (RN-F2). Resolved by
    # id, which is RN-M2.C: the three joins in vps_manager_taxonomy.py used
    # LOWER(sd.name) = LOWER(vs.name), and rename_vision_segment updates only
    # one of the two tables, so the join found nothing after a rename.
    join_row = vps.db.conn.execute(
        """
        SELECT sd.id AS segment_description_id
        FROM vision_segments vs
        JOIN segment_descriptions sd ON sd.id = vs.segment_description_id
        WHERE vs.id = ?
        """,
        (chain["vision_segment_id"],),
    ).fetchone()

    return {
        # APE -> segment, by id (RN-M2.B). This is what the re-filing cascade
        # resolves; resolving it by name is what made an ordinary date change
        # raise ValueError("Segment '<new name>' not found.") after a rename.
        # resolve_segment_id_by_name survives for genuine NAME lookups (user
        # input, import) and is no longer a link path.
        # Through _segment_id_for_ape, the function the cascade calls — NOT by
        # reading the column. Reading the column directly meant a mutation that
        # made _segment_id_for_ape ignore the id and always resolve by name
        # left all 27 tests green, because RN-M3.A now renames
        # segment_descriptions too, so the name lookup succeeds again. Nothing
        # proved the id column was load-bearing for this link.
        "ape_to_segment": vps._segment_id_for_ape(ape) if ape else None,
        # APE -> annual initiative (RN-F4): a title string match today.
        "ape_to_annual_initiative": initiative["id"] if initiative else None,
        # vision_segments -> segment_descriptions (RN-F2).
        "vision_segment_to_description": (
            join_row["segment_description_id"] if join_row else None
        ),
        # RN-F5: already id-based. Asserted so a future refactor to
        # name-matching fails in this test rather than in a user's data.
        "weekly_tactic_to_ape": _tactic_ape(vps, chain["weekly_tactic_id"]),
        "item_to_weekly_tactic": _item_tactic(vps, chain["action_item_id"]),
        "item_to_project": _item_board(vps, chain["action_item_id"]),
        "project_to_ape": _board_ape(vps, chain["project_board_id"]),
    }


def _tactic_ape(vps, tactic_id):
    row = vps.db.conn.execute(
        "SELECT annual_plan_element_id FROM action_items WHERE id = ?",
        (tactic_id,),
    ).fetchone()
    return row["annual_plan_element_id"] if row else None


def _item_tactic(vps, item_id):
    row = vps.db.conn.execute(
        "SELECT weekly_tactic_id FROM action_items WHERE id = ?", (item_id,)
    ).fetchone()
    return row["weekly_tactic_id"] if row else None


def _board_ape(vps, board_id):
    row = vps.db.conn.execute(
        "SELECT annual_plan_element_id FROM project_boards WHERE id = ?",
        (board_id,),
    ).fetchone()
    return row["annual_plan_element_id"] if row else None


def _item_board(vps, item_id):
    row = vps.db.conn.execute(
        "SELECT project_board_id FROM project_board_items WHERE item_id = ?",
        (item_id,),
    ).fetchone()
    return row["project_board_id"] if row else None


RENAME_LEVELS = [
    "segment",
    "subsegment",
    "category",
    "vision_element_key_field",
    "project",
    "weekly_tactic",
]


def _rename(vps, chain, level: str) -> None:
    """Rename one level through the app's own rename path."""
    if level == "segment":
        vps.rename_vision_segment(chain["vision_segment_id"], "Health Renamed")
    elif level == "subsegment":
        vps.rename_vision_subsegment(chain["subsegment_id"], "Living Systems Renamed")
    elif level == "category":
        vps.rename_vision_category(chain["category_id"], "Blog Renamed")
    elif level == "vision_element_key_field":
        vps.update_vision_element(
            chain["vision_element_id"],
            segment_name=chain["segment_name"],
            subsegment_name="Living Systems",
            category_name="Blog Renamed Key",
        )
    elif level == "project":
        # RN-F5: id-based already (project_board_items). Renaming must be a
        # no-op for every link — this level is a regression test, not a fix.
        board = vps.db_manager.get_project_board(chain["project_board_id"])
        board.title = "Renamed Project"
        vps.db_manager.update_project_board(board)
    elif level == "weekly_tactic":
        # RN-F5: id-based already (action_items.weekly_tactic_id /
        # annual_plan_element_id). Same regression-test role.
        tactic = vps.db_manager.get_action_item(chain["weekly_tactic_id"])
        tactic.title = "Weekly Tactic Renamed"
        vps.db_manager.update_action_item(tactic)
    else:  # pragma: no cover - guarded by the parametrize list
        raise AssertionError(f"unknown rename level {level!r}")


# --------------------------------------------------------------------------
# RN-M2.D — the breakage matrix
# --------------------------------------------------------------------------

@pytest.mark.parametrize("level", RENAME_LEVELS)
def test_rn_m2d_no_rename_breaks_any_link(tmp_path, level):
    """RN-M2.D. Rename at each of six levels; every link must still resolve.

    Spec:  docs/spec_2026-08-19_rename_safe_links.md#rn-m2d
    Plan:  docs/implementation_plan_2026-08-19_rename_safe_links.md (step 1)

    Each level gets its own database, so one level's breakage cannot mask or
    cause another's. Snapshots are taken by id before the rename and compared
    after: a link that resolves to None, or to a *different* id, is broken.

    Expected to fail at `segment`, `subsegment` and `vision_element_key_field`
    until steps 2-4 land. That is RN-F1.
    """
    vps = make_vps(tmp_path, name=f"rename_{level}.db")
    try:
        chain = _build_full_chain(vps)
        assert chain["annual_initiative_id"], (
            "the fixture did not produce an annual initiative — the chain is "
            "not built, so this test would pass vacuously"
        )

        before = _resolve_links(vps, chain)
        assert all(v is not None for v in before.values()), (
            f"a link was already broken before any rename: {before}"
        )

        _rename(vps, chain, level)
        _assert_the_rename_happened(vps, chain, level)

        after = _resolve_links(vps, chain)

        broken = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
        assert not broken, (
            f"renaming the {level} broke {len(broken)} link(s). "
            f"before -> after: {broken}"
        )
    finally:
        vps.close()


# --------------------------------------------------------------------------
# RN-M1 — id columns and their migration
# --------------------------------------------------------------------------

def _as_legacy_database(vps):
    """Strip the id columns' values, then re-run the migration.

    RN-M1 is about backfilling rows that already exist — a user upgrading a
    database written before this change. The fixture builds its chain *after*
    ``initialize_schema`` has already migrated, so without this the rows carry
    ids the create paths wrote (step 3) and the backfill has nothing to do:
    every RN-M1 assertion would pass without the backfill existing at all.

    Clearing the ids and re-running is the only way to exercise the thing these
    criteria name.
    """
    for table in SEGMENT_ID_TABLES:
        vps.db.conn.execute(f"UPDATE {table} SET segment_description_id = NULL")
    vps.db.conn.execute("UPDATE annual_initiatives SET annual_plan_element_id = NULL")
    vps.db.conn.commit()
    return run_link_integrity_migrations(vps.db.conn)


def _segment_id_of(vps, table, row_id):
    row = vps.db.conn.execute(
        f"SELECT segment_description_id FROM {table} WHERE id = ?", (row_id,)
    ).fetchone()
    return row["segment_description_id"] if row else None


def test_rn_m1a1_ape_segment_id_added_and_backfilled(tmp_path):
    """RN-M1.A.1 — APE and AVE gain segment_description_id, backfilled.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m1a1
    """
    vps = make_vps(tmp_path, name="m1a1.db")
    try:
        chain = _build_full_chain(vps)
        _as_legacy_database(vps)

        for table in ("annual_plan_elements", "annual_vision_elements"):
            cols = [r[1] for r in vps.db.conn.execute(f"PRAGMA table_info({table})")]
            assert "segment_description_id" in cols, f"{table} has no id column"

        assert _segment_id_of(vps, "annual_plan_elements", chain["ape_id"]) == \
            chain["segment_description_id"], "the APE's segment id was not backfilled"

        ave = vps.db.conn.execute(
            "SELECT id FROM annual_vision_elements LIMIT 1"
        ).fetchone()
        assert ave is not None, "no AVE was created — the fixture is wrong"
        assert _segment_id_of(vps, "annual_vision_elements", ave["id"]) == \
            chain["segment_description_id"]
    finally:
        vps.close()


def test_rn_m1a2_unmatched_segment_is_reported_not_guessed(tmp_path):
    """RN-M1.A.2 — a name matching nothing stays NULL and is counted.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m1a2

    The whole of RN-INV5. A guess here attaches a user's plan element to an
    arbitrary segment, silently and permanently.
    """
    vps = make_vps(tmp_path, name="m1a2.db")
    try:
        chain = _build_full_chain(vps)
        # A row whose segment name matches nothing, with its id cleared so the
        # backfill re-considers it — exactly the state a rename leaves behind.
        vps.db.conn.execute(
            "UPDATE annual_plan_elements "
            "SET segment_name = 'No Such Segment', segment_description_id = NULL "
            "WHERE id = ?",
            (chain["ape_id"],),
        )
        vps.db.conn.commit()

        report = run_link_integrity_migrations(vps.db.conn)
        result = report["backfill_annual_plan_elements"]

        assert _segment_id_of(vps, "annual_plan_elements", chain["ape_id"]) is None, (
            "the backfill GUESSED a segment for a name that matches nothing"
        )
        assert any(u["id"] == chain["ape_id"] for u in result["unmatched"]), (
            f"the unresolvable row was not reported: {result}"
        )
    finally:
        vps.close()


def test_rn_m1b1_initiative_ape_link_backfilled_from_title(tmp_path):
    """RN-M1.B.1 — the title match establishes the id link, once.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m1b1
    """
    vps = make_vps(tmp_path, name="m1b1.db")
    try:
        chain = _build_full_chain(vps)
        _as_legacy_database(vps)
        row = vps.db.conn.execute(
            "SELECT annual_plan_element_id FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()
        assert row["annual_plan_element_id"] == chain["ape_id"], (
            "the initiative was not linked to its APE by the backfill"
        )
    finally:
        vps.close()


def test_rn_m1b2_ambiguous_backfill_is_reported(tmp_path):
    """RN-M1.B.2 — two initiatives for one APE: oldest linked, other NULL, both reported.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m1b2

    This is the duplicate RN-F4 already created in real databases. Dropping the
    second is a tie-break decision this migration does not own (spec §9), so it
    must survive, unlinked and named in the report.
    """
    vps = make_vps(tmp_path, name="m1b2.db")
    try:
        chain = _build_full_chain(vps)
        original = vps.db.conn.execute(
            "SELECT * FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()

        # A second initiative identical but for its id and a later created_at.
        vps.db.conn.execute(
            "INSERT INTO annual_initiatives "
            "(id, annual_plan_id, segment_description_id, year, title, "
            " created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("ai-duplicate", original["annual_plan_id"],
             original["segment_description_id"], original["year"],
             original["title"], "2099-01-01T00:00:00", "2099-01-01T00:00:00"),
        )
        vps.db.conn.execute("UPDATE annual_initiatives SET annual_plan_element_id = NULL")
        vps.db.conn.commit()
        # Segment ids stay: the initiative backfill needs the APE's segment to
        # narrow the title match, and clearing them would make this pass for
        # the wrong reason (nothing matched at all).
        report = run_link_integrity_migrations(vps.db.conn)
        result = report["backfill_initiative_ape"]

        linked = vps.db.conn.execute(
            "SELECT id FROM annual_initiatives WHERE annual_plan_element_id = ?",
            (chain["ape_id"],),
        ).fetchall()
        assert len(linked) == 1, f"expected exactly one link, got {[r['id'] for r in linked]}"
        assert linked[0]["id"] == chain["annual_initiative_id"], (
            "the NEWER initiative was linked; the oldest by created_at must win"
        )

        survivor = vps.db.conn.execute(
            "SELECT annual_plan_element_id FROM annual_initiatives WHERE id = 'ai-duplicate'"
        ).fetchone()
        assert survivor is not None, "the duplicate was deleted; it must survive"
        assert survivor["annual_plan_element_id"] is None

        assert result["ambiguous"], f"the ambiguity was not reported: {result}"
        entry = result["ambiguous"][0]
        assert entry["linked"] == chain["annual_initiative_id"]
        assert "ai-duplicate" in entry["left_null"]
    finally:
        vps.close()


def test_rn_m1c1_vision_segment_link_backfilled(tmp_path):
    """RN-M1.C.1 — vision_segments gains and backfills its segment id (RN-F2).

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m1c1
    """
    vps = make_vps(tmp_path, name="m1c1.db")
    try:
        chain = _build_full_chain(vps)
        _as_legacy_database(vps)
        assert _segment_id_of(vps, "vision_segments", chain["vision_segment_id"]) == \
            chain["segment_description_id"], (
                "vision_segments was not linked to segment_descriptions"
            )
    finally:
        vps.close()


def test_rn_m1d_migration_on_populated_db_run_two(tmp_path):
    """RN-M1.D — dirty state (P8): run #2 changes nothing and reports zeros.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m1d

    The migration runs on every app start. A second run that re-linked, or
    re-reported, would double the audit log and mask a real finding among its
    own noise.
    """
    vps = make_vps(tmp_path, name="m1d.db")
    try:
        _build_full_chain(vps)
        _as_legacy_database(vps)   # run #1: the real backfill

        def _snapshot():
            return {
                table: sorted(
                    (r["id"], r["segment_description_id"])
                    for r in vps.db.conn.execute(
                        f"SELECT id, segment_description_id FROM {table}"
                    )
                )
                for table in ("annual_plan_elements", "annual_vision_elements",
                              "vision_segments")
            }

        before = _snapshot()
        second = run_link_integrity_migrations(vps.db.conn)
        after = _snapshot()

        assert after == before, "the second run changed rows"
        assert second["columns_added"] == {t: False for t in SEGMENT_ID_TABLES}, (
            f"the second run re-added columns: {second['columns_added']}"
        )
        assert second["initiative_column_added"] is False
        for table in SEGMENT_ID_TABLES:
            assert second[f"backfill_{table}"]["linked"] == 0, (
                f"the second run re-linked rows in {table}"
            )
        assert second["backfill_initiative_ape"]["linked"] == 0
    finally:
        vps.close()


def test_rn_migration_runs_once_per_launch(tmp_path):
    """Two managers share one Database; the migration must run once.

    Plan: docs/implementation_plan_2026-08-19_rename_safe_links.md §4

    The weekly-tactic migration ran twice per launch for exactly this reason,
    doubling its repair history and overwriting the first (real) report with a
    second, no-op one. Same trap, same guard.
    """
    vps = make_vps(tmp_path, name="once.db")
    try:
        first = vps.db.link_integrity_report
        assert first is not None, "the migration never ran"
        vps.db.initialize_schema()
        assert vps.db.link_integrity_report is first, (
            "initialize_schema ran the link-integrity migration a second time, "
            "replacing the real report with a no-op one"
        )
    finally:
        vps.close()


# --------------------------------------------------------------------------
# RN-M2 — resolve by id, never by name
# --------------------------------------------------------------------------

def test_rn_m2a_initiative_found_by_id_after_rename(tmp_path):
    """RN-M2.A — the APE's initiative survives a key-field rename.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m2a

    Before: `LOWER(ai.title) = LOWER(ape.key_field)`. A rename made the lookup
    return None, so the next assignment built a second Annual Initiative and a
    second Quarter Initiative for the same APE and quarter (RN-F4).
    """
    vps = make_vps(tmp_path, name="m2a.db")
    try:
        chain = _build_full_chain(vps)
        vps.update_vision_element(
            chain["vision_element_id"],
            segment_name=chain["segment_name"],
            subsegment_name="Living Systems",
            category_name="Renamed Key Field",
        )
        ape = vps._get_annual_plan_element_row(chain["ape_id"])
        found = vps._find_annual_initiative_for_ape(ape)

        assert found is not None, "the initiative was lost by the rename"
        assert found["id"] == chain["annual_initiative_id"], (
            "a DIFFERENT initiative was resolved after the rename"
        )
    finally:
        vps.close()


def test_rn_m2a1_legacy_row_heals_on_first_lookup(tmp_path):
    """RN-M2.A.1 — a NULL id heals once, by the old title match, and stays healed.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m2a

    The heal must WRITE the id, or it fires on every lookup and the rename bug
    is still live for that row — it would just be re-resolved by name each time.
    """
    vps = make_vps(tmp_path, name="m2a1.db")
    try:
        chain = _build_full_chain(vps)
        vps.db.conn.execute(
            "UPDATE annual_initiatives SET annual_plan_element_id = NULL WHERE id = ?",
            (chain["annual_initiative_id"],),
        )
        vps.db.conn.commit()

        ape = vps._get_annual_plan_element_row(chain["ape_id"])
        healed = vps._find_annual_initiative_for_ape(ape)
        assert healed is not None and healed["id"] == chain["annual_initiative_id"]

        stored = vps.db.conn.execute(
            "SELECT annual_plan_element_id FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()
        assert stored["annual_plan_element_id"] == chain["ape_id"], (
            "the heal resolved the row but did not write the id, so it will "
            "resolve by name again next time"
        )
    finally:
        vps.close()


def test_rn_m2a1_ambiguous_legacy_row_is_not_healed(tmp_path):
    """The heal must refuse when two initiatives match (RN-INV5).

    Choosing between them here would silently pick one of a user's two plans.
    """
    vps = make_vps(tmp_path, name="m2a1b.db")
    try:
        chain = _build_full_chain(vps)
        original = vps.db.conn.execute(
            "SELECT * FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()
        vps.db.conn.execute(
            "INSERT INTO annual_initiatives "
            "(id, annual_plan_id, segment_description_id, year, title, "
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("ai-dup-heal", original["annual_plan_id"],
             original["segment_description_id"], original["year"],
             original["title"], "2099-01-01T00:00:00", "2099-01-01T00:00:00"),
        )
        vps.db.conn.execute("UPDATE annual_initiatives SET annual_plan_element_id = NULL")
        vps.db.conn.commit()

        ape = vps._get_annual_plan_element_row(chain["ape_id"])
        assert vps._find_annual_initiative_for_ape(ape) is None, (
            "the heal picked one of two matching initiatives instead of "
            "refusing — that silently attaches the APE to an arbitrary plan"
        )
        still_null = vps.db.conn.execute(
            "SELECT COUNT(*) AS n FROM annual_initiatives "
            "WHERE annual_plan_element_id IS NOT NULL"
        ).fetchone()
        assert still_null["n"] == 0, "the heal wrote a link it should have refused"
    finally:
        vps.close()


def test_rn_m2b_cascade_survives_a_segment_rename(tmp_path):
    """RN-M2.B — the §2 failure, as a test.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m2b

    Renaming a segment made an ordinary date change on a filed Action Item
    RAISE `ValueError: Segment 'Health Renamed' not found.`, and the item
    silently did not move. This drives the real re-filing path.
    """
    vps = make_vps(tmp_path, name="m2b.db")
    try:
        chain = _build_full_chain(vps)
        vps.rename_vision_segment(chain["vision_segment_id"], "Health Renamed")

        ape = vps._get_annual_plan_element_row(chain["ape_id"])
        assert vps._segment_id_for_ape(ape) == chain["segment_description_id"], (
            "the APE lost its segment when the segment was renamed"
        )

        # The cascade itself: assigning the APE to a month must not raise.
        assert vps.assign_ape_to_month(chain["ape_id"], quarter=3, month=8) is True, (
            "the re-filing cascade failed after a segment rename"
        )
    finally:
        vps.close()


def test_rn_m2c_segment_join_survives_a_rename(tmp_path):
    """RN-M2.C — the vision_segments ↔ segment_descriptions join (RN-F2).

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m2c

    Driven through the real admin reader, not a hand-written query: the three
    joins live in vps_manager_taxonomy and this is what reads them.
    """
    vps = make_vps(tmp_path, name="m2c.db")
    try:
        chain = _build_full_chain(vps)
        vps.rename_vision_segment(chain["vision_segment_id"], "Health Renamed")

        rows = vps.get_vision_segments_admin()
        row = next(r for r in rows if r["id"] == chain["vision_segment_id"])
        assert row["name"] == "Health Renamed"
        assert row.get("color_hex"), (
            "the renamed segment lost its colour — the join to "
            "segment_descriptions resolved by name and found nothing"
        )
    finally:
        vps.close()


def test_rn_no_duplicate_initiative_after_rename(tmp_path):
    """RN-F4's second half: a rename must not make the next assignment duplicate.

    Plan: docs/implementation_plan_2026-08-19_rename_safe_links.md §4

    The spec covers the broken link. This covers the duplicate it caused —
    reproduced before the fix as `annual_initiatives: 2, quarter_initiatives: 2`.
    """
    vps = make_vps(tmp_path, name="dupe.db")
    try:
        chain = _build_full_chain(vps)

        def _counts():
            return (
                vps.db.conn.execute(
                    "SELECT COUNT(*) AS n FROM annual_initiatives"
                ).fetchone()["n"],
                vps.db.conn.execute(
                    "SELECT COUNT(*) AS n FROM quarter_initiatives"
                ).fetchone()["n"],
            )

        before = _counts()
        vps.update_vision_element(
            chain["vision_element_id"],
            segment_name=chain["segment_name"],
            subsegment_name="Living Systems",
            category_name="Renamed Again",
        )
        vps.assign_ape_to_month(chain["ape_id"], quarter=2, month=6)

        assert _counts() == before, (
            f"the rename made the next assignment duplicate: {before} -> {_counts()}"
        )
    finally:
        vps.close()


def test_rn_project_and_tactic_links_are_id_based(tmp_path):
    """RN-F5 says these are already safe. Asserted, so a future refactor to
    name-matching fails here rather than in a user's data.

    Plan: docs/implementation_plan_2026-08-19_rename_safe_links.md §4
    """
    vps = make_vps(tmp_path, name="f5.db")
    try:
        chain = _build_full_chain(vps)
        item_columns = [
            r[1] for r in vps.db.conn.execute("PRAGMA table_info(action_items)")
        ]
        assert "weekly_tactic_id" in item_columns
        assert "annual_plan_element_id" in item_columns

        board_item_columns = [
            r[1] for r in vps.db.conn.execute("PRAGMA table_info(project_board_items)")
        ]
        assert "project_board_id" in board_item_columns
        assert "item_id" in board_item_columns

        assert _item_board(vps, chain["action_item_id"]) == chain["project_board_id"]
        assert _tactic_ape(vps, chain["weekly_tactic_id"]) == chain["ape_id"]
    finally:
        vps.close()


# --------------------------------------------------------------------------
# RN-M3 — names stay correct for display
# --------------------------------------------------------------------------

def test_rn_m3a_rename_refreshes_every_display_copy(tmp_path):
    """RN-M3.A / RN-INV4 — every stored copy of the name shows the new value.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m3a

    Including the Annual Initiative's title (RN-D7, settled with the user: the
    title is derived, so a rename refreshes it). Leaving it stale would put two
    different names on one thing.

    And including segment_descriptions, which rename_vision_segment did not
    touch — that is the whole of RN-F2, and spec §2 shows the two tables
    holding different values after a rename.
    """
    vps = make_vps(tmp_path, name="m3a.db")
    try:
        chain = _build_full_chain(vps)
        vps.rename_vision_segment(chain["vision_segment_id"], "Health Renamed")

        stale = {}

        vs = vps.db.conn.execute(
            "SELECT name FROM vision_segments WHERE id = ?",
            (chain["vision_segment_id"],),
        ).fetchone()
        if vs["name"] != "Health Renamed":
            stale["vision_segments.name"] = vs["name"]

        sd = vps.db.conn.execute(
            "SELECT name FROM segment_descriptions WHERE id = ?",
            (chain["segment_description_id"],),
        ).fetchone()
        if sd["name"] != "Health Renamed":
            stale["segment_descriptions.name"] = sd["name"]

        for table in ("annual_plan_elements", "annual_vision_elements"):
            row = vps.db.conn.execute(
                f"SELECT segment_name, key_field FROM {table} "
                "WHERE vision_element_id = ?",
                (chain["vision_element_id"],),
            ).fetchone()
            if row["segment_name"] != "Health Renamed":
                stale[f"{table}.segment_name"] = row["segment_name"]
            if not row["key_field"].startswith("Health Renamed|"):
                stale[f"{table}.key_field"] = row["key_field"]

        initiative = vps.db.conn.execute(
            "SELECT title FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()
        if not initiative["title"].startswith("Health Renamed|"):
            stale["annual_initiatives.title"] = initiative["title"]

        assert not stale, (
            f"{len(stale)} stored copy/copies still show the old name: {stale}"
        )
    finally:
        vps.close()


def test_rn_m3b_tactic_title_follows_rename_without_relinking(tmp_path):
    """RN-M3.B — a tactic's derived title follows, its APE link does not move.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m3b

    Both halves matter. A title that does not follow shows the user two names
    for one thing; a link that moves is the bug this whole change removes.
    """
    vps = make_vps(tmp_path, name="m3b.db")
    try:
        chain = _build_full_chain(vps)
        ape_before = _tactic_ape(vps, chain["weekly_tactic_id"])

        vps.update_vision_element(
            chain["vision_element_id"],
            segment_name=chain["segment_name"],
            subsegment_name="Living Systems",
            category_name="Renamed For Title",
        )

        assert _tactic_ape(vps, chain["weekly_tactic_id"]) == ape_before, (
            "the rename moved the tactic to a different Annual Plan Element"
        )

        ape = vps._get_annual_plan_element_row(chain["ape_id"])
        assert "Renamed For Title" in ape["key_field"], (
            f"the APE's key field did not follow the rename: {ape['key_field']}"
        )
    finally:
        vps.close()


# --------------------------------------------------------------------------
# RN-M5 — repair what is already broken
# --------------------------------------------------------------------------

def test_rn_m5a_existing_breakage_is_reported(tmp_path):
    """RN-M5.A — counts AND ids, so a human can go and look.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m5a

    A user who renamed before this change has orphans now. Three kinds, and
    each must be nameable — a count alone says something is wrong without
    saying where.
    """
    vps = make_vps(tmp_path, name="m5a.db")
    try:
        chain = _build_full_chain(vps)
        original = vps.db.conn.execute(
            "SELECT * FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()

        # 1. an APE whose segment cannot be resolved
        vps.db.conn.execute(
            "UPDATE annual_plan_elements SET segment_description_id = NULL, "
            "segment_name = 'Vanished Segment' WHERE id = ?",
            (chain["ape_id"],),
        )
        # 2. an orphaned initiative, and 3. a duplicate on the same APE
        vps.db.conn.execute(
            "INSERT INTO annual_initiatives "
            "(id, annual_plan_id, segment_description_id, year, title, "
            " created_at, updated_at, annual_plan_element_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ai-orphan", original["annual_plan_id"],
             original["segment_description_id"], original["year"],
             # A composite title, so it looks derived — a hand-created
             # initiative with a plain title is NOT breakage (see the
             # LIKE filter in report_existing_breakage).
             "Health|Living Systems|Orphaned", "2099-01-01T00:00:00",
             "2099-01-01T00:00:00", None),
        )
        vps.db.conn.execute(
            "INSERT INTO annual_initiatives "
            "(id, annual_plan_id, segment_description_id, year, title, "
            " created_at, updated_at, annual_plan_element_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ai-dupe2", original["annual_plan_id"],
             original["segment_description_id"], original["year"],
             original["title"], "2099-01-01T00:00:00", "2099-01-01T00:00:00",
             chain["ape_id"]),
        )
        vps.db.conn.commit()

        breakage = report_existing_breakage(vps.db.conn)

        assert any(r["id"] == chain["ape_id"] for r in breakage["apes_without_segment"]), (
            f"the unresolvable APE was not named: {breakage['apes_without_segment']}"
        )
        assert any(r["id"] == "ai-orphan" for r in breakage["initiatives_without_ape"]), (
            f"the orphaned initiative was not named: {breakage['initiatives_without_ape']}"
        )
        dupes = breakage["duplicate_initiatives"]
        assert dupes, "the duplicate pair was not reported"
        entry = next(d for d in dupes if d["annual_plan_element_id"] == chain["ape_id"])
        assert entry["count"] == 2
        assert set(entry["ids"]) == {chain["annual_initiative_id"], "ai-dupe2"}

        assert breakage["counts"]["apes_without_segment"] >= 1
        assert breakage["counts"]["duplicate_initiatives"] >= 1
    finally:
        vps.close()


def test_rn_m5b_ambiguous_data_is_left_alone(tmp_path):
    """RN-M5.B — the report changes nothing (RN-INV5, RN-D2).

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m5b

    Whether one of two duplicate initiatives holds work worth keeping is a
    judgement no assertion can make, so nothing here may merge or delete.
    Asserted as a full before/after snapshot rather than by spot-checking the
    duplicate: a repair that touched some OTHER row would pass a narrower test.
    """
    vps = make_vps(tmp_path, name="m5b.db")
    try:
        chain = _build_full_chain(vps)
        original = vps.db.conn.execute(
            "SELECT * FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()
        vps.db.conn.execute(
            "INSERT INTO annual_initiatives "
            "(id, annual_plan_id, segment_description_id, year, title, "
            " created_at, updated_at, annual_plan_element_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ai-keepme", original["annual_plan_id"],
             original["segment_description_id"], original["year"],
             original["title"], "2099-01-01T00:00:00", "2099-01-01T00:00:00",
             chain["ape_id"]),
        )
        vps.db.conn.commit()

        def _snapshot():
            return {
                table: sorted(tuple(r) for r in vps.db.conn.execute(f"SELECT * FROM {table}"))
                for table in ("annual_initiatives", "annual_plan_elements",
                              "annual_vision_elements", "vision_segments")
            }

        before = _snapshot()
        report_existing_breakage(vps.db.conn)
        run_link_integrity_migrations(vps.db.conn)
        after = _snapshot()

        assert after == before, (
            "reporting or re-running the migration changed rows. Ambiguous "
            "data must be left exactly as it is."
        )
    finally:
        vps.close()


# --------------------------------------------------------------------------
# RN-M4 — the hole cannot reopen
# --------------------------------------------------------------------------

SRC = Path(__file__).resolve().parents[1] / "src" / "getmoredone"

# Patterns that mean "a link is being resolved through a name". Each is a
# regex over source with comments stripped, so the prose explaining why a
# pattern is forbidden cannot itself trip the scan — the mistake this repo has
# now made three times (LEARNINGS.md).
NAME_LINK_PATTERNS = {
    "segment_join_by_name":
        r"LOWER\(\s*sd\.name\s*\)\s*=\s*LOWER\(\s*vs\.name\s*\)",
    "initiative_by_title":
        r"LOWER\(\s*ai\.title\s*\)\s*=\s*LOWER",
    # Unqualified on purpose. Anchoring on `ape[` missed the VERBATIM line this
    # change deleted from _get_or_create_annual_plan_for_ape:
    #     segment_name = ape["segment_name"]
    #     segment_id = self.resolve_segment_id_by_name(segment_name)
    # — a local variable, not a subscript. Restoring it exactly left all 27
    # tests green, guard included, because RN-M4.A.1's offender sample used the
    # `ape[` spelling rather than the code actually removed. That is the P27
    # corollary: mutate with the verbatim original, never a reconstruction.
    "segment_by_name_any_caller":
        r"resolve_segment_id_by_name\(",
    # Not just sd/vs: any alias pair joining two entity tables on LOWER(name).
    "entity_join_by_name":
        r"LOWER\(\s*\w+\.name\s*\)\s*=\s*LOWER\(\s*\w+\.\w*name\s*\)",
    # An APE name column resolved against segment_descriptions in raw SQL —
    # the shape of db_manager._segment_from_annual_plan, which no pattern saw.
    "segment_descriptions_by_name":
        r"FROM\s+segment_descriptions\s+WHERE\s+LOWER\(\s*name\s*\)\s*=\s*LOWER",
}

# The exact name-based lookups that remain, per file and pattern. Every one is
# explained in NAME_LOOKUP_ALLOWLIST below.
#
# segment_join_by_name is absent: the three `LOWER(sd.name) = LOWER(vs.name)`
# joins RN-M2.C removed are gone from src/ entirely, and this dict being exact
# is what asserts that.
#
# The counts matter more than the file list. An earlier version allowlisted by
# FILE, which let a reintroduced name-join hide inside an allowlisted file
# (P29 — a permissive bound where an exact count belonged).
PERMITTED_NAME_LOOKUPS = {
    # The display colour lineage: two queries, three name joins each.
    ("db_manager_project_boards.py", "entity_join_by_name"): 6,
    # The migration's one-time title match (RN-M1.B.1).
    ("link_integrity.py", "initiative_by_title"): 1,
    # resolve_segment_id_exact, and the backfill's own candidate query.
    ("link_integrity.py", "segment_descriptions_by_name"): 2,
    # The one-time heal (RN-M2.A.1).
    ("vps_manager.py", "initiative_by_title"): 1,
    # resolve_segment_id_by_name's DEFINITION and body. RN-M2.B keeps it for
    # genuine name lookups — user input and import. Neither is a caller.
    # resolve_segment_id_by_name's DEFINITION and body, plus one non-persisting
    # fallback in _segment_id_for_ape. That fallback returns an answer to the
    # CALLER and writes nothing — refusing to answer made the cascade raise.
    ("vps_manager.py", "segment_by_name_any_caller"): 2,
    ("vps_manager.py", "segment_descriptions_by_name"): 1,
    # db_manager's own non-persisting fallback: the helper's definition and
    # its call site, plus the body's query.
    ("db_manager.py", "segment_by_name_any_caller"): 2,
    ("db_manager.py", "segment_descriptions_by_name"): 1,
    # The canonical-name lookup in the taxonomy.
    # The canonical-name lookup, plus delete_vision_segment_admin's ambiguity
    # count — which refuses rather than falling through to a raw DELETE.
    ("vps_manager_taxonomy.py", "segment_descriptions_by_name"): 2,
}

# Allowlisted, BY NAME, each with the reason inline (RN-M4.A).
NAME_LOOKUP_ALLOWLIST = {
    "vps_manager.py::_heal_annual_initiative_link":
        "RN-M2.A.1. The one-time heal for a row whose id is still NULL. It "
        "writes the id when it fires, so it never fires again for that row, "
        "and it refuses when two initiatives match rather than choosing.",
    "link_integrity.py::backfill_initiative_ape_links":
        "RN-M1.B.1. The migration. This is the ONE place the title match is "
        "allowed to establish the link — RN-D2 says migrate by matching the "
        "current name once, then never by name again.",
    "link_integrity.py::backfill_segment_ids":
        "RN-M1.A.1 / RN-M1.C.1. Same migration, same reason.",
    "db_manager_project_boards.py::category colour lineage":
        "Display only. It resolves which vision_category row to read a "
        "COLOUR from, not which rows are linked — the APE's own "
        "annual_plan_element_id is the link. It survives a rename because "
        "RN-M3.A refreshes the APE's name columns and the taxonomy together. "
        "Fragile, and recorded in BACKLOG.md as worth moving to ids.",
    "vps_manager_taxonomy.py::get_vision_subsegments/get_vision_categories":
        "User-input lookup. These take a segment NAME from the caller (a "
        "screen filter) and find rows under it. RN-M2.B keeps "
        "resolve_segment_id_by_name and its kind for exactly this.",
}


def _code_without_comments(text: str) -> str:
    """Source with comments AND docstrings removed, line numbers preserved.

    Two failure modes, both of which this repo has hit:

    * Truncating at the first ``#`` cuts a line short and hides a pattern that
      lives inside a quoted SQL string. Only whole-line comments are dropped.
    * A DOCSTRING that explains a forbidden pattern contains that pattern.
      link_integrity's module docstring quotes
      ``LOWER(ai.title) = LOWER(ape.key_field)`` to say why it is wrong, and a
      scan that counted it would report two hits where there is one — so
      deleting the prose would change the verdict, and pinning a count would
      pin the prose. Docstrings are blanked via the AST.

    Lines are blanked rather than deleted so reported line numbers still point
    at the real source.
    """
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:      # pragma: no cover - every file here parses
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.ClassDef,
                                     ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if not (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                continue
            for i in range(first.lineno - 1, (first.end_lineno or first.lineno)):
                if i < len(lines):
                    lines[i] = ""

    return "\n".join(
        "" if line.strip().startswith("#") else line for line in lines
    )


def _scan_for_name_links(paths):
    """Every (file, pattern, line) where a link is resolved through a name."""
    found = []
    for path in paths:
        code = _code_without_comments(path.read_text(encoding="utf-8"))
        for name, pattern in NAME_LINK_PATTERNS.items():
            for match in re.finditer(pattern, code):
                line = code[: match.start()].count("\n") + 1
                found.append((path.name, name, line))
    return found


def test_rn_m4a_no_link_resolves_through_a_name():
    """RN-M4.A — the hole cannot reopen.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m4a

    Every hit must be one of the allowlisted lookups above, each of which
    carries its reason. A new one is a new way for a rename to break a link.
    """
    hits = _scan_for_name_links(sorted(SRC.rglob("*.py")))
    counts = collections.Counter((f, p) for f, p, _ in hits)

    # EXACT counts, not a set of permitted files. A file-level allowlist let a
    # reintroduced name-join hide inside an allowlisted file — verified by
    # mutation, and it is the same "floor instead of an exact count" mistake
    # LEARNINGS.md P29 records. A count changes whether the new occurrence is
    # in a new file or an old one.
    assert dict(counts) == PERMITTED_NAME_LOOKUPS, (
        "the name-based lookups in src/ have changed.\n"
        f"  found:    {dict(sorted(counts.items()))}\n"
        f"  expected: {dict(sorted(PERMITTED_NAME_LOOKUPS.items()))}\n"
        "A NEW one is a new way for a rename to break a link — resolve by id. "
        "If it is genuinely display or user input, add it here AND to "
        "NAME_LOOKUP_ALLOWLIST with the reason. A REMOVED one is good news: "
        "delete its entry."
    )

    assert NAME_LOOKUP_ALLOWLIST, "the allowlist is empty"
    for key, reason in NAME_LOOKUP_ALLOWLIST.items():
        assert len(reason) > 40, f"{key} has no real reason written next to it"


def test_rn_m4a1_the_scan_can_actually_fire(tmp_path):
    """RN-M4.A.1 — the scan must flag the four patterns this change removes.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m4a

    A scan that is green on the defect and on the fix alike proves nothing.
    That mistake was made twice in the weekly-tactic work, and three times in
    this repo's guard tests generally, so each pattern is driven against a
    synthetic file containing the exact code this change deleted.
    """
    # Each sample is the VERBATIM code this change deleted, not a paraphrase.
    offenders = {
        "segment_join_by_name":
            "LEFT JOIN segment_descriptions sd ON LOWER(sd.name) = LOWER(vs.name)",
        "initiative_by_title":
            "WHERE LOWER(ai.title) = LOWER(?)",
        "segment_by_name_any_caller":
            # The line the previous pattern could not see.
            "segment_id = self.resolve_segment_id_by_name(segment_name)",
        "entity_join_by_name":
            "WHERE LOWER(ss.name) = LOWER(ape.subsegment_name)",
        "segment_descriptions_by_name":
            'SELECT id FROM segment_descriptions WHERE LOWER(name) = LOWER(?)',
    }
    assert set(offenders) == set(NAME_LINK_PATTERNS), (
        "a pattern was added or removed without a matching offender sample, "
        "so the scan is no longer proven able to fire on all of them"
    )

    for name, snippet in offenders.items():
        sample = tmp_path / f"offender_{name}.py"
        sample.write_text(snippet + "\n", encoding="utf-8")
        hits = _scan_for_name_links([sample])
        assert any(h[1] == name for h in hits), (
            f"the scan does NOT flag {name!r} against the exact code this "
            f"change removed:\n    {snippet}"
        )

    # And the other direction: the id-based replacements must NOT trip it.
    clean = tmp_path / "clean.py"
    clean.write_text(
        "LEFT JOIN segment_descriptions sd ON sd.id = vs.segment_description_id\n"
        "WHERE ai.annual_plan_element_id = ?\n"
        'segment_id = self._segment_id_for_ape(ape)\n',
        encoding="utf-8",
    )
    assert _scan_for_name_links([clean]) == [], (
        "the scan flags the id-based code that replaced the defect, so it "
        "cannot be satisfied by fixing the problem"
    )


def test_rn_m4a_comment_stripper_keeps_hashes_inside_strings(tmp_path):
    """The scan must not be defeated by its own comment handling.

    Three guards in this repo have died to a stripper that truncated at the
    first ``#``, hiding a pattern that lived inside a quoted string.
    """
    sample = tmp_path / "hashy.py"
    sample.write_text(
        '# LOWER(sd.name) = LOWER(vs.name) — explained, must NOT count\n'
        'q = "SELECT 1 # not a comment: LOWER(sd.name) = LOWER(vs.name)"\n',
        encoding="utf-8",
    )
    hits = _scan_for_name_links([sample])
    # Exactly one: the quoted string. The comment must not count, and the
    # string must not be truncated at the `#` inside it. Two patterns can match
    # this line (entity_join_by_name is the general form), so compare on the
    # set of LINES hit rather than the number of matches.
    assert {h[2] for h in hits} == {2}, (
        f"expected hits on line 2 only — the string, not the comment — got {hits}"
    )


def test_rn_deleting_a_segment_with_plan_elements_is_refused(tmp_path):
    """A segment with Annual Plan Elements under it must not be deletable.

    Found by the sweep, and it was introduced BY this change. RN-M1 gave
    annual_plan_elements a segment_description_id declared ON DELETE SET NULL —
    chosen so delete_segment would stop raising FOREIGN KEY constraint failed
    on the auto-created vision_segments shadow row. That signal was real; it
    just pointed at the wrong table.

    The result: deleting a segment reported "no child records", silently nulled
    every APE's link, and the next cascade raised
    `ValueError: Segment '<name>' not found.` — the exact spec §2 failure this
    change exists to remove, reintroduced by the change.
    """
    vps = make_vps(tmp_path, name="delseg.db")
    try:
        chain = _build_full_chain(vps)

        ok, counts = vps.delete_segment(chain["segment_description_id"])

        assert ok is False, (
            "a segment with an Annual Plan Element under it was deleted"
        )
        assert "Annual Plan Elements" in counts, (
            f"the refusal does not name the plan elements blocking it: {counts}"
        )

        # And the link survives, so the cascade still works.
        ape = vps._get_annual_plan_element_row(chain["ape_id"])
        assert ape["segment_description_id"] == chain["segment_description_id"]
        assert vps.assign_ape_to_month(chain["ape_id"], quarter=4, month=11) is True, (
            "the refused delete still broke the re-filing cascade"
        )
    finally:
        vps.close()


def test_rn_ambiguous_name_is_never_resolved_to_a_link(tmp_path):
    """RN-INV5 across the migration AND every other write site.

    Found by the sweep. `segment_descriptions.name` is UNIQUE but
    case-sensitive, so 'Health' and 'health' coexist legally. The backfill was
    careful — it reported the row as ambiguous and left it NULL — and then
    `sync_vision_segments_with_settings`, which runs at EVERY manager init
    moments later, wrote a guess into the same row.

    The report was false about the database it had just described. A missing
    link is visible in the report; a wrong one is not.
    """
    vps = make_vps(tmp_path, name="ambig.db")
    try:
        chain = _build_full_chain(vps)
        original = vps.db.conn.execute(
            "SELECT name FROM segment_descriptions WHERE id = ?",
            (chain["segment_description_id"],),
        ).fetchone()["name"]

        # A second description whose name differs only by case.
        vps.db.conn.execute(
            "INSERT INTO segment_descriptions "
            "(id, name, color_hex, order_index, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("sd-twin", original.lower() if original != original.lower()
             else original.upper(), "#123456", 99,
             "2099-01-01T00:00:00", "2099-01-01T00:00:00"),
        )
        vps.db.conn.execute("UPDATE vision_segments SET segment_description_id = NULL")
        vps.db.conn.execute(
            "UPDATE annual_plan_elements SET segment_description_id = NULL"
        )
        vps.db.conn.commit()

        report = run_link_integrity_migrations(vps.db.conn)
        assert report["backfill_vision_segments"]["ambiguous"], (
            "the migration did not report the ambiguity"
        )

        # The thing that used to undo it: a fresh manager init on the same file.
        vps.sync_vision_segments_with_settings()

        still_null = vps.db.conn.execute(
            "SELECT segment_description_id FROM vision_segments WHERE id = ?",
            (chain["vision_segment_id"],),
        ).fetchone()["segment_description_id"]
        assert still_null is None, (
            f"a write site guessed {still_null!r} for a name matching two "
            "segment descriptions, after the migration refused to"
        )

        # _segment_id_for_ape may still ANSWER the caller from the name — a
        # refusal there made assign_ape_to_month raise the spec §2 error for
        # every plan element created while two names collide. What must never
        # happen is a WRITE.
        ape = vps._get_annual_plan_element_row(chain["ape_id"])
        vps._segment_id_for_ape(ape)
        persisted = vps.db.conn.execute(
            "SELECT segment_description_id FROM annual_plan_elements WHERE id = ?",
            (chain["ape_id"],),
        ).fetchone()["segment_description_id"]
        assert persisted is None, (
            f"the heal WROTE {persisted!r} for a name matching two segment "
            "descriptions, after the migration refused to"
        )

        # And the cascade still works rather than raising.
        assert vps.assign_ape_to_month(chain["ape_id"], quarter=3, month=9) is True, (
            "refusing to resolve an ambiguous name broke the cascade — the "
            "exact spec §2 failure this change exists to remove"
        )
    finally:
        vps.close()


def test_rn_item_segment_follows_the_ape_link_not_its_name(tmp_path):
    """An Action Item's segment comes from the APE's id, not its name column.

    Found by the sweep: `_segment_from_annual_plan` runs on every
    create_action_item and resolved the segment by matching the APE's
    segment_name against segment_descriptions.name — while its sibling
    `_segment_from_week_action` already read an id column.

    So an APE carrying the CORRECT id and a drifted name — exactly the state
    RN-M5 exists to report — derived None, and the item was stamped with no
    segment at all.
    """
    vps = make_vps(tmp_path, name="derive.db")
    try:
        chain = _build_full_chain(vps)
        # The id is right; the name has drifted. Nothing else changes.
        vps.db.conn.execute(
            "UPDATE annual_plan_elements SET segment_name = 'Drifted Name' WHERE id = ?",
            (chain["ape_id"],),
        )
        vps.db.conn.commit()

        derived = vps.db_manager._segment_from_annual_plan(chain["ape_id"])
        assert derived == chain["segment_description_id"], (
            f"the item's segment was derived as {derived!r}; the APE's link "
            f"says {chain['segment_description_id']!r}"
        )
    finally:
        vps.close()


def test_rn_a_hand_edited_initiative_title_survives_a_rename(tmp_path):
    """RN-D7 says the title is derived — of how it STARTS, not of what the
    user may have made it.

    Found by the sweep. The Annual Initiative editor offers a Title field and
    update_annual_initiative persists it, so a blanket
    `UPDATE annual_initiatives SET title = <key_field>` on any taxonomy rename
    discarded the user's text silently.

    An untouched title still follows the rename — that is RN-M3.A, asserted in
    test_rn_m3a_rename_refreshes_every_display_copy.
    """
    vps = make_vps(tmp_path, name="handedit.db")
    try:
        chain = _build_full_chain(vps)
        vps.update_annual_initiative(
            chain["annual_initiative_id"], title="Grow the blog to 10k readers"
        )

        vps.rename_vision_subsegment(chain["subsegment_id"], "Publishing")

        title = vps.db.conn.execute(
            "SELECT title FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()["title"]
        assert title == "Grow the blog to 10k readers", (
            f"the rename overwrote a hand-edited title with {title!r}"
        )
    finally:
        vps.close()


def test_rn_repointing_a_vision_element_moves_its_segment_link(tmp_path):
    """Re-pointing a vision element to a DIFFERENT segment must move the link.

    Found by the cold review, and it was a regression introduced BY this
    change. `update_vision_element` updates the APE's segment_name but did not
    update segment_description_id, and `_segment_id_for_ape` returns the stored
    id whenever it is non-NULL — so the heal never ran and the APE kept
    pointing at the OLD segment.

    The old name-based code got this right. Worse than a stale display: the
    annual plan, initiative and tactics stay filed under the old segment, whose
    id columns are ON DELETE CASCADE, so deleting it destroys work the UI shows
    under the new one.
    """
    vps = make_vps(tmp_path, name="repoint.db")
    try:
        chain = _build_full_chain(vps)
        segments = vps.get_all_segments(active_only=False)
        other = next(s for s in segments if s["id"] != chain["segment_description_id"])

        vps.create_vision_subsegment(other["name"], "Other Sub")
        vps.update_vision_element(
            chain["vision_element_id"],
            segment_name=other["name"],
            subsegment_name="Other Sub",
            category_name="Blog",
        )

        ape = vps._get_annual_plan_element_row(chain["ape_id"])
        assert ape["segment_name"] == other["name"], "the fixture did not re-point"
        assert vps._segment_id_for_ape(ape) == other["id"], (
            f"the APE still resolves to {vps._segment_id_for_ape(ape)!r}; it was "
            f"re-pointed to {other['id']!r} ({other['name']!r})"
        )
    finally:
        vps.close()


def test_rn_a_hand_created_initiative_is_not_warned_about(tmp_path, caplog):
    """The report must not cry wolf on normal data.

    Found by the sweep. An Annual Initiative can be created from the editor
    with no APE, by design. Reporting every one as "orphaned by a rename" put
    a WARNING in the audit log at every launch, forever — and that log is what
    the spec's §10 human-review step depends on.
    """
    vps = make_vps(tmp_path, name="notbreakage.db")
    try:
        chain = _build_full_chain(vps)
        original = vps.db.conn.execute(
            "SELECT * FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()
        vps.db.conn.execute(
            "INSERT INTO annual_initiatives "
            "(id, annual_plan_id, segment_description_id, year, title, "
            " created_at, updated_at, annual_plan_element_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ai-byhand", original["annual_plan_id"],
             original["segment_description_id"], original["year"],
             "Grow the blog to 10k readers",
             "2099-01-01T00:00:00", "2099-01-01T00:00:00", None),
        )
        vps.db.conn.commit()

        # It IS in the report — RN-INV5 says never silently skipped, and no
        # filter can tell a hand-created initiative from an orphaned one.
        breakage = report_existing_breakage(vps.db.conn)
        ids = [r["id"] for r in breakage["initiatives_without_ape"]]
        assert "ai-byhand" in ids, "RN-INV5: it must still be reported"

        # What must not happen is a WARNING at every launch. It is stated at
        # INFO instead, so a WARNING in this log always means something needs
        # a human.
        with caplog.at_level(logging.INFO):
            run_link_integrity_migrations(vps.db.conn)
        warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING and "initiatives_without_ape" in r.getMessage()
        ]
        assert not warnings, (
            f"a hand-created initiative produced a WARNING: "
            f"{[w.getMessage() for w in warnings]}"
        )
    finally:
        vps.close()


def test_rn_a_lookup_leaves_no_open_transaction(tmp_path):
    """The heals write inside getters; they must not leave a write open.

    Found by the sweep. `_find_annual_initiative_for_ape` is used as a pure
    read — weekly_tactic's before-snapshot, and unassign_ape_from_month, either
    of which can return without committing. The heal's UPDATE was then
    discarded at close (so the heal silently did not happen) while the
    connection held a RESERVED lock in the meantime.
    """
    vps = make_vps(tmp_path, name="txn.db")
    try:
        chain = _build_full_chain(vps)
        vps.db.conn.execute(
            "UPDATE annual_initiatives SET annual_plan_element_id = NULL WHERE id = ?",
            (chain["annual_initiative_id"],),
        )
        vps.db.conn.commit()
        assert vps.db.conn.in_transaction is False, "the fixture left one open"

        ape = vps._get_annual_plan_element_row(chain["ape_id"])
        found = vps._find_annual_initiative_for_ape(ape)

        assert found is not None, "the heal did not fire"
        assert vps.db.conn.in_transaction is False, (
            "a lookup left an open write transaction on the shared connection"
        )
        # And the heal actually persisted, rather than being rolled back.
        stored = vps.db.conn.execute(
            "SELECT annual_plan_element_id FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()["annual_plan_element_id"]
        assert stored == chain["ape_id"], "the heal was written but not committed"
    finally:
        vps.close()


def test_rn_m3a_title_refreshes_on_the_update_vision_element_path_too(tmp_path):
    """RN-M3.A must hold on BOTH rename paths, not just one.

    Found by the sweep. The title refresh went into
    _sync_vision_element_derived_fields; `update_vision_element` is its
    near-identical sibling and did the same mirror updates itself, so renaming
    through it left the initiative showing the old composite.

    test_rn_m3a drives rename_vision_segment (the fixed function) and
    test_rn_m3b drives update_vision_element but only checks the APE and the
    tactic — so the two jointly missed it.
    """
    vps = make_vps(tmp_path, name="m3a2.db")
    try:
        chain = _build_full_chain(vps)
        vps.update_vision_element(
            chain["vision_element_id"],
            segment_name=chain["segment_name"],
            subsegment_name="Living Systems",
            category_name="Renamed Cat",
        )

        title = vps.db.conn.execute(
            "SELECT title FROM annual_initiatives WHERE id = ?",
            (chain["annual_initiative_id"],),
        ).fetchone()["title"]
        assert "Renamed Cat" in title, (
            f"the initiative title is stale after update_vision_element: {title!r}"
        )
    finally:
        vps.close()


def test_rn_the_cascade_resolver_reads_the_id_not_the_name(tmp_path):
    """`_segment_id_for_ape` must be load-bearing, and only a drift proves it.

    The previous attempt at this routed the matrix's `ape_to_segment` through
    this function and claimed that made a mutation fail. It did not: RN-M3.A
    keeps the APE's segment_name and segment_descriptions.name in step, so the
    by-name fallback returns the same answer and the mutation stayed green
    across all 35 tests.

    Drifting the name is the only thing that separates them — and a drifted
    name is exactly the state RN-M5 exists to report, so it is a real state,
    not a contrived one.
    """
    vps = make_vps(tmp_path, name="loadbearing.db")
    try:
        chain = _build_full_chain(vps)
        vps.db.conn.execute(
            "UPDATE annual_plan_elements SET segment_name = 'Drifted' WHERE id = ?",
            (chain["ape_id"],),
        )
        vps.db.conn.commit()

        ape = vps._get_annual_plan_element_row(chain["ape_id"])
        assert vps._segment_id_for_ape(ape) == chain["segment_description_id"], (
            "the cascade's segment resolver did not read the stored id — with "
            "the name drifted, only the id column has the right answer"
        )
    finally:
        vps.close()
