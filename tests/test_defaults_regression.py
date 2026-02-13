"""Regression tests for defaults behavior (priority, group/category, date offsets)."""

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import Defaults


def test_defaults_persist_priority_group_category_and_offsets(tmp_path):
    db_file = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_file))

    defaults = Defaults(
        scope_type="system",
        who="ClientA",
        importance=10,
        urgency=5,
        size=4,
        value=8,
        group="G-Alpha",
        category="C-Beta",
        planned_minutes=30,
        start_offset_days=2,
        due_offset_days=3,
    )
    db_manager.save_defaults(defaults)

    loaded = db_manager.get_defaults("system")
    assert loaded is not None
    assert loaded.who == "ClientA"
    assert loaded.importance == 10
    assert loaded.urgency == 5
    assert loaded.size == 4
    assert loaded.value == 8
    assert loaded.group == "G-Alpha"
    assert loaded.category == "C-Beta"
    assert loaded.planned_minutes == 30
    assert loaded.start_offset_days == 2
    assert loaded.due_offset_days == 3
