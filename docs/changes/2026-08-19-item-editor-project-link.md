# Handoff Note

- Date: 2026-08-19
- Agent: Code
- Topic: item-editor-project-link

## Summary

Two things, in one change to the Action Item editor:

1. **Project linking.** A **Set Project** button beside Set Wk Tactic opens a new
   picker (`SetProjectDialog`) that lists active and pending projects, clears the
   link, or creates a Project inline through the Projects screen's own
   `ProjectBoardEditorDialog`. So a new Action Item and the Project it belongs to
   can now be created from one screen. The link is written by `save_item`, and
   only when the selection actually changed — `clear_item_project_links` also
   nulls the item's Annual Plan Element, so a guard scoped to the save rather
   than to the change would have stripped the APE from every item saved without
   a project.
2. **Layout rework.** The weekly fields left the Organization tab (now Group and
   Category only) for a new **Action Plan** block in the top left showing
   Project, Wk Tactic and Orig. Week together. Buttons re-paired: Cancel with
   Timer, Add Follow-up with Add Subtasks (renamed from "Add Sub-tasks"), Set
   Parent with Show Related, Set Wk Tactic with Set Project. The **Duplicate**
   button is gone — it and the follow-up path merged into one method that saves
   first, a guard only Duplicate had.

Plus PL12: a follow-up (and complete-and-create) now inherits the original's
Project link, the way it already inherited the weekly lineage.

## Files changed

- `src/getmoredone/screens/item_editor_project_dialog.py` (new) — `SetProjectDialog`
- `src/getmoredone/screens/item_editor.py` — Action Plan block, stripped Org tab,
  button rework, `set_project` / `apply_project_selection` / `_apply_project_link` /
  `refresh_project_display` / `_load_project_baseline`, merged `create_followup`
- `src/getmoredone/db_manager_project_boards.py` — `inherit_project_links`
- `src/getmoredone/db_manager.py` — both copy paths call it
- `tests/test_item_editor_project_link.py` (new) — PL1–PL7, PL9.1, PL12
- `tests/test_item_editor_layout.py` (new) — PL8–PL10
- `tests/test_item_editor.py` — the two Duplicate tests rewritten as PL11
- `tests/test_ui_presence.py` — screen contract updated
- `docs/implementation_plan_2026-08-19_item_editor_project_link.md`,
  `docs/spec_coverage_2026-08-19_item_editor_project_link.md`,
  `docs/USER_GUIDE.md`, `CHANGELOG.md`

## Verification

- Command: `venv/bin/python -m pytest -q`
- Result: PASS — 866 passed, 2 skipped, exit code 0
- Real widgets: `ItemEditorDialog` and `SetProjectDialog` built under the venv
  against a seeded temporary database and captured with `screencapture`; layout,
  pairings and picker all render as specified.
- App log: no new errors in `weekly_tactic_debug.log`.

## Self-review finding, fixed before commit

A first pass put **Set Project** inside the existing-item branch of the button
block, so it did not render on a new item — the headline case ("create an item
and file it under a project from one screen") would have been reachable from the
API and from tests, but not from the screen (P25). The Set Wk Tactic / Set
Project row now renders on both paths, which also revives the unsaved-item branch
of `apply_weekly_tactic_selection` that had no way to be reached from the UI
(P21). Covered by PL10.4 / PL10.5.

## Risks / Known gaps

- Filing an item under a Project stamps that project's APE onto the item, and
  clearing the project clears the APE. This is pre-existing behaviour of
  `link_item_to_project_exclusive` (the Scheduler's drag-drop does the same), now
  reachable from a second surface.
- Where a project link and a Weekly Tactic disagree about the APE, the project
  wins on save, because the link is applied after the item is written.
- `inherit_project_links` stamps the copy's APE from the first board **only when
  the copy has no APE yet**, so it never overwrites the weekly lineage a
  follow-up just inherited. Existing APE drift between an item and its board is
  not repaired.
- The running app serves code from memory (P16) — restart GetMoreDone to see
  this.

## Adjacent issues found, not fixed

- `LinkProjectActionItemsDialog._link` (`screens/project_boards.py`) uses the
  **non**-exclusive `link_action_item_to_project_board`, while the Scheduler and
  now the item editor use the exclusive one. The two surfaces disagree about
  whether an item may belong to several projects. This change tolerates both
  (the Action Plan block reports `+N more`) but does not reconcile them.
- `get_unlinked_action_items` has no `LIMIT`, so the Projects screen's link
  dialog loads every open unlinked item.

## Next agent actions

- Docs Agent: nothing outstanding — `docs/USER_GUIDE.md` and `CHANGELOG.md` were
  updated in this change.
- Decide whether the Projects screen's "link existing items" dialog should become
  exclusive, so one rule governs every surface.
