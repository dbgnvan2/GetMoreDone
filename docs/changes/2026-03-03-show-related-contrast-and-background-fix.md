# Handoff Note

- Date: 2026-03-03
- Agent: Code
- Topic: Show Related dialog contrast + background color cleanup

## Summary
Refactored `ShowRelatedDialog` styling to eliminate low-contrast dark-on-dark and white-on-light combinations. Replaced hard-coded colors with semantic theme colors for section headers, table header row, row content labels, status text, and action buttons. This keeps contrast readable in both light and dark modes and aligns with the app’s theme tokens.

## Files changed
- src/getmoredone/screens/item_editor.py

## Verification
- Command: `python3 -m compileall src/getmoredone/screens/item_editor.py`
- Result: PASS
- Command: `pytest -q`
- Result: PASS (`221 passed, 1 skipped`)

## Risks / Known gaps
- The dialog still uses legacy `pack` layout (unchanged by this pass); this change only targeted color/contrast readability.

## Next agent actions
- If requested, align `SetParentDialog` list styling with the same semantic contrast treatment for consistency.
