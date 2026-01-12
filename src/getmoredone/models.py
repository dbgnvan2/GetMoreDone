"""
Data models for GetMoreDone application.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass
class Contact:
    """Represents a contact/client."""

    name: str
    contact_type: str = "Contact"  # Client, Contact, or Personal
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True
    id: Optional[int] = None  # None for new contacts, set by DB
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ActionItem:
    """Represents a trackable action item."""

    who: str
    title: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    importance: Optional[int] = None
    urgency: Optional[int] = None
    size: Optional[int] = None
    value: Optional[int] = None
    priority_score: int = 0
    group: Optional[str] = None
    category: Optional[str] = None
    planned_minutes: Optional[int] = None
    status: str = "open"
    completed_at: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def calculate_priority_score(self) -> int:
        """
        Calculate priority score as product of all factors.
        Returns 0 if any factor is 0 or None.
        """
        factors = [
            self.importance or 0,
            self.urgency or 0,
            self.size or 0,
            self.value or 0
        ]

        if any(f == 0 for f in factors):
            return 0

        score = 1
        for f in factors:
            score *= f
        return score

    def update_priority_score(self):
        """Update the priority_score field based on current factors."""
        self.priority_score = self.calculate_priority_score()


@dataclass
class ItemLink:
    """Represents a link/attachment on an action item."""

    item_id: str
    url: str
    label: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Defaults:
    """Represents default values for action item fields."""

    scope_type: str  # "system" or "who"
    scope_key: Optional[str] = None  # None for system, who value for who-scope
    importance: Optional[int] = None
    urgency: Optional[int] = None
    size: Optional[int] = None
    value: Optional[int] = None
    group: Optional[str] = None
    category: Optional[str] = None
    planned_minutes: Optional[int] = None
    start_offset_days: Optional[int] = None
    due_offset_days: Optional[int] = None


@dataclass
class RescheduleHistory:
    """Represents a reschedule event for an action item."""

    item_id: str
    from_start: Optional[str] = None
    from_due: Optional[str] = None
    to_start: Optional[str] = None
    to_due: Optional[str] = None
    reason: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TimeBlock:
    """Represents a planned time block."""

    block_date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    planned_minutes: int
    item_id: Optional[str] = None
    label: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class WorkLog:
    """Represents actual work performed on an action item."""

    item_id: str
    started_at: str  # ISO datetime
    minutes: int
    ended_at: Optional[str] = None  # ISO datetime
    note: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# Priority factor constants
class PriorityFactors:
    """Constants for priority factor values."""

    IMPORTANCE = {
        "Critical": 20,
        "High": 10,
        "Medium": 5,
        "Low": 1,
        "None": 0
    }

    URGENCY = {
        "Critical": 20,
        "High": 10,
        "Medium": 5,
        "Low": 1,
        "None": 0
    }

    SIZE = {
        "XL": 16,
        "L": 8,
        "M": 4,
        "S": 2,
        "P": 0
    }

    VALUE = {
        "XL": 16,
        "L": 8,
        "M": 4,
        "S": 2,
        "P": 0
    }


# Status constants
class Status:
    """Valid status values for action items."""

    OPEN = "open"
    COMPLETED = "completed"
    CANCELED = "canceled"
