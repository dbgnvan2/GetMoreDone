# Handoff Note

- Date: 2026-02-27
- Agent: Code
- Topic: Weekly parent/child context formatting fix

## Summary
Fixed context/title formatting for weekly-derived items so both parent and child items are parser-compatible with `Context - Immediate Step`:
- Parent weekly items now include a separator after week token (`... - W# - (...)`) so context parsing is stable.
- Child action items created from a selected weekly item now build titles using parsed/inferred context + entered immediate step via shared title helpers.

## Files changed
- src/getmoredone/vps_manager.py
- src/getmoredone/screens/weekly_items.py
- docs/changes/2026-02-27-weekly-context-format-fix.md

## Verification
- Command: `pytest -q`
- Result: PASS

## Risks / Known gaps
- Existing already-created weekly items keep their prior title format until edited/recreated; this change applies to newly created items.

## Next agent actions
- Docs Agent: optional note describing improved weekly context/title consistency.
