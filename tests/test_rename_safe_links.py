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

from datetime import date

import pytest

from src.getmoredone.link_integrity import (
    SEGMENT_ID_TABLES,
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

def _resolve_links(vps, chain):
    """Every link in the chain, resolved now, as ids.

    Compared against the snapshot taken before the rename. A link that returns
    None, or a different id, is broken.
    """
    ape = vps._get_annual_plan_element_row(chain["ape_id"])
    initiative = vps._find_annual_initiative_for_ape(ape) if ape else None

    # The vision_segments <-> segment_descriptions join (RN-F2), exactly as
    # vps_manager_taxonomy.py does it.
    join_row = vps.db.conn.execute(
        """
        SELECT sd.id AS segment_description_id
        FROM vision_segments vs
        JOIN segment_descriptions sd ON LOWER(sd.name) = LOWER(vs.name)
        WHERE vs.id = ?
        """,
        (chain["vision_segment_id"],),
    ).fetchone()

    return {
        # APE -> segment. This is what the re-filing cascade calls, and what
        # raises ValueError("Segment '<new name>' not found.") once renamed.
        "ape_to_segment": (
            vps.resolve_segment_id_by_name(ape["segment_name"]) if ape else None
        ),
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
