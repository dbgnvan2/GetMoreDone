# Handoff Note

- Date: 2026-03-02
- Agent: Code
- Topic: Drag Schedule list view lineage columns + color chips

## Summary
Refactored the Drag Schedule "Next Items" list to match the newer list-view treatment by adding a compact header and per-row columns for `Immediate Step`, `Segment`, `SubSegment`, `Category`, and `Date`.
Rows now resolve lineage from APE linkage first (with parent fallback), then from structured title context, and apply Segment/SubSegment/Category background chips using live VPS colors.

## Files changed
- src/getmoredone/screens/drag_schedule.py

## Verification
- Command: `python3 -m compileall src/getmoredone/screens/drag_schedule.py`
- Result: PASS
- Command: `pytest -q tests/test_color_contrast.py tests/test_weekly_title_cleanup.py`
- Result: PASS
- Command: `pytest -q`
- Result: PASS (`221 passed, 1 skipped`)

## Risks / Known gaps
- Items without APE linkage and without structured `SEG|SUB|CAT` context fall back to segment-only lineage (subsegment/category show `-`).
- Drag Schedule row height is still governed by the existing `drag_schedule_box_height_px` setting; very large values can reduce density.

## Next agent actions
- If needed, add a shared lineage resolver helper for action-item screens to reduce duplicated fallback logic.
- If UX asks for higher density, split `drag_schedule_box_height_px` into independent controls for date boxes vs item rows.
