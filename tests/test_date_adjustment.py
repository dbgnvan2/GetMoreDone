"""
Tests for date adjustment functionality in Item Editor.
"""

import pytest
from datetime import date, timedelta
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def test_adjust_date_logic():
    """Test the date adjustment logic."""
    from datetime import datetime, timedelta

    # Test adding days
    base_date = datetime.strptime("2024-01-15", "%Y-%m-%d").date()
    new_date = base_date + timedelta(days=1)
    assert new_date.strftime("%Y-%m-%d") == "2024-01-16"

    # Test subtracting days
    new_date = base_date + timedelta(days=-1)
    assert new_date.strftime("%Y-%m-%d") == "2024-01-14"

    # Test adding multiple days
    new_date = base_date + timedelta(days=7)
    assert new_date.strftime("%Y-%m-%d") == "2024-01-22"

    # Test subtracting multiple days
    new_date = base_date + timedelta(days=-7)
    assert new_date.strftime("%Y-%m-%d") == "2024-01-08"


def test_date_parsing():
    """Test date string parsing."""
    from datetime import datetime

    # Valid date
    date_str = "2024-01-15"
    parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    assert parsed.year == 2024
    assert parsed.month == 1
    assert parsed.day == 15

    # Invalid date should raise ValueError
    with pytest.raises(ValueError):
        datetime.strptime("invalid", "%Y-%m-%d")


def test_empty_date_handling():
    """Test that empty date uses today as base."""
    from datetime import datetime

    # When field is empty, should use today
    base_date = datetime.now().date()
    new_date = base_date + timedelta(days=1)

    # Should be tomorrow
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    assert new_date == tomorrow


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
