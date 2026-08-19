# Implementation plan — Link an Action Item to a Project from the Item Editor

Date: 2026-08-19
Status: awaiting approval (no implementation code written)

## Goal

From the Action Item **Create** and **Edit** screen (`ItemEditorDialog`), the user can:

1. See which Project the item is filed under.
2. Pick a different Project, or clear it.
3. Create a brand-new Project without leaving the editor, and have the item filed
   under it — all in one screen.

"Project" here is a `ProjectBoard` row; the item↔project relation is the
`project_board_items` table.

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

The only precedent for setting the link outside the Projects screen is the
Scheduler drag-drop (`screens/drag_schedule.py:1266`), which uses exactly the
exclusive/clear pair above. This change follows that same contract, so the two
surfaces cannot drift.

---

## Design decisions (call these out before approving)

- **D1 — Placement: Organization tab.** The Project row goes in the Org tab
  beside Group / Category / Wk Tactic, which is where every other filing field
  already lives. Still one window, still one save.
- **D2 — One project per item (exclusive).** Matches the Scheduler's model and
  `link_item_to_project_exclusive`. A combo box, not a multi-select.
- **D3 — Linking overwrites the item's Annual Plan Element.** This is existing
  behaviour of `link_item_to_project_exclusive`, not new. Picking a project
  stamps that project's APE onto the item. **Consequence to accept:** clearing
  the project to "(none)" nulls the item's APE — so the clear path only fires
  when the user actively moves a linked item to "(none)", never as a side effect
  of an ordinary save (see D4).
- **D4 — Apply only on change.** `save_item` compares the combo against the
  value loaded when the dialog opened. Unchanged ⇒ no link/clear call at all.
  This is what keeps an ordinary "Save" on an item with an APE but no project
  from wiping the APE (P13 — the guard must scope exactly to the change).
- **D5 — Weekly Tactic records are excluded.** For `item_type == 'week'` the
  control is disabled in `_apply_record_type_ui()`, the same place the Context
  field is disabled. A week item's title is derived from its APE
  (`_canonical_weekly_tactic_title`), so letting a project re-stamp its APE
  would silently rewrite its title.
- **D6 — Which projects are listed:** active + pending (`show_pending=True`),
  completed excluded. A completed project already linked to this item is still
  shown as the current value so it never silently disappears.
- **D7 — Pre-existing multi-links are preserved.** `link_action_item_to_project_board`
  (used by the Projects screen's "Link existing items" dialog) is *not*
  exclusive, so an item can already carry more than one link. The combo shows
  the first and labels it `+N more`; because of D4, saving without touching the
  control leaves all of them intact (P2 — never silently drop).

---

## Acceptance criteria → tests

New test file: `tests/test_item_editor_project_link.py`
(dialog methods driven with `SimpleNamespace` stubs, the pattern already used by
`tests/test_project_board_dates_ui.py` and `tests/test_item_editor_weekly_tactic_ui.py`).

| ID | Criterion | Verified by |
|---|---|---|
| **PL1** | The Org tab renders a Project combo and a "+ New Project" button; the combo's values come from `get_project_boards`, with a `(none)` entry first. | `test_pl1_org_tab_builds_project_control` — calls `_setup_org_tab` on a stub, asserts `project_var` / `project_combo` / `btn_new_project` exist and the values list contains the seeded board titles + `(none)`. |
| **PL1.1** | Two projects with the same title get distinct labels (no silent collapse in the label→id map). | `test_pl1_1_duplicate_titles_get_distinct_labels` — two boards titled "Website", assert `len(label_to_id) == 2`. |
| **PL2** | Opening an item already linked to a project preselects that project. | `test_pl2_existing_link_preselected` — link via db, run the loader, assert `project_var` holds that board's label. |
| **PL2.1** | An item with no link shows `(none)`. | `test_pl2_1_unlinked_shows_none` |
| **PL2.2** | An item with two pre-existing links shows the first labelled `+1 more`. | `test_pl2_2_multi_link_is_surfaced_not_hidden` |
| **PL3** | **New item:** choosing a project and saving creates the item *and* the link, and the item's APE is the board's APE. | `test_pl3_new_item_saves_and_links` — drives `ItemEditorDialog.save_item` on a stub with no `item_id`; asserts `get_project_board_ids_for_item(new_id) == [board_id]`. |
| **PL4** | **Edit item:** changing the project re-links exclusively (old link gone, one new link). | `test_pl4_edit_item_relinks_exclusively` |
| **PL4.1** | Setting the combo to `(none)` on a linked item removes the link. | `test_pl4_1_selecting_none_clears_link` |
| **PL4.2** | Saving **without touching** the combo makes **no** link/clear call — an item with an APE and no project keeps its APE. | `test_pl4_2_untouched_combo_never_clears` — intercepts `clear_item_project_links` / `link_item_to_project_exclusive` on the manager, asserts zero calls, and asserts `annual_plan_element_id` survives. (This is the highest-risk fix in the change — written first, per P10.) |
| **PL4.3** | Saving without touching the combo leaves a pre-existing **multi**-link intact. | `test_pl4_3_untouched_combo_preserves_multi_link` |
| **PL5** | "+ New Project" opens `ProjectBoardEditorDialog`, persists the returned board via `create_project_board`, and selects it in the combo. Cancel creates nothing. | `test_pl5_new_project_button_creates_and_selects` + `test_pl5_1_cancel_creates_nothing` — the dialog class is monkeypatched to a fake returning a `ProjectBoard` / `"__cancel__"`; patched name restored in `finally`. |
| **PL6** | For an `item_type == 'week'` record the Project control is disabled. | `test_pl6_weekly_tactic_record_disables_project_control` — drives `_apply_record_type_ui` on a week-item stub, asserts `configure(state="disabled")` was recorded. |
| **PL7** | The link actually lands in the DB through the real `DatabaseManager` (not a mock), and survives a re-read. | `test_pl7_link_round_trips_through_db` |

**Not code-testable — flagged for human review:** the visual layout of the new
row in the Org tab (spacing/width against the existing Group/Category/Wk Tactic
rows). Proposed human check: launch the app under the venv, open New Action Item
and an existing one, screenshot the Organization tab, and confirm the app log is
clean — per `~/.claude/standards/ui-regression.md` and the project rule that DB
unit tests alone are not sufficient for this UI.

---

## Implementation order

1. `tests/test_item_editor_project_link.py` — PL4.2 first (highest-risk: the
   no-op-on-unchanged guard), then PL3/PL4.
2. `screens/item_editor.py` — `_setup_org_tab`: Project label + combo + "+ New
   Project" button; `_load_project_options()` and `_project_label_for_board()`
   helpers; store `self._loaded_project_id` as the change baseline.
3. `screens/item_editor.py` — `load_item_data`: preselect the current link;
   new-item path leaves `(none)` unless a project was passed in.
4. `screens/item_editor.py` — `create_new_project()`: open
   `ProjectBoardEditorDialog`, `create_project_board`, refresh + select.
5. `screens/item_editor.py` — `save_item`: after the create/update branch (so a
   new item has an id), apply the link **only if changed** (D4). Both branches —
   the new-item path and the edit path — get the same call, in the same change
   (P5: no hardened-one-sibling-only).
6. `screens/item_editor.py` — `_apply_record_type_ui`: disable for week records.
7. Run the full suite; launch the app and do the PL-manual check above.
8. Docs: `docs/changes/2026-08-19-item-editor-project-link.md` handoff note,
   `CHANGELOG.md`, `docs/USER_GUIDE.md` (Action Item editor section),
   `docs/spec_coverage.md` row per PL id.

Dependencies: steps 2→3→5 are sequential (5 needs the baseline from 2). Step 4
is independent of 3. No schema migration, no `requirements.txt` change.

---

## Adjacent issues found, not fixed (rule 10)

- `LinkProjectActionItemsDialog._link` (`project_boards.py:374`) uses the
  **non**-exclusive `link_action_item_to_project_board`, while the Scheduler uses
  the exclusive one. The two surfaces disagree about whether an item may belong
  to several projects. This change works with both (D7) but does not reconcile
  them. Worth a decision separately.
- `get_unlinked_action_items` has no `LIMIT`, so the Projects screen's link
  dialog loads every open unlinked item. Out of scope here.
