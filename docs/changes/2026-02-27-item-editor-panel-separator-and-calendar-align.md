# Handoff Note

- Date: 2026-02-27
- Agent: Code
- Topic: Item editor panel separator placement and calendar alignment

## Summary
Moved the draggable black separator to the boundary between panel 1 (top form area) and panel 2 (Dates/Priority/Organization/Notes tabs) so dragging it resizes those two panels. Also adjusted the Dates tab Is Meeting row so the Calendar button starts at the same horizontal anchor as the Today buttons above.

## Files changed
- src/getmoredone/screens/item_editor.py
- docs/changes/2026-02-27-item-editor-panel-separator-and-calendar-align.md

## Verification
- Command: `pytest -q`
- Result: PASS

## Risks / Known gaps
- Panel drag-resize behavior is active in single-column layout; in wide two-column layout, the separator is hidden.

## Next agent actions
- Docs Agent: optional note in changelog about revised Edit Action Item panel resizing behavior.
