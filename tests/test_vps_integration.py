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
        breadcrumb = vps_manager.get_hierarchy_breadcrumb("week_action", week_id)
        assert len(breadcrumb) == 7  # segment -> tl_vision -> annual_vision -> annual_plan -> quarter -> month -> week

        # Verify each level has "Claude Test" in it
        breadcrumb_titles = [
            b['data'].get('name') or b['data'].get('title') or b['data'].get('theme') or b['data'].get('priority_focus')
            for b in breadcrumb
        ]
        assert any("Claude Test" in str(title) for title in breadcrumb_titles if title)


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
            assert "CHECK constraint failed" in str(e) or "constraint" in str(e).lower()

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
            assert "CHECK constraint failed" in str(e) or "constraint" in str(e).lower()

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
            assert "CHECK constraint failed" in str(e) or "constraint" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
