# Handoff Note

- Date: 2026-07-17
- Agent: Code
- Topic: scheduler-projects-attach + item-editor-ux + email-import-cleaning

## Summary
Four features shipped together on branch `feat/scheduler-projects-and-editor-ux`:

1. **Scheduler → attach items to projects.** Root cause of "not working": `get_project_boards(show_pending=True)` replaced ACTIVE with PENDING, returning zero boards (0 pending exist), so the Projects tab was empty. Fixed to always include ACTIVE and let the flags augment. Added a header **Project:** filter (shares `selected_project_id` with clicking a project box, synced both ways) and a **Select-All** checkbox in the item-list header. Item→project links remain exclusive.
2. **Item Editor resizable window + draggable divider** between the two columns; removed dead reflow handlers that threw on resize.
3. **Notes** seeded from the item's Description + Next Action; note-row Open button made reachable (packing order) + double-click-to-open.
4. **Gmail import** body cleaning: collapse blank lines, strip separators, truncate footer boilerplate. Editorial vocabulary in `email_cleaning_rules.json`.

## Files changed
- src/getmoredone/db_manager_project_boards.py
- src/getmoredone/screens/drag_schedule.py
- src/getmoredone/screens/item_editor.py
- src/getmoredone/screens/item_editor_notes.py
- src/getmoredone/screens/item_editor_note_dialogs.py
- src/getmoredone/email_cleaning.py (new)
- src/getmoredone/email_cleaning_rules.json (new; .gitignore exception added)
- src/getmoredone/gmail_importer.py
- tests/test_scheduler_project_attach.py, tests/test_item_editor_sash.py, tests/test_note_seed_content.py, tests/test_email_cleaning.py (new)
- tests/test_database.py, tests/test_ui_presence.py (updated)
- NOTES.md, README.md, .gitignore

## Verification
- Command: `pytest -q`
- Result: PASS — 387 passed, 1 skipped
- Also: headless instantiation of DragScheduleScreen against a copy of the live DB (17 project boxes render, select-all checks 65 rows, project filter syncs) and ItemEditorDialog sash-drag; app relaunched after each change.

## Risks / Known gaps
- Email footer detection is substring-based and intentionally aggressive for automated notifications; a legitimate mid-body "unsubscribe"-type phrase after the first content line would truncate what follows. Mitigations: first content line is never treated as a footer; the importer logs the removed-line count; phrases are tunable in `email_cleaning_rules.json`.
- `_on_select_all_toggled` keeps a broad `except` per checkbox to tolerate a widget destroyed mid-refresh (accepted, low risk).
- Moving project-filtered items to a date requires switching from the Projects tab to the Date Boxes/Calendar tab (the filter persists). No in-Projects-tab date affordance yet.

## Next agent actions
- Docs Agent: nothing outstanding (README Features bullet + NOTES.md updated here).
- If footer over-cutting is reported, prefer anchoring aggressive phrases to line-start in `email_cleaning_rules.json` rather than loosening detection globally.
