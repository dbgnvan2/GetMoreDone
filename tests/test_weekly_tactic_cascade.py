"""WT-M4 — start-date-driven re-filing and the scaffolding cascade.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4
"""

import sqlite3
from unittest.mock import patch

import pytest

from src.getmoredone.models import ActionItem
from src.getmoredone.db_manager import DatabaseManager
from tests.weekly_tactic_fixtures import (
    make_daily_item,
    make_vps,
    make_week_item,
    seed_ape,
)

# The eight tables a full year rollover must build exactly one row in each of.
LINEAGE_TABLES = (
    "annual_visions",
    "annual_plans",
    "annual_vision_elements",
    "annual_plan_elements",
    "annual_initiatives",
    "quarter_initiatives",
    "month_tactics",
)


def _counts(conn, year=None):
    out = {}
    for table in LINEAGE_TABLES:
        sql = f"SELECT COUNT(*) AS n FROM {table}"
        params = ()
        if year is not None:
            sql += " WHERE year = ?"
            params = (year,)
        out[table] = conn.execute(sql, params).fetchone()["n"]
    sql = "SELECT COUNT(*) AS n FROM action_items WHERE item_type = 'week'"
    params = ()
    if year is not None:
        sql += " AND start_date LIKE ?"
        params = (f"{year}-%",)
    out["week_items"] = conn.execute(sql, params).fetchone()["n"]
    return out


def _filed_item(vps, start="2026-02-25", week_start="2026-02-23", due=None):
    """An item attached to a tactic on ``week_start``.

    ``start`` must fall inside that week: attaching is itself a save, so it
    re-files for the item's own start date and would otherwise build a second
    tactic before the test began.
    """
    ape_id = seed_ape(vps)
    tactic = make_week_item(vps, ape_id, start=week_start,
                            due=vps.db_manager.weekly_tactic_engine.calendar
                            .end(week_start).isoformat())
    item = make_daily_item(vps, "Task", start=start, due=due or start)
    stored = vps.db_manager.get_action_item(item.id)
    stored.weekly_tactic_id = tactic.id
    vps.db_manager.update_action_item(stored)
    return ape_id, tactic, vps.db_manager.get_action_item(item.id)


def _move(manager, item_id, start, due=None):
    stored = manager.get_action_item(item_id)
    stored.start_date = start
    stored.due_date = due or start
    manager.update_action_item(stored)
    return manager.get_action_item(item_id)


# --------------------------------------------------------------------------
# WT-M4.A — re-filing to the right lineage
# --------------------------------------------------------------------------

def test_wt_m4a1_relink_to_existing_week_creates_nothing(tmp_path):
    """Moving into a week that already has a tactic relinks and builds nothing."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)
        # Same month and quarter as the item's current week, so the only thing
        # that could be created is the week itself — and it already exists.
        vps.assign_ape_to_month(ape_id, 1, 2)
        target = make_week_item(vps, ape_id, start="2026-02-09", due="2026-02-15",
                                title="Target week")
        before = _counts(manager.db.conn)

        moved = _move(manager, item.id, "2026-02-11")

        assert moved.weekly_tactic_id == target.id
        assert _counts(manager.db.conn) == before, "nothing should have been created"
        assert manager.last_cascade_report.created == []
    finally:
        vps.close()


def test_wt_m4a2_lineage_inherited_from_current_tactic(tmp_path):
    """The lineage comes from the item's own tactic, not from whatever covers today."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        # A second, unrelated lineage with a tactic on the target week. The
        # re-file must not drift onto it.
        other_ape = seed_ape(vps, subsegment="Other", key_field="Podcast")
        decoy = make_week_item(vps, other_ape, start="2026-03-02", due="2026-03-08",
                               title="Decoy")

        moved = _move(manager, item.id, "2026-03-04")

        assert moved.weekly_tactic_id != decoy.id
        landed = manager.get_action_item(moved.weekly_tactic_id)
        assert landed.annual_plan_element_id == ape_id
    finally:
        vps.close()


def test_wt_m4a3_item_ape_reconciled_after_refile(tmp_path):
    """The item's own APE is brought into line with its tactic's."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        # Point the item at a different APE by hand, as stale data would.
        other_ape = seed_ape(vps, subsegment="Other", key_field="Podcast")
        stored = manager.get_action_item(item.id)
        stored.annual_plan_element_id = other_ape
        manager.update_action_item(stored)

        moved = _move(manager, item.id, "2026-03-04")
        week = manager.get_action_item(moved.weekly_tactic_id)
        assert moved.annual_plan_element_id == week.annual_plan_element_id == ape_id
    finally:
        vps.close()


# --------------------------------------------------------------------------
# WT-M4.B — bottom-up scaffolding per WT-D6
# --------------------------------------------------------------------------

def test_wt_m4b1_creates_week_only_within_month(tmp_path):
    """Same quarter, same month, no week -> only the Weekly Tactic is created."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps, start="2026-02-03", week_start="2026-02-02")
        # Put the quarter and month assignment in place first, so only the week
        # is missing.
        vps.assign_ape_to_month(ape_id, 1, 2)
        before = _counts(manager.db.conn)

        moved = _move(manager, item.id, "2026-02-25")   # another week, same month

        after = _counts(manager.db.conn)
        assert after["week_items"] == before["week_items"] + 1
        for table in LINEAGE_TABLES:
            assert after[table] == before[table], f"{table} should not have grown"
        kinds = [entry["kind"] for entry in manager.last_cascade_report.created]
        assert kinds == ["weekly_tactic"]
    finally:
        vps.close()


def test_wt_m4b2_creates_month_assignment_on_month_cross(tmp_path):
    """Crossing a month end creates the month tactic and the week, reusing the quarter."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps, start="2026-02-25", week_start="2026-02-23")
        vps.assign_ape_to_month(ape_id, 1, 2)
        before = _counts(manager.db.conn)

        _move(manager, item.id, "2026-03-04")   # February -> March, same quarter

        after = _counts(manager.db.conn)
        assert after["month_tactics"] == before["month_tactics"] + 1
        assert after["quarter_initiatives"] == before["quarter_initiatives"]
        assert after["week_items"] == before["week_items"] + 1

        ape = manager.db.conn.execute(
            "SELECT m3 FROM annual_plan_elements WHERE id = ?", (ape_id,)
        ).fetchone()
        assert ape["m3"] == 1, "the month flag must be set too"
    finally:
        vps.close()


def test_wt_m4b3_creates_quarter_assignment_on_quarter_cross(tmp_path):
    """Crossing a quarter end creates quarter, then month, then week."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps, start="2026-02-25", week_start="2026-02-23")
        vps.assign_ape_to_month(ape_id, 1, 2)
        before = _counts(manager.db.conn)

        _move(manager, item.id, "2026-05-06")   # Q1 -> Q2

        after = _counts(manager.db.conn)
        assert after["quarter_initiatives"] == before["quarter_initiatives"] + 1
        assert after["month_tactics"] == before["month_tactics"] + 1
        assert after["week_items"] == before["week_items"] + 1

        flags = manager.db.conn.execute(
            "SELECT q2, m5 FROM annual_plan_elements WHERE id = ?", (ape_id,)
        ).fetchone()
        assert flags["q2"] == 1 and flags["m5"] == 1

        kinds = [entry["kind"] for entry in manager.last_cascade_report.created]
        assert kinds == ["quarter_initiative", "month_tactic", "weekly_tactic"], kinds
    finally:
        vps.close()


def test_wt_m4b4_cascade_is_idempotent(tmp_path):
    """A second identical move creates nothing more."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        _move(manager, item.id, "2026-05-06")
        after_first = _counts(manager.db.conn)

        _move(manager, item.id, "2026-05-06")
        assert _counts(manager.db.conn) == after_first
        assert manager.last_cascade_report.created == []
    finally:
        vps.close()


def test_wt_m4b5_ancestor_selection_deterministic(tmp_path):
    """Duplicates at quarter/month level are not deduped, so selection must not vary."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)
        _move(manager, item.id, "2026-05-06")

        week_id = manager.get_action_item(item.id).weekly_tactic_id
        engine = manager.weekly_tactic_engine
        ape = engine._row("annual_plan_elements", ape_id)

        first = [row["id"] for row in engine._quarter_rows(ape, 2, 2026)]
        second = [row["id"] for row in engine._quarter_rows(ape, 2, 2026)]
        assert first == second and first, "quarter selection must be stable"

        months_a = [row["id"] for row in engine._month_rows(ape, 2, 5, 2026)]
        months_b = [row["id"] for row in engine._month_rows(ape, 2, 5, 2026)]
        assert months_a == months_b and months_a

        # And the tactic lookup itself is ordered, not "whatever comes back".
        from datetime import date
        assert engine.find_tactic(ape_id, date(2026, 5, 4))["id"] == week_id
    finally:
        vps.close()


# --------------------------------------------------------------------------
# WT-M4.C — year rollover
# --------------------------------------------------------------------------

def test_wt_m4c1_year_rollover_builds_exactly_one_row_per_table(tmp_path):
    """A year with no structure gets a complete chain — and no extras."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)
        boards_before = manager.db.conn.execute(
            "SELECT COUNT(*) AS n FROM project_boards"
        ).fetchone()["n"]

        _move(manager, item.id, "2027-03-03")

        after = _counts(manager.db.conn, year=2027)
        for table in LINEAGE_TABLES:
            assert after[table] == 1, f"{table} should hold exactly one 2027 row, got {after[table]}"
        assert after["week_items"] == 1

        # Q2: a project spans any timeframe, so a new year needs no new board.
        assert manager.db.conn.execute(
            "SELECT COUNT(*) AS n FROM project_boards"
        ).fetchone()["n"] == boards_before
    finally:
        vps.close()


def test_wt_m4c2_rollover_preserves_vision_element_lineage(tmp_path):
    """The new APE keeps the source vision_element_id and key_field."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)
        source = dict(manager.db.conn.execute(
            "SELECT * FROM annual_plan_elements WHERE id = ?", (ape_id,)).fetchone())

        moved = _move(manager, item.id, "2027-03-03")
        new_ape = dict(manager.db.conn.execute(
            "SELECT * FROM annual_plan_elements WHERE id = ?",
            (moved.annual_plan_element_id,)).fetchone())

        assert new_ape["id"] != ape_id
        assert new_ape["year"] == 2027
        assert new_ape["vision_element_id"] == source["vision_element_id"]
        assert new_ape["key_field"] == source["key_field"]
        assert new_ape["segment_name"] == source["segment_name"]
        assert new_ape["subsegment_name"] == source["subsegment_name"]
        assert new_ape["category_name"] == source["category_name"]
    finally:
        vps.close()


def test_wt_m4c3_editorial_fields_blank_and_flagged(tmp_path):
    """WT-D7a — structural fields carry across; editorial text never does."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        _move(manager, item.id, "2027-03-03")

        vision = dict(manager.db.conn.execute(
            "SELECT * FROM annual_visions WHERE year = 2027").fetchone())
        assert vision["created_by_rollover"] == 1
        for column in ("title", "vision_statement", "key_priorities"):
            assert not (vision[column] or "").strip(), f"annual_visions.{column} must be blank"

        plan = dict(manager.db.conn.execute(
            "SELECT * FROM annual_plans WHERE year = 2027").fetchone())
        assert plan["created_by_rollover"] == 1
        for column in ("theme", "objective", "description"):
            assert not (plan[column] or "").strip(), f"annual_plans.{column} must be blank"
    finally:
        vps.close()


def test_wt_m4c3a_year_scoped_fks_repointed_not_copied(tmp_path):
    """The new APE must point at the new year's AVE, not carry the old one over."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        moved = _move(manager, item.id, "2027-03-03")
        new_ape = dict(manager.db.conn.execute(
            "SELECT * FROM annual_plan_elements WHERE id = ?",
            (moved.annual_plan_element_id,)).fetchone())
        new_ave = dict(manager.db.conn.execute(
            "SELECT * FROM annual_vision_elements WHERE id = ?",
            (new_ape["annual_vision_element_id"],)).fetchone())

        assert new_ape["annual_vision_element_id"] == new_ave["id"]
        assert new_ave["year"] == 2027

        old_ave_id = manager.db.conn.execute(
            "SELECT annual_vision_element_id FROM annual_plan_elements WHERE id = ?",
            (ape_id,)).fetchone()["annual_vision_element_id"]
        assert new_ave["id"] != old_ave_id, "the year-scoped FK was copied, not re-pointed"
    finally:
        vps.close()


def test_wt_m4c3b_stub_discovery_uses_flag_not_emptiness(tmp_path):
    """A hand-authored vision with a blank statement is not a stub (WT-D13)."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        # The adversarial case: a real 2026 vision the user simply left blank.
        manager.db.conn.execute(
            "UPDATE annual_visions SET vision_statement = '', key_priorities = '' "
            "WHERE year = 2026"
        )
        manager.db.conn.commit()

        _move(manager, item.id, "2027-03-03")

        stubs = manager.db.conn.execute(
            "SELECT year FROM annual_visions WHERE created_by_rollover = 1"
        ).fetchall()
        assert [row["year"] for row in stubs] == [2027], (
            "emptiness must not make a hand-authored row read as a stub"
        )

        reported = {entry["id"] for entry in manager.last_cascade_report.stubs}
        blank_2026 = manager.db.conn.execute(
            "SELECT id FROM annual_visions WHERE year = 2026").fetchone()["id"]
        assert blank_2026 not in reported
    finally:
        vps.close()


def test_wt_m4c3c_existing_ape_assignment_callers_unaffected(tmp_path):
    """The four shipped callers still get their titles (WT-F3, WT-M4.C.3c)."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps, year=2028)
        ape = dict(manager.db.conn.execute(
            "SELECT * FROM annual_plan_elements WHERE id = ?", (ape_id,)).fetchone())

        # This is the call ape_assignment.py / ape_period_view.py make.
        vps._get_or_create_annual_plan_for_ape(ape)
        manager.db.conn.commit()

        vision = dict(manager.db.conn.execute(
            "SELECT * FROM annual_visions WHERE year = 2028").fetchone())
        plan = dict(manager.db.conn.execute(
            "SELECT * FROM annual_plans WHERE year = 2028").fetchone())

        assert vision["title"] == f"{ape['segment_name']} 2028"
        assert plan["theme"] == f"{ape['segment_name']} 2028 Plan"
        assert vision["created_by_rollover"] == 0
        assert plan["created_by_rollover"] == 0
    finally:
        vps.close()


def test_wt_m4c4_rollover_returns_report_and_bool_callers_unbroken(tmp_path):
    """The report is a new type; the boolean contract is untouched (WT-F13, P22)."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        _move(manager, item.id, "2027-03-03")
        report = manager.last_cascade_report

        assert report.target_year == 2027
        assert report.week_start == "2027-03-01"
        kinds = [entry["kind"] for entry in report.created]
        for expected in ("annual_vision_elements", "annual_plan_elements",
                         "annual_visions", "annual_plans", "annual_initiatives",
                         "quarter_initiative", "month_tactic", "weekly_tactic"):
            assert expected in kinds, f"{expected} missing from {kinds}"
        assert report.describe().startswith("Created ")
        assert "need your words" in report.describe()

        # The bare-boolean contract those two functions have kept since WT-F13.
        assert vps.assign_ape_to_quarter(ape_id, 3) is True
        assert vps.assign_ape_to_month(ape_id, 3, 8) is True
    finally:
        vps.close()


def test_wt_m4c5_second_rollover_is_idempotent(tmp_path):
    """A second move into the same year reuses the rows."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        _move(manager, item.id, "2027-03-03")
        after_first = _counts(manager.db.conn, year=2027)

        _move(manager, item.id, "2026-02-25")
        _move(manager, item.id, "2027-03-03")

        assert _counts(manager.db.conn, year=2027) == after_first
    finally:
        vps.close()


def test_wt_m4c6_partial_lineage_completed_not_adopted(tmp_path):
    """A half-built target year is completed, not treated as finished."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)
        source = dict(manager.db.conn.execute(
            "SELECT * FROM annual_plan_elements WHERE id = ?", (ape_id,)).fetchone())

        # Build only the AVE + APE for 2027, leaving the vision/plan/initiative
        # and every period row missing.
        vps.create_annual_records_from_vision_element(2027, source["vision_element_id"])
        partial = _counts(manager.db.conn, year=2027)
        assert partial["annual_plan_elements"] == 1
        assert partial["annual_visions"] == 0
        assert partial["quarter_initiatives"] == 0

        _move(manager, item.id, "2027-03-03")

        after = _counts(manager.db.conn, year=2027)
        for table in LINEAGE_TABLES:
            assert after[table] == 1, f"{table} left incomplete at {after[table]}"
        assert after["week_items"] == 1
    finally:
        vps.close()


def test_wt_m4c7_backward_and_multi_year_moves(tmp_path):
    """Backwards and multi-year moves build the target year only."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        _move(manager, item.id, "2025-03-05")
        assert _counts(manager.db.conn, year=2025)["annual_plan_elements"] == 1

        _move(manager, item.id, "2028-03-08")
        assert _counts(manager.db.conn, year=2028)["annual_plan_elements"] == 1

        # 2027 sits between 2026 and 2028 and was never asked for.
        assert _counts(manager.db.conn, year=2027)["annual_plan_elements"] == 0, (
            "intermediate years must not be fabricated"
        )
    finally:
        vps.close()


# --------------------------------------------------------------------------
# WT-M4.D — atomicity
# --------------------------------------------------------------------------

def test_wt_m4d1_cascade_runs_in_one_transaction(tmp_path):
    """The whole cascade commits once, not once per row.

    Tested by counting commits rather than by scanning source: the creators nest
    several deep (annual initiative -> annual plan -> annual vision -> TL
    vision), and a single missed ``commit=False`` anywhere in that chain defeats
    the rollback. A count catches it regardless of depth (WT-F11).
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        commits = []

        class _CountingConn:
            """Counts commits that actually reach the database.

            A deferred commit is a no-op, so counting calls would measure
            attempts rather than writes — and the whole point is how many times
            the database was really committed.
            """

            def __init__(self, inner):
                self._inner = inner

            def commit(self):
                if not self._inner.commits_deferred:
                    commits.append(1)
                return self._inner.commit()

            def force_commit(self):
                # The transaction owner's own commit, which the gate lets
                # through by design — this is the one that must happen exactly
                # once.
                commits.append(1)
                return self._inner.force_commit()

            def __getattr__(self, name):
                return getattr(self._inner, name)

        original = manager.db.conn
        manager.db.conn = _CountingConn(original)
        try:
            _move(manager, item.id, "2027-03-03")
        finally:
            manager.db.conn = original

        assert len(commits) == 1, (
            f"a full year rollover committed {len(commits)} times; every creator "
            "on the path must honour commit=False"
        )
        assert _counts(manager.db.conn, year=2027)["annual_plan_elements"] == 1
    finally:
        vps.close()


def test_wt_m4d2_failure_at_last_row_rolls_back_everything(tmp_path):
    """A failure on the final row leaves none of the previous seven behind."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)
        before_item = manager.get_action_item(item.id)
        assert _counts(manager.db.conn, year=2027)["annual_plan_elements"] == 0

        engine = manager.weekly_tactic_engine
        real_ensure = engine.ensure_tactic

        def _fail_on_the_week(*args, **kwargs):
            real_ensure(*args, **kwargs)          # build all seven rows first
            raise RuntimeError("injected failure on the last row")

        with patch.object(engine, "ensure_tactic", _fail_on_the_week):
            with pytest.raises(RuntimeError, match="injected failure"):
                _move(manager, item.id, "2027-03-03")

        after = _counts(manager.db.conn, year=2027)
        for table in LINEAGE_TABLES:
            assert after[table] == 0, f"{table} kept {after[table]} row(s) after a rollback"
        assert after["week_items"] == 0

        unchanged = manager.get_action_item(item.id)
        assert unchanged.weekly_tactic_id == before_item.weekly_tactic_id
        assert unchanged.start_date == before_item.start_date
        assert unchanged.due_date == before_item.due_date
    finally:
        vps.close()


def test_wt_m4d3_missing_segment_rolls_back(tmp_path):
    """The real mid-chain raise site, not a synthetic exception.

    A segment that cannot be resolved raises ValueError inside
    ``assign_ape_to_quarter`` / ``assign_ape_to_month`` — a genuine failure
    part-way through the chain, and this asserts the whole cascade rolls back.

    It used to induce that by patching ``resolve_segment_id_by_name``. RN-M2.B
    moved every link caller onto ``_segment_id_for_ape``, which reads the APE's
    stored ``segment_description_id`` — so the old patch no longer causes a
    failure at all. That is the point of the rename-safe-links change, not a
    regression: the rollback contract here is unchanged, only the way to
    produce a missing segment moved.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)
        before = _counts(manager.db.conn, year=2027)

        with patch.object(vps, "_segment_id_for_ape", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                _move(manager, item.id, "2027-03-03")

        assert _counts(manager.db.conn, year=2027) == before, (
            "a mid-chain ValueError must leave nothing behind"
        )
        assert manager.get_action_item(item.id).start_date == "2026-02-25"
    finally:
        vps.close()


def test_wt_m4d4_no_cascade_for_unlinked_item(tmp_path):
    """WT-INV6 — a start-date change on an unlinked item runs no cascade at all."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        seed_ape(vps)
        item = make_daily_item(vps, "Unlinked", start="2026-02-25", due="2026-02-25")
        before = _counts(manager.db.conn)

        _move(manager, item.id, "2027-03-03")

        assert _counts(manager.db.conn) == before
        after = manager.get_action_item(item.id)
        assert after.start_date == "2027-03-03"
        assert after.weekly_tactic_id is None
        assert manager.last_cascade_report is None
    finally:
        vps.close()


def test_wt_m4b_week_boundary_has_one_source(tmp_path, monkeypatch):
    """Changing "First day of week" mid-session must not split the boundary.

    The engine held a calendar built once at startup while
    ``_normalize_week_item_dates`` read the setting live. The cascade then made
    a week row on one boundary and the save snapped it to the other, so the
    tactic could never be found again — and the next move into that week hit the
    WT-INV5 unique index and lost the save.
    """
    from types import SimpleNamespace

    from src.getmoredone.app_settings import AppSettings

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)
        second = make_daily_item(vps, "Second", start="2026-02-25", due="2026-02-25")
        stored = manager.get_action_item(second.id)
        stored.weekly_tactic_id = tactic.id
        manager.update_action_item(stored)

        # The user flips to Sunday-start weeks between saves.
        monkeypatch.setattr(
            AppSettings, "load",
            staticmethod(lambda: SimpleNamespace(first_day_of_week=6,
                                                 first_week_of_year_rule="iso")),
        )

        _move(manager, item.id, "2026-03-04")
        _move(manager, second.id, "2026-03-05")   # must not raise

        a = manager.get_action_item(item.id)
        b = manager.get_action_item(second.id)
        assert a.weekly_tactic_id == b.weekly_tactic_id, (
            "two items in the same week landed on different tactics"
        )
        week = manager.get_action_item(a.weekly_tactic_id)
        assert week.start_date == "2026-03-01", "Sunday-start weeks now"
        assert manager._get_first_day_of_week() == 6
        assert manager.weekly_tactic_engine.calendar.first_day == 6, (
            "the engine's calendar must follow the setting"
        )
    finally:
        vps.close()


def test_wt_m4a_missing_lineage_is_reported_not_silently_skipped(tmp_path):
    """A re-file that cannot happen must say so, not look like "nothing to do"."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed_item(vps)

        # A tactic whose APE has gone (annual_plan_element_id has no FK).
        manager.db.conn.execute(
            "UPDATE action_items SET annual_plan_element_id = NULL WHERE id = ?",
            (tactic.id,))
        manager.db.conn.commit()

        _move(manager, item.id, "2026-03-04")

        report = manager.last_cascade_report
        assert report is not None, "a failure must not look like an unlinked item"
        assert report.status == "ape_missing"
        assert report.failed is True

        # ...and an item that loses its dates while already filed is benign,
        # but still distinguishable from a failure. (Choosing a tactic for a
        # dateless item is a different case: it files by that tactic's week.)
        healthy_ape = seed_ape(vps, subsegment="Healthy", key_field="Other")
        healthy = make_week_item(vps, healthy_ape, start="2026-02-23",
                                 due="2026-03-01", title="Healthy")
        dateless = make_daily_item(vps, "Dateless", start="2026-02-25",
                                   due="2026-02-25")
        stored = manager.get_action_item(dateless.id)
        stored.weekly_tactic_id = healthy.id
        manager.update_action_item(stored)

        cleared = manager.get_action_item(dateless.id)
        cleared.start_date = None
        cleared.due_date = None
        manager.update_action_item(cleared)
        assert manager.last_cascade_report.status == "no_target_date"
        assert manager.last_cascade_report.failed is False
    finally:
        vps.close()


def test_wt_m4d_the_commit_gate_reopens_on_any_exception(tmp_path):
    """A BaseException through a transaction must not close the gate for good.

    ``except Exception`` does not catch KeyboardInterrupt. With the gate
    reopened only in the except/else arms, one Ctrl-C left commits suppressed
    for the life of the process while ``_in_transaction`` read False — so every
    later save looked fine on the connection and was silently discarded at
    close(). ``./start.sh`` runs the app from a terminal, so Ctrl-C is a
    reachable trigger.
    """
    vps = make_vps(tmp_path, "gate.db")
    db_path = vps.db_manager.db.db_path
    try:
        manager = vps.db_manager
        seed_ape(vps)

        with pytest.raises(KeyboardInterrupt):
            with manager.transaction():
                make_daily_item(vps, "Discarded", start="2026-02-25", due="2026-02-25")
                raise KeyboardInterrupt

        assert manager.db.conn.commits_deferred is False, (
            "the commit gate stayed closed after a BaseException"
        )
        assert manager._in_transaction is False

        # A later save must actually reach disk.
        kept = make_daily_item(vps, "Kept", start="2026-02-25", due="2026-02-25")
    finally:
        vps.close()

    reopened = DatabaseManager(db_path)
    try:
        titles = {row["title"] for row in reopened.db.conn.execute(
            "SELECT title FROM action_items")}
        assert "Kept" in titles, "the save after the interrupt never reached disk"
        assert "Discarded" not in titles, "the interrupted transaction must roll back"
    finally:
        reopened.close()


def test_wt_m4d_a_failing_commit_still_rolls_back(tmp_path):
    """An exception from the owning commit is invisible to `except` above it."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        seed_ape(vps)
        conn = manager.db.conn

        class _FailingCommit:
            def __init__(self, inner):
                self._inner = inner
                self.rolled_back = False

            def force_commit(self):
                raise sqlite3.OperationalError("database is locked")

            def rollback(self):
                self.rolled_back = True
                return self._inner.rollback()

            def __getattr__(self, name):
                return getattr(self._inner, name)

        proxy = _FailingCommit(conn)
        manager.db.conn = proxy
        try:
            with pytest.raises(sqlite3.OperationalError):
                with manager.transaction():
                    proxy.execute(
                        "INSERT INTO action_items (id, who, title, status, "
                        "item_type, priority_score, created_at, updated_at) "
                        "VALUES ('x', 'a', 'b', 'open', 'daily', 0, 'n', 'n')")
            assert proxy.rolled_back, (
                "a failed commit left the writes on the connection for the next "
                "unrelated save to publish"
            )
            assert proxy.commits_deferred is False
        finally:
            manager.db.conn = conn
    finally:
        vps.close()
