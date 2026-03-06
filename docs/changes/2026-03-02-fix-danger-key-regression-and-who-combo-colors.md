# Handoff Note

- Date: 2026-03-02
- Agent: Code
- Topic: Fix danger-key regression and normalize Who combo colors

## Summary
- Fixed runtime regression (`KeyError: 'danger'`) by adding a semantic `danger` token in theme color map.
- Kept Priority field red-background behavior for critical I/U based on this semantic token.
- Updated Who filter combobox styling for search/filter use to white background and black text (including dropdown and button area).

## Files changed
- src/getmoredone/theme.py
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/completed.py

## Verification
- Command: `python3 -m compileall -q src/getmoredone/theme.py src/getmoredone/screens/all_items.py src/getmoredone/screens/upcoming.py src/getmoredone/screens/completed.py`
- Result: PASS
- Command: `pytest -q tests/test_weekly_item_filters.py tests/test_weekly_title_cleanup.py tests/test_vps_hub_crud.py`
- Result: PASS (9 passed)
- Command: `pytest -q`
- Result: PASS (216 passed, 1 skipped)

## Risks / Known gaps
- Combo styling is explicitly overridden for Who filters and may differ from pure theme defaults by design.

## Next agent actions
- Launch app and verify Upcoming screen loads cleanly and Who dropdown renders white/black under active theme.
