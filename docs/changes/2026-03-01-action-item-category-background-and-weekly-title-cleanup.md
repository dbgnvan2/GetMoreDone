# Handoff Note

- Date: 2026-03-01
- Agent: Code
- Topic: Action item category-row colors and weekly immediate-step date cleanup

## Summary
- Updated the three action-item list views (`All Items`, `Today`, `Upcoming`) so each row background uses the resolved lineage color (category first, then fallback), and the Immediate Step text renders in black.
- Removed week-item title date suffix generation (`- (YYYY-MM-DD)`) at creation time so week records no longer inject date text into Immediate Step parsing.
- Added title parsing cleanup for legacy records so stored bodies like `(2026-02-23)` or `(2026-02-23) - ...` are stripped from the Immediate Step field.
- Added regression tests for both legacy title parsing cleanup and week-item title generation without date suffixes.

## Files changed
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/today.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/title_format.py
- src/getmoredone/screens/weekly_items.py
- src/getmoredone/vps_manager.py
- tests/test_weekly_title_cleanup.py

## Verification
- Command: `pytest -q tests/test_weekly_title_cleanup.py tests/test_weekly_item_filters.py tests/test_vision_planning_regressions.py`
- Result: PASS (8 passed)
- Command: `pytest -q`
- Result: PASS (215 passed, 1 skipped)

## Risks / Known gaps
- Existing saved action-item titles that include date text in non-standard formats beyond the new cleanup patterns may still need manual correction.
- Using explicit black text in list rows is intentional per request and may be lower contrast under non-light appearance modes.

## Next agent actions
- Validate visually in app that all three list views now show category-background rows and black Immediate Step text in your active theme.
- If dark mode support is required for these rows, switch title text to a semantic contrast helper that adapts by background luminance.
