# Handoff Note

- Date: 2026-03-09
- Agent: Code
- Topic: annual-plan-elements-label-rename

## Summary
Renamed the user-facing `Annual Vision Elements` label to `Annual Plan Elements` in the Vision Planning hub and the Annual Vision Elements screen. This updates the tab label, screen header, right-panel title, edit dialog title, and the navigation docstrings/aliases that refer to that screen.

## Files changed
- src/getmoredone/app.py
- src/getmoredone/screens/vision_planning_hub.py
- src/getmoredone/screens/annual_vision_segments.py

## Verification
- Command: `rg -n "Annual Vision Elements" src/getmoredone/app.py src/getmoredone/screens/vision_planning_hub.py src/getmoredone/screens/annual_vision_segments.py`
- Result: PASS
- Command: `python3 -m py_compile src/getmoredone/app.py src/getmoredone/screens/vision_planning_hub.py src/getmoredone/screens/annual_vision_segments.py`
- Result: PASS

## Risks / Known gaps
- Internal filenames, class names, and older docs still use `annual_vision_*` naming to preserve existing routing and avoid a broader refactor.

## Next agent actions
- If terminology needs to be fully normalized beyond the live UI, sweep docs and internal symbols in a separate pass with broader regression coverage.
