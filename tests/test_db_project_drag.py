"""
Tests for Project Board drag-and-drop database logic.
"""

import pytest
import tempfile
import os
from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.vps_manager import VPSManager
from src.getmoredone.models import ActionItem, ProjectBoard

@pytest.fixture
def db_manager():
    """Create a temporary database and VPS manager for testing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()

    db_mgr = DatabaseManager(temp_file.name)
    vps_mgr = VPSManager(temp_file.name)
    
    yield db_mgr, vps_mgr

    db_mgr.close()
    vps_mgr.close()
    if os.path.exists(temp_file.name):
        os.unlink(temp_file.name)

def _seed_ape(vps_mgr: VPSManager, segment_name: str, subsegment: str, category: str) -> str:
    """Helper to seed APE data."""
    vps_mgr.create_vision_subsegment(segment_name, subsegment)
    ve_id = vps_mgr.create_or_get_vision_element(segment_name, subsegment, category)
    ids = vps_mgr.create_annual_records_from_vision_element(2026, ve_id)
    return ids["annual_plan_element_id"]

def test_link_item_to_project_exclusive(db_manager):
    db_mgr, vps_mgr = db_manager
    
    # 1. Seed two APEs and their boards
    seg_name = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id1 = _seed_ape(vps_mgr, seg_name, "Sub 1", "Cat 1")
    ape_id2 = _seed_ape(vps_mgr, seg_name, "Sub 2", "Cat 2")
    
    # ensure_project_board_for_ape is called during seeding or we call it manually
    board_id1 = db_mgr.ensure_project_board_for_ape(ape_id1)
    board_id2 = db_mgr.ensure_project_board_for_ape(ape_id2)
    
    # 2. Create an action item
    item = ActionItem(who="TestUser", title="Task to Link")
    item_id = db_mgr.create_action_item(item, apply_defaults=False)
    
    # 3. Link to project 1
    db_mgr.link_item_to_project_exclusive(board_id1, item_id)
    
    # Verify link and APE sync
    links = db_mgr.get_project_board_ids_for_item(item_id)
    assert links == [board_id1]
    
    updated_item = db_mgr.get_action_item(item_id)
    assert updated_item.annual_plan_element_id == ape_id1
    
    # 4. Link to project 2 (replaces project 1)
    db_mgr.link_item_to_project_exclusive(board_id2, item_id)
    
    # Verify link replaced and APE updated
    links = db_mgr.get_project_board_ids_for_item(item_id)
    assert links == [board_id2]
    
    updated_item = db_mgr.get_action_item(item_id)
    assert updated_item.annual_plan_element_id == ape_id2

def test_get_unlinked_action_items(db_manager):
    db_mgr, vps_mgr = db_manager
    
    seg_name = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id = _seed_ape(vps_mgr, seg_name, "Sub 1", "Cat 1")
    board_id = db_mgr.ensure_project_board_for_ape(ape_id)
    
    # Create one linked item
    item_linked = ActionItem(who="Test", title="Linked Task")
    item_linked_id = db_mgr.create_action_item(item_linked, apply_defaults=False)
    db_mgr.link_action_item_to_project_board(board_id, item_linked_id)
    
    # Create one unlinked item
    item_unlinked = ActionItem(who="Test", title="Unlinked Task")
    item_unlinked_id = db_mgr.create_action_item(item_unlinked, apply_defaults=False)
    
    unlinked_items = db_mgr.get_unlinked_action_items()
    unlinked_ids = [it.id for it in unlinked_items]
    
    assert item_unlinked_id in unlinked_ids
    assert item_linked_id not in unlinked_ids

def test_clear_item_project_links(db_manager):
    db_mgr, vps_mgr = db_manager
    
    seg_name = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id = _seed_ape(vps_mgr, seg_name, "Sub 1", "Cat 1")
    board_id = db_mgr.ensure_project_board_for_ape(ape_id)
    
    item = ActionItem(who="Test", title="Task to Clear", annual_plan_element_id=ape_id)
    item_id = db_mgr.create_action_item(item, apply_defaults=False)
    db_mgr.link_action_item_to_project_board(board_id, item_id)
    
    # Verify it is linked
    assert len(db_mgr.get_project_board_ids_for_item(item_id)) == 1
    
    # Clear links
    db_mgr.clear_item_project_links(item_id)
    
    # Verify unlinked and APE cleared
    assert len(db_mgr.get_project_board_ids_for_item(item_id)) == 0
    updated_item = db_mgr.get_action_item(item_id)
    assert updated_item.annual_plan_element_id is None
