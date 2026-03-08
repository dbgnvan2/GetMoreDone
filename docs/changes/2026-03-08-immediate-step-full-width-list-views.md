# Handoff Note

- Date: 2026-03-08
- Agent: Code
- Topic: immediate-step-full-width-list-views

## Summary
Updated all main Action Item list views so the **Immediate Step** column uses the full available row width instead of truncating to a fixed character limit/width.

Applied to:
- Today
- Upcoming
- All Items
- Completed
- Hierarchical

Implementation details:
- Removed Immediate Step title truncation in row renderers.
- Removed fixed title width clamps so the title cell expands with available space.
- Adjusted the All Items header column weighting so Immediate Step is the flex column.
- Preserved existing Context/Who/date/priority columns and existing WT badge behavior.

## Files changed
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/today.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/completed.py
- src/getmoredone/screens/hierarchical.py
- docs/changes/2026-03-08-immediate-step-full-width-list-views.md

## Verification
- Command: `python3 -m py_compile src/getmoredone/screens/all_items.py src/getmoredone/screens/today.py src/getmoredone/screens/upcoming.py src/getmoredone/screens/completed.py src/getmoredone/screens/hierarchical.py`
- Result: PASS
- Command: `pytest -q tests/test_today_screen.py tests/test_upcoming_items.py tests/test_database.py`
- Result: PASS

## Risks / Known gaps
- This is a UI/layout behavior change and still needs runtime visual confirmation on your preferred window sizes.

## Next agent actions
- Docs Agent: optional UI note/screenshots update for wider Immediate Step display in list views.
