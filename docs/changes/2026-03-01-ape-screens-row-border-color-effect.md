# Handoff Note

- Date: 2026-03-01
- Agent: Code
- Topic: Apply segment-colored row borders across APE screens

## Summary
- Applied a `2px` border color effect to APE row cards across Vision Planning APE screens.
- Border color uses each row's resolved Segment color for consistent lineage cueing.
- Extended the same border treatment to related-action rows in APE Weekly for cross-tab consistency.

## Files changed
- src/getmoredone/screens/ape_assignment.py
- src/getmoredone/screens/ape_period_view.py
- src/getmoredone/screens/weekly_items.py

## Verification
- Command: `python3 -m compileall -q src/getmoredone/screens/ape_assignment.py src/getmoredone/screens/ape_period_view.py src/getmoredone/screens/weekly_items.py`
- Result: PASS
- Command: `pytest -q tests/test_weekly_item_filters.py tests/test_weekly_title_cleanup.py tests/test_vps_hub_crud.py`
- Result: PASS (8 passed)

## Risks / Known gaps
- Very light segment colors may produce low-contrast borders on light backgrounds.

## Next agent actions
- Visual QA each APE tab at multiple window widths to confirm border visibility and spacing.
