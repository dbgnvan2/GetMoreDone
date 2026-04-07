# Handoff Note

- Date: 2026-03-09
- Agent: Code
- Topic: ape-quarter-and-month-assignment

## Summary
Reworked the APE planning flow into two separate two-panel assignment screens. `APE Assignment` is now `APE Quarter Assignment`, with a quarter selector next to year and a right-side `APE For Quarter Qn` panel backed by quarter-initiative creation. `APE Period View` is now `APE Month Assignment`, with left-side quarter-assigned APEs and a right-side `APE For Month Mn` panel backed by month-tactic creation. The manager now exposes quarter/month assignment helpers so the UI can assign and unassign APEs while keeping quarter/month execution records in sync.

## Files changed
- src/getmoredone/vps_manager.py
- src/getmoredone/screens/ape_assignment.py
- src/getmoredone/screens/ape_period_view.py
- src/getmoredone/screens/vision_planning_hub.py
- tests/test_vps_hub_crud.py

## Verification
- Command: `python3 -m py_compile src/getmoredone/vps_manager.py src/getmoredone/screens/ape_assignment.py src/getmoredone/screens/ape_period_view.py src/getmoredone/screens/vision_planning_hub.py`
- Result: PASS
- Command: `pytest -q tests/test_vps_hub_crud.py`
- Result: PASS

## Risks / Known gaps
- The new screens mirror the Annual Plan Elements save-based workflow with checkbox selection rather than true row drag-and-drop.
- The month selector currently allows any month value regardless of selected quarter; the data model supports it, but the UI does not yet restrict month choices to the quarter's 3-month range.

## Next agent actions
- If the user wants literal drag-and-drop behavior, add pointer-based row dragging on top of the current save-based assignment flow.
- If quarter/month coupling should be enforced in the UI, constrain the month selector based on the selected quarter.
