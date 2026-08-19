"""Shared fixtures for the Weekly Tactic scheduling tests.

Purpose: build a real VSP lineage, because a Weekly Tactic is only meaningful
         with an Annual Plan Element behind it (WT-M1.C.4).
Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1c4

Not named ``test_*`` on purpose — it holds helpers, not tests.
"""

from typing import Optional

from src.getmoredone.models import ActionItem
from src.getmoredone.vps_manager import VPSManager


def make_vps(tmp_path, name: str = "weekly_tactic.db") -> VPSManager:
    """A VPSManager on a fresh temporary database."""
    return VPSManager(str(tmp_path / name))


def seed_ape(
    vps: VPSManager,
    year: int = 2026,
    subsegment: str = "Living Systems",
    key_field: str = "Blog",
) -> str:
    """Create a full vision -> annual lineage and return the APE id.

    Goes through the real creators rather than raw INSERTs, so the tests
    exercise the same rows the app builds.
    """
    segment_name = vps.get_all_segments(active_only=False)[0]["name"]
    vps.create_vision_subsegment(segment_name, subsegment)
    vision_element_id = vps.create_or_get_vision_element(
        segment_name, subsegment, key_field
    )
    created = vps.create_annual_records_from_vision_element(year, vision_element_id)
    return created["annual_plan_element_id"]


def seed_second_ape(
    vps: VPSManager,
    year: int = 2026,
    subsegment: str = "Other Systems",
    key_field: str = "Podcast",
) -> str:
    """A second, independent lineage — for tests that need two APEs."""
    return seed_ape(vps, year=year, subsegment=subsegment, key_field=key_field)


def make_week_item(
    vps: VPSManager,
    ape_id: str,
    start: str = "2026-02-23",
    due: str = "2026-03-01",
    title: str = "Week",
) -> ActionItem:
    """A Weekly Tactic (``item_type='week'``) on the given APE."""
    item = ActionItem(
        who="VSP",
        title=title,
        start_date=start,
        due_date=due,
        item_type="week",
        annual_plan_element_id=ape_id,
    )
    vps.db_manager.create_action_item(item, apply_defaults=False)
    return item


def make_daily_item(
    vps: VPSManager,
    title: str = "Task",
    start: str = "2026-02-25",
    due: str = "2026-02-25",
    weekly_tactic_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    refile: bool = True,
) -> ActionItem:
    """An ordinary Action Item.

    ``refile=False`` writes the tactic link exactly as given, without the
    create-time re-file. The dedupe and repair tests need it: they seed the
    dirty state those routines exist to clean up, and the app can no longer
    produce that state through its own paths.
    """
    item = ActionItem(
        who="Self",
        title=title,
        start_date=start,
        due_date=due,
        weekly_tactic_id=weekly_tactic_id,
        parent_id=parent_id,
    )
    vps.db_manager.create_action_item(item, apply_defaults=False, refile=refile)
    return item
