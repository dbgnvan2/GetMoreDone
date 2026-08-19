"""WT-M2 — week identity and week numbering have exactly one owner.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m2

WT-F2 found three defects at once: three call sites took ``isocalendar().week``
and threw the ISO year away, and week *identity* was decided in three different
places — settings-driven in one, hardcoded to Monday in two.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.getmoredone import week_calendar
from src.getmoredone.app_settings import AppSettings
from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.week_calendar import (
    RULE_FIRST_FULL,
    RULE_ISO,
    RULE_JAN1,
    WeekCalendar,
    normalize_rule,
    year_and_week,
)
from tests.weekly_tactic_fixtures import make_daily_item, make_vps, make_week_item, seed_ape

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "getmoredone"


# --------------------------------------------------------------------------
# WT-M2.A — the rule
# --------------------------------------------------------------------------

def test_wt_m2a1_rule_table_matches_spec():
    """The spec's table, asserted cell by cell.

    Monday-start is stated explicitly rather than inherited: ``jan1`` and
    ``first_full`` both depend on where a week begins, and a test that read the
    machine's saved setting would pass or fail by accident.
    """
    expected = {
        # date            iso          jan1         first_full
        "2026-12-28": ((2026, 53), (2026, 53), (2026, 52)),
        "2027-01-01": ((2026, 53), (2027, 1), (2026, 52)),
        "2027-01-04": ((2027, 1), (2027, 2), (2027, 1)),
    }
    for day, (iso, jan1, first_full) in expected.items():
        assert year_and_week(day, RULE_ISO, 0) == iso, f"{day} under iso"
        assert year_and_week(day, RULE_JAN1, 0) == jan1, f"{day} under jan1"
        assert year_and_week(day, RULE_FIRST_FULL, 0) == first_full, f"{day} under first_full"


def test_wt_m2a2_unknown_rule_falls_back_to_iso():
    """An unknown or empty rule must not raise in the middle of a save."""
    for bad in (None, "", "   ", "gregorian", "ISO-8601", 7):
        assert normalize_rule(bad) == RULE_ISO
    assert year_and_week("2027-01-01", "nonsense", 0) == (2026, 53)

    # And the settings normaliser agrees with the helper.
    assert AppSettings._normalize_first_week_of_year_rule("nonsense") == "iso"
    assert AppSettings._normalize_first_week_of_year_rule("JAN1") == "jan1"


def test_wt_m2a3_helper_returns_year_and_week():
    """WT-F2b — never a bare week number.

    2026-12-28 and 2027-01-01 are both ISO week 53; only the year separates
    them, and a bare 53 cannot.
    """
    a = year_and_week("2026-12-28", RULE_ISO, 0)
    b = year_and_week("2027-01-01", RULE_ISO, 0)
    assert isinstance(a, tuple) and len(a) == 2
    assert a[1] == b[1] == 53
    assert a[0] == b[0] == 2026

    across = year_and_week("2027-01-04", RULE_ISO, 0)
    assert across == (2027, 1)
    assert across[1] == 1 and a[1] == 53, (
        "the week numbers alone would compare backwards across the boundary"
    )

    assert year_and_week(None) is None
    assert year_and_week("not a date") is None


def test_wt_m2a_week_identity_follows_first_day_of_week():
    """Identity is settings-driven; the number follows the rule (WT-F2c)."""
    assert week_calendar.week_start("2026-02-25", 0).isoformat() == "2026-02-23"  # Monday
    assert week_calendar.week_start("2026-02-25", 6).isoformat() == "2026-02-22"  # Sunday
    assert week_calendar.week_end("2026-02-25", 6).isoformat() == "2026-02-28"


def test_wt_m2a_completed_at_datetime_is_accepted():
    """``completed_at`` is a full ISO datetime (db_manager.py:191)."""
    assert week_calendar.coerce_date("2026-02-25T14:03:11.123456").isoformat() == "2026-02-25"
    assert year_and_week("2026-02-25T14:03:11", RULE_ISO, 0) == (2026, 9)


# --------------------------------------------------------------------------
# WT-M2.B — one owner
# --------------------------------------------------------------------------

# date_utils uses weekday() to skip weekends when shifting a date. That is
# business-day arithmetic, not week identity, and it must not be rewritten to
# ask a week calendar.
WEEK_MATH_ALLOWLIST = {"week_calendar.py", "date_utils.py"}

def _is_week_start_arithmetic(code: str) -> bool:
    """A line that derives a week boundary from ``weekday()`` itself.

    Deliberately blunt — ``weekday()`` and ``% 7`` on one line is week-start
    arithmetic in every form it takes in this codebase, and a narrower pattern
    missed ``(6 - value.weekday()) % 7`` on the first attempt.
    """
    return "weekday()" in code and "% 7" in code


def _source_files():
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def test_wt_m2b1_no_direct_week_math_callers():
    """No module computes a week number or a week start for itself.

    A single owner is the whole point: WT-F2c's three-way disagreement was not
    a typo, it was three modules each deciding what a week is.
    """
    iso_offenders = []
    start_offenders = []
    for path in _source_files():
        if path.name in WEEK_MATH_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            code = line.split("#", 1)[0]
            if "isocalendar()" in code:
                iso_offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}")
            if _is_week_start_arithmetic(code):
                start_offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}")

    assert not iso_offenders, (
        "isocalendar() called outside week_calendar.py — these discard the ISO "
        f"year (WT-F2b): {iso_offenders}"
    )
    assert not start_offenders, (
        "ad-hoc week-start arithmetic outside week_calendar.py — week identity "
        f"must have one owner (WT-F2c): {start_offenders}"
    )


def test_wt_m2b1_the_scan_can_actually_fail(tmp_path):
    """Guards the guard: a scan that matches nothing proves nothing (P24)."""
    assert _is_week_start_arithmetic("offset = (d.weekday() - first_day) % 7")
    assert _is_week_start_arithmetic("start += timedelta(days=(6 - value.weekday()) % 7)")
    assert not _is_week_start_arithmetic("if current_date.weekday() >= 5:")


def test_wt_m2b2_title_week_number_follows_setting(tmp_path, monkeypatch):
    """Changing the rule changes the generated title, via the editor's helper too."""
    from src.getmoredone.screens.item_editor import ItemEditorDialog
    from src.getmoredone import weekly_tactic_titles

    vps = make_vps(tmp_path)
    try:
        ape_id = seed_ape(vps)
        key_field = vps.db.conn.execute(
            "SELECT key_field FROM annual_plan_elements WHERE id = ?", (ape_id,)
        ).fetchone()["key_field"]

        # 2027-01-01 is ISO 2026-W53 but jan1 2027-W1 — a title that changes.
        iso_title = weekly_tactic_titles.canonical_weekly_tactic_title(
            key_field, "2027-01-01", WeekCalendar(0, RULE_ISO))
        jan1_title = weekly_tactic_titles.canonical_weekly_tactic_title(
            key_field, "2027-01-01", WeekCalendar(0, RULE_JAN1))
        assert iso_title.endswith(" - W53")
        assert jan1_title.endswith(" - W1")

        # WT-M6/P25 shape: the editor's own helper must follow the setting too,
        # not just the library underneath it.
        stub = SimpleNamespace(vps_manager=vps)

        def _settings(rule):
            return SimpleNamespace(first_day_of_week=0, first_week_of_year_rule=rule)

        monkeypatch.setattr(AppSettings, "load", staticmethod(lambda: _settings(RULE_ISO)))
        assert ItemEditorDialog._canonical_weekly_tactic_title(
            stub, "anything", ape_id, "2027-01-01").endswith(" - W53")

        monkeypatch.setattr(AppSettings, "load", staticmethod(lambda: _settings(RULE_JAN1)))
        assert ItemEditorDialog._canonical_weekly_tactic_title(
            stub, "anything", ape_id, "2027-01-01").endswith(" - W1")
    finally:
        vps.close()


def test_wt_m2b3_first_day_change_on_populated_db(tmp_path, monkeypatch):
    """Dirty state (P8): flipping first_day_of_week on a database with tactics.

    WT-INV3 forbids moving a ``weekly_tactic_start_date`` automatically, so the
    ones that no longer land on a week start must be *reported*, not rewritten.
    """
    from src.getmoredone.weekly_tactic_maintenance import audit_stamp_week_starts

    vps = make_vps(tmp_path, "flip.db")
    db_path = vps.db_manager.db.db_path
    try:
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = make_daily_item(vps, "Filed", weekly_tactic_id=tactic.id)
        stored = vps.db_manager.get_action_item(item.id)
        stored.weekly_tactic_start_date = "2026-02-23"   # a Monday
        vps.db_manager.update_action_item(stored)

        monday = audit_stamp_week_starts(vps.db_manager.db.conn, WeekCalendar(0))
        assert monday["checked"] == 1
        assert monday["misaligned"] == 0

        sunday = audit_stamp_week_starts(vps.db_manager.db.conn, WeekCalendar(6))
        assert sunday["misaligned"] == 1, "a Monday stamp is mid-week under Sunday weeks"
        assert sunday["details"][0]["stamp"] == "2026-02-23"
        assert sunday["details"][0]["week_start_now"] == "2026-02-22"

        # The stamp itself is untouched by the audit (WT-INV3).
        assert vps.db_manager.get_action_item(item.id).weekly_tactic_start_date == "2026-02-23"
    finally:
        vps.close()

    monkeypatch.setattr(
        AppSettings, "load",
        staticmethod(lambda: SimpleNamespace(first_day_of_week=6,
                                             first_week_of_year_rule=RULE_ISO)),
    )
    reopened = DatabaseManager(db_path)
    try:
        report = reopened.db.weekly_tactic_migration_report
        assert report["stamp_audit"]["misaligned"] == 1, (
            "the migration must surface the misalignment, not pass silently"
        )
        row = reopened.db.conn.execute(
            "SELECT weekly_tactic_start_date FROM action_items "
            "WHERE weekly_tactic_start_date IS NOT NULL"
        ).fetchone()
        assert row["weekly_tactic_start_date"] == "2026-02-23", "WT-INV3: never rewritten"
    finally:
        reopened.close()
