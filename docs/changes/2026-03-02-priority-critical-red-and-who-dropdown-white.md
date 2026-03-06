# Handoff Note

- Date: 2026-03-02
- Agent: Code
- Topic: Priority critical highlighting + Who dropdown color fix

## Summary
- Updated list-view Priority field rendering so the Priority field gets a red background when either `importance` or `urgency` is Critical (`20`).
- Updated Who filter/search combobox styling to use white background and black text, including dropdown menu items.

## Files changed
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/today.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/completed.py
- src/getmoredone/screens/hierarchical.py

## Verification
- Command: `python3 -m compileall -q src/getmoredone/screens/all_items.py src/getmoredone/screens/today.py src/getmoredone/screens/upcoming.py src/getmoredone/screens/completed.py src/getmoredone/screens/hierarchical.py`
- Result: PASS
- Command: `pytest -q tests/test_weekly_item_filters.py tests/test_weekly_title_cleanup.py tests/test_vps_hub_crud.py`
- Result: PASS (9 passed)

## Risks / Known gaps
- Who combobox color override is applied to screens with explicit Who filters (All Items, Upcoming, Completed).

## Next agent actions
- Visual QA: confirm priority field red only when I/U are critical, and Who dropdown colors in active theme.
