# Handoff Note

- Date: 2026-03-24
- Agent: Code
- Topic: editor-dialog-render-fix

## Summary
Fixed blank editor/dialog windows affecting the Action Item editor and Weekly Tactic editor on macOS-style windowing paths. The dialogs now build their child widgets while hidden, then position and reveal themselves after layout completes. Also fixed the Action Item editor centering logic so it uses the actual dialog size instead of forcing a mismatched hardcoded geometry.

Added explicit regression coverage for:
- Action Item editor centering using requested dialog dimensions
- Action Item editor reveal order (`center -> show -> idle finalize`)
- VSP editor dialog reveal order used by the Weekly Tactic editor

Updated the main README testing section so the editor dialog regression test path is documented.

## Files changed
- src/getmoredone/screens/item_editor.py
- src/getmoredone/screens/vps_editors.py
- tests/test_item_editor.py
- README.md
- docs/changes/2026-03-24-editor-dialog-render-fix.md

## Verification
- Command: `python3 -m py_compile src/getmoredone/screens/item_editor.py src/getmoredone/screens/vps_editors.py`
- Result: PASS
- Command: `pytest -q tests/test_item_editor.py`
- Result: PASS

## Risks / Known gaps
- The helper was applied directly to `WeekActionEditorDialog`; other VSP editor dialogs still use their older show sequence.
- This change was verified by compile/tests, not by automated GUI screenshot coverage.

## Next agent actions
- If blank-shell behavior appears in other VSP dialogs, move the same finalize helper to the remaining editor classes in `vps_editors.py`.
- Consider adding a lightweight GUI smoke test path for editor creation if the toolkit allows it.
