# Handoff Note

- Date: 2026-03-01
- Agent: Code
- Topic: ape-period-weekly-alignment-and-right-shrink-priority

## Summary
Applied the same APE Assignment layout treatment to APE Period View and APE Weekly:
- title row + one aligned controls row under it
- compact control sizing
- body column sizing that keeps left pane priority and shrinks right side first

## Files changed
- src/getmoredone/screens/ape_period_view.py
- src/getmoredone/screens/weekly_items.py
- docs/changes/2026-03-01-ape-period-weekly-alignment-and-right-shrink-priority.md

## Verification
- Command: `pytest -q`
- Result: PASS

## Risks / Known gaps
- At very narrow widths, long status text can still truncate in APE Weekly header.

## Next agent actions
- If desired, move status text to its own row on narrow screens to preserve control alignment.
