# Handoff Note

- Date: 2026-03-02
- Agent: Code
- Topic: Critical I/U fields render red in list views

## Summary
- Updated list-view factor field rendering so `I` (Importance) and `U` (Urgency) fields use a red background when value is Critical (`20`).
- Kept all factor text black for readability consistency.

## Files changed
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/today.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/completed.py

## Verification
- Command: `python3 -m compileall -q src/getmoredone/screens/all_items.py src/getmoredone/screens/today.py src/getmoredone/screens/upcoming.py src/getmoredone/screens/completed.py`
- Result: PASS
- Command: `pytest -q tests/test_weekly_item_filters.py tests/test_weekly_title_cleanup.py tests/test_vps_hub_crud.py`
- Result: PASS (8 passed)

## Risks / Known gaps
- This change applies where expanded factor columns are shown; collapsed views still indicate criticality via row-level styling where already implemented.

## Next agent actions
- Visual QA each list view with columns expanded to confirm only critical `I`/`U` fields show red background.
