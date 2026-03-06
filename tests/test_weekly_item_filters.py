"""
Regression tests for Set Weekly Tactic data sources.

These cover the helper queries shared between the Vision Planning APE Weekly
screen and the Action Item editor dialog so we know a populated database
actually returns records for the picker.
"""

from datetime import datetime

from src.getmoredone.models import ActionItem
from src.getmoredone.screens.segment_color_utils import resolve_segment_color_for_item
from src.getmoredone.vps_manager import VPSManager


def _seed_weekly_item(manager: VPSManager) -> None:
    conn = manager.db.conn
    now = datetime.now().isoformat()

    seg_id = "seg-test"
    conn.execute(
        """
        INSERT INTO segment_descriptions (id, name, description, color_hex, order_index, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (seg_id, "Creative", "Test Segment", "#112233", 1, 1, now, now),
    )

    vision_segment_id = "vs-1"
    vision_subsegment_id = "vsub-1"
    vision_category_id = "vcat-1"
    vision_element_id = "ve-1"
    annual_vision_element_id = "ave-1"
    ape_id = "ape-test"

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
        (vision_subsegment_id, vision_segment_id, "Books", "#44AA66", now, now),
    )
    conn.execute(
        """
        INSERT INTO vision_categories (id, subsegment_id, name, color_hex, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (vision_category_id, vision_subsegment_id, "Learning", "#CC8844", now, now),
    )
    conn.execute(
        """
        INSERT INTO vision_elements (id, segment_id, subsegment_id, category_id, key_field, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (vision_element_id, vision_segment_id, vision_subsegment_id, vision_category_id, "Creative|Books", 1, now, now),
    )
    conn.execute(
        """
        INSERT INTO annual_vision_elements (
            id, year, vision_element_id, segment_name, subsegment_name, category_name, key_field, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (annual_vision_element_id, 2026, vision_element_id, "Creative", "Books", "Learning", "Creative|Books", now, now),
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
            "Books",
            "Learning",
            "Creative|Books",
            now,
            now,
        ),
    )

    conn.commit()

    weekly_item = ActionItem(
        who="Tester",
        title="C|W|APW Book - W9",
        start_date="2026-02-23",
        due_date="2026-03-01",
        item_type="week",
        annual_plan_element_id=ape_id,
        segment_description_id=seg_id,
    )
    manager.db_manager.create_action_item(weekly_item, apply_defaults=False)


def test_weekly_item_helpers_return_records(tmp_path):
    db_path = tmp_path / "weekly.db"
    manager = VPSManager(db_path=str(db_path))
    try:
        _seed_weekly_item(manager)

        items = manager.get_weekly_action_items_in_range(
            "2026-02-01",
            "2026-02-29",
            ape_only=True,
        )
        assert len(items) == 1
        assert items[0]["title"] == "C|W|APW Book - W9"

        # Month picker metadata should include February 2026
        months = manager.get_weekly_action_item_months()
        assert months and months[0]["month"] == 2 and months[0]["year"] == 2026

        # All-weeks fallback uses the stored min/max bounds
        bounds = manager.get_weekly_action_item_bounds()
        assert bounds == ("2026-02-23", "2026-02-23")

        catalog = manager.get_weekly_action_items(ape_only=True)
        assert len(catalog) == 1
        assert catalog[0]["ape_segment_name"] == "Creative"
        assert catalog[0]["ape_subsegment_name"] == "Books"
        assert catalog[0]["ape_category_name"] == "Learning"

        weekly_item = manager.db_manager.get_action_item(catalog[0]["id"])
        color = resolve_segment_color_for_item(
            weekly_item,
            manager.get_segment_colors_by_id(),
            manager.get_segment_color_map(),
            manager.db_manager,
            {},
            {},
            {},
        )
        assert color == "#CC8844"
    finally:
        manager.close()
