# Handoff Note

- Date: 2026-02-27
- Agent: Code
- Topic: Weekly Tactics list converted to 3-column chips without accent bar

## Summary
Updated APE Weekly left-side Weekly Tactics list to match the same visual treatment:
- removed left-edge vertical accent bars.
- replaced title/key-style row text with 3 columns: Segment, SubSegment, Category.
- applied segment and subsegment chip colors with compact clipped labels.
- added manager query fields for APE subsegment/category so weekly rows can render all 3 columns directly.

## Files changed
- src/getmoredone/vps_manager.py
- src/getmoredone/screens/weekly_items.py
- docs/changes/2026-02-27-weekly-tactics-3-column-no-accent.md

## Verification
- Command: `pytest -q`
- Result: PASS

## Risks / Known gaps
- For legacy weekly titles without APE subsegment/category linkage, the UI falls back to parsing title pipes and may show `-` when parts are missing.

## Next agent actions
- Docs Agent: optional screenshot/text update for APE Weekly left list.
