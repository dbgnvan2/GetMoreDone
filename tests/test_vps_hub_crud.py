from pathlib import Path

import pytest

from src.getmoredone.models import ActionItem, ProjectBoard
from src.getmoredone.vps_manager import (
    VPSManager,
    ProjectBoardsAttachedError,
    VisionElementHasDependentsError,
)


def _manager(tmp_path: Path) -> VPSManager:
    db_path = tmp_path / "vps_hub_crud.db"
    return VPSManager(str(db_path))


def _seed_segment_and_subsegment(manager: VPSManager, sub_name: str = "Archive") -> tuple[str, str]:
    seg_name = manager.get_all_segments(active_only=False)[0]["name"]
    manager.create_vision_subsegment(seg_name, sub_name)
    return seg_name, sub_name


def test_update_vision_element_updates_mirror_rows(tmp_path):
    manager = _manager(tmp_path)
    try:
        segment_name, sub_name = _seed_segment_and_subsegment(manager, "Archive")
        ve_id = manager.create_or_get_vision_element(segment_name, sub_name, "Archive")
        manager.create_annual_records_from_vision_element(2026, ve_id)

        updated = manager.update_vision_element(
            ve_id,
            segment_name,
            sub_name,
            "Website",
            "Ship weekly content cadence",
        )
        assert updated is True

        row = manager.db.conn.execute(
            "SELECT key_field, vision_text FROM vision_elements WHERE id = ?",
            (ve_id,),
        ).fetchone()
        assert row and row["key_field"] == f"{segment_name}|{sub_name}|Website"
        assert row["vision_text"] == "Ship weekly content cadence"

        ave = manager.db.conn.execute(
            "SELECT key_field FROM annual_vision_elements WHERE year = 2026 AND vision_element_id = ?",
            (ve_id,),
        ).fetchone()
        assert ave and ave["key_field"] == f"{segment_name}|{sub_name}|Website"

        ape = manager.db.conn.execute(
            "SELECT key_field FROM annual_plan_elements WHERE year = 2026 AND vision_element_id = ?",
            (ve_id,),
        ).fetchone()
        assert ape and ape["key_field"] == f"{segment_name}|{sub_name}|Website"
    finally:
        manager.close()


def test_delete_annual_records_for_vision_element_clears_links(tmp_path):
    manager = _manager(tmp_path)
    try:
        segment_name, sub_name = _seed_segment_and_subsegment(manager, "Archive")
        ve_id = manager.create_or_get_vision_element(segment_name, sub_name, "Archive")
        ids = manager.create_annual_records_from_vision_element(2026, ve_id)
        ape_id = ids["annual_plan_element_id"]

        board_row = manager.db.conn.execute(
            "SELECT id FROM project_boards WHERE annual_plan_element_id = ?",
            (ape_id,),
        ).fetchone()
        assert board_row is not None

        weekly = ActionItem(
            who="VSP",
            title="Weekly Parent",
            item_type="week",
            start_date="2026-02-23",
            due_date="2026-02-23",
            annual_plan_element_id=ape_id,
        )
        manager.db_manager.create_action_item(weekly, apply_defaults=False)

        deleted = manager.delete_annual_records_for_vision_element(2026, ve_id)
        assert deleted is True

        ave_count = manager.db.conn.execute(
            "SELECT COUNT(*) AS c FROM annual_vision_elements WHERE year = 2026 AND vision_element_id = ?",
            (ve_id,),
        ).fetchone()["c"]
        ape_count = manager.db.conn.execute(
            "SELECT COUNT(*) AS c FROM annual_plan_elements WHERE year = 2026 AND vision_element_id = ?",
            (ve_id,),
        ).fetchone()["c"]
        assert ave_count == 0
        assert ape_count == 0

        linked = manager.db.conn.execute(
            "SELECT annual_plan_element_id FROM action_items WHERE id = ?",
            (weekly.id,),
        ).fetchone()
        assert linked and linked["annual_plan_element_id"] is None

        board_row = manager.db.conn.execute(
            "SELECT id FROM project_boards WHERE annual_plan_element_id = ?",
            (ape_id,),
        ).fetchone()
        assert board_row is None
    finally:
        manager.close()


def test_delete_annual_record_blocked_when_extra_projects_attached(tmp_path):
    """Multiple project boards share one APE -> deletion is refused, none lost."""
    manager = _manager(tmp_path)
    try:
        segment_name, sub_name = _seed_segment_and_subsegment(manager, "Projects")
        ve_id = manager.create_or_get_vision_element(segment_name, sub_name, "Projects")
        ids = manager.create_annual_records_from_vision_element(2026, ve_id)
        ape_id = ids["annual_plan_element_id"]

        # A user-created project parked on the same (catch-all) APE.
        manager.db_manager.create_project_board(
            ProjectBoard(title="My Parked Project", annual_plan_element_id=ape_id)
        )

        with pytest.raises(ProjectBoardsAttachedError) as excinfo:
            manager.delete_annual_records_for_vision_element(2026, ve_id)

        assert "My Parked Project" in excinfo.value.board_titles

        # Nothing was deleted.
        ape_count = manager.db.conn.execute(
            "SELECT COUNT(*) AS c FROM annual_plan_elements WHERE id = ?",
            (ape_id,),
        ).fetchone()["c"]
        board_count = manager.db.conn.execute(
            "SELECT COUNT(*) AS c FROM project_boards WHERE annual_plan_element_id = ?",
            (ape_id,),
        ).fetchone()["c"]
        assert ape_count == 1
        assert board_count == 2
    finally:
        manager.close()


def test_delete_annual_record_blocked_when_board_has_items(tmp_path):
    """A single board that has linked action items also blocks deletion."""
    manager = _manager(tmp_path)
    try:
        segment_name, sub_name = _seed_segment_and_subsegment(manager, "Projects")
        ve_id = manager.create_or_get_vision_element(segment_name, sub_name, "Projects")
        ids = manager.create_annual_records_from_vision_element(2026, ve_id)
        ape_id = ids["annual_plan_element_id"]

        board_id = manager.db.conn.execute(
            "SELECT id FROM project_boards WHERE annual_plan_element_id = ?",
            (ape_id,),
        ).fetchone()["id"]

        item = ActionItem(who="Me", title="Real Work")
        manager.db_manager.create_action_item(item, apply_defaults=False)
        manager.db_manager.link_action_item_to_project_board(board_id, item.id)

        with pytest.raises(ProjectBoardsAttachedError):
            manager.delete_annual_records_for_vision_element(2026, ve_id)
    finally:
        manager.close()


def test_delete_vision_element_blocked_when_children_exist(tmp_path):
    """A Vision Element with annual records / projects cannot be deleted."""
    manager = _manager(tmp_path)
    try:
        segment_name, sub_name = _seed_segment_and_subsegment(manager, "Projects")
        ve_id = manager.create_or_get_vision_element(segment_name, sub_name, "Projects")
        manager.create_annual_records_from_vision_element(2026, ve_id)  # auto-creates APE + board

        with pytest.raises(VisionElementHasDependentsError) as excinfo:
            manager.delete_vision_element(ve_id)

        # Year shows up in the human-readable summary.
        assert any("2026" in line for line in excinfo.value.summary_lines)

        # Nothing deleted.
        still_there = manager.db.conn.execute(
            "SELECT COUNT(*) AS c FROM vision_elements WHERE id = ?", (ve_id,)
        ).fetchone()["c"]
        assert still_there == 1
    finally:
        manager.close()


def test_delete_vision_element_succeeds_when_no_children(tmp_path):
    """A Vision Element with no annual records / projects deletes normally."""
    manager = _manager(tmp_path)
    try:
        segment_name, sub_name = _seed_segment_and_subsegment(manager, "Projects")
        ve_id = manager.create_or_get_vision_element(segment_name, sub_name, "Projects")
        # No annual records created -> no dependents.

        assert manager.delete_vision_element(ve_id) is True
        gone = manager.db.conn.execute(
            "SELECT COUNT(*) AS c FROM vision_elements WHERE id = ?", (ve_id,)
        ).fetchone()["c"]
        assert gone == 0
    finally:
        manager.close()


def test_delete_weekly_action_item_removes_children(tmp_path):
    manager = _manager(tmp_path)
    try:
        weekly = ActionItem(
            who="VSP",
            title="Weekly Parent",
            item_type="week",
            start_date="2026-02-23",
            due_date="2026-02-23",
        )
        manager.db_manager.create_action_item(weekly, apply_defaults=False)

        child = ActionItem(
            who="VSP",
            title="Child Item",
            parent_id=weekly.id,
            start_date="2026-02-23",
            due_date="2026-02-23",
        )
        manager.db_manager.create_action_item(child, apply_defaults=False)

        deleted = manager.delete_weekly_action_item(weekly.id)
        assert deleted is True

        parent_row = manager.db.conn.execute(
            "SELECT id FROM action_items WHERE id = ?",
            (weekly.id,),
        ).fetchone()
        child_row = manager.db.conn.execute(
            "SELECT id FROM action_items WHERE id = ?",
            (child.id,),
        ).fetchone()
        assert parent_row is None
        assert child_row is None
    finally:
        manager.close()


def test_update_level_vision_texts(tmp_path):
    manager = _manager(tmp_path)
    try:
        segment_name, sub_name = _seed_segment_and_subsegment(manager, "Writing")
        ve_id = manager.create_or_get_vision_element(segment_name, sub_name, "APW Book")
        row = manager.get_vision_elements()[0]
        assert row["id"] == ve_id

        assert manager.update_segment_vision_text(row["segment_id"], "Creative long-term vision")
        assert manager.update_subsegment_vision_text(row["subsegment_id"], "Writing craft vision")
        assert manager.update_category_vision_text(row["category_id"], "APW Book publishing vision")

        refreshed = manager.get_vision_elements()[0]
        assert refreshed["segment_vision_text"] == "Creative long-term vision"
        assert refreshed["subsegment_vision_text"] == "Writing craft vision"
        assert refreshed["category_vision_text"] == "APW Book publishing vision"
    finally:
        manager.close()


def test_rename_segment_subsegment_category_propagates_keys(tmp_path):
    manager = _manager(tmp_path)
    try:
        segment_name, sub_name = _seed_segment_and_subsegment(manager, "Writing")
        ve_id = manager.create_or_get_vision_element(segment_name, sub_name, "APW Book")
        manager.create_annual_records_from_vision_element(2026, ve_id)
        row = manager.get_vision_elements()[0]

        assert manager.rename_vision_segment(row["segment_id"], "Creative Work")
        row = manager.get_vision_elements()[0]
        assert manager.rename_vision_subsegment(row["subsegment_id"], "Writing Studio")
        row = manager.get_vision_elements()[0]
        assert manager.rename_vision_category(row["category_id"], "APW Books")

        updated = manager.get_vision_elements()[0]
        assert updated["segment_name"] == "Creative Work"
        assert updated["subsegment_name"] == "Writing Studio"
        assert updated["category_name"] == "APW Books"
        assert updated["key_field"] == "Creative Work|Writing Studio|APW Books"

        ave = manager.db.conn.execute(
            "SELECT key_field, segment_name, subsegment_name, category_name FROM annual_vision_elements WHERE vision_element_id = ?",
            (ve_id,),
        ).fetchone()
        assert ave["key_field"] == "Creative Work|Writing Studio|APW Books"
        assert ave["segment_name"] == "Creative Work"
        assert ave["subsegment_name"] == "Writing Studio"
        assert ave["category_name"] == "APW Books"
    finally:
        manager.close()


def test_assign_ape_to_quarter_creates_quarter_initiative_and_flag(tmp_path):
    manager = _manager(tmp_path)
    try:
        segment_name, sub_name = _seed_segment_and_subsegment(manager, "Writing")
        ve_id = manager.create_or_get_vision_element(segment_name, sub_name, "APW Book")
        ids = manager.create_annual_records_from_vision_element(2026, ve_id)
        ape_id = ids["annual_plan_element_id"]

        assert manager.assign_ape_to_quarter(ape_id, 2) is True

        ape_row = manager.db.conn.execute(
            "SELECT q2 FROM annual_plan_elements WHERE id = ?",
            (ape_id,),
        ).fetchone()
        assert ape_row and ape_row["q2"] == 1

        annual_initiative = manager.db.conn.execute(
            "SELECT id FROM annual_initiatives WHERE year = 2026 AND title = ?",
            (f"{segment_name}|{sub_name}|APW Book",),
        ).fetchone()
        assert annual_initiative is not None

        quarter_row = manager.db.conn.execute(
            "SELECT quarter, year FROM quarter_initiatives WHERE annual_initiative_id = ?",
            (annual_initiative["id"],),
        ).fetchone()
        assert quarter_row and quarter_row["quarter"] == 2 and quarter_row["year"] == 2026
    finally:
        manager.close()


def test_assign_ape_to_month_creates_month_tactic_and_flag(tmp_path):
    manager = _manager(tmp_path)
    try:
        segment_name, sub_name = _seed_segment_and_subsegment(manager, "Writing")
        ve_id = manager.create_or_get_vision_element(segment_name, sub_name, "APW Book")
        ids = manager.create_annual_records_from_vision_element(2026, ve_id)
        ape_id = ids["annual_plan_element_id"]

        assert manager.assign_ape_to_month(ape_id, 2, 5) is True

        ape_row = manager.db.conn.execute(
            "SELECT q2, m5 FROM annual_plan_elements WHERE id = ?",
            (ape_id,),
        ).fetchone()
        assert ape_row and ape_row["q2"] == 1 and ape_row["m5"] == 1

        annual_initiative = manager.db.conn.execute(
            "SELECT id FROM annual_initiatives WHERE year = 2026 AND title = ?",
            (f"{segment_name}|{sub_name}|APW Book",),
        ).fetchone()
        assert annual_initiative is not None

        quarter_row = manager.db.conn.execute(
            "SELECT id FROM quarter_initiatives WHERE annual_initiative_id = ? AND quarter = 2 AND year = 2026",
            (annual_initiative["id"],),
        ).fetchone()
        assert quarter_row is not None

        month_row = manager.db.conn.execute(
            "SELECT month, year FROM month_tactics WHERE quarter_initiative_id = ? AND month = 5 AND year = 2026",
            (quarter_row["id"],),
        ).fetchone()
        assert month_row and month_row["month"] == 5 and month_row["year"] == 2026
    finally:
        manager.close()
