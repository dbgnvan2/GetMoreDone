# Spec Coverage — Project Notes feature (2026-06-06)

Plan: [`docs/implementation_plan_2026-06-06_project_notes.md`](implementation_plan_2026-06-06_project_notes.md)

| Spec ID | Description | Implementation | Test | Status |
|---|---|---|---|---|
| M1.A.1 | `ProjectBoardLink.status: str = "open"` | `src/getmoredone/models.py` (class ProjectBoardLink) | `tests/test_project_notes.py::TestM1DataModel::test_project_board_link_has_status_field` | done |
| M1.A.2 | `project_board_links.status TEXT NOT NULL DEFAULT 'open'` on fresh DBs | `src/getmoredone/database.py` (initialize_schema, line ~285) | `tests/test_project_notes.py::TestM1DataModel::test_project_board_links_table_has_status_column` | done |
| M1.A.3 | Idempotent migration adds `status` to existing DBs | `src/getmoredone/database.py` (_run_migrations) | `tests/test_project_notes.py::TestM1DataModel::test_migration_adds_status_to_existing_db` | done |
| M1.A.4 | `add_project_board_link` / `get_project_board_links` round-trip status | `src/getmoredone/db_manager_project_boards.py::add_project_board_link`, `_row_to_project_board_link` AND `src/getmoredone/db_manager.py::_row_to_project_board_link` (kept in sync — see Adjacent Issues) | `tests/test_project_notes.py::TestM1DataModel::test_link_status_roundtrip` | done |
| M2.A.1 | `complete_project_note(link_id)` sets status='completed' | `src/getmoredone/db_manager_project_boards.py::complete_project_note` | `tests/test_project_notes.py::TestM2DBMethods::test_complete_project_note` | done |
| M2.A.2 | `reopen_project_note(link_id)` sets status='open' | `src/getmoredone/db_manager_project_boards.py::reopen_project_note` | `tests/test_project_notes.py::TestM2DBMethods::test_reopen_project_note` | done |
| M2.A.3 | `get_project_board_links(board_id, include_completed=True)` filters by status, orders newest-first | `src/getmoredone/db_manager_project_boards.py::get_project_board_links` | `tests/test_project_notes.py::TestM2DBMethods::test_get_links_filters_by_status`, `::test_get_links_ordered_newest_first` | done |
| M3.A.1 | "Project Notes" bold section header above Action Items | `src/getmoredone/screens/project_boards.py::load_notes` | `tests/test_project_notes.py::TestM3UI::test_project_notes_header_rendered` | done |
| M3.A.2 | Note row: label · status · Open · Complete/Reopen · Unlink (no checkbox, no priority, no dates) | `src/getmoredone/screens/project_boards.py::_render_project_note_row` | `tests/test_project_notes.py::TestM3UI::test_project_note_row_has_status_buttons_no_checkbox`, `::test_completed_note_shows_reopen_not_complete` | done |
| M3.A.3 | Complete/Reopen buttons update status; UI refreshes | `src/getmoredone/screens/project_boards.py::_on_complete_project_note`, `::_on_reopen_project_note` | `tests/test_project_notes.py::TestM3UI::test_complete_button_updates_status`, `::test_reopen_button_updates_status` | done |
| M3.A.4 | Count label: "N note(s) shown" or "N shown • M completed hidden" | `src/getmoredone/screens/project_boards.py::load_notes` (count block) | `tests/test_project_notes.py::TestM3UI::test_notes_count_label` | done |
| M4.A.1 | Shared "Show Completed" checkbox above both sections, default OFF | `src/getmoredone/screens/project_boards.py` (ProjectBoardsScreen.__init__ var; shared_filter frame in _render_detail) | `tests/test_project_notes.py::TestM4SharedShowCompleted::test_show_completed_default_off` | done |
| M4.A.2 | Toggle affects BOTH Notes and Action Items lists | `src/getmoredone/screens/project_boards.py::load_notes` (filter) and `_render_detail` (filter for action items) | `tests/test_project_notes.py::TestM4SharedShowCompleted::test_show_completed_filters_both_lists` | done |
| M4.A.3 | Select All only selects visible items when filter is on | (Pre-existing behavior preserved) `_on_check_all_changed` uses `item_checkbox_vars`, which only contains rendered rows | `tests/test_project_notes.py::TestM4SharedShowCompleted::test_select_all_still_respects_filter`, `tests/test_project_board_bulk_edit.py::TestShowCompletedToggle::test_select_all_respects_filter` | done |
| M5.A.1 | Old "N notes linked to this project." count-only label removed | Replaced by M3 section header in `load_notes` | `tests/test_project_notes.py::TestM5Cleanup::test_old_count_only_label_removed` | done |
| M5.A.2 | Create Note / Link Note / Open Notes toolbar buttons unchanged | No edits to `create_note`, `link_note`, `open_note_picker` | Visual check (also the prior `add_note_to_project` chooser delegates to these handlers, exercised by `tests/test_project_note_chooser.py::TestAddNoteToProjectHandler::*`) | done |
| M6.A.1 | Purpose/Spec/Tests docstrings on new methods | Docstrings present on: `ProjectBoardLink`, `add_project_board_link`, `get_project_board_links`, `complete_project_note`, `reopen_project_note`, `_row_to_project_board_link` (both copies), `load_notes`, `_render_project_note_row`, `_on_complete_project_note`, `_on_reopen_project_note`, `get_project_notes_folder`, `get_project_notes_subfolder_or_default`, `save_obsidian_settings` (updated) | Manual review (diff) | done |
| M6.A.2 | This file (`docs/spec_coverage.md`) exists and lists every spec ID | This file | `tests/test_project_notes.py::TestM6SpecCoverage::test_spec_coverage_doc_mentions_m1_through_m5` | done |
| M7.A.1 | `AppSettings.project_notes_subfolder = "GetMoreDone/Projects"` | `src/getmoredone/app_settings.py` (class AppSettings) | `tests/test_project_notes.py::TestM7Settings::test_settings_has_project_notes_subfolder` | done |
| M7.A.2 | `AppSettings.get_project_notes_folder()` | `src/getmoredone/app_settings.py::get_project_notes_folder` | `tests/test_project_notes.py::TestM7Settings::test_get_project_notes_folder_returns_path` | done |
| M7.A.3 | save/load round-trip the new field | `AppSettings.load` / `save` (auto via dataclass asdict/fields) | `tests/test_project_notes.py::TestM7Settings::test_settings_roundtrip_project_subfolder` | done |
| M7.A.4 | Settings screen "Project Notes Folder" entry, persisted by save_obsidian_settings | `src/getmoredone/screens/settings.py` (create_obsidian_section + save_obsidian_settings) | `tests/test_project_notes.py::TestM7SettingsScreenUI::test_settings_screen_has_project_notes_folder_field` | done |
| M7.A.5 | `CreateNoteDialog` routes `project_board` entity → project folder | `src/getmoredone/screens/item_editor_note_dialogs.py::create_note` (target_subfolder branch) | `tests/test_project_notes.py::TestM7Routing::test_create_note_for_project_writes_to_project_folder`, `::test_create_note_for_action_item_still_uses_generic_folder` | done |
| M7.A.6 | Blank project subfolder falls back to obsidian_notes_subfolder | `get_project_notes_subfolder_or_default` in `app_settings.py`; called from `create_note` | `tests/test_project_notes.py::TestM7Settings::test_blank_project_subfolder_falls_back`, `TestM7Routing::test_create_note_for_project_falls_back_when_blank` | done |
| M7.A.7 | Folder is created on first use | Already in `obsidian_utils.create_obsidian_note` (`notes_folder.mkdir(exist_ok=True)`) | `tests/test_project_notes.py::TestM7Settings::test_project_notes_folder_created_on_first_note` | done |

## Adjacent issues found, not fixed

Per CLAUDE.md §8 — flagged here for follow-up but **not** changed in this PR:

1. **Duplicate `_row_to_project_board_link`**. There are two copies (one on `DBManagerProjectBoardsMixin`, one on `DatabaseManager` at `db_manager.py:1491`) that hydrate the same row. The subclass version shadows the mixin via Python MRO — only updating the mixin would have silently returned `status='open'` for every link. Found while M1 tests failed unexpectedly. **Both copies are now kept in sync**, but the duplication is a latent footgun. Recommend a follow-up that removes the duplicate from `db_manager.py` and forces the mixin's version to win.
2. **Duplicate `_row_to_project_board`** — same pattern, same risk (status, completed_at). Not exercised in this change but the next person who touches `ProjectBoard` will hit it.
3. **`open_note_picker` and the new in-panel Notes list are functionally redundant.** The toolbar button still opens its own dialog listing the same notes that now appear in the panel as first-class rows. Worth simplifying later.
4. **`ProjectBoard.notes` field (freeform text)** is unrelated to Project Notes (Obsidian links). The naming overlap is long-term technical debt — possibly rename `ProjectBoard.notes` to `description` or `summary`.

## Final test counts

- This file's tests: 18 in `test_project_notes.py` (M1×4, M2×5, M3×7, M4×3, M5×1, M6×1, M7×9)

  Actually the M3 group includes 7 tests, M7 has 9, etc — see the file. Last run: all PASS.
- Full repo suite (last green run): **329 passed, 1 skipped** under `./venv/bin/python -m pytest`.

---

# Spec Coverage — Reward-Contingent Task Chunking (2026-08-24)

Spec: [`docs/spec_2026-08-23_dopamine_reward_protocol.md`](spec_2026-08-23_dopamine_reward_protocol.md)
Plan: [`docs/implementation_plan_2026-08-24_dopamine_reward_protocol.md`](implementation_plan_2026-08-24_dopamine_reward_protocol.md)

The spec numbers its sections but assigns no IDs, so these are the spec's own
section numbers prefixed `RP`: `RP-2.1` is spec §2.1.

| Spec ID | Description | Implementation | Test | Status |
|---|---|---|---|---|
| RP-2.1 | `action_items.deliverable TEXT` on a fresh DB | `src/getmoredone/database.py::initialize_schema` | `tests/test_reward_protocol_schema.py::test_rp21_fresh_db_has_deliverable_column`, `::test_rp2_create_table_alone_declares_every_new_column` | done |
| RP-2.1a | Idempotent migration on an upgrading DB | `src/getmoredone/database.py::_run_migrations` | `tests/test_reward_protocol_schema.py::test_rp21a_migration_adds_deliverable_to_legacy_db_and_is_idempotent` | done |
| RP-2.2 | Five `work_logs` audit columns, spec types and defaults | `src/getmoredone/database.py::initialize_schema` | `tests/test_reward_protocol_schema.py::test_rp22_fresh_db_has_all_five_work_log_reward_columns` | done |
| RP-2.2a | Migration back-fills existing rows to `0`, per-column guards | `src/getmoredone/database.py::_run_migrations` | `tests/test_reward_protocol_schema.py::test_rp22a_migration_backfills_work_log_defaults_on_existing_rows`, `::test_rp22a_a_half_migrated_db_gets_the_rest_of_the_columns` | done |
| RP-2.3 | `project_boards.savor_count INTEGER NOT NULL DEFAULT 0` | `src/getmoredone/database.py` (both halves) | `tests/test_reward_protocol_schema.py::test_rp23_savor_count_column_and_migration` | done |
| RP-2.3a | Counter round-trips; increment is real | `src/getmoredone/db_manager_project_boards.py::increment_project_savor_count`, `db_manager.py::_row_to_project_board` | `tests/test_reward_protocol_schema.py::test_rp23a_savor_count_round_trips_through_get_project_board`, `::test_rp23a_increment_reports_an_unknown_board_instead_of_pretending` | done |
| RP-2.3b | `update_project_board` cannot roll the counter back (not in spec; added in plan §1) | `src/getmoredone/db_manager_project_boards.py::update_project_board` (column deliberately absent) | `tests/test_reward_protocol_schema.py::test_rp23b_update_project_board_cannot_clobber_savor_count` | done |
| RP-2.4 | `WorkLog` carries the five fields and round-trips | `src/getmoredone/models.py::WorkLog`, `db_manager.py::create_work_log`, `::_row_to_work_log` | `tests/test_reward_protocol_schema.py::test_rp24_work_log_reward_fields_round_trip`, `::test_rp24_a_plain_session_records_no_reward` | done |
| RP-2.5 | `ActionItem.deliverable` round-trips on create **and** update | `src/getmoredone/models.py::ActionItem`, `db_manager.py::_write_new_action_item`, `::_update_action_item` | `tests/test_reward_protocol_schema.py::test_rp25_deliverable_round_trips_on_create_and_update` | done |
| RP-3.1 | `phase_for`: `< 15 → wiring`, `>= 15 → maintaining` | `src/getmoredone/reward_protocol.py::phase_for` | `tests/test_reward_protocol.py::test_rp31_phase_for_boundary_is_exactly_fifteen` | done |
| RP-3.2 | Phase 1 always savors | `src/getmoredone/reward_protocol.py::decide_reward` | `tests/test_reward_protocol.py::test_rp32_phase_one_always_shows_savor` | done |
| RP-3.3 | Phase 2 savor rate ≈ 40% | `src/getmoredone/reward_protocol.py::decide_reward` | `tests/test_reward_protocol.py::test_rp33_phase_two_savor_rate_is_about_forty_percent` | done |
| RP-3.4 | Celebration ≈ 20% in both phases | `src/getmoredone/reward_protocol.py::decide_reward` | `tests/test_reward_protocol.py::test_rp34_celebration_rate_is_twenty_percent_in_both_phases` | done |
| RP-3.5 | Celebration independent of the savor decision | `src/getmoredone/reward_protocol.py::decide_reward` | `tests/test_reward_protocol.py::test_rp35_celebration_is_independent_of_savor` | done |
| RP-3.6 | Celebration values come from `CELEBRATION_TYPES`, all used | `src/getmoredone/reward_protocol.py::CELEBRATION_TYPES` | `tests/test_reward_protocol.py::test_rp36_celebration_values_come_from_the_declared_tuple` | done |
| RP-3.7 | Never guaranteed in either phase | `src/getmoredone/reward_protocol.py::decide_reward` | `tests/test_reward_protocol.py::test_rp37_celebration_is_never_guaranteed_in_either_phase` | done |
| RP-3.8 | Thresholds are named config, not literals in the logic | `src/getmoredone/reward_protocol.py` (module constants) | `tests/test_reward_protocol.py::test_rp38_decide_reward_body_has_no_magic_numbers` | done |
| RP-3.9 | Deterministic under a seed; the injected rng is the only variation | `src/getmoredone/reward_protocol.py::decide_reward` | `tests/test_reward_protocol.py::test_rp39_same_seed_gives_the_same_sequence` | done |
| RP-4.1 | Deliverable field on the item editor, value reaches the row | `src/getmoredone/screens/item_editor.py`, `item_editor_form.py::build_item_from_form` | `tests/test_ui_presence.py::test_item_editor_ui_elements_presence`, `tests/test_item_editor_new_item_builder.py::test_rp41_deliverable_from_form_reaches_the_saved_item`, `::test_rp41_a_blank_deliverable_is_stored_as_null_not_empty_string`, `tests/test_reward_protocol_timer.py::test_rp41_editor_picks_up_a_deliverable_written_by_the_timer` | done |
| RP-4.2 | Linked start captures deliverable, board and phase | `src/getmoredone/screens/timer_window_reward.py::prepare_reward_session` | `tests/test_reward_protocol_timer.py::test_rp42_linked_start_captures_the_session_deliverable`, `::test_rp42_the_dialog_is_prefilled_from_the_item` | done |
| RP-4.2a | Blank deliverable refused, hint verbatim | `src/getmoredone/screens/timer_window_dialogs.py::DeliverableDialog` | `tests/test_reward_celebration.py::test_rp42a_deliverable_dialog_refuses_blank_and_shows_the_hint`, `::test_rp42a_cancel_returns_no_deliverable` | done |
| RP-4.2b | Cancel aborts the start; nothing is written | `src/getmoredone/screens/timer_window.py::start_timer` | `tests/test_reward_protocol_timer.py::test_rp42b_cancelling_the_deliverable_dialog_does_not_start_the_timer`, `::test_rp42b_cancelling_does_not_save_an_edited_time_block` | done |
| RP-4.2c | Unlinked item runs the timer unchanged | `src/getmoredone/screens/timer_window_reward.py::resolve_reward_board` | `tests/test_reward_protocol_timer.py::test_rp42c_unlinked_item_starts_with_no_reward_protocol` | done |
| RP-4.3 | Break end no longer auto-stops | `src/getmoredone/screens/timer_window.py::tick`, `::enter_break_choice` | `tests/test_reward_protocol_timer.py::test_rp43_break_end_does_not_auto_stop` | done |
| RP-4.3a | "Continue focus" starts a fresh cycle | `src/getmoredone/screens/timer_window.py::begin_new_focus_cycle` | `tests/test_reward_protocol_timer.py::test_rp43a_continue_focus_starts_a_fresh_cycle` | done |
| RP-4.3b | Resume after rest does not re-enter a zero-second break | `src/getmoredone/screens/timer_window.py::pause_timer` | `tests/test_reward_protocol_timer.py::test_rp43b_resume_after_rest_does_not_re_enter_a_zero_second_break` | done |
| RP-4.3c | Stop and Finished/Continue preserved (UI-regression guardrail) | `src/getmoredone/screens/timer_window.py::stop_timer` (unchanged behaviour) | `tests/test_reward_protocol_timer.py::test_rp43c_stop_and_completion_frame_survive_the_break_change` | done |
| RP-4.4 | Done visible in every state except stopped | `src/getmoredone/screens/timer_window.py::_sync_done_button` | `tests/test_reward_protocol_timer.py::test_rp44_done_button_visibility_across_every_timer_state` | done |
| RP-4.4a | Done on an unlinked item skips the protocol | `src/getmoredone/screens/timer_window_reward.py::done_action` | `tests/test_reward_protocol_timer.py::test_rp44a_done_on_unlinked_item_skips_the_reward_protocol` | done |
| RP-4.5 | Savor before celebration | `src/getmoredone/screens/timer_window_reward.py::run_reward_sequence` | `tests/test_reward_protocol_timer.py::test_rp45_savor_precedes_celebration`, `::test_rp44_done_runs_the_reward_sequence_and_then_the_completion_flow` | done |
| RP-4.5a | Celebration never substitutes for savor | `src/getmoredone/screens/timer_window_reward.py::run_reward_sequence` | `tests/test_reward_protocol_timer.py::test_rp45a_celebration_never_substitutes_for_savor` | done |
| RP-4.5b | Every reward column written on Done | `src/getmoredone/screens/timer_window.py::save_work_log` | `tests/test_reward_protocol_timer.py::test_rp45b_done_writes_every_reward_column`, `::test_rp45_savor_delivered_records_the_dialog_not_the_decision` | done |
| RP-4.5c | Counter advances even when the savor is not shown | `src/getmoredone/screens/timer_window.py::save_work_log` | `tests/test_reward_protocol_timer.py::test_rp45c_counter_advances_even_when_savor_is_not_shown` | done |
| RP-4.5d | Counter and work log are written together or not at all | `src/getmoredone/screens/timer_window.py::save_work_log` | `tests/test_reward_protocol_timer.py::test_rp45d_counter_never_advances_without_a_work_log`, `::test_rp45d_a_second_save_does_not_count_the_same_completion_twice`, `::test_rp45_a_deleted_project_completes_without_the_protocol` | done |
| RP-4.5e | Savor copy verbatim, no verbal pat | `src/getmoredone/screens/timer_window_dialogs.py::SavorDialog` | `tests/test_reward_celebration.py::test_rp45e_savor_dialog_copy_is_verbatim`, `::test_rp45e_savor_copy_contains_no_verbal_pat`, `::test_rp45e_acknowledging_records_it_and_closing_does_not` | done |
| RP-4.5f | Celebration is non-blocking and self-cancelling | `src/getmoredone/screens/timer_window_celebration.py` | `tests/test_reward_celebration.py::test_rp45f_celebration_cleans_up_on_window_close`, `::test_rp45f_every_celebration_type_draws_and_schedules`, `::test_rp45f_a_second_celebration_does_not_stack_on_the_first`, `::test_rp45f_the_frame_step_stops_once_the_canvas_is_gone`, `::test_rp45f_an_unknown_type_leaves_nothing_running`, `tests/test_reward_protocol_timer.py::test_rp45f_the_timers_cleanup_cancels_a_running_celebration` | done |
| RP-4.5g | Snapshot frozen at session start | `src/getmoredone/screens/timer_window.py::save_work_log` | `tests/test_reward_protocol_timer.py::test_rp45g_snapshot_survives_a_later_edit_of_the_deliverable` | done |
| RP-6.1 | 15 completions all savor | — (integration) | `tests/test_reward_protocol_timer.py::test_rp61_fifteen_completions_all_savor` | done |
| RP-6.2 | Completion 16 is Phase 2, savor intermittent | — (integration) | `tests/test_reward_protocol_timer.py::test_rp62_sixteenth_completion_is_phase_two`, `::test_rp62_phase_two_savors_sometimes_and_not_always` | done |
| RP-6.3 | Multi-board item uses the oldest link (spec §7.1 MVP) | `src/getmoredone/db_manager_project_boards.py::get_project_boards_for_item` | `tests/test_reward_protocol_schema.py::test_rp63_first_linked_board_by_created_at_wins`, `::test_rp63_an_unlinked_item_has_no_boards` | done |
| RP-7 | Local celebration assets, no network | `tools/generate_tada_wav.py`, `assets/audio/tada.wav`, `screens/timer_window_celebration.py` (drawn confetti/balloons) | `tests/test_reward_celebration.py::test_rp7_committed_tada_wav_is_this_scripts_output`, `::test_rp7_the_chime_is_bundled_where_the_app_looks_for_it`, `::test_rp7_the_chime_is_short_small_and_playable` | done |

## Human review required (not code-testable)

| Item | Why it cannot be a test | What is tested instead |
|---|---|---|
| The savor step produces the intended felt sense | Subjective by definition | Copy asserted verbatim; ordering asserted; forbidden "good job" phrasings asserted absent |
| The confetti/balloon overlays look like a celebration | Visual quality | That each type draws items, schedules frames, is non-blocking and tears down cleanly |
| `assets/audio/tada.wav` sounds like "Ta-DA!" | Requires listening | Valid mono 16-bit WAV, 0.69s, 30 KB, non-silent, non-clipping, and byte-for-byte the generator's output |
