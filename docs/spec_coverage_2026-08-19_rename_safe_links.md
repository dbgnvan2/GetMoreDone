# Spec coverage — Renaming must never break a link

Generated 2026-08-20 by cross-checking every
`::test_...` reference in `docs/spec_2026-08-19_rename_safe_links.md`
against a real `pytest --collect-only` run. Not hand-written: a hand-written
coverage table is a claim, and this repo has shipped a doc asserting a
component was "integrated" when nothing called it (LEARNINGS.md P21).

**17 spec criteria, 17 tests, 0 missing. 13 further tests beyond the spec.**

| Criterion | Test | Collected |
|---|---|---|
| RN-M1.A.1 | `test_rn_m1a1_ape_segment_id_added_and_backfilled` | yes (1 case) |
| RN-M1.A.2 | `test_rn_m1a2_unmatched_segment_is_reported_not_guessed` | yes (1 case) |
| RN-M1.B.1 | `test_rn_m1b1_initiative_ape_link_backfilled_from_title` | yes (1 case) |
| RN-M1.B.2 | `test_rn_m1b2_ambiguous_backfill_is_reported` | yes (1 case) |
| RN-M1.C.1 | `test_rn_m1c1_vision_segment_link_backfilled` | yes (1 case) |
| RN-M1.D | `test_rn_m1d_migration_on_populated_db_run_two` | yes (1 case) |
| RN-M2.A | `test_rn_m2a_initiative_found_by_id_after_rename` | yes (1 case) |
| RN-M2.A | `test_rn_m2a1_legacy_row_heals_on_first_lookup` | yes (1 case) |
| RN-M2.B | `test_rn_m2b_cascade_survives_a_segment_rename` | yes (1 case) |
| RN-M2.C | `test_rn_m2c_segment_join_survives_a_rename` | yes (1 case) |
| RN-M2.D | `test_rn_m2d_no_rename_breaks_any_link` | yes (6 cases) |
| RN-M3.A | `test_rn_m3a_rename_refreshes_every_display_copy` | yes (1 case) |
| RN-M3.B | `test_rn_m3b_tactic_title_follows_rename_without_relinking` | yes (1 case) |
| RN-M4.A | `test_rn_m4a_no_link_resolves_through_a_name` | yes (1 case) |
| RN-M4.A | `test_rn_m4a1_the_scan_can_actually_fire` | yes (1 case) |
| RN-M5.A | `test_rn_m5a_existing_breakage_is_reported` | yes (1 case) |
| RN-M5.B | `test_rn_m5b_ambiguous_data_is_left_alone` | yes (1 case) |

## Beyond the spec

Every one exists because the implementation or a review exposed something
the spec did not anticipate. Seven were added after two independent
reviews found defects — three of them regressions this change introduced.

| Test |
|---|
| `test_rn_a_hand_created_initiative_is_not_reported_as_breakage` |
| `test_rn_a_hand_edited_initiative_title_survives_a_rename` |
| `test_rn_a_lookup_leaves_no_open_transaction` |
| `test_rn_ambiguous_name_is_never_resolved_to_a_link` |
| `test_rn_deleting_a_segment_with_plan_elements_is_refused` |
| `test_rn_item_segment_follows_the_ape_link_not_its_name` |
| `test_rn_m2a1_ambiguous_legacy_row_is_not_healed` |
| `test_rn_m3a_title_refreshes_on_the_update_vision_element_path_too` |
| `test_rn_m4a_comment_stripper_keeps_hashes_inside_strings` |
| `test_rn_migration_runs_once_per_launch` |
| `test_rn_no_duplicate_initiative_after_rename` |
| `test_rn_project_and_tactic_links_are_id_based` |
| `test_rn_repointing_a_vision_element_moves_its_segment_link` |

