# Spec Coverage — Item editor Project link + layout rework (2026-08-19)

Plan: [`docs/implementation_plan_2026-08-19_item_editor_project_link.md`](implementation_plan_2026-08-19_item_editor_project_link.md)

Suite: `venv/bin/python -m pytest -q` → **866 passed, 2 skipped**, exit code 0.

## A. Project linking

| Spec ID | Criterion | Implementation | Test | Status |
|---|---|---|---|---|
| PL1 | Picker lists active + pending projects; completed are not offered | `screens/item_editor_project_dialog.py::SetProjectDialog.load_boards` | `tests/test_item_editor_project_link.py::test_pl1_dialog_lists_active_and_pending_projects` | done |
| PL1.1 | A completed project already linked to the item is still listed | same | `::test_pl1_1_current_project_is_listed_even_when_completed` | done |
| PL2 | A linked item shows its project in the Action Plan block | `screens/item_editor.py::_load_project_baseline`, `::refresh_project_display` | `::test_pl2_action_plan_shows_current_project` | done |
| PL2.1 | An unlinked item shows `(none)` | same | `::test_pl2_1_unlinked_item_shows_none` | done |
| PL2.2 | Pre-existing multi-link shows `+N more` | same | `::test_pl2_2_multi_link_is_surfaced_not_hidden` | done |
| PL2.3 | Deleting a board takes its links with it, so the display reads `(none)` | schema `ON DELETE CASCADE` | `::test_pl2_3_deleting_the_board_unfiles_the_item` | done |
| PL3 | New item: choosing a project and saving creates the item, the link, and stamps the APE | `screens/item_editor.py::save_item` → `_apply_project_link` | `::test_pl3_new_item_saves_and_links` | done |
| PL4 | Edit item: a different project re-links exclusively | `db_manager_project_boards.py::link_item_to_project_exclusive` | `::test_pl4_edit_item_relinks_exclusively` | done |
| PL4.1 | Clear Project removes the link | `db_manager_project_boards.py::clear_item_project_links` | `::test_pl4_1_clearing_the_project_removes_the_link` | done |
| PL4.2 | An untouched dialog makes **no** link/clear call; the item's APE survives | `screens/item_editor.py::_apply_project_link` (guard) | `::test_pl4_2_untouched_selection_never_clears` | done |
| PL4.3 | An untouched dialog preserves a pre-existing multi-link | same guard | `::test_pl4_3_untouched_selection_preserves_multi_link` | done |
| PL4.4 | Re-picking the project the item is already on writes nothing | same guard | `::test_pl4_4_re_picking_the_same_project_writes_nothing` | done |
| PL5 | "+ New Project" persists the board and returns it as the selection | `SetProjectDialog.create_new_project` (reuses `ProjectBoardEditorDialog`) | `::test_pl5_new_project_creates_and_selects` | done |
| PL5.1 | Cancelling the new-project dialog creates nothing | same | `::test_pl5_1_cancelling_the_new_project_creates_nothing` | done |
| PL6 | `set_project` is a no-op on a Weekly Tactic record | `screens/item_editor.py::set_project` | `::test_pl6_week_record_cannot_be_filed_under_a_project` | done |
| PL6.1 | The Set Project button is disabled on a Weekly Tactic record | `screens/item_editor.py::_apply_record_type_ui`, `::_set_project_button_state` | `::test_pl6_1_week_record_disables_the_button` | done |
| PL7 | The link round-trips: the board reports the item as one of its items | `db_manager_project_boards.py::get_project_board_items` | `::test_pl7_link_round_trips_through_db` | done |

## B. Layout

| Spec ID | Criterion | Implementation | Test | Status |
|---|---|---|---|---|
| PL8 | The Organization tab holds Group and Category only | `screens/item_editor.py::_setup_org_tab` | `tests/test_item_editor_layout.py::test_pl8_org_tab_has_no_weekly_widgets` | done |
| PL9 | Action Plan block in the left column holds Project, Wk Tactic and Orig. Week | `screens/item_editor.py::create_form` | `tests/test_item_editor_layout.py::test_pl9_action_plan_block_holds_project_and_tactic` | done |
| PL9.1 | Orig. Week still round-trips through save from its new home | `screens/item_editor.py::save_item` | `tests/test_item_editor_project_link.py::test_pl9_1_orig_week_still_saves_from_the_action_plan_block` | done |
| PL10 | Button pairings asserted by grid cell (Timer/Cancel, Follow-up/Subtasks, Set Parent/Show Related, Set Wk Tactic/Set Project, Complete/Delete) | `screens/item_editor.py::create_form` | `tests/test_item_editor_layout.py::test_pl10_button_pairs_share_a_row` | done |
| PL10.1 | Label is exactly `Add Subtasks`; no Duplicate button; no `duplicate_item` method | same | `tests/test_item_editor_layout.py::test_pl10_1_labels_and_removed_duplicate`, `tests/test_item_editor.py::test_pl10_1_duplicate_editor_method_is_gone`, `tests/test_ui_presence.py::test_item_editor_existing_item_buttons` | done |
| PL10.2 | A new item (no Timer) still has Cancel, paired with Save + New | same | `tests/test_item_editor_layout.py::test_pl10_2_new_item_still_has_cancel` | done |
| PL10.3 | A completed item (no Timer) still has a placed Cancel | same | `tests/test_item_editor_layout.py::test_pl10_3_completed_item_still_has_cancel` | done |
| PL10.4 | Set Wk Tactic and Set Project render on a **new** item, paired | `screens/item_editor.py::create_form` | `tests/test_item_editor_layout.py::test_pl10_4_new_item_can_set_a_project_before_it_is_saved` | done |
| PL10.5 | A project chosen before the first save is held, not discarded | `screens/item_editor.py::apply_project_selection` | `tests/test_item_editor_layout.py::test_pl10_5_new_item_selection_survives_to_the_save` | done |
| PL11 | The merged follow-up saves before copying | `screens/item_editor.py::create_followup` | `tests/test_item_editor.py::test_pl11_followup_saves_first` | done |
| PL11.1 | A failed save leaves no follow-up behind | same | `tests/test_item_editor.py::test_pl11_1_followup_aborts_on_save_failure` | done |

## C. Follow-up inheritance

| Spec ID | Criterion | Implementation | Test | Status |
|---|---|---|---|---|
| PL12 | A follow-up inherits the original's Project link and APE | `db_manager_project_boards.py::inherit_project_links`, called from `db_manager.py::create_followup_item` | `tests/test_item_editor_project_link.py::test_pl12_followup_inherits_project_link` | done |
| PL12.1 | The sibling copy path (`complete_and_create`) inherits it too — **precautionary**: that function has no caller in `src/` today, only tests, so `create_followup_item` is the only live path | `db_manager.py::complete_and_create` | `::test_pl12_1_complete_and_create_inherits_project_link` | done |
| PL12.2 | A follow-up of an unfiled item stays unfiled | `inherit_project_links` early return | `::test_pl12_2_followup_of_an_unfiled_item_stays_unfiled` | done |
| PL12.3 | Every link is copied, not just the first | `inherit_project_links` loop | `::test_pl12_3_multi_link_source_copies_every_link` | done |

## Human review (not code-testable)

| Item | How it was checked | Result |
|---|---|---|
| Visual fit of the Action Plan block and the re-paired button grid | Real `ItemEditorDialog` built under the venv against a seeded temporary database, window captured with `screencapture` | done — block reads Project / Wk Tactic / Orig. Week in the left column; all six button rows pair as specified |
| The Project picker renders | Real `SetProjectDialog` built the same way and captured | done — search box, one card per project with lineage and open-item count, current project marked, `+ New Project` / `Clear Project` / `Cancel` |
| App log clean | `~/Library/Application Support/GetMoreDone/weekly_tactic_debug.log` | done — no new errors; the only ERROR lines are pre-existing weekly-tactic migration entries from 2026-08-18 |
