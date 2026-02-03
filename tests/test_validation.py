"""
Tests for validation functionality.
"""

import pytest
from src.getmoredone.models import ActionItem, PriorityFactors
from src.getmoredone.validation import Validator, ValidationError


def test_validate_who_required():
    """Test that 'who' field is required."""
    item = ActionItem(who="", title="Test")
    errors = Validator.validate_action_item(item)

    assert len(errors) > 0
    assert any(e.field == "who" for e in errors)


def test_validate_title_required():
    """Test that 'title' field is required."""
    item = ActionItem(who="User", title="")
    errors = Validator.validate_action_item(item)

    assert len(errors) > 0
    assert any(e.field == "title" for e in errors)


def test_validate_due_before_start():
    """Test that due date cannot be before start date."""
    item = ActionItem(
        who="User",
        title="Test",
        start_date="2024-01-15",
        due_date="2024-01-10"  # Before start
    )
    errors = Validator.validate_action_item(item)

    assert len(errors) > 0
    assert any(e.field == "due_date" for e in errors)


def test_validate_valid_item():
    """Test that a valid item passes validation."""
    item = ActionItem(
        who="User",
        title="Valid Task",
        start_date="2024-01-10",
        due_date="2024-01-15",
        importance=PriorityFactors.IMPORTANCE["High"],
        urgency=PriorityFactors.URGENCY["Medium"],
        size=PriorityFactors.SIZE["M"],
        value=PriorityFactors.VALUE["L"]
    )
    errors = Validator.validate_action_item(item)

    assert len(errors) == 0


def test_validate_invalid_importance():
    """Test that invalid importance value is caught."""
    item = ActionItem(
        who="User",
        title="Test",
        importance=999  # Invalid value
    )
    errors = Validator.validate_action_item(item)

    assert len(errors) > 0
    assert any(e.field == "importance" for e in errors)


def test_parse_date_various_formats():
    """Test date parsing with various formats."""
    # YYYY-MM-DD
    result = Validator.parse_date("2024-01-15")
    assert result == "2024-01-15"

    # MM/DD/YYYY
    result = Validator.parse_date("01/15/2024")
    assert result == "2024-01-15"

    # Invalid
    result = Validator.parse_date("invalid-date")
    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
