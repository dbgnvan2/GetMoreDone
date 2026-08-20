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
