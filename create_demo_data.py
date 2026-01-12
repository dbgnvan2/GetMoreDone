#!/usr/bin/env python3
"""
Create demo data for GetMoreDone application.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from getmoredone.db_manager import DatabaseManager
from getmoredone.models import ActionItem, Defaults, PriorityFactors


def create_demo_data():
    """Create demo data in the database."""
    print("Creating demo data for GetMoreDone...")

    db = DatabaseManager()

    # Create system defaults
    print("Creating system defaults...")
    system_defaults = Defaults(
        scope_type="system",
        importance=PriorityFactors.IMPORTANCE["Medium"],
        urgency=PriorityFactors.URGENCY["Medium"],
        size=PriorityFactors.SIZE["M"],
        value=PriorityFactors.VALUE["M"],
        planned_minutes=30
    )
    db.save_defaults(system_defaults)

    # Create who-specific defaults
    print("Creating who-specific defaults...")
    client_defaults = Defaults(
        scope_type="who",
        scope_key="ClientA",
        importance=PriorityFactors.IMPORTANCE["High"],
        urgency=PriorityFactors.URGENCY["High"],
        size=PriorityFactors.SIZE["L"],
        value=PriorityFactors.VALUE["L"],
        category="Client Work"
    )
    db.save_defaults(client_defaults)

    # Create sample action items
    print("Creating sample action items...")

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
            planned_minutes=60
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
            planned_minutes=240
        ),
        ActionItem(
            who="Self",
            title="Update documentation",
            description="Update the API documentation with latest changes",
            due_date=(today + timedelta(days=3)).isoformat(),
            importance=PriorityFactors.IMPORTANCE["Medium"],
            urgency=PriorityFactors.URGENCY["Low"],
            size=PriorityFactors.SIZE["S"],
            value=PriorityFactors.VALUE["M"],
            category="Documentation",
            planned_minutes=45
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
            planned_minutes=120
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
            planned_minutes=30
        ),
        ActionItem(
            who="ClientA",
            title="Database migration",
            description="Migrate production database to new server",
            due_date=(today + timedelta(days=5)).isoformat(),
            importance=PriorityFactors.IMPORTANCE["High"],
            urgency=PriorityFactors.URGENCY["Medium"],
            size=PriorityFactors.SIZE["L"],
            value=PriorityFactors.VALUE["XL"],
            category="Infrastructure",
            planned_minutes=180
        ),
        ActionItem(
            who="Self",
            title="Code review",
            description="Review pull requests from team members",
            due_date=(today + timedelta(days=1)).isoformat(),
            importance=PriorityFactors.IMPORTANCE["Medium"],
            urgency=PriorityFactors.URGENCY["Medium"],
            size=PriorityFactors.SIZE["M"],
            value=PriorityFactors.VALUE["M"],
            category="Code Review",
            planned_minutes=60
        ),
    ]

    for item in items:
        db.create_action_item(item, apply_defaults=False)
        print(f"  Created: {item.title}")

    # Create one completed item
    print("Creating completed item...")
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
        completed_at=datetime.now().isoformat()
    )
    db.create_action_item(completed_item, apply_defaults=False)
    print(f"  Created: {completed_item.title} (completed)")

    db.close()
    print("\nDemo data created successfully!")
    print("Run the application with: python run.py")


if __name__ == "__main__":
    create_demo_data()
