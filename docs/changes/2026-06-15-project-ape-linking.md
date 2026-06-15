# Handoff Note

- Date: 2026-06-15
- Agent: Code
- Topic: scheduler-group-drag + project↔APE linking fixes + delete guards

## Summary
Four related pieces of work:

1. **Scheduler checkbox group-drag** — Added a checkbox to each item row on the
   Scheduler's left list. Dragging a *checked* row reschedules/links every checked
   item together; dragging an *unchecked* row moves only that item (single-drag
   unchanged). Drag label shows the count when dragging a group.

2. **Link Action Items dialog: filters + bulk link** — The project "Link Action
   Item" dialog now has `Completed` / `Not Completed` / `Linked` / `Not Linked`
   filter buttons (AND logic), per-row checkboxes, and a **Link Selected** button.

3. **Project↔APE root-cause fix** — A `UNIQUE INDEX idx_project_boards_unique_ape`
   enforced one project per APE. Linking a project to an already-used APE threw
   `UNIQUE constraint failed` *after* the editor dialog closed, so Save silently
   failed and the APE stayed null → project card had no color. A migration drops
   the unique index (regular `idx_project_boards_ape` retained); multiple projects
   may now share one APE. The project editor also now *requires* an APE and
   defaults new projects to `Contribution - Projects - Projects`.

4. **Delete guards** — Deleting an APE (annual plan record) is blocked when
   projects are attached beyond the empty starter board / any board with linked
   items. Deleting a Vision Element is blocked when child records exist (annual
   records, projects, linked action items). Both raise typed exceptions caught by
   the UI, which shows a dialog listing what is attached.

## Files changed
- src/getmoredone/database.py — drop unique APE index (fresh schema + migration)
- src/getmoredone/screens/drag_schedule.py — checkbox group-drag
- src/getmoredone/screens/project_boards.py — link-dialog filters/bulk link; APE required + default
- src/getmoredone/vps_manager.py — `ProjectBoardsAttachedError`; APE delete guard; re-export `VisionElementHasDependentsError`
- src/getmoredone/vps_manager_taxonomy.py — `VisionElementHasDependentsError`; vision-element dependents check + delete guard
- src/getmoredone/screens/annual_vision_segments.py — catch APE-delete guard, show message
- src/getmoredone/screens/vision_elements.py — catch vision-element delete guard, show message
- tests/test_schedule_checkbox_drag.py (new)
- tests/test_link_action_items_dialog_filters.py (new)
- tests/test_project_shared_ape.py (new)
- tests/test_vps_hub_crud.py — delete-guard cases
- docs/USER_GUIDE.md, NOTES.md — documentation

## Verification
- Command: `pytest`
- Result: PASS — 334 passed, 1 skipped
- Also verified against a copy of the real DB: APE now persists on save; two
  projects share one APE; shared-APE boards resolve segment lineage + color.
- requirements.txt: unchanged (no new third-party imports).

## Risks / Known gaps
- The unique-index drop runs as a migration on next app launch; the live DB still
  had the index at hand-off (relaxes itself on startup, no data touched).
- Adjacent, not changed: `get_project_boards(show_pending=True)` returns only
  pending boards (active is added only when no status flag is passed).
- The delete-guard message tells users to "delete or reassign" projects, but there
  is no one-click detach-from-APE in the project editor yet (reassign = pick a
  different APE and Save).

## Next agent actions
- Docs Agent: none outstanding — USER_GUIDE.md + NOTES.md updated here.
- Optional follow-up: add an explicit "detach project from APE" affordance, and
  consider whether `get_project_boards` status-filter semantics should include
  active alongside pending/completed.
