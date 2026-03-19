# Handoff Note

- Date: 2026-03-09
- Agent: Code
- Topic: list-view-lineage-cache-fix

## Summary
Fixed a startup regression in the List Views caused by reusing the same APE cache for both color resolution and lineage labels. The color path stores a single color string, while the lineage path expects a 3-tuple of `segment/subsegment/category`. Added a dedicated lineage cache to the affected screens and hardened the shared lineage helper so malformed cache entries are ignored and recomputed instead of crashing the app.

## Files changed
- src/getmoredone/screens/item_lineage.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/today.py
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/hierarchical.py
- tests/test_vision_planning_regressions.py

## Verification
- Command: `python3 -m py_compile src/getmoredone/screens/item_lineage.py src/getmoredone/screens/upcoming.py src/getmoredone/screens/today.py src/getmoredone/screens/all_items.py src/getmoredone/screens/hierarchical.py`
- Result: PASS
- Command: `pytest -q tests/test_vision_planning_regressions.py tests/test_vps_hub_crud.py`
- Result: PASS

## Risks / Known gaps
- This fixes the crash path in the shared List Views, but any future screen that mixes color-cache and lineage-cache responsibilities into one dict can recreate the same problem.

## Next agent actions
- If more lineage/color work is planned, keep separate cache types for color strings vs lineage tuples and extend the regression suite when new shared helpers are introduced.
