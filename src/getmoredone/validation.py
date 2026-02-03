"""
Validation logic for GetMoreDone application.
"""

from datetime import datetime
from typing import Dict, List, Optional

from .models import ActionItem, PriorityFactors


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class Validator:
    """Validates action items and related entities."""

    @staticmethod
    def validate_action_item(item: ActionItem) -> List[ValidationError]:
        """
        Validate an action item.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Required: who
        if not item.who or not item.who.strip():
            errors.append(ValidationError("who", "Who is required"))

        # Required: title
        if not item.title or not item.title.strip():
            errors.append(ValidationError("title", "Title is required"))

        # Date validation: due_date must not be earlier than start_date
        if item.start_date and item.due_date:
            try:
                start = datetime.fromisoformat(item.start_date.replace('Z', '+00:00'))
                due = datetime.fromisoformat(item.due_date.replace('Z', '+00:00'))
                if due < start:
                    errors.append(
                        ValidationError("due_date", "Due date cannot be earlier than start date")
                    )
            except ValueError:
                errors.append(ValidationError("dates", "Invalid date format"))

        # Validate priority factors if present
        if item.importance is not None:
            if item.importance not in PriorityFactors.IMPORTANCE.values():
                errors.append(
                    ValidationError(
                        "importance",
                        f"Invalid importance value. Must be one of: {list(PriorityFactors.IMPORTANCE.values())}"
                    )
                )

        if item.urgency is not None:
            if item.urgency not in PriorityFactors.URGENCY.values():
                errors.append(
                    ValidationError(
                        "urgency",
                        f"Invalid urgency value. Must be one of: {list(PriorityFactors.URGENCY.values())}"
                    )
                )

        if item.size is not None:
            if item.size not in PriorityFactors.SIZE.values():
                errors.append(
                    ValidationError(
                        "size",
                        f"Invalid size value. Must be one of: {list(PriorityFactors.SIZE.values())}"
                    )
                )

        if item.value is not None:
            if item.value not in PriorityFactors.VALUE.values():
                errors.append(
                    ValidationError(
                        "value",
                        f"Invalid value. Must be one of: {list(PriorityFactors.VALUE.values())}"
                    )
                )

        # Validate planned_minutes if present
        if item.planned_minutes is not None and item.planned_minutes < 0:
            errors.append(ValidationError("planned_minutes", "Planned minutes cannot be negative"))

        # Validate status
        valid_statuses = ["open", "completed", "canceled"]
        if item.status not in valid_statuses:
            errors.append(
                ValidationError("status", f"Status must be one of: {valid_statuses}")
            )

        return errors

    @staticmethod
    def validate_and_raise(item: ActionItem):
        """
        Validate action item and raise exception if invalid.

        Raises:
            ValidationError: If validation fails
        """
        errors = Validator.validate_action_item(item)
        if errors:
            raise errors[0]

    @staticmethod
    def parse_date(date_str: str) -> Optional[str]:
        """
        Parse and validate a date string.

        Args:
            date_str: Date string in various formats

        Returns:
            Normalized YYYY-MM-DD string or None if invalid
        """
        if not date_str:
            return None

        try:
            # Try parsing various formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

            # If all formats fail, return None
            return None
        except Exception:
            return None

    @staticmethod
    def get_validation_messages(errors: List[ValidationError]) -> Dict[str, str]:
        """
        Convert list of validation errors to field -> message dict.

        Args:
            errors: List of validation errors

        Returns:
            Dict mapping field names to error messages
        """
        return {error.field: error.message for error in errors}
