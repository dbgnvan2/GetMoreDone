# Handoff Note

- Date: 2026-03-06
- Agent: Code
- Topic: weekly-tactic-title-sync-and-identity

## Summary
Fixed weekly-tactic title/context drift in the Action Item editor and made weekly records visually identifiable:
- Weekly tactic editor now shows a clear `Weekly Tactic` record-type badge.
- Context field is disabled for weekly tactic records (`item_type='week'`) because weekly titles are canonical single-field values.
- Added canonical-title normalization for weekly records so stale mixed titles like:
  - `PW|LS|Blog - W8 - PW|LS|Teaching - W11`
  normalize to:
  - `PW|LS|Teaching - W11`
- On opening a weekly tactic record, normalization is auto-applied and persisted.
- On changing weekly tactic linkage, weekly records are normalized before save.

## Files changed
- src/getmoredone/screens/item_editor.py
- docs/changes/2026-03-06-weekly-tactic-title-sync-and-identity.md

## Verification
- Command: `python3 -m py_compile src/getmoredone/screens/item_editor.py`
- Result: PASS
- Command: `pytest -q tests/test_weekly_item_filters.py tests/test_weekly_title_cleanup.py tests/test_vision_planning_regressions.py`
- Result: PASS

## Risks / Known gaps
- UI-level behavior is validated by runtime/manual verification; there is no direct widget test for this dialog state.
- Existing stale weekly records are normalized when opened/edited; there is no one-shot bulk migration command in this change.

## Next agent actions
- Docs Agent: add a short note in user documentation that weekly tactic records use canonical title-only format and display a Weekly Tactic type badge in the editor.
