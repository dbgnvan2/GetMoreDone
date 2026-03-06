from pathlib import Path

import pytest

from src.getmoredone.vps_manager import VPSManager


def _manager(tmp_path: Path) -> VPSManager:
    db_path = tmp_path / "vps_subsegments.db"
    return VPSManager(str(db_path))


def test_subsegment_gets_default_related_color(tmp_path):
    manager = _manager(tmp_path)
    try:
        seg_name = manager.get_all_segments(active_only=False)[0]["name"]
        manager.create_vision_subsegment(seg_name, "Blog")
        manager.create_or_get_vision_element(seg_name, "Blog", "Content")
        rows = manager.get_vision_subsegments(seg_name)
        assert rows
        color = (rows[0].get("color_hex") or "").strip()
        assert color.startswith("#")
        assert len(color) == 7
    finally:
        manager.close()


def test_subsegment_color_can_be_overridden(tmp_path):
    manager = _manager(tmp_path)
    try:
        seg_name = manager.get_all_segments(active_only=False)[0]["name"]
        manager.create_vision_subsegment(seg_name, "Writing")
        manager.create_or_get_vision_element(seg_name, "Writing", "Book")
        row = manager.get_vision_subsegments(seg_name)[0]
        ok = manager.update_vision_subsegment_color(row["id"], "#7C3AED")
        assert ok is True
        updated = manager.get_vision_subsegments(seg_name)[0]
        assert updated["color_hex"] == "#7C3AED"
    finally:
        manager.close()


def test_segment_and_subsegment_must_exist_in_settings_first(tmp_path):
    manager = _manager(tmp_path)
    try:
        with pytest.raises(ValueError):
            manager.create_or_get_vision_element("Not In Settings", "Sub", "Cat")

        seg_name = manager.get_all_segments(active_only=False)[0]["name"]
        with pytest.raises(ValueError):
            manager.create_or_get_vision_element(seg_name, "Missing Subsegment", "Cat")

        manager.create_vision_subsegment(seg_name, "Configured Subsegment")
        ve_id = manager.create_or_get_vision_element(seg_name, "Configured Subsegment", "Cat")
        assert ve_id
    finally:
        manager.close()
