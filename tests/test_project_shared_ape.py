"""Regression tests: multiple project boards may share one Annual Plan Element.

An earlier schema created UNIQUE INDEX idx_project_boards_unique_ape, which made
the project editor's Save silently fail (UNIQUE constraint) whenever a project was
linked to an APE already used by another project — including a shared catch-all
default. The migration drops that index; these tests lock in the new behavior.
"""

import os
import tempfile

import pytest

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.vps_manager import VPSManager
from src.getmoredone.models import ProjectBoard


@pytest.fixture
def managers():
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    db_mgr = DatabaseManager(temp_file.name)
    vps_mgr = VPSManager(temp_file.name)
    yield db_mgr, vps_mgr
    db_mgr.close()
    vps_mgr.close()
    if os.path.exists(temp_file.name):
        os.unlink(temp_file.name)


def _seed_ape(vps_mgr: VPSManager, segment_name: str, subsegment: str, category: str) -> str:
    vps_mgr.create_vision_subsegment(segment_name, subsegment)
    ve_id = vps_mgr.create_or_get_vision_element(segment_name, subsegment, category)
    ids = vps_mgr.create_annual_records_from_vision_element(2026, ve_id)
    return ids["annual_plan_element_id"]


def test_unique_ape_index_is_dropped(managers):
    """The 1:1 APE constraint index must not exist after init/migration."""
    db_mgr, _ = managers
    row = db_mgr.db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_project_boards_unique_ape'"
    ).fetchone()
    assert row is None


def test_two_projects_can_share_one_ape(managers):
    """Creating two boards on the same APE must not raise and both persist."""
    db_mgr, vps_mgr = managers
    seg = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id = _seed_ape(vps_mgr, seg, "Projects", "Projects")

    id1 = db_mgr.create_project_board(ProjectBoard(title="Catch-all A", annual_plan_element_id=ape_id))
    id2 = db_mgr.create_project_board(ProjectBoard(title="Catch-all B", annual_plan_element_id=ape_id))

    assert id1 != id2
    assert db_mgr.get_project_board(id1).annual_plan_element_id == ape_id
    assert db_mgr.get_project_board(id2).annual_plan_element_id == ape_id


def test_update_links_existing_project_to_shared_ape(managers):
    """Editing a project to point at an already-used APE must persist (the
    original 'Save does nothing' bug)."""
    db_mgr, vps_mgr = managers
    seg = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id = _seed_ape(vps_mgr, seg, "Projects", "Projects")

    # First board takes the APE; second starts with no APE.
    db_mgr.create_project_board(ProjectBoard(title="First", annual_plan_element_id=ape_id))
    target_id = db_mgr.create_project_board(ProjectBoard(title="Second", annual_plan_element_id=None))

    board = db_mgr.get_project_board(target_id)
    board.annual_plan_element_id = ape_id
    db_mgr.update_project_board(board)  # must NOT raise UNIQUE constraint

    assert db_mgr.get_project_board(target_id).annual_plan_element_id == ape_id


def test_shared_ape_boards_resolve_segment_lineage(managers):
    """Boards sharing an APE each surface the APE's segment lineage (drives the
    Schedule-tab segment/subsegment filter and card color)."""
    db_mgr, vps_mgr = managers
    seg = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id = _seed_ape(vps_mgr, seg, "Projects", "Projects")

    db_mgr.create_project_board(ProjectBoard(title="A", annual_plan_element_id=ape_id))
    db_mgr.create_project_board(ProjectBoard(title="B", annual_plan_element_id=ape_id))

    shared = [
        b for b in db_mgr.get_project_boards()
        if b.get("annual_plan_element_id") == ape_id
    ]
    assert len(shared) >= 2
    for board in shared:
        assert board.get("segment_name") == seg
        assert board.get("subsegment_name") == "Projects"
