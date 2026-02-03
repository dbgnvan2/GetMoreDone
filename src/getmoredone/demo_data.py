"""Demo data loader for GetMoreDone.

This is used for:
- onboarding / screenshots
- shared builds where a user wants to explore the app quickly

Important:
- This *adds* sample records into the target DB.
- It does not delete or overwrite existing action items.

"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .db_manager import DatabaseManager
from .models import ActionItem, Defaults, PriorityFactors


def load_demo_data(db_path: Optional[str] = None) -> int:
    """Insert demo data into the specified DB.

    Returns number of action items created.
    """
    db = DatabaseManager(db_path=db_path)
    created = 0

    try:
        # System defaults (upsert)
        system_defaults = Defaults(
            scope_type="system",
            importance=PriorityFactors.IMPORTANCE["Medium"],
            urgency=PriorityFactors.URGENCY["Medium"],
            size=PriorityFactors.SIZE["M"],
            value=PriorityFactors.VALUE["M"],
            planned_minutes=30,
        )
        db.save_defaults(system_defaults)

        # Who defaults (example)
        client_defaults = Defaults(
            scope_type="who",
            scope_key="ClientA",
            importance=PriorityFactors.IMPORTANCE["High"],
            urgency=PriorityFactors.URGENCY["High"],
            size=PriorityFactors.SIZE["L"],
            value=PriorityFactors.VALUE["L"],
            category="Client Work",
        )
        db.save_defaults(client_defaults)

        today = datetime.now().date()

        items = [
            ActionItem(
                who="Self",
                title="Review project proposal",
                description="Review and approve the Q1 project proposal",
                due_date=(today + timedelta(days=1)).isoformat(),
                importance=PriorityFactors.IMPORTANCE["High"],
                urgency=PriorityFactors.URGENCY["High"],
                size=PriorityFactors.SIZE["M"],
                value=PriorityFactors.VALUE["L"],
                category="Planning",
                planned_minutes=60,
            ),
            ActionItem(
                who="ClientA",
                title="Complete website redesign mockups",
                description="Create initial mockups for the website redesign project",
                due_date=(today + timedelta(days=2)).isoformat(),
                importance=PriorityFactors.IMPORTANCE["Critical"],
                urgency=PriorityFactors.URGENCY["High"],
                size=PriorityFactors.SIZE["XL"],
                value=PriorityFactors.VALUE["XL"],
                category="Design",
                planned_minutes=240,
            ),
            ActionItem(
                who="Self",
                title="Update documentation",
                description="Update the documentation with the latest changes",
                due_date=(today + timedelta(days=3)).isoformat(),
                importance=PriorityFactors.IMPORTANCE["Medium"],
                urgency=PriorityFactors.URGENCY["Low"],
                size=PriorityFactors.SIZE["S"],
                value=PriorityFactors.VALUE["M"],
                category="Documentation",
                planned_minutes=45,
            ),
            ActionItem(
                who="ClientB",
                title="Fix login bug",
                description="Debug and fix the login issue reported by users",
                due_date=today.isoformat(),
                importance=PriorityFactors.IMPORTANCE["Critical"],
                urgency=PriorityFactors.URGENCY["Critical"],
                size=PriorityFactors.SIZE["M"],
                value=PriorityFactors.VALUE["XL"],
                category="Bug Fix",
                planned_minutes=120,
            ),
            ActionItem(
                who="Self",
                title="Team meeting preparation",
                description="Prepare agenda and materials for weekly team meeting",
                due_date=today.isoformat(),
                importance=PriorityFactors.IMPORTANCE["Medium"],
                urgency=PriorityFactors.URGENCY["High"],
                size=PriorityFactors.SIZE["S"],
                value=PriorityFactors.VALUE["M"],
                category="Meetings",
                planned_minutes=30,
            ),
        ]

        for item in items:
            db.create_action_item(item, apply_defaults=False)
            created += 1

        completed_item = ActionItem(
            who="Self",
            title="Setup development environment",
            description="Install and configure all development tools",
            importance=PriorityFactors.IMPORTANCE["High"],
            urgency=PriorityFactors.URGENCY["High"],
            size=PriorityFactors.SIZE["M"],
            value=PriorityFactors.VALUE["L"],
            category="Setup",
            status="completed",
            completed_at=datetime.now().isoformat(),
        )
        db.create_action_item(completed_item, apply_defaults=False)
        created += 1

    finally:
        db.close()

    return created
