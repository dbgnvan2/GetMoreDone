"""Re-filing an Action Item into the Weekly Tactic that covers its start date.

Purpose: move an item's week membership when its dates move, creating any
         missing Quarter / Month / Week scaffolding — including across a year.
Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m3
         docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4
Tests:   tests/test_weekly_tactic_linking.py
         tests/test_weekly_tactic_cascade.py

Imports no VPS module at load time: ``db_manager`` imports this, and
``vps_manager`` imports ``db_manager``. The VPS manager arrives as an argument,
or is built lazily on the same connection.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from . import week_calendar
from .models import ActionItem
from .weekly_tactic_logging import get_weekly_tactic_logger
from .weekly_tactic_titles import canonical_weekly_tactic_title, title_prefix

logger = get_weekly_tactic_logger()

# The editorial fields a year rollover creates blank (WT-D7a). Structural
# fields — every FK and the segment/subsegment/category/key_field lineage — are
# copied or re-pointed; editorial text is never copied forward and never
# invented.
ROLLOVER_BLANK_FIELDS = {
    "annual_visions": ("title", "vision_statement", "key_priorities"),
    "annual_plans": ("theme", "objective", "description"),
}

QUARTER_OF_MONTH = {
    1: 1, 2: 1, 3: 1,
    4: 2, 5: 2, 6: 2,
    7: 3, 8: 3, 9: 3,
    10: 4, 11: 4, 12: 4,
}


@dataclass
class CascadeReport:
    """What a re-file did, in enough detail to show the user.

    Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4c4
    Tests: tests/test_weekly_tactic_cascade.py::test_wt_m4c4_rollover_returns_report_and_bool_callers_unbroken

    A new type, not a changed return: ``assign_ape_to_quarter`` and
    ``assign_ape_to_month`` keep their bare-boolean contract, which
    ``tests/test_vps_hub_crud.py`` asserts with ``is True`` (WT-F13, P22).
    """

    item_id: Optional[str] = None
    tactic_id: Optional[str] = None
    previous_tactic_id: Optional[str] = None
    target_year: Optional[int] = None
    week_start: Optional[str] = None
    created: List[Dict[str, str]] = field(default_factory=list)
    stubs: List[Dict[str, str]] = field(default_factory=list)
    moved_dates: Optional[Dict[str, Optional[str]]] = None

    def record(self, kind: str, record_id: str, label: str = "", stub: bool = False):
        entry = {"kind": kind, "id": record_id, "label": label}
        self.created.append(entry)
        if stub:
            self.stubs.append(entry)

    @property
    def created_anything(self) -> bool:
        return bool(self.created)

    def describe(self) -> str:
        """One human sentence naming what was created, or an empty string."""
        if not self.created:
            return ""
        names = ", ".join(
            f"{entry['kind'].replace('_', ' ')} {entry['label']}".strip()
            for entry in self.created
        )
        text = f"Created {len(self.created)} planning record(s): {names}."
        if self.stubs:
            text += (
                f" {len(self.stubs)} were created blank by the year rollover and "
                "need your words."
            )
        return text


def tactic_of(item: Optional[ActionItem]) -> Optional[str]:
    """WT-M3.D.1 — the one predicate that decides whether an item is week-filed.

    Purpose: WT-INV6 says an item with no Weekly Tactic is never modified by any
             rule in this spec. That is only enforceable if exactly one place
             decides what "has a Weekly Tactic" means.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m3d1
    Tests:   tests/test_weekly_tactic_linking.py::test_wt_m3d1_single_tactic_predicate
    """
    if item is None:
        return None
    tactic_id = getattr(item, "weekly_tactic_id", None)
    return tactic_id or None


def bring_into_week(
    item: ActionItem,
    week_start: date,
    week_end: date,
) -> Dict[str, Optional[str]]:
    """WT-M3.B — move an item's dates into a week, in a defined order.

    Purpose: shift ``start_date`` and ``due_date`` by whole weeks so the weekday
             survives; then, only if ``due_date`` still falls outside, clamp it
             to the week end.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m3b
    Tests:   tests/test_weekly_tactic_linking.py::test_wt_m3b1_whole_week_shift_preserves_weekday
             tests/test_weekly_tactic_linking.py::test_wt_m3b2_multi_week_item_due_date_clamped

    The clamp overrides weekday preservation, because WT-D5 says an Action Item
    never spans weeks. A NULL date is handled explicitly rather than by
    arithmetic on None (WT-M3.B.4): a missing start becomes the week start, and
    a missing due is left missing.
    """
    before = {"start_date": item.start_date, "due_date": item.due_date}

    start = week_calendar.coerce_date(item.start_date)
    due = week_calendar.coerce_date(item.due_date)

    if start is None:
        # Nothing to preserve the weekday of. Land on the week start.
        new_start = week_start
        shift = None
    else:
        # Whole weeks only, so a Thursday stays a Thursday.
        shift = timedelta(days=(week_start - week_calendar.week_start(
            start, _first_day_from_week_start(week_start))).days)
        new_start = start + shift

    if due is None:
        new_due = None
    elif shift is None:
        new_due = week_end
    else:
        new_due = due + shift

    if new_due is not None and new_due > week_end:
        new_due = week_end          # WT-D5: never spans weeks
    if new_due is not None and new_due < new_start:
        new_due = new_start

    item.start_date = new_start.isoformat()
    item.due_date = new_due.isoformat() if new_due is not None else None

    return {
        "from_start": before["start_date"],
        "from_due": before["due_date"],
        "to_start": item.start_date,
        "to_due": item.due_date,
    }


def _first_day_from_week_start(week_start: date) -> int:
    """The first-day-of-week implied by a week's own start date."""
    return week_start.weekday()


class WeeklyTacticEngine:
    """Re-files an Action Item and builds whatever plan records that needs.

    Purpose: one object owns the whole WT-M3/WT-M4/WT-M5 behaviour, so the three
             hooked ``db_manager`` methods share it rather than each having a
             version.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4
    Tests:   tests/test_weekly_tactic_cascade.py
    """

    def __init__(self, db_manager, vps_manager=None, calendar=None):
        self.db_manager = db_manager
        self._vps = vps_manager
        self.calendar = calendar or week_calendar.WeekCalendar.from_settings()

    # -- plumbing ---------------------------------------------------------

    @property
    def conn(self):
        return self.db_manager.db.conn

    @property
    def vps(self):
        """The VPS manager, built lazily on the *same* connection.

        Imported here rather than at module load: ``vps_manager`` imports
        ``db_manager``, which imports this module.
        """
        if self._vps is None:
            from .vps_manager import VPSManager
            self._vps = VPSManager(db_manager=self.db_manager)
        return self._vps

    def _row(self, table: str, row_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not row_id:
            return None
        row = self.conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (row_id,)
        ).fetchone()
        return dict(row) if row else None

    # -- WT-M3.A: the original-week stamp ---------------------------------

    def stamp_original_week(self, item: ActionItem, week_start: date) -> bool:
        """WT-INV3 — write ``weekly_tactic_start_date`` once, and never again.

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m3a
        Tests: tests/test_weekly_tactic_linking.py::test_wt_m3a1_first_attach_stamps_original_week

        Returns True when this call stamped it. A stamp that survives its
        tactic's deletion is kept, not overwritten — it is the only record of
        when the item was originally meant to start (WT-M3.A.4).
        """
        if item.weekly_tactic_start_date:
            return False
        item.weekly_tactic_start_date = week_start.isoformat()
        return True

    def stale_stamp(self, item: ActionItem) -> Optional[str]:
        """A stamp left behind by a tactic that no longer exists (WT-M3.A.4)."""
        if not item.weekly_tactic_start_date or tactic_of(item):
            return None
        return item.weekly_tactic_start_date

    # -- WT-M4.B: quarter / month scaffolding ------------------------------

    def _ensure_quarter_and_month(self, ape: Dict[str, Any], target: date,
                                  report: CascadeReport) -> None:
        """WT-D6 — walk back from the APE, creating only what is missing.

        New Quarter only when the move crosses a quarter end and none exists;
        new Month only when it crosses a month end and none exists.
        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4b
        Tests: tests/test_weekly_tactic_cascade.py::test_wt_m4b2_creates_month_assignment_on_month_cross
        """
        month = target.month
        quarter = QUARTER_OF_MONTH[month]
        year = int(ape["year"])

        before_q = self._quarter_rows(ape, quarter, year)
        before_m = self._month_rows(ape, quarter, month, year)

        # assign_ape_to_month calls assign_ape_to_quarter itself, so one call
        # covers both levels and keeps their get-or-create logic in one place.
        self.vps.assign_ape_to_month(ape["id"], quarter, month)

        if not before_q:
            for row in self._quarter_rows(ape, quarter, year):
                report.record("quarter_initiative", row["id"],
                              f"Q{quarter} {year}")
                break
        if not before_m:
            for row in self._month_rows(ape, quarter, month, year):
                report.record("month_tactic", row["id"], f"M{month} {year}")
                break

    def _quarter_rows(self, ape: Dict[str, Any], quarter: int, year: int) -> List[Dict[str, Any]]:
        initiative = self.vps._find_annual_initiative_for_ape(ape)
        if not initiative:
            return []
        return self.vps.get_quarter_initiatives(
            annual_initiative_id=initiative["id"], quarter=quarter,
            year=year, active_only=False,
        )

    def _month_rows(self, ape: Dict[str, Any], quarter: int, month: int,
                    year: int) -> List[Dict[str, Any]]:
        quarter_rows = self._quarter_rows(ape, quarter, year)
        if not quarter_rows:
            return []
        return self.vps.get_month_tactics(
            quarter_initiative_id=quarter_rows[0]["id"], month=month,
            year=year, active_only=False,
        )

    # -- WT-M4.C: year rollover -------------------------------------------

    def ape_for_year(self, ape: Dict[str, Any], target_year: int,
                     report: CascadeReport) -> Dict[str, Any]:
        """The Annual Plan Element for this lineage in ``target_year``.

        Purpose: within a year that is the same APE row; across a year it is the
                 corresponding row, built if absent (WT-D7).
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4c
        Tests:   tests/test_weekly_tactic_cascade.py::test_wt_m4c1_year_rollover_builds_exactly_one_row_per_table
                 tests/test_weekly_tactic_cascade.py::test_wt_m4c2_rollover_preserves_vision_element_lineage

        The lineage is keyed on ``vision_element_id``, and the target year's
        rows are built from the taxonomy rather than copied from last year's —
        which is what re-points ``annual_vision_element_id`` at the new year's
        row instead of carrying the old one across (WT-M4.C.3a).

        Both annual tables carry ``UNIQUE(year, vision_element_id)``, so a
        second move into the same year finds the rows rather than making more
        (WT-M4.C.5). Intermediate years are never fabricated (WT-M4.C.7).
        """
        if int(ape["year"]) == target_year:
            return ape

        existing = self.conn.execute(
            "SELECT * FROM annual_plan_elements WHERE year = ? AND vision_element_id = ?",
            (target_year, ape["vision_element_id"]),
        ).fetchone()
        if existing:
            return dict(existing)

        before = self._annual_row_ids(target_year, ape["vision_element_id"])
        created = self.vps.create_annual_records_from_vision_element(
            target_year, ape["vision_element_id"],
            commit=False,
            # Q2: a project spans any timeframe, so a new year needs no board.
            ensure_project_board=False,
        )
        after = self._annual_row_ids(target_year, ape["vision_element_id"])
        for kind in ("annual_vision_elements", "annual_plan_elements"):
            if after.get(kind) and after[kind] != before.get(kind):
                report.record(kind, after[kind], str(target_year))

        new_ape = self._row("annual_plan_elements", created["annual_plan_element_id"])
        # Building the annual initiative pulls the vision/plan chain in behind
        # it, so the stubs are created and flagged here rather than later.
        self._ensure_annual_chain(new_ape, report)
        return new_ape

    def _annual_row_ids(self, year: int, vision_element_id: str) -> Dict[str, Optional[str]]:
        out: Dict[str, Optional[str]] = {}
        for table in ("annual_vision_elements", "annual_plan_elements"):
            row = self.conn.execute(
                f"SELECT id FROM {table} WHERE year = ? AND vision_element_id = ?",
                (year, vision_element_id),
            ).fetchone()
            out[table] = row["id"] if row else None
        return out

    def _ensure_annual_chain(self, ape: Dict[str, Any], report: CascadeReport) -> None:
        """Build tl_vision / annual_vision / annual_plan / annual_initiative.

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4c3
        Tests: tests/test_weekly_tactic_cascade.py::test_wt_m4c3_editorial_fields_blank_and_flagged

        Rows created here are marked ``created_by_rollover = 1`` and their
        editorial fields left blank (WT-D7a, WT-D13). Discovery is by that flag,
        never by emptiness: a hand-authored vision with a blank statement is not
        a stub (WT-M4.C.3b).
        """
        before = {
            table: self._ids(table)
            for table in ("annual_visions", "annual_plans", "annual_initiatives")
        }
        self.vps._get_or_create_annual_initiative_for_ape(ape, created_by_rollover=True)

        for table in ("annual_visions", "annual_plans", "annual_initiatives"):
            for row_id in self._ids(table) - before[table]:
                stub = table in ROLLOVER_BLANK_FIELDS
                report.record(table, row_id, str(ape["year"]), stub=stub)

    def _ids(self, table: str) -> set:
        return {row["id"] for row in self.conn.execute(f"SELECT id FROM {table}")}

    # -- the week item itself ---------------------------------------------

    def find_tactic(self, ape_id: str, week_start: date) -> Optional[Dict[str, Any]]:
        """The Weekly Tactic for this APE and week, if it exists.

        ``ORDER BY created_at, id`` so the choice is the same on every run even
        when the WT-INV5 index could not be created (WT-M4.B.5).
        """
        row = self.conn.execute(
            """
            SELECT * FROM action_items
            WHERE item_type = 'week'
              AND annual_plan_element_id = ?
              AND start_date = ?
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (ape_id, week_start.isoformat()),
        ).fetchone()
        return dict(row) if row else None

    def ensure_tactic(self, ape: Dict[str, Any], week_start: date,
                      report: CascadeReport) -> Dict[str, Any]:
        """Get or create the Weekly Tactic for an APE's week (WT-D6).

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4b1
        Tests: tests/test_weekly_tactic_cascade.py::test_wt_m4b1_creates_week_only_within_month
        """
        found = self.find_tactic(ape["id"], week_start)
        if found:
            return found

        week_end = week_start + timedelta(days=6)
        title = canonical_weekly_tactic_title(
            ape["key_field"], week_start, self.calendar
        ) or f"{title_prefix(ape['key_field']) or 'Weekly Tactic'} - {week_start.isoformat()}"

        tactic = ActionItem(
            who=ape["segment_name"] or "VSP",
            title=title,
            description=(
                f"Weekly action item for {ape['key_field']} "
                f"(starts {week_start.isoformat()})"
            ),
            start_date=week_start.isoformat(),
            due_date=week_end.isoformat(),
            category="VSP",
            status="open",
            item_type="week",
            annual_plan_element_id=ape["id"],
            segment_description_id=self.vps.resolve_segment_id_by_name(ape["segment_name"]),
        )
        self.db_manager.create_action_item(tactic, apply_defaults=False)
        report.record("weekly_tactic", tactic.id, title)
        return self._row("action_items", tactic.id)

    # -- WT-M4.A: the re-file itself ---------------------------------------

    def plan_refile(self, item: ActionItem, target_date) -> Optional[CascadeReport]:
        """Where ``item`` should be filed for ``target_date``, building the way there.

        Purpose: the whole WT-M4 cascade, in one call, for an item that already
                 has a tactic.
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4a
        Tests:   tests/test_weekly_tactic_cascade.py::test_wt_m4a1_relink_to_existing_week_creates_nothing
                 tests/test_weekly_tactic_cascade.py::test_wt_m4a2_lineage_inherited_from_current_tactic

        Returns None — changing nothing — when the item has no tactic (WT-INV6,
        WT-M4.D.4) or the target date is unusable. The lineage comes from the
        item's *current* tactic, never from whatever tactic covers today.
        """
        current_tactic_id = tactic_of(item)
        if not current_tactic_id:
            return None

        target = week_calendar.coerce_date(target_date)
        if target is None:
            return None

        current = self._row("action_items", current_tactic_id)
        if not current:
            # The tactic was deleted underneath us (ON DELETE SET NULL has
            # already cleared the column on a committed delete; this is the
            # in-memory case). Nothing to inherit a lineage from.
            return None

        source_ape = self._row("annual_plan_elements", current["annual_plan_element_id"])
        if not source_ape:
            return None

        week_start = self.calendar.start(target)
        week_end = week_start + timedelta(days=6)
        report = CascadeReport(
            item_id=item.id,
            previous_tactic_id=current_tactic_id,
            target_year=week_start.year,
            week_start=week_start.isoformat(),
        )

        # A week can belong to the year its start date falls in, which is what
        # decides the lineage year — not the target date's own year.
        ape = self.ape_for_year(source_ape, week_start.year, report)
        self._ensure_quarter_and_month(ape, week_start, report)
        tactic = self.ensure_tactic(ape, week_start, report)

        item.weekly_tactic_id = tactic["id"]
        # WT-M4.A.3 — the item's own APE is reconciled to its tactic's, so the
        # two can never disagree about which plan element it belongs to.
        item.annual_plan_element_id = ape["id"]
        self.stamp_original_week(item, week_calendar.week_start(
            week_calendar.coerce_date(current["start_date"]) or week_start,
            self.calendar.first_day,
        ))
        report.moved_dates = bring_into_week(item, week_start, week_end)
        report.tactic_id = tactic["id"]
        return report
