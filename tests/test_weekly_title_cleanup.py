from datetime import datetime

from src.getmoredone.models import Defaults
from src.getmoredone.screens.title_format import split_action_item_title
from src.getmoredone.vps_manager import VPSManager


def _seed_minimal_ape(manager: VPSManager) -> str:
    conn = manager.db.conn
    now = datetime.now().isoformat()

    vision_segment_id = "vs-clean"
    vision_subsegment_id = "vsub-clean"
    vision_category_id = "vcat-clean"
    vision_element_id = "ve-clean"
    annual_vision_element_id = "ave-clean"
    ape_id = "ape-clean"

    conn.execute(
        """
        INSERT INTO vision_segments (id, name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (vision_segment_id, "Creative", now, now),
    )
    conn.execute(
        """
        INSERT INTO vision_subsegments (id, segment_id, name, color_hex, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (vision_subsegment_id, vision_segment_id, "Writing", "#44AA66", now, now),
    )
    conn.execute(
        """
        INSERT INTO vision_categories (id, subsegment_id, name, color_hex, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (vision_category_id, vision_subsegment_id, "APW Book", "#CC8844", now, now),
    )
    conn.execute(
        """
        INSERT INTO vision_elements (id, segment_id, subsegment_id, category_id, key_field, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            vision_element_id,
            vision_segment_id,
            vision_subsegment_id,
            vision_category_id,
            "Creative|Writing|APW Book",
            1,
            now,
            now,
        ),
    )
    conn.execute(
        """
        INSERT INTO annual_vision_elements (
            id, year, vision_element_id, segment_name, subsegment_name, category_name, key_field, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            annual_vision_element_id,
            2026,
            vision_element_id,
            "Creative",
            "Writing",
            "APW Book",
            "Creative|Writing|APW Book",
            now,
            now,
        ),
    )
    conn.execute(
        """
        INSERT INTO annual_plan_elements (
            id, year, vision_element_id, annual_vision_element_id,
            segment_name, subsegment_name, category_name, key_field,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ape_id,
            2026,
            vision_element_id,
            annual_vision_element_id,
            "Creative",
            "Writing",
            "APW Book",
            "Creative|Writing|APW Book",
            now,
            now,
        ),
    )
    conn.commit()
    return ape_id


def test_split_action_item_title_removes_legacy_week_date_stub():
    parsed = split_action_item_title("C|W|APW Book - W9 - (2026-02-23)")
    assert parsed.context == "C|W|APW Book - W9"
    assert parsed.title == ""

    parsed_with_body = split_action_item_title(
        "C|W|APW Book - W9 - (2026-02-23) - Draft chapter notes"
    )
    assert parsed_with_body.context == "C|W|APW Book - W9"
    assert parsed_with_body.title == "Draft chapter notes"


def test_create_week_items_no_date_in_title(tmp_path):
    db_path = tmp_path / "weekly-title-cleanup.db"
    manager = VPSManager(db_path=str(db_path))
    try:
        ape_id = _seed_minimal_ape(manager)
        result = manager.create_week_action_items_for_ape(ape_id, 2026, 2, ["2026-02-23"])
        assert result["created_count"] == 1

        row = manager.db.conn.execute(
            "SELECT title, \"group\" AS group_name FROM action_items WHERE id = ?", (result["created_ids"][0],)
        ).fetchone()
        assert row is not None
        assert row["title"] == "C|W|APW Book - W9"
        assert "(" not in row["title"]
        assert row["group_name"] == "Weekly Tactic"
    finally:
        manager.close()


def test_create_week_items_uses_system_priority_defaults(tmp_path):
    db_path = tmp_path / "weekly-title-defaults.db"
    manager = VPSManager(db_path=str(db_path))
    try:
        manager.db_manager.save_defaults(
            Defaults(
                scope_type="system",
                importance=10,
                urgency=20,
                size=4,
                value=8,
            )
        )
        ape_id = _seed_minimal_ape(manager)
        result = manager.create_week_action_items_for_ape(ape_id, 2026, 2, ["2026-02-23"])
        assert result["created_count"] == 1

        row = manager.db.conn.execute(
            "SELECT importance, urgency, size, value, priority_score, \"group\" AS group_name FROM action_items WHERE id = ?",
            (result["created_ids"][0],),
        ).fetchone()
        assert row is not None
        assert row["importance"] == 10
        assert row["urgency"] == 20
        assert row["size"] == 4
        assert row["value"] == 8
        assert row["priority_score"] == 6400
        assert row["group_name"] == "Weekly Tactic"
    finally:
        manager.close()
