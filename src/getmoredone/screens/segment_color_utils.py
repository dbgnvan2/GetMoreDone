"""Utilities for resolving VPS segment colors on screen rows."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..models import ActionItem

DEFAULT_SEGMENT_COLOR = "#334155"


def resolve_segment_color_for_item(
    item: ActionItem,
    segment_colors_by_id: Dict[str, str],
    segment_colors_by_name: Dict[str, str],
    db_manager: Any,
    parent_segment_cache: Dict[str, Tuple[Optional[str], Optional[str], Optional[str]]],
    ape_segment_cache: Dict[str, Optional[str]],
    week_action_cache: Dict[str, Optional[str]],
) -> Optional[str]:
    """Return the hex color for an action item based on its segment lineage."""

    # 1) Direct segment ID on the action item
    color = _color_from_segment_id(
        getattr(item, "segment_description_id", None), segment_colors_by_id
    )
    if color:
        return color

    # 2) Segment stored on linked week_action row
    color = _color_from_week_action(
        getattr(item, "week_action_id", None),
        segment_colors_by_id,
        db_manager,
        week_action_cache,
    )
    if color:
        return color

    # 3) Segment from parent Weekly item (cached)
    color = _color_from_parent(
        getattr(item, "parent_id", None),
        segment_colors_by_id,
        segment_colors_by_name,
        db_manager,
        parent_segment_cache,
        ape_segment_cache,
        week_action_cache,
    )
    if color:
        return color

    # 4) Segment derived from annual plan element linkage
    return _color_from_ape(
        getattr(item, "annual_plan_element_id", None),
        segment_colors_by_name,
        db_manager,
        ape_segment_cache,
    )


def _normalize_color(color: Optional[str]) -> Optional[str]:
    """Ensure we return a non-empty hex color when available."""
    if not color:
        return None
    stripped = color.strip()
    return stripped or DEFAULT_SEGMENT_COLOR


def _color_from_segment_id(segment_id: Optional[str], segment_colors: Dict[str, str]) -> Optional[str]:
    if not segment_id:
        return None
    return _normalize_color(segment_colors.get(segment_id))


def _color_from_parent(
    parent_id: Optional[str],
    segment_colors_by_id: Dict[str, str],
    segment_colors_by_name: Dict[str, str],
    db_manager: Any,
    parent_segment_cache: Dict[str, Tuple[Optional[str], Optional[str], Optional[str]]],
    ape_segment_cache: Dict[str, Optional[str]],
    week_action_cache: Dict[str, Optional[str]],
) -> Optional[str]:
    if not parent_id:
        return None

    if parent_id not in parent_segment_cache:
        parent = db_manager.get_action_item(parent_id)
        if parent:
            parent_segment_cache[parent_id] = (
                getattr(parent, "segment_description_id", None),
                getattr(parent, "annual_plan_element_id", None),
                getattr(parent, "week_action_id", None),
            )
        else:
            parent_segment_cache[parent_id] = (None, None, None)

    parent_segment_id, parent_ape_id, parent_week_action_id = parent_segment_cache[parent_id]
    color = _color_from_segment_id(parent_segment_id, segment_colors_by_id)
    if color:
        return color
    color = _color_from_week_action(
        parent_week_action_id,
        segment_colors_by_id,
        db_manager,
        week_action_cache,
    )
    if color:
        return color
    return _color_from_ape(parent_ape_id, segment_colors_by_name, db_manager, ape_segment_cache)


def _color_from_ape(
    ape_id: Optional[str],
    segment_colors_by_name: Dict[str, str],
    db_manager: Any,
    ape_segment_cache: Dict[str, Optional[str]],
) -> Optional[str]:
    if not ape_id:
        return None

    if ape_id not in ape_segment_cache:
        segment_name = None
        if hasattr(db_manager, "db") and db_manager.db and db_manager.db.conn:
            row = db_manager.db.conn.execute(
                "SELECT segment_name FROM annual_plan_elements WHERE id = ?",
                (ape_id,),
            ).fetchone()
            if row:
                segment_name = (row["segment_name"] or "").strip().lower()
        ape_segment_cache[ape_id] = (
            segment_colors_by_name.get(segment_name) if segment_name else None
        )

    return ape_segment_cache.get(ape_id)


def _color_from_week_action(
    week_action_id: Optional[str],
    segment_colors_by_id: Dict[str, str],
    db_manager: Any,
    week_action_cache: Dict[str, Optional[str]],
) -> Optional[str]:
    if not week_action_id:
        return None

    if week_action_id not in week_action_cache:
        color = None
        if hasattr(db_manager, "db") and db_manager.db and db_manager.db.conn:
            row = db_manager.db.conn.execute(
                "SELECT segment_description_id FROM week_actions WHERE id = ?",
                (week_action_id,),
            ).fetchone()
            if row and row["segment_description_id"]:
                color = _color_from_segment_id(row["segment_description_id"], segment_colors_by_id)
        week_action_cache[week_action_id] = color

    return week_action_cache.get(week_action_id)
