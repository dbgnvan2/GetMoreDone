"""
Date utility functions for weekend-aware date calculations.
"""

from datetime import date, timedelta
from typing import Optional, Tuple


def increment_date(start_date: date, days: int, include_saturday: bool = True, include_sunday: bool = True) -> date:
    """
    Increment a date by the specified number of days, skipping weekends if configured.

    Args:
        start_date: The starting date
        days: Number of days to increment (can be negative for decrement)
        include_saturday: Whether Saturday is included in date calculations
        include_sunday: Whether Sunday is included in date calculations

    Returns:
        The new date, potentially adjusted to skip excluded weekend days

    Note:
        - If both Saturday and Sunday are included, this behaves like normal date arithmetic
        - If one or both weekend days are excluded, the function will skip over them
        - This only applies to automated calculations; manual date entry is unrestricted
    """
    # If both weekend days are included, just do normal date arithmetic
    if include_saturday and include_sunday:
        return start_date + timedelta(days=days)

    # Calculate the direction of movement
    direction = 1 if days > 0 else -1
    remaining_days = abs(days)
    current_date = start_date

    # Move day by day, skipping excluded weekend days
    while remaining_days > 0:
        current_date += timedelta(days=direction)

        # Check if current date is an excluded weekend day
        weekday = current_date.weekday()  # 0=Monday, 5=Saturday, 6=Sunday
        is_excluded_saturday = weekday == 5 and not include_saturday
        is_excluded_sunday = weekday == 6 and not include_sunday

        # Only count this day if it's not an excluded weekend day
        if not (is_excluded_saturday or is_excluded_sunday):
            remaining_days -= 1

    return current_date


def adjust_to_business_day(target_date: date, include_saturday: bool = True, include_sunday: bool = True) -> date:
    """
    Adjust a date forward to the next business day if it falls on an excluded weekend day.

    Args:
        target_date: The date to potentially adjust
        include_saturday: Whether Saturday is included as a business day
        include_sunday: Whether Sunday is included as a business day

    Returns:
        The adjusted date (same as input if already a business day)
    """
    # If both weekend days are included, no adjustment needed
    if include_saturday and include_sunday:
        return target_date

    current_date = target_date

    # Keep moving forward until we find a non-excluded day
    while True:
        weekday = current_date.weekday()  # 0=Monday, 5=Saturday, 6=Sunday

        is_excluded_saturday = weekday == 5 and not include_saturday
        is_excluded_sunday = weekday == 6 and not include_sunday

        # If this day is acceptable, return it
        if not (is_excluded_saturday or is_excluded_sunday):
            return current_date

        # Move to next day
        current_date += timedelta(days=1)


def get_next_business_day(from_date: date, include_saturday: bool = True, include_sunday: bool = True) -> date:
    """
    Get the next business day after the given date.

    This is a convenience function that increments by 1 day and adjusts to business day.

    Args:
        from_date: The starting date
        include_saturday: Whether Saturday is included as a business day
        include_sunday: Whether Sunday is included as a business day

    Returns:
        The next business day
    """
    return increment_date(from_date, 1, include_saturday, include_sunday)


def first_of_next_month(today_date: date) -> date:
    year = today_date.year + (1 if today_date.month == 12 else 0)
    month = 1 if today_date.month == 12 else today_date.month + 1
    return date(year, month, 1)


def first_of_next_quarter(today_date: date) -> date:
    current_quarter = (today_date.month - 1) // 3 + 1
    next_quarter = current_quarter + 1
    year = today_date.year
    if next_quarter == 5:
        next_quarter = 1
        year += 1
    month = (next_quarter - 1) * 3 + 1
    return date(year, month, 1)


def future_date_targets(
    today_date: date,
    near_term_days: int,
    long_term_days: int,
    next_month_offset_days: int,
    next_quarter_offset_days: int,
) -> Tuple[date, date, date, date]:
    near_term_days = max(1, int(near_term_days))
    long_term_days = max(1, int(long_term_days))
    near_date = today_date + timedelta(days=near_term_days)
    long_date = today_date + timedelta(days=long_term_days)
    month_date = first_of_next_month(today_date) + timedelta(days=int(next_month_offset_days))
    quarter_date = first_of_next_quarter(today_date) + timedelta(days=int(next_quarter_offset_days))
    return near_date, long_date, month_date, quarter_date
