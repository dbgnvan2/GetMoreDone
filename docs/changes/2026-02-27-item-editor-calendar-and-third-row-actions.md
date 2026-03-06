# Handoff Note

- Date: 2026-02-27
- Agent: Code
- Topic: Item editor calendar placement and third-row actions

## Summary
Moved the Calendar button into the Dates tab next to the Is Meeting field to align with the date action controls. Reorganized bottom action controls so Complete, Cancel, and Delete are on a third row in that order.

## Files changed
- src/getmoredone/screens/item_editor.py
- docs/changes/2026-02-27-item-editor-calendar-and-third-row-actions.md

## Verification
- Command: `pytest -q`
- Result: PASS

## Risks / Known gaps
- Third-row order applies when editing existing items; new items still show only Cancel on the third row (no Complete/Delete available).

## Next agent actions
- Docs Agent: optional changelog note for item editor action layout updates.
