# Handoff Note

- Date: 2026-03-01
- Agent: Code
- Topic: Remove priority chip background in list views

## Summary
- Removed priority chip-style background from list view rows so Priority uses the same plain background style as other fields.
- Priority text remains black for consistency with prior list-view text updates.

## Files changed
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/today.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/hierarchical.py

## Verification
- Command: `python3 -m compileall -q src/getmoredone/screens/all_items.py src/getmoredone/screens/today.py src/getmoredone/screens/upcoming.py src/getmoredone/screens/hierarchical.py`
- Result: PASS
- Command: `pytest -q tests/test_weekly_item_filters.py tests/test_weekly_title_cleanup.py tests/test_vps_hub_crud.py`
- Result: PASS (8 passed)

## Risks / Known gaps
- None beyond expected visual change to priority emphasis.

## Next agent actions
- Visual QA in list views to confirm Priority field appearance matches adjacent fields.
