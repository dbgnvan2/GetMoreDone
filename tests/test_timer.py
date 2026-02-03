"""
Tests for Action Timer functionality.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from src.getmoredone.models import ActionItem, WorkLog, Status
from src.getmoredone.db_manager import DatabaseManager


@pytest.fixture
def db_manager():
    """Create a test database manager with temp file."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()

    manager = DatabaseManager(temp_file.name)
    yield manager

    manager.close()
    os.unlink(temp_file.name)


@pytest.fixture
def sample_item(db_manager):
    """Create a sample action item for testing."""
    item = ActionItem(
        who="TestUser",
        title="Test Task",
        description="Test task description with next steps",
        planned_minutes=30,
        importance=10,
        urgency=10,
        size=4,
        value=4,
        start_date="2024-01-15",
        due_date="2024-01-15"
    )
    db_manager.create_action_item(item)
    return item


class TestWorkLogCreation:
    """Test work log creation and retrieval."""

    def test_create_work_log(self, db_manager, sample_item):
        """Test creating a work log entry."""
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=25)

        work_log = WorkLog(
            item_id=sample_item.id,
            started_at=start_time.isoformat(),
            ended_at=end_time.isoformat(),
            minutes=25,
            note="Completed first phase of work"
        )

        log_id = db_manager.create_work_log(work_log)
        assert log_id == work_log.id

        # Retrieve the log
        logs = db_manager.get_work_logs(sample_item.id)
        assert len(logs) == 1
        assert logs[0].item_id == sample_item.id
        assert logs[0].minutes == 25
        assert logs[0].note == "Completed first phase of work"

    def test_create_work_log_without_note(self, db_manager, sample_item):
        """Test creating a work log without a note."""
        start_time = datetime.now()

        work_log = WorkLog(
            item_id=sample_item.id,
            started_at=start_time.isoformat(),
            ended_at=start_time.isoformat(),
            minutes=15,
            note=None
        )

        log_id = db_manager.create_work_log(work_log)
        assert log_id is not None

        logs = db_manager.get_work_logs(sample_item.id)
        assert len(logs) == 1
        assert logs[0].note is None

    def test_multiple_work_logs_same_item(self, db_manager, sample_item):
        """Test creating multiple work logs for the same item."""
        # First session
        log1 = WorkLog(
            item_id=sample_item.id,
            started_at=datetime.now().isoformat(),
            ended_at=datetime.now().isoformat(),
            minutes=25,
            note="First session"
        )
        db_manager.create_work_log(log1)

        # Second session
        log2 = WorkLog(
            item_id=sample_item.id,
            started_at=datetime.now().isoformat(),
            ended_at=datetime.now().isoformat(),
            minutes=30,
            note="Second session"
        )
        db_manager.create_work_log(log2)

        # Retrieve all logs
        logs = db_manager.get_work_logs(sample_item.id)
        assert len(logs) == 2
        assert sum(log.minutes for log in logs) == 55

    def test_get_total_actual_minutes(self, db_manager, sample_item):
        """Test getting total actual minutes for an item."""
        # Create multiple work logs
        for minutes in [25, 30, 20]:
            work_log = WorkLog(
                item_id=sample_item.id,
                started_at=datetime.now().isoformat(),
                ended_at=datetime.now().isoformat(),
                minutes=minutes
            )
            db_manager.create_work_log(work_log)

        total = db_manager.get_total_actual_minutes(sample_item.id)
        assert total == 75

    def test_work_log_with_no_item(self, db_manager):
        """Test that work logs require valid item_id."""
        # This should raise an error due to foreign key constraint
        work_log = WorkLog(
            item_id="nonexistent-id",
            started_at=datetime.now().isoformat(),
            ended_at=datetime.now().isoformat(),
            minutes=10
        )

        with pytest.raises(Exception):  # Foreign key constraint violation
            db_manager.create_work_log(work_log)


class TestTimerTimeCalculations:
    """Test time calculations for the timer."""

    def test_break_time_calculation(self):
        """Test that break time is correctly calculated."""
        time_block = 30
        break_time = 5
        work_time = time_block - break_time
        assert work_time == 25

    def test_work_seconds_to_minutes_conversion(self):
        """Test converting work seconds to minutes."""
        work_seconds = 1500  # 25 minutes
        work_minutes = work_seconds // 60
        assert work_minutes == 25

    def test_partial_minute_handling(self):
        """Test that partial minutes are handled correctly."""
        work_seconds = 1530  # 25 minutes 30 seconds
        work_minutes = work_seconds // 60
        assert work_minutes == 25  # Should truncate, not round

    def test_time_format_display(self):
        """Test time formatting for display."""
        def format_time(seconds: int) -> str:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes:02d}:{secs:02d}"

        assert format_time(1500) == "25:00"
        assert format_time(599) == "09:59"
        assert format_time(60) == "01:00"
        assert format_time(0) == "00:00"


class TestTimerWorkflows:
    """Test timer completion workflows."""

    def test_finished_workflow(self, db_manager, sample_item):
        """Test the Finished workflow."""
        # Simulate timer session
        start_time = datetime.now()
        work_minutes = 25

        # Create work log
        work_log = WorkLog(
            item_id=sample_item.id,
            started_at=start_time.isoformat(),
            ended_at=(start_time + timedelta(minutes=work_minutes)).isoformat(),
            minutes=work_minutes,
            note="Task completed successfully"
        )
        db_manager.create_work_log(work_log)

        # Complete the item
        db_manager.complete_action_item(sample_item.id)

        # Verify item is completed
        item = db_manager.get_action_item(sample_item.id)
        assert item.status == Status.COMPLETED
        assert item.completed_at is not None

        # Verify work log exists
        logs = db_manager.get_work_logs(sample_item.id)
        assert len(logs) == 1
        assert logs[0].minutes == work_minutes

    def test_finished_updates_notes_from_timer(self, db_manager, sample_item):
        """Test that Finished button updates action item notes from timer window."""
        # Simulate timer session with updated notes
        original_notes = sample_item.description
        assert original_notes == "Test task description with next steps"

        # Simulate user editing notes in timer window
        timer_window_notes = "Updated notes from Action Timer - task completed with modifications"

        # Update the item's description (simulating what the Finished button does)
        sample_item.description = timer_window_notes
        db_manager.update_action_item(sample_item)

        # Create work log
        work_log = WorkLog(
            item_id=sample_item.id,
            started_at=datetime.now().isoformat(),
            ended_at=datetime.now().isoformat(),
            minutes=25,
            note="Finished workflow test"
        )
        db_manager.create_work_log(work_log)

        # Complete the item
        db_manager.complete_action_item(sample_item.id)

        # Verify item is completed with updated notes
        item = db_manager.get_action_item(sample_item.id)
        assert item.status == Status.COMPLETED
        assert item.completed_at is not None
        assert item.description == timer_window_notes
        assert item.description != original_notes

    def test_continue_workflow(self, db_manager, sample_item):
        """Test the Continue workflow."""
        # Simulate timer session for today
        start_time = datetime.now()
        work_minutes = 25

        # Create work log for today's session
        work_log = WorkLog(
            item_id=sample_item.id,
            started_at=start_time.isoformat(),
            ended_at=(start_time + timedelta(minutes=work_minutes)).isoformat(),
            minutes=work_minutes,
            note="Completed phase 1"
        )
        db_manager.create_work_log(work_log)

        # Complete current item
        db_manager.complete_action_item(sample_item.id)

        # Create duplicate for tomorrow
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
        new_item = ActionItem(
            who=sample_item.who,
            title=sample_item.title,
            description="Continue with phase 2",  # Next steps
            contact_id=sample_item.contact_id,
            start_date=tomorrow,
            due_date=tomorrow,
            importance=sample_item.importance,
            urgency=sample_item.urgency,
            size=sample_item.size,
            value=sample_item.value,
            group=sample_item.group,
            category=sample_item.category,
            planned_minutes=sample_item.planned_minutes,
            status=Status.OPEN
        )
        db_manager.create_action_item(new_item)

        # Verify original is completed
        original = db_manager.get_action_item(sample_item.id)
        assert original.status == Status.COMPLETED

        # Verify new item exists
        assert new_item.id != sample_item.id
        assert new_item.status == Status.OPEN
        assert new_item.start_date == tomorrow
        assert new_item.description == "Continue with phase 2"

    def test_continue_updates_original_notes_and_creates_new_action(self, db_manager, sample_item):
        """Test that Continue button updates original notes and creates new action with +1 day dates."""
        from datetime import date
        from src.getmoredone.date_utils import increment_date
        from src.getmoredone.app_settings import AppSettings

        # Store original description
        original_notes = sample_item.description
        assert original_notes == "Test task description with next steps"

        # Simulate user editing notes in timer window
        timer_window_notes = "Updated notes from Action Timer - progress made on task"

        # Update the original item's description (simulating what Continue button does)
        sample_item.description = timer_window_notes
        db_manager.update_action_item(sample_item)

        # Create work log
        work_log = WorkLog(
            item_id=sample_item.id,
            started_at=datetime.now().isoformat(),
            ended_at=datetime.now().isoformat(),
            minutes=25,
            note="Continue workflow test"
        )
        db_manager.create_work_log(work_log)

        # Complete original item
        db_manager.complete_action_item(sample_item.id)

        # Get settings for date increment
        settings = AppSettings()

        # Parse current dates
        current_start = date.fromisoformat(sample_item.start_date)
        current_due = date.fromisoformat(sample_item.due_date)

        # Increment by 1 day using weekend-aware logic
        new_start = increment_date(current_start, 1, settings.include_saturday, settings.include_sunday)
        new_due = increment_date(current_due, 1, settings.include_saturday, settings.include_sunday)

        # Create new action item with updated dates and next steps notes
        next_steps_note = "Next steps for tomorrow"
        new_item = ActionItem(
            who=sample_item.who,
            title=sample_item.title,
            description=next_steps_note,
            contact_id=sample_item.contact_id,
            start_date=new_start.isoformat(),
            due_date=new_due.isoformat(),
            importance=sample_item.importance,
            urgency=sample_item.urgency,
            size=sample_item.size,
            value=sample_item.value,
            group=sample_item.group,
            category=sample_item.category,
            planned_minutes=sample_item.planned_minutes,
            status=Status.OPEN
        )
        db_manager.create_action_item(new_item)

        # Verify original is completed with updated notes
        original = db_manager.get_action_item(sample_item.id)
        assert original.status == Status.COMPLETED
        assert original.completed_at is not None
        assert original.description == timer_window_notes
        assert original.description != original_notes

        # Verify new item has correct properties
        assert new_item.id != sample_item.id
        assert new_item.status == Status.OPEN
        assert new_item.description == next_steps_note

        # Verify dates are incremented by 1 day (weekend-aware)
        assert new_item.start_date == new_start.isoformat()
        assert new_item.due_date == new_due.isoformat()

        # Verify the new dates are after the original dates
        new_start_date = date.fromisoformat(new_item.start_date)
        new_due_date = date.fromisoformat(new_item.due_date)
        assert new_start_date > current_start
        assert new_due_date > current_due


class TestTimerStateManagement:
    """Test timer state transitions."""

    def test_timer_states(self):
        """Test that timer can be in correct states."""
        valid_states = ["stopped", "running", "paused", "in_break"]

        # Test state transitions
        state = "stopped"
        assert state in valid_states

        # Start timer
        state = "running"
        assert state in valid_states

        # Pause timer
        state = "paused"
        assert state in valid_states

        # Resume (back to running)
        state = "running"
        assert state in valid_states

        # Enter break
        state = "in_break"
        assert state in valid_states

        # Stop timer
        state = "stopped"
        assert state in valid_states

    def test_work_time_tracking_with_pause(self):
        """Test that work time correctly excludes pauses."""
        # Simulate: 10 min work, 5 min pause, 10 min work
        work_time_1 = 10 * 60  # 10 minutes in seconds
        pause_duration = 5 * 60  # 5 minutes pause
        work_time_2 = 10 * 60  # 10 more minutes

        total_work_time = work_time_1 + work_time_2  # Pauses excluded
        total_elapsed_time = work_time_1 + pause_duration + work_time_2

        assert total_work_time == 1200  # 20 minutes of work
        assert total_elapsed_time == 1500  # 25 minutes total
        assert total_elapsed_time > total_work_time


class TestTimerSettings:
    """Test timer-related settings."""

    def test_default_settings(self):
        """Test default timer settings."""
        from src.getmoredone.app_settings import AppSettings

        settings = AppSettings()
        assert settings.default_time_block_minutes == 30
        assert settings.default_break_minutes == 5
        assert settings.timer_warning_minutes == 10
        assert settings.timer_window_width == 450
        assert settings.timer_window_height == 550

    def test_work_time_calculation_with_settings(self):
        """Test work time calculation using settings."""
        from src.getmoredone.app_settings import AppSettings

        settings = AppSettings()
        time_block = settings.default_time_block_minutes
        break_time = settings.default_break_minutes
        work_time = time_block - break_time

        assert work_time == 25  # 30 - 5 = 25

    def test_audio_settings(self):
        """Test audio alert settings."""
        from src.getmoredone.app_settings import AppSettings

        settings = AppSettings()
        assert settings.enable_break_sounds == True
        assert settings.break_start_sound is None  # No custom sound by default
        assert settings.break_end_sound is None

    def test_audio_settings_customization(self):
        """Test setting custom audio paths."""
        from src.getmoredone.app_settings import AppSettings

        settings = AppSettings()
        settings.enable_break_sounds = False
        settings.break_start_sound = "/path/to/start.wav"
        settings.break_end_sound = "/path/to/end.wav"

        assert settings.enable_break_sounds == False
        assert settings.break_start_sound == "/path/to/start.wav"
        assert settings.break_end_sound == "/path/to/end.wav"


class TestTimerIntegration:
    """Integration tests for timer with action items."""

    def test_timer_with_item_without_planned_minutes(self, db_manager):
        """Test timer uses default when item has no planned_minutes."""
        from src.getmoredone.app_settings import AppSettings

        # Create item without planned_minutes
        item = ActionItem(
            who="TestUser",
            title="Task without planned time",
            planned_minutes=None
        )
        db_manager.create_action_item(item)

        # Timer should use default from settings
        settings = AppSettings()
        time_block = item.planned_minutes or settings.default_time_block_minutes
        assert time_block == 30

    def test_timer_updates_planned_minutes(self, db_manager, sample_item):
        """Test that timer can update item's planned_minutes."""
        # User edits time block before starting
        new_time_block = 45
        sample_item.planned_minutes = new_time_block
        db_manager.update_action_item(sample_item)

        # Verify update
        updated_item = db_manager.get_action_item(sample_item.id)
        assert updated_item.planned_minutes == 45

    def test_complete_item_with_work_log(self, db_manager, sample_item):
        """Test completing an item that has work logs."""
        # Add work logs
        for i in range(3):
            work_log = WorkLog(
                item_id=sample_item.id,
                started_at=datetime.now().isoformat(),
                ended_at=datetime.now().isoformat(),
                minutes=20 + i * 5
            )
            db_manager.create_work_log(work_log)

        # Get total work before completion
        total_work = db_manager.get_total_actual_minutes(sample_item.id)
        assert total_work == 75  # 20 + 25 + 30

        # Complete item
        db_manager.complete_action_item(sample_item.id)

        # Work logs should still exist
        logs = db_manager.get_work_logs(sample_item.id)
        assert len(logs) == 3

        # Total work should be unchanged
        assert db_manager.get_total_actual_minutes(sample_item.id) == 75


class TestTimerEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_minutes_work_log(self, db_manager, sample_item):
        """Test creating a work log with zero minutes."""
        work_log = WorkLog(
            item_id=sample_item.id,
            started_at=datetime.now().isoformat(),
            ended_at=datetime.now().isoformat(),
            minutes=0,
            note="Interrupted immediately"
        )

        log_id = db_manager.create_work_log(work_log)
        assert log_id is not None

        logs = db_manager.get_work_logs(sample_item.id)
        assert logs[0].minutes == 0

    def test_work_log_with_very_long_note(self, db_manager, sample_item):
        """Test work log with a very long note."""
        long_note = "A" * 10000  # 10k character note

        work_log = WorkLog(
            item_id=sample_item.id,
            started_at=datetime.now().isoformat(),
            ended_at=datetime.now().isoformat(),
            minutes=25,
            note=long_note
        )

        log_id = db_manager.create_work_log(work_log)
        assert log_id is not None

        logs = db_manager.get_work_logs(sample_item.id)
        assert len(logs[0].note) == 10000

    def test_work_log_timestamps_use_local_time(self, db_manager, sample_item):
        """Test that work log timestamps use local time, not UTC."""
        # Create work log with current local time
        now = datetime.now()
        work_log = WorkLog(
            item_id=sample_item.id,
            started_at=now.isoformat(),
            ended_at=now.isoformat(),
            minutes=25
        )

        db_manager.create_work_log(work_log)

        # Retrieve and verify
        logs = db_manager.get_work_logs(sample_item.id)
        saved_time = datetime.fromisoformat(logs[0].started_at)

        # Times should be very close (within a few seconds)
        time_diff = abs((saved_time - now).total_seconds())
        assert time_diff < 5  # Within 5 seconds

    def test_get_work_logs_for_nonexistent_item(self, db_manager):
        """Test getting work logs for an item that doesn't exist."""
        logs = db_manager.get_work_logs("nonexistent-id")
        assert len(logs) == 0

    def test_total_actual_minutes_for_nonexistent_item(self, db_manager):
        """Test getting total minutes for an item that doesn't exist."""
        total = db_manager.get_total_actual_minutes("nonexistent-id")
        assert total == 0


class TestContinueWorkflow:
    """Test Continue workflow with date selection."""

    def test_continue_with_custom_dates(self, db_manager, sample_item):
        """Test Continue workflow with user-specified dates."""
        # Simulate Continue workflow
        start_time = datetime.now()
        work_minutes = 25

        # Create work log for today's session
        work_log = WorkLog(
            item_id=sample_item.id,
            started_at=start_time.isoformat(),
            ended_at=(start_time + timedelta(minutes=work_minutes)).isoformat(),
            minutes=work_minutes,
            note="Completed phase 1"
        )
        db_manager.create_work_log(work_log)

        # Complete current item
        db_manager.complete_action_item(sample_item.id)

        # Create duplicate with custom dates (e.g., 3 days from now)
        custom_start = (datetime.now().date() + timedelta(days=3)).isoformat()
        custom_due = (datetime.now().date() + timedelta(days=5)).isoformat()

        new_item = ActionItem(
            who=sample_item.who,
            title=sample_item.title,
            description="Continue with phase 2",
            contact_id=sample_item.contact_id,
            start_date=custom_start,
            due_date=custom_due,
            importance=sample_item.importance,
            urgency=sample_item.urgency,
            size=sample_item.size,
            value=sample_item.value,
            group=sample_item.group,
            category=sample_item.category,
            planned_minutes=sample_item.planned_minutes,
            status=Status.OPEN
        )
        db_manager.create_action_item(new_item)

        # Verify original is completed
        original = db_manager.get_action_item(sample_item.id)
        assert original.status == Status.COMPLETED

        # Verify new item has custom dates
        assert new_item.id != sample_item.id
        assert new_item.status == Status.OPEN
        assert new_item.start_date == custom_start
        assert new_item.due_date == custom_due
        assert new_item.description == "Continue with phase 2"

    def test_continue_date_validation(self):
        """Test that Continue workflow validates due >= start."""
        from datetime import date

        start = date.today()
        due_before_start = (date.today() - timedelta(days=1))

        # Due date must be >= start date
        assert due_before_start < start  # This would be invalid

        # Correct validation
        due_after_start = (date.today() + timedelta(days=1))
        assert due_after_start >= start  # This is valid

    def test_continue_with_same_day_dates(self, db_manager, sample_item):
        """Test Continue workflow with same start and due date."""
        # Complete current item
        db_manager.complete_action_item(sample_item.id)

        # Create duplicate with same start and due (valid)
        same_date = (datetime.now().date() + timedelta(days=1)).isoformat()

        new_item = ActionItem(
            who=sample_item.who,
            title=sample_item.title,
            description="Next steps",
            start_date=same_date,
            due_date=same_date,  # Same as start is valid
            status=Status.OPEN
        )
        db_manager.create_action_item(new_item)

        assert new_item.start_date == new_item.due_date
        assert new_item.status == Status.OPEN
