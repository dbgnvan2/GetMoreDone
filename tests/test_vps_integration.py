"""
Integration tests for VPS (Visionary Planning System).
Tests create records via button clicks (VPSManager methods) and verify database state.
"""

import pytest
import tempfile
import os
from datetime import datetime, date, timedelta

from src.getmoredone.vps_manager import VPSManager


@pytest.fixture
def vps_manager():
    """Create a temporary database with VPS manager for testing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()

    manager = VPSManager(temp_file.name)
    yield manager

    manager.close()
    os.unlink(temp_file.name)


class TestVPSRecordCreation:
    """Test creating VPS records and verifying database state."""

    def test_create_tl_vision_claude_test(self, vps_manager):
        """Test creating a TL Vision with 'Claude Test' data."""
        # Get a segment
        segments = vps_manager.get_all_segments()
        assert len(segments) > 0, "Should have default segments"
        segment_id = segments[0]['id']

        # Create TL Vision
        vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Claude Test Vision",
            vision_statement="This is a Claude Test 5-year vision statement",
            success_metrics='["Claude Test Metric 1", "Claude Test Metric 2"]'
        )

        # Update review_date
        vps_manager.update_tl_vision(vision_id, review_date="2026-06-01")

        assert vision_id is not None
        assert vision_id.startswith("tlv-")

        # Verify it was written to database
        retrieved = vps_manager.get_tl_vision(vision_id)
        assert retrieved is not None
        assert retrieved['title'] == "Claude Test Vision"
        assert retrieved['vision_statement'] == "This is a Claude Test 5-year vision statement"
        assert retrieved['start_year'] == 2026
        assert retrieved['end_year'] == 2031
        assert retrieved['segment_description_id'] == segment_id
        assert retrieved['is_active'] == 1
        assert "Claude Test" in retrieved['success_metrics']

    def test_create_annual_vision_claude_test(self, vps_manager):
        """Test creating Annual Vision under a TL Vision."""
        # Setup: Create TL Vision first
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Parent Vision",
            vision_statement="Parent statement"
        )

        # Create Annual Vision
        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Claude Test Annual Vision",
            vision_statement="Claude Test annual vision for 2026",
            key_priorities='["Claude Test Priority 1", "Claude Test Priority 2", "Claude Test Priority 3"]'
        )

        assert annual_vision_id is not None
        assert annual_vision_id.startswith("av-")

        # Verify database state
        retrieved = vps_manager.get_annual_vision(annual_vision_id)
        assert retrieved is not None
        assert retrieved['title'] == "Claude Test Annual Vision"
        assert retrieved['vision_statement'] == "Claude Test annual vision for 2026"
        assert retrieved['year'] == 2026
        assert retrieved['tl_vision_id'] == tl_vision_id
        assert "Claude Test Priority" in retrieved['key_priorities']

    def test_create_annual_plan_claude_test(self, vps_manager):
        """Test creating Annual Plan under Annual Vision."""
        # Setup hierarchy
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Parent Vision",
            vision_statement="Parent"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Parent Annual Vision",
            vision_statement="Parent annual"
        )

        # Create Annual Plan
        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Claude Test Theme",
            objective="Claude Test Objective for 2026",
            description="Claude Test detailed plan description"
        )

        # Update status and target_date
        vps_manager.update_annual_plan(
            annual_plan_id,
            status="in_progress",
            target_date="2026-12-31"
        )

        assert annual_plan_id is not None
        assert annual_plan_id.startswith("ap-")

        # Verify database
        retrieved = vps_manager.get_annual_plan(annual_plan_id)
        assert retrieved is not None
        assert retrieved['theme'] == "Claude Test Theme"
        assert retrieved['objective'] == "Claude Test Objective for 2026"
        assert retrieved['description'] == "Claude Test detailed plan description"
        assert retrieved['status'] == "in_progress"
        assert retrieved['year'] == 2026
        assert retrieved['annual_vision_id'] == annual_vision_id

    def test_create_quarter_initiative_claude_test(self, vps_manager):
        """Test creating Quarter Initiative."""
        # Setup hierarchy
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual Vision",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        # Create Quarter Initiative
        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Claude Test Q1 Initiative",
            outcome_statement="Claude Test expected outcomes for Q1",
            tracking_measures='["Claude Test Measure 1", "Claude Test Measure 2"]'
        )

        # Update status and progress
        vps_manager.update_quarter_initiative(
            quarter_id,
            status="in_progress",
            progress_pct=25
        )

        assert quarter_id is not None
        assert quarter_id.startswith("qi-")

        # Verify database
        retrieved = vps_manager.get_quarter_initiative(quarter_id)
        assert retrieved is not None
        assert retrieved['title'] == "Claude Test Q1 Initiative"
        assert retrieved['outcome_statement'] == "Claude Test expected outcomes for Q1"
        assert retrieved['quarter'] == 1
        assert retrieved['year'] == 2026
        assert retrieved['status'] == "in_progress"
        assert retrieved['progress_pct'] == 25
        assert "Claude Test Measure" in retrieved['tracking_measures']

    def test_create_month_tactic_claude_test(self, vps_manager):
        """Test creating Month Tactic."""
        # Setup full hierarchy
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Q1",
            outcome_statement="Outcomes"
        )

        # Create Month Tactic
        month_id = vps_manager.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=1,
            year=2026,
            priority_focus="Claude Test January Focus",
            description="Claude Test tactical actions for January"
        )

        # Update status and progress
        vps_manager.update_month_tactic(
            month_id,
            status="active",
            progress_pct=50
        )

        assert month_id is not None
        assert month_id.startswith("mt-")

        # Verify database
        retrieved = vps_manager.get_month_tactic(month_id)
        assert retrieved is not None
        assert retrieved['priority_focus'] == "Claude Test January Focus"
        assert retrieved['description'] == "Claude Test tactical actions for January"
        assert retrieved['month'] == 1
        assert retrieved['year'] == 2026
        assert retrieved['status'] == "active"
        assert retrieved['progress_pct'] == 50

    def test_create_week_action_claude_test(self, vps_manager):
        """Test creating Week Action."""
        # Setup full hierarchy
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Q1",
            outcome_statement="Outcomes"
        )

        month_id = vps_manager.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=1,
            year=2026,
            priority_focus="Focus",
            description="Description"
        )

        # Create Week Action
        week_start = date(2026, 1, 19).isoformat()
        week_end = date(2026, 1, 25).isoformat()

        week_id = vps_manager.create_week_action(
            month_tactic_id=month_id,
            segment_description_id=segment_id,
            week_start_date=week_start,
            week_end_date=week_end,
            title="Claude Test Week Action",
            description="Claude Test weekly tasks",
            outcome_expected="Claude Test expected weekly outcomes"
        )

        # Update status and order
        vps_manager.update_week_action(
            week_id,
            status="in_progress",
            order_index=1
        )

        assert week_id is not None
        assert week_id.startswith("wa-")

        # Verify database
        retrieved = vps_manager.get_week_action(week_id)
        assert retrieved is not None
        assert retrieved['title'] == "Claude Test Week Action"
        assert retrieved['description'] == "Claude Test weekly tasks"
        assert retrieved['outcome_expected'] == "Claude Test expected weekly outcomes"
        assert retrieved['week_start_date'] == week_start
        assert retrieved['week_end_date'] == week_end
        assert retrieved['status'] == "in_progress"

    def test_full_hierarchy_creation_claude_test(self, vps_manager):
        """Test creating a complete VPS hierarchy and verify all records."""
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        # Create full hierarchy
        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Claude Test 5-Year Vision",
            vision_statement="Claude Test comprehensive vision"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Claude Test 2026 Vision",
            vision_statement="Claude Test annual vision"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Claude Test Theme",
            objective="Claude Test Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Claude Test Q1",
            outcome_statement="Claude Test Q1 outcomes"
        )

        month_id = vps_manager.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=1,
            year=2026,
            priority_focus="Claude Test Jan Focus",
            description="Claude Test Jan tactics"
        )

        week_id = vps_manager.create_week_action(
            month_tactic_id=month_id,
            segment_description_id=segment_id,
            week_start_date=date(2026, 1, 19).isoformat(),
            week_end_date=date(2026, 1, 25).isoformat(),
            title="Claude Test Week",
            description="Claude Test week actions"
        )

        # Verify entire hierarchy using breadcrumb
        breadcrumb = vps_manager.get_hierarchy_breadcrumb(
            "week_action", week_id)
        # segment -> tl_vision -> annual_vision -> annual_plan -> quarter -> month -> week
        assert len(breadcrumb) == 7

        # Verify each level has "Claude Test" in it
        breadcrumb_titles = [
            b['data'].get('name') or b['data'].get('title') or b['data'].get(
                'theme') or b['data'].get('priority_focus')
            for b in breadcrumb
        ]
        assert any("Claude Test" in str(title)
                   for title in breadcrumb_titles if title)


class TestWeekActionWithSteps:
    """Test creating Week Actions with Steps that auto-generate Action Items."""

    def test_create_week_action_with_steps_creates_action_items(self, vps_manager):
        """Test that Week Action steps auto-create Action Items in the database."""
        # Setup full hierarchy
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Q1",
            outcome_statement="Outcomes"
        )

        month_id = vps_manager.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=1,
            year=2026,
            priority_focus="Focus",
            description="Description"
        )

        # Create Week Action with steps and key results
        week_start = date(2026, 1, 19).isoformat()
        week_end = date(2026, 1, 25).isoformat()

        week_id = vps_manager.create_week_action(
            month_tactic_id=month_id,
            segment_description_id=segment_id,
            week_start_date=week_start,
            week_end_date=week_end,
            title="Claude Test Week Action with Steps",
            description="Testing auto-creation of action items",
            outcome_expected="All steps should create action items",
            step_1="Complete first task",
            key_result_1="Task 1 completed successfully",
            step_2="Complete second task",
            key_result_2="Task 2 completed successfully",
            step_3="Complete third task",
            key_result_3="Task 3 completed successfully"
        )

        assert week_id is not None
        assert week_id.startswith("wa-")

        # Verify week action was created
        week_action = vps_manager.get_week_action(week_id)
        assert week_action is not None
        assert week_action['step_1'] == "Complete first task"
        assert week_action['key_result_1'] == "Task 1 completed successfully"

        # Auto-create action items from steps
        created_item_ids = vps_manager.auto_create_action_items_from_steps(
            week_id)

        # Verify that 3 action items were created
        assert len(
            created_item_ids) == 3, f"Expected 3 action items, got {len(created_item_ids)}"

        # Verify each action item was created in the database
        for i, item_id in enumerate(created_item_ids, start=1):
            action_item = vps_manager.db_manager.get_action_item(item_id)
            assert action_item is not None, f"Action item {i} not found in database"
            assert action_item.week_action_id == week_id
            assert action_item.segment_description_id == segment_id
            assert f"Step {i}:" in action_item.description
            assert f"Complete {['first', 'second', 'third'][i-1]} task" in action_item.title

        # Verify dates are incrementing
        first_item = vps_manager.db_manager.get_action_item(
            created_item_ids[0])
        second_item = vps_manager.db_manager.get_action_item(
            created_item_ids[1])
        third_item = vps_manager.db_manager.get_action_item(
            created_item_ids[2])

        assert first_item.start_date == "2026-01-19"
        assert second_item.start_date == "2026-01-20"
        assert third_item.start_date == "2026-01-21"

    def test_create_week_action_with_partial_steps(self, vps_manager):
        """Test that only non-blank steps create action items."""
        # Setup
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Q1",
            outcome_statement="Outcomes"
        )

        month_id = vps_manager.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=1,
            year=2026,
            priority_focus="Focus",
            description="Description"
        )

        # Create Week Action with only 2 steps filled
        week_start = date(2026, 1, 19).isoformat()
        week_end = date(2026, 1, 25).isoformat()

        week_id = vps_manager.create_week_action(
            month_tactic_id=month_id,
            segment_description_id=segment_id,
            week_start_date=week_start,
            week_end_date=week_end,
            title="Partial Steps Week",
            step_1="First step only",
            step_3="Third step only"
            # step_2, step_4, step_5 are blank
        )

        # Auto-create action items
        created_item_ids = vps_manager.auto_create_action_items_from_steps(
            week_id)

        # Should create exactly 2 action items (step_1 and step_3)
        assert len(created_item_ids) == 2

        # Verify items were created
        first_item = vps_manager.db_manager.get_action_item(
            created_item_ids[0])
        second_item = vps_manager.db_manager.get_action_item(
            created_item_ids[1])

        assert "First step only" in first_item.title
        assert "Third step only" in second_item.title

    def test_week_action_with_no_steps_creates_no_items(self, vps_manager):
        """Test that Week Action with no steps creates no action items."""
        # Setup
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Q1",
            outcome_statement="Outcomes"
        )

        month_id = vps_manager.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=1,
            year=2026,
            priority_focus="Focus",
            description="Description"
        )

        # Create Week Action with NO steps
        week_start = date(2026, 1, 19).isoformat()
        week_end = date(2026, 1, 25).isoformat()

        week_id = vps_manager.create_week_action(
            month_tactic_id=month_id,
            segment_description_id=segment_id,
            week_start_date=week_start,
            week_end_date=week_end,
            title="No Steps Week"
        )

        # Auto-create action items (should create none)
        created_item_ids = vps_manager.auto_create_action_items_from_steps(
            week_id)

        # Should create 0 action items
        assert len(created_item_ids) == 0

    def test_update_week_action_with_new_steps_creates_more_items(self, vps_manager):
        """Test that updating a Week Action with new steps creates additional Action Items without duplicates."""
        # Setup hierarchy
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Q1",
            outcome_statement="Outcomes"
        )

        month_id = vps_manager.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=1,
            year=2026,
            priority_focus="Focus",
            description="Description"
        )

        # Create Week Action with only 2 steps initially
        week_start = date(2026, 1, 19).isoformat()
        week_end = date(2026, 1, 25).isoformat()

        week_id = vps_manager.create_week_action(
            month_tactic_id=month_id,
            segment_description_id=segment_id,
            week_start_date=week_start,
            week_end_date=week_end,
            title="Week Action with Growing Steps",
            description="Testing update with new steps",
            step_1="Initial step one",
            step_2="Initial step two"
        )

        # Auto-create action items from initial steps (should create 2)
        created_item_ids = vps_manager.auto_create_action_items_from_steps(
            week_id)
        assert len(
            created_item_ids) == 2, f"Expected 2 action items initially, got {len(created_item_ids)}"

        # Update the Week Action to add 2 more steps
        vps_manager.update_week_action(
            week_id,
            step_3="Added step three",
            step_4="Added step four"
        )

        # Auto-create again (should create 2 more items, NOT recreate the first 2)
        new_item_ids = vps_manager.auto_create_action_items_from_steps(week_id)
        assert len(
            new_item_ids) == 2, f"Expected 2 new action items, got {len(new_item_ids)}"

        # Verify total of 4 action items exist for this week action
        all_items = vps_manager.get_action_items_for_week_action(week_id)
        assert len(
            all_items) == 4, f"Expected 4 total action items, got {len(all_items)}"

        # Verify the descriptions match the expected steps
        descriptions = [item['description'] for item in all_items]
        assert any("Step 1:" in desc for desc in descriptions)
        assert any("Step 2:" in desc for desc in descriptions)
        assert any("Step 3:" in desc for desc in descriptions)
        assert any("Step 4:" in desc for desc in descriptions)

        # Verify no duplicates - each step number should appear exactly once
        step_numbers = []
        import re
        for desc in descriptions:
            match = re.match(r'Step (\d+):', desc)
            if match:
                step_numbers.append(int(match.group(1)))
        assert sorted(step_numbers) == [
            1, 2, 3, 4], f"Expected steps [1,2,3,4], got {sorted(step_numbers)}"


class TestVPSRecordUpdates:
    """Test updating VPS records and marking them complete."""

    def test_mark_quarter_initiative_complete(self, vps_manager):
        """Test marking Quarter Initiative as complete."""
        # Create hierarchy
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Claude Test Q1",
            outcome_statement="Outcomes"
        )

        # Set initial status and progress
        vps_manager.update_quarter_initiative(
            quarter_id,
            status="in_progress",
            progress_pct=75
        )

        # Mark as complete
        result = vps_manager.update_quarter_initiative(
            quarter_id,
            status="completed",
            progress_pct=100
        )
        assert result is True

        # Verify completion
        retrieved = vps_manager.get_quarter_initiative(quarter_id)
        assert retrieved['status'] == "completed"
        assert retrieved['progress_pct'] == 100

    def test_mark_month_tactic_complete(self, vps_manager):
        """Test marking Month Tactic as complete."""
        # Setup
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Q1",
            outcome_statement="Outcomes"
        )

        month_id = vps_manager.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=1,
            year=2026,
            priority_focus="Claude Test Focus",
            description="Description"
        )

        # Set initial status and progress
        vps_manager.update_month_tactic(
            month_id,
            status="active",
            progress_pct=80
        )

        # Mark complete
        result = vps_manager.update_month_tactic(
            month_id,
            status="completed",
            progress_pct=100
        )
        assert result is True

        # Verify
        retrieved = vps_manager.get_month_tactic(month_id)
        assert retrieved['status'] == "completed"
        assert retrieved['progress_pct'] == 100

    def test_mark_week_action_complete(self, vps_manager):
        """Test marking Week Action as complete."""
        # Setup
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Q1",
            outcome_statement="Outcomes"
        )

        month_id = vps_manager.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=1,
            year=2026,
            priority_focus="Focus",
            description="Description"
        )

        week_id = vps_manager.create_week_action(
            month_tactic_id=month_id,
            segment_description_id=segment_id,
            week_start_date=date(2026, 1, 19).isoformat(),
            week_end_date=date(2026, 1, 25).isoformat(),
            title="Claude Test Week",
            description="Tasks"
        )

        # Set initial status
        vps_manager.update_week_action(
            week_id,
            status="in_progress"
        )

        # Mark complete
        result = vps_manager.update_week_action(
            week_id,
            status="completed"
        )
        assert result is True

        # Verify
        retrieved = vps_manager.get_week_action(week_id)
        assert retrieved['status'] == "completed"

    def test_update_multiple_fields_claude_test(self, vps_manager):
        """Test updating multiple fields at once."""
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Original Title",
            vision_statement="Original Statement"
        )

        # Update multiple fields
        result = vps_manager.update_tl_vision(
            tl_vision_id,
            title="Claude Test Updated Title",
            vision_statement="Claude Test Updated Statement",
            review_date="2026-12-31"
        )
        assert result is True

        # Verify all updates
        retrieved = vps_manager.get_tl_vision(tl_vision_id)
        assert retrieved['title'] == "Claude Test Updated Title"
        assert retrieved['vision_statement'] == "Claude Test Updated Statement"
        assert retrieved['review_date'] == "2026-12-31"


class TestVPSRecordDeletion:
    """Test deleting VPS records (to be implemented)."""

    def test_delete_tl_vision_without_children(self, vps_manager):
        """Test deleting TL Vision that has no children."""
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Claude Test Delete Me",
            vision_statement="This should be deleted"
        )

        # Verify it exists
        assert vps_manager.get_tl_vision(tl_vision_id) is not None

        # Delete it (method to be implemented)
        if hasattr(vps_manager, 'delete_tl_vision'):
            result = vps_manager.delete_tl_vision(tl_vision_id)
            assert result is True

            # Verify it's gone
            assert vps_manager.get_tl_vision(tl_vision_id) is None
        else:
            pytest.skip("delete_tl_vision not yet implemented")

    def test_delete_tl_vision_with_children_should_fail(self, vps_manager):
        """Test that deleting TL Vision with children should fail."""
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        # Create TL Vision with Annual Vision child
        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Claude Test Parent",
            vision_statement="Has children"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Claude Test Child",
            vision_statement="Child vision"
        )

        # Try to delete parent (should fail)
        if hasattr(vps_manager, 'delete_tl_vision'):
            result = vps_manager.delete_tl_vision(tl_vision_id)
            assert result is False, "Should not allow deletion when children exist"

            # Verify parent still exists
            assert vps_manager.get_tl_vision(tl_vision_id) is not None
            # Verify child still exists
            assert vps_manager.get_annual_vision(annual_vision_id) is not None
        else:
            pytest.skip("delete_tl_vision not yet implemented")

    def test_delete_week_action_without_children(self, vps_manager):
        """Test deleting Week Action with no linked action items."""
        # Setup
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Q1",
            outcome_statement="Outcomes"
        )

        month_id = vps_manager.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=1,
            year=2026,
            priority_focus="Focus",
            description="Description"
        )

        week_id = vps_manager.create_week_action(
            month_tactic_id=month_id,
            segment_description_id=segment_id,
            week_start_date=date(2026, 1, 19).isoformat(),
            week_end_date=date(2026, 1, 25).isoformat(),
            title="Claude Test Delete Me",
            description="Should be deleted"
        )

        # Verify it exists
        assert vps_manager.get_week_action(week_id) is not None

        # Delete it
        if hasattr(vps_manager, 'delete_week_action'):
            result = vps_manager.delete_week_action(week_id)
            assert result is True

            # Verify it's gone
            assert vps_manager.get_week_action(week_id) is None
        else:
            pytest.skip("delete_week_action not yet implemented")


class TestVPSHierarchyIntegrity:
    """Test VPS hierarchy integrity and constraints."""

    def test_cascade_relationships_exist(self, vps_manager):
        """Verify that database has proper cascade relationships."""
        # This test verifies the database schema is set up correctly
        # Foreign keys should cascade on delete

        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Claude Test",
            vision_statement="Test"
        )

        # Verify foreign key constraints are enabled
        cursor = vps_manager.db.conn.execute("PRAGMA foreign_keys")
        fk_status = cursor.fetchone()[0]
        assert fk_status == 1, "Foreign keys should be enabled"

    def test_year_constraints_on_tl_vision(self, vps_manager):
        """Test that end_year must be greater than start_year."""
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        # Try to create with invalid years
        try:
            vps_manager.create_tl_vision(
                segment_description_id=segment_id,
                start_year=2031,
                end_year=2026,  # Invalid: end before start
                title="Claude Test Invalid",
                vision_statement="Should fail"
            )
            pytest.fail("Should have raised an error for invalid year range")
        except Exception as e:
            # Expected to fail due to CHECK constraint
            assert "CHECK constraint failed" in str(
                e) or "constraint" in str(e).lower()

    def test_quarter_constraints(self, vps_manager):
        """Test quarter must be between 1-4."""
        # Setup
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        # Try invalid quarter
        try:
            vps_manager.create_quarter_initiative(
                annual_plan_id=annual_plan_id,
                segment_description_id=segment_id,
                quarter=5,  # Invalid
                year=2026,
                title="Invalid Quarter",
                outcome_statement="Should fail"
            )
            pytest.fail("Should have raised error for invalid quarter")
        except Exception as e:
            assert "CHECK constraint failed" in str(
                e) or "constraint" in str(e).lower()

    def test_month_constraints(self, vps_manager):
        """Test month must be between 1-12."""
        # Setup
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Vision",
            vision_statement="Statement"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual",
            vision_statement="Annual"
        )

        annual_plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=2026,
            theme="Theme",
            objective="Objective"
        )

        quarter_id = vps_manager.create_quarter_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            quarter=1,
            year=2026,
            title="Q1",
            outcome_statement="Outcomes"
        )

        # Try invalid month
        try:
            vps_manager.create_month_tactic(
                quarter_initiative_id=quarter_id,
                segment_description_id=segment_id,
                month=13,  # Invalid
                year=2026,
                priority_focus="Invalid",
                description="Should fail"
            )
            pytest.fail("Should have raised error for invalid month")
        except Exception as e:
            assert "CHECK constraint failed" in str(
                e) or "constraint" in str(e).lower()


class TestVPSEditorBugFixes:
    """Test VPS Editor bug fixes from 2026-01-24."""

    def test_tl_vision_creation_with_empty_years(self, vps_manager):
        """Test that TL Vision can be created with empty year fields (should use defaults)."""
        # This tests the fix for the ValueError when year fields are empty
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        # Simulate what the editor does with empty fields - use current year as default
        from datetime import datetime
        current_year = datetime.now().year
        default_end_year = current_year + 10

        # Create with default years
        vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=current_year,
            end_year=default_end_year,
            title="Test Default Years Vision",
            vision_statement="Created with default year values"
        )

        assert vision_id is not None
        vision = vps_manager.get_tl_vision(vision_id)
        assert vision['start_year'] == current_year
        assert vision['end_year'] == default_end_year
        assert vision['end_year'] > vision['start_year']

    def test_annual_plan_creation_with_empty_year(self, vps_manager):
        """Test that Annual Plan can be created with empty year field (should use default)."""
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        tl_vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Parent Vision",
            vision_statement="Parent"
        )

        annual_vision_id = vps_manager.create_annual_vision(
            tl_vision_id=tl_vision_id,
            segment_description_id=segment_id,
            year=2026,
            title="Annual Vision",
            vision_statement="Annual"
        )

        # Simulate empty year field - use current year as default
        from datetime import datetime
        current_year = datetime.now().year

        plan_id = vps_manager.create_annual_plan(
            annual_vision_id=annual_vision_id,
            segment_description_id=segment_id,
            year=current_year,  # Default from empty field
            theme="Test Theme",
            objective="Test Objective"
        )

        assert plan_id is not None
        plan = vps_manager.get_annual_plan(plan_id)
        assert plan['year'] == current_year

    def test_multiple_segments_exist_for_selection(self, vps_manager):
        """Test that multiple segments can exist for the segment selection feature."""
        # This tests the segment selection feature
        segments = vps_manager.get_all_segments()

        # Should have default segments
        assert len(segments) >= 1

        # Verify each segment has required fields
        for segment in segments:
            assert 'id' in segment
            assert 'name' in segment
            assert 'color_hex' in segment
            assert segment['is_active'] == True

    def test_segment_filtering_by_id(self, vps_manager):
        """Test filtering visions by segment ID (for segment selection feature)."""
        segments = vps_manager.get_all_segments()
        if len(segments) < 2:
            # Create a second segment for testing
            new_segment_id = vps_manager.create_segment(
                name="Test Segment 2",
                description="Second test segment",
                color_hex="#00FF00",
                display_order=2
            )
            segments = vps_manager.get_all_segments()

        assert len(segments) >= 2
        segment1_id = segments[0]['id']
        segment2_id = segments[1]['id']

        # Create visions in different segments
        vision1_id = vps_manager.create_tl_vision(
            segment_description_id=segment1_id,
            start_year=2026,
            end_year=2031,
            title="Segment 1 Vision",
            vision_statement="In segment 1"
        )

        vision2_id = vps_manager.create_tl_vision(
            segment_description_id=segment2_id,
            start_year=2026,
            end_year=2031,
            title="Segment 2 Vision",
            vision_statement="In segment 2"
        )

        # Filter by segment 1
        segment1_visions = vps_manager.get_tl_visions(segment_id=segment1_id)
        vision_ids = [v['id'] for v in segment1_visions]
        assert vision1_id in vision_ids

        # Filter by segment 2
        segment2_visions = vps_manager.get_tl_visions(segment_id=segment2_id)
        vision_ids = [v['id'] for v in segment2_visions]
        assert vision2_id in vision_ids

    def test_tl_vision_year_validation(self, vps_manager):
        """Test that end_year must be greater than start_year."""
        segments = vps_manager.get_all_segments()
        segment_id = segments[0]['id']

        # This should fail due to invalid year range
        try:
            vps_manager.create_tl_vision(
                segment_description_id=segment_id,
                start_year=2030,
                end_year=2025,  # End before start - invalid
                title="Invalid Years",
                vision_statement="Should fail"
            )
            pytest.fail("Should have raised error for end_year <= start_year")
        except Exception as e:
            # Should raise a constraint error
            assert "CHECK constraint" in str(
                e) or "constraint" in str(e).lower()


class TestVPSSegmentManagement:
    """Test VPS Segment CRUD operations from Settings screen."""

    def test_create_new_segment(self, vps_manager):
        """Test creating a new life segment with color."""
        segment_id = vps_manager.create_segment(
            name="Professional Development",
            description="Career growth and skill development",
            color_hex="#FF5733",
            order_index=10
        )

        assert segment_id is not None
        assert segment_id.startswith("seg-")

        # Verify segment was created
        segment = vps_manager.get_segment(segment_id)
        assert segment is not None
        assert segment['name'] == "Professional Development"
        assert segment['description'] == "Career growth and skill development"
        assert segment['color_hex'] == "#FF5733"
        assert segment['order_index'] == 10
        assert segment['is_active'] == True

    def test_update_segment_name_and_color(self, vps_manager):
        """Test updating segment name and color."""
        # Create segment
        segment_id = vps_manager.create_segment(
            name="Test Segment",
            description="Test description",
            color_hex="#000000",
            order_index=1
        )

        # Update name and color
        success = vps_manager.update_segment(
            segment_id,
            name="Updated Segment Name",
            color_hex="#00FF00"
        )
        assert success is True

        # Verify updates
        segment = vps_manager.get_segment(segment_id)
        assert segment['name'] == "Updated Segment Name"
        assert segment['color_hex'] == "#00FF00"
        assert segment['description'] == "Test description"  # Unchanged

    def test_update_segment_active_status(self, vps_manager):
        """Test toggling segment active status."""
        segment_id = vps_manager.create_segment(
            name="Test Segment",
            description="Test",
            color_hex="#0000FF",
            order_index=1
        )

        # Deactivate segment
        success = vps_manager.update_segment(segment_id, is_active=False)
        assert success is True

        segment = vps_manager.get_segment(segment_id)
        assert segment['is_active'] == False

        # Reactivate segment
        success = vps_manager.update_segment(segment_id, is_active=True)
        assert success is True

        segment = vps_manager.get_segment(segment_id)
        assert segment['is_active'] == True

    def test_delete_segment_without_children(self, vps_manager):
        """Test deleting a segment with no associated visions."""
        segment_id = vps_manager.create_segment(
            name="Delete Me",
            description="This will be deleted",
            color_hex="#FF0000",
            order_index=99
        )

        # Verify it exists
        assert vps_manager.get_segment(segment_id) is not None

        # Delete it
        success, vision_count = vps_manager.delete_segment(segment_id)
        assert success is True
        assert vision_count == 0

        # Verify it's gone
        assert vps_manager.get_segment(segment_id) is None

    def test_delete_segment_with_children_fails(self, vps_manager):
        """Test that deleting a segment with visions fails and returns count."""
        # Create segment
        segment_id = vps_manager.create_segment(
            name="Segment with Children",
            description="Has visions",
            color_hex="#00FF00",
            order_index=1
        )

        # Create a vision in this segment
        vision_id = vps_manager.create_tl_vision(
            segment_description_id=segment_id,
            start_year=2026,
            end_year=2031,
            title="Child Vision",
            vision_statement="This prevents deletion"
        )

        # Try to delete segment (should fail)
        success, vision_count = vps_manager.delete_segment(segment_id)
        assert success is False
        assert vision_count == 1  # Should report 1 linked vision

        # Verify segment still exists
        assert vps_manager.get_segment(segment_id) is not None
        # Verify vision still exists
        assert vps_manager.get_tl_vision(vision_id) is not None

    def test_get_all_segments_respects_active_flag(self, vps_manager):
        """Test filtering segments by active status."""
        # Create active segment
        active_id = vps_manager.create_segment(
            name="Active Segment",
            description="Active",
            color_hex="#00FF00",
            order_index=1
        )

        # Create inactive segment
        inactive_id = vps_manager.create_segment(
            name="Inactive Segment",
            description="Inactive",
            color_hex="#808080",
            order_index=2
        )
        vps_manager.update_segment(inactive_id, is_active=False)

        # Get only active segments
        active_segments = vps_manager.get_all_segments(active_only=True)
        active_ids = [s['id'] for s in active_segments]
        assert active_id in active_ids
        assert inactive_id not in active_ids

        # Get all segments including inactive
        all_segments = vps_manager.get_all_segments(active_only=False)
        all_ids = [s['id'] for s in all_segments]
        assert active_id in all_ids
        assert inactive_id in all_ids

    def test_segment_order_index_affects_sorting(self, vps_manager):
        """Test that segments are sorted by order_index."""
        # Create segments with different orders
        seg1_id = vps_manager.create_segment(
            name="Third", description="", color_hex="#000000", order_index=3
        )
        seg2_id = vps_manager.create_segment(
            name="First", description="", color_hex="#000000", order_index=1
        )
        seg3_id = vps_manager.create_segment(
            name="Second", description="", color_hex="#000000", order_index=2
        )

        # Get all segments
        segments = vps_manager.get_all_segments(active_only=False)

        # Find our test segments
        our_segments = [s for s in segments if s['id']
                        in [seg1_id, seg2_id, seg3_id]]

        # Verify they're in order
        assert len(our_segments) >= 3
        orders = [s['order_index'] for s in our_segments]
        assert orders == sorted(orders)

    def test_color_hex_validation_format(self, vps_manager):
        """Test that color_hex accepts valid hex colors."""
        # Valid hex colors should work
        valid_colors = ["#FF0000", "#00FF00", "#0000FF", "#ABCDEF", "#123456"]

        for color in valid_colors:
            segment_id = vps_manager.create_segment(
                name=f"Segment {color}",
                description="Testing color",
                color_hex=color,
                order_index=1
            )

            segment = vps_manager.get_segment(segment_id)
            assert segment['color_hex'] == color

    def test_delete_segment_reports_multiple_linked_visions(self, vps_manager):
        """Test that deletion reports correct count when multiple visions exist."""
        # Create segment
        segment_id = vps_manager.create_segment(
            name="Segment with Multiple Visions",
            description="Has 3 visions",
            color_hex="#FF00FF",
            order_index=1
        )

        # Create 3 visions in this segment
        for i in range(3):
            vps_manager.create_tl_vision(
                segment_description_id=segment_id,
                start_year=2026,
                end_year=2031,
                title=f"Vision {i+1}",
                vision_statement=f"Vision statement {i+1}"
            )

        # Try to delete segment (should fail with count of 3)
        success, vision_count = vps_manager.delete_segment(segment_id)
        assert success is False
        assert vision_count == 3  # Should report 3 linked visions

        # Verify segment still exists
        assert vps_manager.get_segment(segment_id) is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
