# Handoff Note

- Date: 2026-03-15
- Agent: Code
- Topic: list-view-column-collapse-priority

## Summary
Adjusted List View row rendering so narrower window widths shrink `Segment`, `SubSegment`, `Category`, and `Who` before shrinking the `Immediate Step` / context area. Added a shared responsive column-budget helper and applied it to `Today`, `Upcoming`, `All Items`, and `Hierarchical`.

## Files changed
- src/getmoredone/screens/title_format.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/today.py
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/hierarchical.py
- tests/test_vision_planning_regressions.py

## Verification
- Command: `python3 -m py_compile src/getmoredone/screens/title_format.py src/getmoredone/screens/upcoming.py src/getmoredone/screens/today.py src/getmoredone/screens/all_items.py src/getmoredone/screens/hierarchical.py`
- Result: PASS
- Command: `pytest -q tests/test_vision_planning_regressions.py`
- Result: PASS

## Risks / Known gaps
- This is still a character-budget approach rather than true pixel-perfect responsive measurement, so exact collapse behavior may vary slightly by font/rendering.

## Next agent actions
- If needed, refine the breakpoints or move to measured text widths for even tighter responsive behavior.
