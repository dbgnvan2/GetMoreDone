# Handoff Note

- Date: 2026-03-03
- Agent: Code
- Topic: Drag Schedule row highlighting + compact SubSegment/Category + date status colors

## Summary
Updated Drag Schedule "Next Items" rendering so each row is highlighted by the resolved Category color and the `Title`, `SubSegment`, and `Category` chips all use Category-color backgrounds. Tightened `SubSegment` and `Category` text clipping to 15 characters. Added date-chip background logic: pink for dates before today, yellow for today, and light green for future dates.

## Files changed
- src/getmoredone/screens/drag_schedule.py

## Verification
- Command: `python3 -m compileall src/getmoredone/screens/drag_schedule.py`
- Result: PASS
- Command: `pytest -q`
- Result: PASS (`221 passed, 1 skipped`)

## Risks / Known gaps
- Date chip color is based on the displayed date (`start_date`, falling back to `due_date` when start date is empty).

## Next agent actions
- If needed, switch date-coloring to strictly `start_date` only and show a distinct style for missing start dates.
