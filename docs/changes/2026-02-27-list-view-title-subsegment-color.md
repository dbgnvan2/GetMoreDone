# Handoff Note

- Date: 2026-02-27
- Agent: Code
- Topic: List view title color now prefers SubSegment color

## Summary
Updated shared list-row color resolution so title coloring prefers SubSegment color (when an item is linked to an Annual Plan Element with segment/subsegment names). Segment color remains the fallback when subsegment color cannot be resolved.

This affects list-view screens that use `resolve_segment_color_for_item` for title color styling.

## Files changed
- src/getmoredone/screens/segment_color_utils.py
- docs/changes/2026-02-27-list-view-title-subsegment-color.md

## Verification
- Command: `pytest -q`
- Result: PASS

## Risks / Known gaps
- Color preference relies on name-based lookup (`annual_plan_elements` names to `vision_subsegments` names); mismatched naming could trigger fallback to segment color.

## Next agent actions
- Docs Agent: optional note in changelog about list-title color source change (segment -> subsegment preference).
