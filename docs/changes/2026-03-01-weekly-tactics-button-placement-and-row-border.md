# Handoff Note

- Date: 2026-03-01
- Agent: Code
- Topic: Weekly tactics button placement and segment-colored row borders

## Summary
- Repositioned weekly-control buttons so week-level actions live under the Weekly Tactics panel (left), and related-action controls stay under the Related Action Items panel (right).
- Renamed `Open Weekly Action` to `Edit Week Tactic`.
- Renamed `+ Action Item` to `Add Action Item`.
- Added a `2px` border to each Weekly Tactics row using that row's resolved Segment color.

## Files changed
- src/getmoredone/screens/weekly_items.py

## Verification
- Command: `pytest -q tests/test_weekly_item_filters.py tests/test_weekly_title_cleanup.py`
- Result: PASS (3 passed)
- Command: `python3 -m compileall -q src/getmoredone/screens/weekly_items.py`
- Result: PASS

## Risks / Known gaps
- Border contrast depends on segment color brightness; very light segment colors may look subtle against light backgrounds.

## Next agent actions
- Visually verify button positions at your preferred window width and confirm row border thickness/contrast for all segment colors.
