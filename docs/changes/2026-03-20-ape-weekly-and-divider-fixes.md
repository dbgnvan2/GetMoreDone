# Handoff Note

- Date: 2026-03-20
- Agent: Code
- Topic: ape-weekly-and-divider-fixes

## Summary
Fixed two Vision Planning issues:
- added the horizontal resize cursor to the `Annual Plan Elements` center divider so the resize affordance is visible
- added an `Add Weekly Tactic` action to `APE Weekly` so users can create a weekly-parent item for the currently selected week without leaving the screen

The new weekly-tactic flow opens a picker for Annual Plan Elements filtered by the current screen filters and creates the weekly item through the existing VSP weekly-item creation helper.

## Files changed
- src/getmoredone/screens/annual_vision_segments.py
- src/getmoredone/screens/weekly_items.py
- docs/changes/2026-03-20-ape-weekly-and-divider-fixes.md

## Verification
- Command: `python3 -m py_compile src/getmoredone/screens/annual_vision_segments.py src/getmoredone/screens/weekly_items.py`
- Result: PASS
- Command: `rg -n "Add Weekly Tactic|create_weekly_tactic_for_week|cursor=\"sb_h_double_arrow\"" src/getmoredone/screens/annual_vision_segments.py src/getmoredone/screens/weekly_items.py`
- Result: PASS

## Risks / Known gaps
- The new weekly-tactic picker uses the selected week's calendar year and current APE lineage filters; it does not yet expose an additional year override in the dialog.
- This change was compile-verified but not exercised with an automated GUI interaction test.

## Next agent actions
- Add a small regression test around the weekly-tactic creation helper if GUI-free coverage is desired.
- If needed, add the same visible resize cursor check to any remaining older split panes.
