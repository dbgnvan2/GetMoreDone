# Implementation plan — Project link + Action Item editor layout rework

Date: 2026-08-19 (revised after review feedback)
Status: **implemented** — see [`docs/spec_coverage_2026-08-19_item_editor_project_link.md`](spec_coverage_2026-08-19_item_editor_project_link.md)

## Goal

Two things in one change to the Action Item **Create/Edit** screen
(`ItemEditorDialog`):

**A. Project linking.** The user can see which Project the item is filed under,
pick a different one, clear it, or **create a brand-new Project without leaving
the editor** — so a new Action Item can be created and filed to a new Project
from one screen.

**B. Layout rework.** The weekly-tactic fields leave the Organization tab, a new
**Action Plan** block in the top-left shows the item's Project and Weekly Tactic,
and the action buttons are re-paired.

"Project" here is a `ProjectBoard` row; the item↔project relation is the
`project_board_items` table.

> The screenshot supplied with the review confirmed this reading; it changed
> nothing in the plan beyond making Timer half-width so Cancel can sit beside it.

---

## What already exists (no new DB work needed)

| Piece | Location |
|---|---|
| `project_board_items` link table | `database.py` schema |
| `link_item_to_project_exclusive(board_id, item_id)` — clears prior links, adds one, **copies the board's APE onto the item** | `db_manager_project_boards.py:177` |
| `clear_item_project_links(item_id)` — removes links **and nulls the item's `annual_plan_element_id`** | `db_manager_project_boards.py:220` |
| `get_project_board_ids_for_item(item_id)` | `db_manager_project_boards.py:230` |
| `get_project_boards(show_pending, show_completed)` | `db_manager_project_boards.py:81` |
| `create_project_board(board)` | `db_manager_project_boards.py:13` |
| `ProjectBoardEditorDialog` — full New/Edit Project dialog, sets `.result`, caller persists | `screens/project_boards.py:25` |
| `SetWeeklyTacticDialog` — the picker the "Set Wk Tactic" button already opens | `screens/item_editor_weekly_tactic_dialog.py` |

The only precedent for setting the link outside the Projects screen is the
Scheduler drag-drop (`screens/drag_schedule.py:1266`), which uses exactly the
exclusive/clear pair above. This change follows that same contract, so the two
surfaces cannot drift.

---

## B. Layout rework — the six points

### 1. Weekly fields off the Organization tab
`_setup_org_tab` keeps **Group** and **Category** only. The `Wk Tactic:` label
and the `Orig. Week:` entry move to the new Action Plan block (point 6).
`refresh_weekly_tactic_display()` keeps its name and contract — only the widget
it writes to moves — so the existing tests and the
`apply_weekly_tactic_selection` caller keep working.

### 6. New "Action Plan" block, top-left
A titled block in the left column, directly under the Title row and above
Description:

```
Action Plan
  Project:     Website Rebuild                 (read-only label)
  Wk Tactic:   Ship v2 | W34 (2026-08-17 to 2026-08-23)   (read-only label)
  Orig. Week:  [2026-08-10]                    (editable entry, unchanged behaviour)
```

Both values are set through the **Set Project** / **Set Wk Tactic** buttons, so
the labels are read-only — same treatment the Wk Tactic already had. `Orig. Week`
stays an editable entry because `save_item` reads it (WT-M6.A.3); it has nowhere
else to live once it leaves the Org tab.

### 2–5. Button block

Current (right column, `create_form`) → proposed:

| | Left | Right |
|---|---|---|
| primary | **Save & Close** | **Save** |
| new items only | **Save + New** | **Cancel** |
| existing items | **⏱ Timer** | **Cancel** |
| existing items | **Add Follow-up** | **Add Subtasks** |
| existing items | **Set Parent** | **Show Related** |
| **both** | **Set Wk Tactic** | **Set Project** |
| existing items | **Complete** | **Delete** |

The Set row renders on a **new** item too (PL10.4). Filing a not-yet-saved item
under a Project is the headline case — a button available only after "save it
first" would leave it unreachable from the screen it was asked for (P25). Both
pickers already hold the choice for an unsaved item and apply it on insert.

- **2.** Cancel leaves the primary row and pairs with Timer. On a *new* item
  there is no Timer button, so Cancel pairs with **Save + New** — Cancel must
  exist on every state of the dialog (P25: don't lose a control on one path).
- **2.** **Duplicate is removed.** `duplicate_item()` and `create_followup()`
  merge into one method: save first, create the derived item, open it in an
  offset window. The surviving button is **Add Follow-up**, backed by
  `create_followup_item`.
  - Two real consequences, both improvements: `create_followup` currently does
    **not** save pending edits first (only `duplicate_item` did) — the merged
    method always saves first, so the P5 sibling gap closes. And
    `create_followup_item` carries the weekly lineage (`_inherit_weekly_lineage`,
    WT-M5.C.1) that plain `duplicate_action_item` drops.
  - `db_manager.duplicate_action_item` **stays** — `complete_and_create` and
    `create_followup_item` both call it. Only the editor's button and its
    wrapper method go.
- **3.** "Add Sub-tasks" is relabelled **Add Subtasks** (no hyphen) and pairs
  with Add Follow-up.
- **4.** Set Parent and Show Related pair on one row.
- **5.** New **Set Project** button beside Set Wk Tactic.

### Set Project dialog

Rather than a combo on a tab, point 5 makes Project a *button-driven* picker,
matching Set Wk Tactic. New `SetProjectDialog` in a new module
`screens/item_editor_project_dialog.py`:

- A searchable list of projects (active + pending; a completed project already
  linked to this item is still listed so it can't vanish).
- **Clear Project** button → `(none)`.
- **+ New Project** button → opens the existing `ProjectBoardEditorDialog`,
  persists via `create_project_board`, selects the new project and returns.
- On choose, calls back into the editor exactly like
  `apply_weekly_tactic_selection` does: for a saved item the link is written
  immediately; for an unsaved new item the choice is held and applied on insert.
  Implemented as a single deferred path — the choice is recorded in
  `_selected_project_id` and written by `save_item` for saved and new items
  alike, so Cancel really cancels and there is one place the link is written.

---

## Design decisions (call these out before approving)

- **D1 — One project per item (exclusive).** Matches the Scheduler and
  `link_item_to_project_exclusive`.
- **D2 — Linking overwrites the item's Annual Plan Element.** Existing behaviour
  of `link_item_to_project_exclusive`, not new. Clearing the project to `(none)`
  nulls the item's APE. Guarded per D3.
- **D3 — Apply only on change.** `save_item` compares against the value loaded
  when the dialog opened. Unchanged ⇒ no link/clear call at all, so an ordinary
  Save on an item that has an APE but no project cannot wipe the APE (P13).
- **D4 — Weekly Tactic records:** Set Project is disabled for `item_type ==
  'week'` in `_apply_record_type_ui()`, where Context is already disabled. A week
  item's title derives from its APE, so letting a project re-stamp the APE would
  silently rewrite the title.
- **D5 — Pre-existing multi-links preserved.** The Projects screen's "link
  existing items" dialog is *not* exclusive, so an item may already hold several
  links. The Action Plan label shows the first plus `+N more`; because of D3,
  saving without touching Set Project leaves all of them intact (P2).

---

## Acceptance criteria → tests

New file `tests/test_item_editor_project_link.py` (PL1–PL7) and
`tests/test_item_editor_layout.py` (PL8–PL12), driven with `SimpleNamespace`
stubs — the pattern already used by `tests/test_project_board_dates_ui.py` and
`tests/test_item_editor_weekly_tactic_ui.py`.

### A. Project linking

| ID | Criterion | Verified by |
|---|---|---|
| **PL1** | `SetProjectDialog` lists active + pending projects, plus any completed project already linked to this item. | `test_pl1_dialog_lists_projects` |
| **PL2** | Opening the editor on a linked item shows that project in the Action Plan block; an unlinked item shows `(none)`. | `test_pl2_action_plan_shows_current_project`, `test_pl2_1_unlinked_shows_none` |
| **PL2.2** | An item with two pre-existing links shows the first labelled `+1 more`. | `test_pl2_2_multi_link_is_surfaced_not_hidden` |
| **PL3** | **New item:** choosing a project then saving creates the item *and* the link, and stamps the board's APE. | `test_pl3_new_item_saves_and_links` — drives `save_item` on a stub with no `item_id`. |
| **PL4** | **Edit item:** choosing a different project re-links exclusively (old link gone, exactly one new link). | `test_pl4_edit_item_relinks_exclusively` |
| **PL4.1** | Clear Project removes the link. | `test_pl4_1_clear_removes_link` |
| **PL4.2** | Saving **without** touching Set Project makes **no** link/clear call — an item with an APE and no project keeps its APE. | `test_pl4_2_untouched_selection_never_clears` — intercepts both manager methods, asserts zero calls. **Written first** (highest-risk, P10). |
| **PL4.3** | Saving without touching Set Project leaves a pre-existing multi-link intact. | `test_pl4_3_untouched_selection_preserves_multi_link` |
| **PL5** | **+ New Project** opens `ProjectBoardEditorDialog`, persists the result via `create_project_board`, and selects it. Cancel creates nothing. | `test_pl5_new_project_creates_and_selects`, `test_pl5_1_cancel_creates_nothing` — dialog class monkeypatched, patch restored in `finally`. |
| **PL6** | Set Project is disabled for an `item_type == 'week'` record. | `test_pl6_week_record_disables_set_project` |
| **PL7** | The link round-trips through the real `DatabaseManager` and survives a re-read. | `test_pl7_link_round_trips_through_db` |

### B. Layout

| ID | Criterion | Verified by |
|---|---|---|
| **PL8** | `_setup_org_tab` creates Group and Category only — no `weekly_tactic_label`, no `weekly_tactic_start_entry`. | `test_pl8_org_tab_has_no_weekly_widgets` |
| **PL9** | The Action Plan block exists and `refresh_weekly_tactic_display` writes into it; `Orig. Week` still round-trips through `save_item`. | `test_pl9_action_plan_block_shows_project_and_tactic`, `test_pl9_1_orig_week_still_saves` |
| **PL10** | Button pairings: Cancel with Timer (existing item) / with Save + New (new item); Add Follow-up with Add Subtasks; Set Parent with Show Related; Set Wk Tactic with Set Project. Verified by grid row/column, not by "the widget exists". | `test_pl10_button_pairs_share_a_row` |
| **PL10.1** | No Duplicate button on any path; label reads exactly `Add Subtasks`. | `test_pl10_1_duplicate_button_is_gone` |
| **PL11** | The merged follow-up method saves before creating, and aborts entirely when the save fails. | `test_pl11_followup_saves_first`, `test_pl11_1_followup_aborts_on_save_failure` (rewrites of the existing `test_duplicate_item_*` pair in `tests/test_item_editor.py`, which target the removed method). |
| **PL12** | *(optional — needs your call, see below)* A follow-up inherits the original's project link. | `test_pl12_followup_inherits_project_link` |

**Not code-testable — flagged for human review:** the visual result of the
rework (Action Plan block spacing, button grid fit inside the scrollable
container at the default 920×550 and when the sash is dragged). Proposed human
check: launch under the venv, open a new item and an existing one, screenshot the
left column and the button block, confirm `app.log` is clean — per
`~/.claude/standards/ui-regression.md`.

---

## Implementation order

1. `tests/` — PL4.2 first, then PL3/PL4, then the layout tests.
2. `screens/item_editor_project_dialog.py` — new `SetProjectDialog`.
3. `screens/item_editor.py` — `_setup_org_tab` stripped to Group/Category (PL8).
4. `screens/item_editor.py` — Action Plan block in `create_form`; move
   `weekly_tactic_label` / `weekly_tactic_start_entry` there; add
   `project_label`; `refresh_project_display()` (PL9, PL2).
5. `screens/item_editor.py` — button block re-pairing, Cancel move, Duplicate
   removal, `Add Subtasks` relabel, `Set Project` button (PL10).
6. `screens/item_editor.py` — merge `duplicate_item` + `create_followup` into
   one method; update the two existing tests (PL11).
7. `screens/item_editor.py` — `set_project()` + `apply_project_selection()`;
   `save_item` applies the pending/changed link after create/update, both
   branches in the same change (P5) (PL3–PL4.3).
8. `_apply_record_type_ui` — disable Set Project for week records (PL6).
9. Full suite; then launch the app for the manual check.
10. Docs: `docs/changes/2026-08-19-item-editor-project-link.md` handoff note,
    `CHANGELOG.md`, `docs/USER_GUIDE.md`, `docs/spec_coverage.md`.

Steps 4→7 are sequential (7 needs the baseline stored in 4). No schema
migration, no `requirements.txt` change.

---

## Needs your call

- **PL12 — should a follow-up inherit the project link?** Today a follow-up
  inherits the weekly lineage and APE (`_inherit_weekly_lineage`) but nothing
  copies `project_board_items`, so a follow-up of a project task lands with no
  project. Coherent to fix while we're here; it is a behaviour change outside
  the six points, so I'm not folding it in silently. Include, or leave for later?

## Adjacent issues found, not fixed (rule 10)

- `LinkProjectActionItemsDialog._link` (`project_boards.py:374`) uses the
  **non**-exclusive `link_action_item_to_project_board` while the Scheduler uses
  the exclusive one. The two surfaces disagree about whether an item may belong
  to several projects. This change tolerates both (D5) but does not reconcile
  them.
- `get_unlinked_action_items` has no `LIMIT`, so the Projects screen's link
  dialog loads every open unlinked item.
