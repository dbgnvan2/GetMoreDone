# Handoff Note

- Date: 2026-06-06
- Agent: Code
- Topic: project-notes-and-bulk-edit

## Summary

Two related Project tab features landed in this session:

1. **Bulk Edit on Project → Action Items**. Checkbox multi-select + "Select All" + a "Bulk Edit" button (enabled when ≥1 selected) opens a dialog that sets Start Date and/or Priority across all selected items. Start Date is future-only; Due Date auto-sets to Start + 1 day. Leaving a field blank / selecting "(Skip)" preserves existing values per item.

2. **First-class Project Notes**. The right panel of a selected project now lists each linked Obsidian note as its own row (label · status pill · Open · Complete/Reopen · Unlink), with a bold "Project Notes" section header above the Action Items section.
   - `ProjectBoardLink` gained a `status` column (Open / Completed) with an idempotent ALTER TABLE migration for existing DBs.
   - DB methods `complete_project_note` / `reopen_project_note`; `get_project_board_links` now supports `include_completed=False` and orders newest-first.
   - A new "Project Notes Folder" setting (default `GetMoreDone/Projects`) routes new project notes to a separate subfolder of the Obsidian vault. Blank value falls back to the existing generic Notes Subfolder.
   - A shared "Show Completed" toggle above both sections (default OFF) filters BOTH the Notes list and the Action Items list.
   - The 📄 icon on a project tile now opens a small chooser ("Create New Obsidian Note" / "Link Existing Obsidian Note") that delegates to the existing dialogs.
   - The legacy "N notes linked to this project." one-liner is removed.

## Files changed

Source:
- `src/getmoredone/models.py` — `ProjectBoardLink.status: str = "open"`
- `src/getmoredone/database.py` — schema column + migration
- `src/getmoredone/db_manager.py` — `bulk_update_action_items`; updated `_row_to_project_board_link` (kept in sync with the mixin's copy — see Known gaps #1)
- `src/getmoredone/db_manager_project_boards.py` — `add_project_board_link` / `get_project_board_links` / `_row_to_project_board_link` updated; new `complete_project_note` / `reopen_project_note`
- `src/getmoredone/app_settings.py` — `project_notes_subfolder` field + `get_project_notes_folder` + `get_project_notes_subfolder_or_default`
- `src/getmoredone/screens/settings.py` — "Project Notes Folder" entry + save wiring
- `src/getmoredone/screens/item_editor_note_dialogs.py` — `CreateNoteDialog.create_note` routes `project_board` entity to the project subfolder
- `src/getmoredone/screens/project_boards.py` — checkbox/Bulk Edit UI, `BulkEditItemsDialog`, `NoteActionChooserDialog`, `add_note_to_project`, Project Notes section, shared Show Completed toggle, default flip to OFF

Tests:
- `tests/test_project_notes.py` (new — 30 tests covering M1.A.1…M7.A.7 + M6 meta-test)
- `tests/test_project_board_bulk_edit.py` (existing — flipped one test for the default-off Show Completed)
- `tests/test_project_note_chooser.py` (added earlier in session)

Docs:
- `docs/implementation_plan_2026-06-06.md` (plan for bulk edit feature)
- `docs/implementation_plan_2026-06-06_project_notes.md` (plan for project notes feature)
- `docs/spec_coverage.md` (every M1.A.1…M7.A.7 → impl → test → status)
- `docs/USER_GUIDE.md` (Project Board detail panel, Settings → Project Notes Folder)
- `NOTES.md` (Recent Changes 2026-06-06)
- `docs/changes/2026-06-06-project-notes-and-bulk-edit.md` (this file)
- `docs/status_report_2026-06-06_bulk_edit.md` (interim, from earlier in session)

## Verification

- Command: `./venv/bin/python -m pytest`
- Result: **PASS** — 328 passed, 1 skipped.
- Command: `./start.sh` (launching the real app against the production-side DB at `~/Library/Application Support/GetMoreDone/getmoredone.db`)
- Result: **PASS** — app starts cleanly, `_run_migrations` added the new `status` column without data loss, no tracebacks in `/tmp/app.log`.

## Risks / Known gaps

1. **Duplicate `_row_to_project_board_link`** exists in both `db_manager.py:1491` and `db_manager_project_boards.py`. M1's test caught a regression where only the mixin's copy was updated and status silently read back as `"open"`. Both copies are now in sync; the duplication remains. **Recommend a follow-up PR that removes the duplicate from `db_manager.py`** and forces the mixin's version to win.
2. **Same pattern for `_row_to_project_board`** — status/completed_at risk for `ProjectBoard` hydration the next time someone adds a column.
3. **`open_note_picker` toolbar handler is now redundant** with the in-panel Notes list. Worth simplifying.
4. **`ProjectBoard.notes` (freeform card text)** name-clashes with the Project Notes concept; long-term naming debt.
5. **Migration touches the production DB on first start** — verified locally with no errors, but anyone restoring an old backup will get the column added on next launch.

## Next agent actions

- **Docs Agent**: Confirm `docs/USER_GUIDE.md` reads correctly end-to-end after the Project Board detail-panel and Settings edits.
- **Docs Agent / Code Agent**: Consider whether `docs/MULTI_AGENT_WORKFLOW.md` or `docs/ROADMAP.md` need an entry for these features.
- **Code Agent (follow-up)**: Remove the duplicate `_row_to_project_board_link` / `_row_to_project_board` shadow methods in `db_manager.py`, keep only the mixin versions, add a regression test that fails if the shadow is reintroduced.
- **GitHub Agent**: PR description should highlight the migration (idempotent ALTER TABLE) and the new setting (default fallback safe for users who don't configure it). Tests gate already passes.

## Commits

- `e69cf62` — M1+M2 — status field + complete/reopen DB ops
- `26f42e2` — M7 — Project Notes Folder setting + entity-aware routing
- `cf4189d` — M3+M4+M5+M6 — UI section, shared filter, cleanup, spec coverage
- Earlier in session: `82774e6` (bulk edit feature), `20068bd` (checkbox visibility), `92bf450` (Select All), `f599c39` (selected_item_ids set fix), `57dbf28` (note count line), `8bc1731` (Action Items header + Show Completed), `7aee7a5` (📄 chooser), `d7766a0` (M7 plan addition), `20f9167` (project notes plan)

(This handoff plus the docs/spec_coverage.md table together satisfy CLAUDE.md §6 traceability.)
