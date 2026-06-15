## Recent Changes (2026-06-15)

### Scheduler group-drag, Project↔APE linking fixes, and delete guards

- ✅ **Scheduler checkbox group-drag** — Each item row on the Scheduler's left list now has a checkbox. Dragging a *checked* row moves every checked item together to the dropped date or project; dragging an *unchecked* row still moves just that one item (single-drag unchanged). The drag label shows the count when dragging a group.
- ✅ **Link Action Items dialog: filters + bulk link** — The project "Link Action Item" dialog gained `Completed` / `Not Completed` / `Linked` / `Not Linked` filter buttons (AND logic), per-row checkboxes, and a **Link Selected** button to attach a batch at once.
- ✅ **Projects require an APE** — The project editor now requires an Annual Plan Element and defaults new projects to `Contribution - Projects - Projects`. This was the real cause of "Save doesn't work / cards have no color": see next item.
- ✅ **Root-cause fix — dropped 1:1 APE↔project unique index** — A `UNIQUE INDEX idx_project_boards_unique_ape` enforced one project per APE. Editing a project to use an already-used APE threw `UNIQUE constraint failed` *after* the dialog closed, so the save silently failed and the APE stayed null → no card color. A migration drops the index (the regular `idx_project_boards_ape` lookup index is retained); multiple projects can now share one APE (e.g. the catch-all default). Runs automatically on next launch.
- ✅ **Delete guards (prevent silent cascade data loss)** — Deleting an **Annual Plan record (APE)** is blocked when projects are attached (more than the lone empty starter board, or any board with linked items). Deleting a **Vision Element** is blocked when child records exist (annual records, projects, or linked action items). Both show a dialog listing what is attached and require manual delete/reassign first.
- ✅ **Tests** — New: `tests/test_schedule_checkbox_drag.py`, `tests/test_link_action_items_dialog_filters.py`, `tests/test_project_shared_ape.py`, plus delete-guard cases in `tests/test_vps_hub_crud.py`. Full suite: **334 passed, 1 skipped**.
- ⚠️ Adjacent (not changed): `get_project_boards(show_pending=True)` returns only pending boards (active is added only when no status flag is passed) — pre-existing, unrelated to this work.

---

## Recent Changes (2026-06-06)

### Project Board: Bulk Edit + first-class Project Notes section

- ✅ **Bulk Edit on Action Items** — Checkbox-based multi-select with a "Select All" header on the project's Action Items list. The "Bulk Edit" button (enabled when ≥1 item is selected) opens a dialog to set Start Date and/or Priority on the selected items at once. Start Date validation: today or later only; Due Date auto-set to Start + 1 day; leaving a field blank or selecting "(Skip)" preserves existing values.
- ✅ **📄 chooser on project tile** — Clicking the paper icon now opens a small chooser asking "Create New Obsidian Note" or "Link Existing Obsidian Note" (the "Open Notes" toolbar button is unchanged for explicit "browse my linked notes").
- ✅ **Project Notes section** — The right panel of a selected project now lists each linked Obsidian note as a first-class row with its own Status, Open / Complete-or-Reopen / Unlink buttons. Sorted newest-linked first. The old "N notes linked to this project." one-liner is removed.
- ✅ **Per-link Status on `ProjectBoardLink`** — Project Notes have Open / Completed lifecycle (migration runs automatically; existing notes default to Open). Status is per-project, so the same Obsidian doc linked to two projects has independent statuses.
- ✅ **Shared "Show Completed" toggle, default OFF** — One checkbox above both sections filters BOTH the Project Notes list AND the Action Items list. Default off so the first view shows only open work (per user direction).
- ✅ **New setting: Project Notes Folder** — Settings → Obsidian Integration now has a "Project Notes Folder" entry (default `GetMoreDone/Projects`). New project notes land here instead of the generic Notes Subfolder. Blank value falls back to the generic Notes Subfolder so users who don't set it don't break.
- ✅ **30 new automated tests** in `tests/test_project_notes.py` plus updates to existing tests. Full suite: 328 passed, 1 skipped.
- 📄 Spec coverage table: [`docs/spec_coverage.md`](docs/spec_coverage.md).
- 📄 Plan: [`docs/implementation_plan_2026-06-06_project_notes.md`](docs/implementation_plan_2026-06-06_project_notes.md).
- ⚠️ Known follow-ups, not fixed in this change (documented in `docs/spec_coverage.md`):
  - Duplicate `_row_to_project_board_link` / `_row_to_project_board` methods in `db_manager.py` shadow the mixin's via Python MRO — both are now in sync but the duplication is a latent footgun.
  - `open_note_picker` (toolbar "Open Notes" dialog) is now functionally redundant with the in-panel list.
  - The freeform `ProjectBoard.notes` text field shares a name with the Obsidian Project Notes concept — long-term naming debt.

---

## Recent Changes (2026-01-24)

### VPS Segment Management in Settings (NEW)

- ✅ **New Settings Tab: VPS Life Segments** - Manage all life segments in one place
- ✅ **Create/Edit/Delete Segments** - Full CRUD operations for life segments
- ✅ **Color Picker** - Visual color picker with hex code input and preview
- ✅ **Segment Display** - Shows color preview, name, description, and active status
- ✅ **Order Management** - Set display order for segments
- ✅ **Active/Inactive Toggle** - Hide segments without deleting them
- ✅ **Smart Deletion Protection** - Cannot delete segments with linked records
  - Shows exact count of linked visions (e.g., "3 linked visions")
  - Provides step-by-step instructions to remove linked records first
  - Warns about cascade deletion of child records
- ✅ **9 Comprehensive Tests** - Full test coverage including multiple vision scenarios

### VPS (Visionary Planning System) Bug Fixes

- ✅ **Fixed New Vision button crash** - Replaced non-existent `CTkMessageBox` with standard `tkinter.messagebox`
- ✅ **Fixed empty year field validation** - Now provides sensible defaults (current year for start, +10 years for end)
- ✅ **Added segment multi-select** - New checkbox dialog to select/deselect multiple life segments for display
  - "Select Segments..." button shows selection dialog
  - Select All / Deselect All options
  - Button displays count (e.g., "3 of 5 Segments")

---

## Recent Changes (2026-01-23)

### Item Editor Improvements

- ✅ **Save button** - Now keeps window open after saving (shows "✓ Saved" confirmation)
- ✅ **Save & Close button** - New button that saves and closes window
- ✅ **Duplicate button** - Saves current changes first, then opens duplicate in NEW window (keeps original open)
- ✅ **Create Tasks button** - Renamed from "Create Sub-Item", now creates one child task per line in Next Action field

### Timer Window Improvements

- ✅ **Independent music controls** - Separate Play/Pause buttons for music (purple) independent from timer controls
- ✅ **Music continues when timer paused** - Timer pause doesn't affect music playback

---

## Known Issues

Bug - the Today listing should ONLY show items completed on Today. Not previous days.

---

## Feature Requests

FR - make the Edit Next Action screen float independent the main screen.
