# Spec — Weekly Tactic Scheduling for Action Items

**Status:** Draft v2, awaiting approval
**Date:** 2026-08-18
**Spec ID root:** `WT`
**Supersedes:** v1 of this file (commits 39e0049, e853fa3).
**Extends:** the VSP subsystem (`vps_manager.py`, `weekly_items.py`, `item_editor.py`).

> **v2 changelog.** Two independent reviews of v1 found twelve substantive defects.
> Corrected here: the tactic link column (WT-D11), the rollover stub policy
> (WT-D7a restated per-field), rollback feasibility (WT-M4.D), the front-end
> enumeration (WT-M6), the already-violated invariants (WT-M7.B), the
> APE-vs-lineage contradiction (WT-M4.A), and four factual errors in §5.

---

## 1. Goal

An Action Item's week membership is managed by the app, not by hand. Moving an
item's start date re-files it into the correct Weekly Tactic and creates any
missing Quarter / Month / Week scaffolding along the way — including across a
year boundary — so the user never has to build plan records just to reschedule a
task. A new `weekly_tactic_start_date` on the Action Item preserves the week the
item was *originally* supposed to start, so push-out stays visible after the
start date has moved on.

## 2. Model

Two independent axes on an Action Item, **both optional** (WT-D2):

- **What** — Action Item → Project → Annual Plan Element
- **When** — Action Item → Weekly Tactic (the week bucket) + its own start date (the day)

A Weekly Tactic may also hang off a Project, so both axes can agree without
being the same link.

**Storage.** These axes are only independent once the tactic link has its own
column. Today it shares `parent_id` with ordinary subtask nesting; WT-D11 fixes
that, and every rule below assumes the fix.

## 3. Non-goals

- Retiring `action_items.week_action_id` (dead legacy FK — see §9).
- Validation or auto-derivation of Project start/end dates (WT-D9).
- Adherence reporting built on `weekly_tactic_start_date`. This spec stores the
  field; reports come later.
- Google Calendar import triggering the cascade (WT-D12).
- Changing how Weekly Tactics are created from the APE Weekly screen — except
  where WT-M1.C's new index changes that path's failure mode (WT-M1.C.3).

## 4. Decisions taken (2026-08-18, user)

| # | Decision |
|---|---|
| WT-D1 | The Action Item's **start date moves with the Weekly Tactic**. It must land inside the attached tactic's date range. The goal is organising tasks, not tracking adherence. |
| WT-D2 | Weekly Tactic and Project links are both **optional**. One-off items, and users not running APE/VSP at all, must work untouched. |
| WT-D3 | `weekly_tactic_start_date` is a **new field on the Action Item**, stamped once on first attach, never moved automatically, manually overridable. |
| WT-D4 | **One** Weekly Tactic per Action Item at a time. The last one is the week it was completed. |
| WT-D5 | The item's **due/end date must also fall inside** the tactic's date range. An Action Item never spans weeks. |
| WT-D6 | "Make a new one" walks the chain back from the APE: new Quarter only when the move crosses a quarter end and none exists; new Month only when it crosses a month end and none exists; new Week whenever absent. |
| WT-D7 | Rolling into a **new year is allowed**. Copy the lineage forward and build Quarter / Month / Week. |
| WT-D7a | **Field-level split on rollover.** Structural fields — every FK and the `segment_name` / `subsegment_name` / `category_name` / `key_field` lineage — are copied or re-pointed so the new year's chain is valid. A named set of **editorial** fields is created blank: `annual_visions.title` / `vision_statement` / `key_priorities`, and `annual_plans.theme` / `objective` / `description`. Editorial text is never copied forward and never invented. Rows created this way are marked (WT-D13) and reported to the user. |
| WT-D8 | Exactly **one Weekly Tactic per week per APE**. Existing duplicates are cleaned up and their children repointed. |
| WT-D9 | Project start/end dates are **informational and manually edited**. No validation, no auto-extension. |
| WT-D10 | The **first week of a year** is a user setting with a choice of rules. No backfill of `weekly_tactic_start_date` on existing items (follows from WT-D2). |
| WT-D11 | The tactic link gets its **own column**, `action_items.weekly_tactic_id`. The 49 existing `week → daily` `parent_id` rows migrate onto it and `parent_id` is left to ordinary nesting. An item may be both a subtask and week-filed. |
| WT-D12 | **Google Calendar import is out of scope.** `calendar_importer.py` updates dates without re-filing and without creating any plan record. An imported item may sit outside its tactic's week until touched manually. |
| WT-D13 | Rollover-created rows are marked with an explicit **`created_by_rollover`** flag, not inferred from empty fields. |

## 5. Findings from spec research

All verified against the live DB (`~/Library/Application Support/GetMoreDone/getmoredone.db`)
and the working tree at commit e853fa3.

| ID | Finding | Evidence |
|---|---|---|
| WT-F1 | The quarter→month get-or-create cascade **already exists** and works. | `assign_ape_to_quarter()` / `assign_ape_to_month()`, `vps_manager.py:343-434` |
| WT-F2 | Week numbering has **three** defects, not one. (a) Three call sites use `isocalendar()`, not two: `vps_manager.py:604`, `vps_manager.py:667`, **`item_editor.py:559`** — the third is inside `_canonical_weekly_tactic_title()`, which rewrites titles on every weekly save. (b) All three take `.week` and **discard the ISO year**, so a boundary week's number is ambiguous: 2026-12-28 and 2027-01-01 are both ISO **2026-W53** (2026 has 53 ISO weeks); 2027-01-04 is 2027-W1. (c) Week *identity* — which week contains a date — is decided separately and inconsistently: setting-driven in `db_manager._compute_week_bounds`, **hardcoded Monday** in `vps_manager_planning.py:329` and `:677`. | verified by running `date.isocalendar()`; `grep -rn "isocalendar()" src/` |
| WT-F3 | Most of the year chain **already auto-creates**. `_get_or_create_annual_plan_for_ape` (`vps_manager.py:505-567`) get-or-creates `tl_visions`, `annual_visions`, `annual_plans`, `annual_initiatives` for any year. Genuinely new: the `annual_vision_elements` / `annual_plan_elements` lineage copy and the week item. **It writes non-empty editorial text today** — `title=f"{segment_name} {year}"` (`:553`), `theme=f"{segment_name} {year} Plan"` (`:563`) — which WT-D7a changes for an already-shipped path with four callers (`ape_assignment.py:233,387`; `ape_period_view.py:242,396`). | source read |
| WT-F4 | `project_boards` has **no date columns**. | `pragma_table_info` |
| WT-F5 | One duplicate violates WT-D8: APE `ape-f28e63eb`, week 2026-02-23, 2 rows. The **older** row is titled `W8` and the newer `W9`; 2026-02-23 is ISO week 9, so "keep the oldest" would preserve the mis-numbered title. The loser carries 1 `reschedule_history` row, which `ON DELETE CASCADE` would destroy. | `group by ape, start_date having count(*) > 1` |
| WT-F6 | `action_items.week_action_id` is NULL on **all 646 rows** and points at the empty legacy `week_actions` table. | `select count(*)` → 646 total, 0 non-null |
| WT-F7 | The Edit Action → Org tab combo reads the empty `week_actions` table and can never show anything. | `item_editor.py:465` |
| WT-F8 | Push-out is already tracked at the day grain by `reschedule_history` (2,100 rows) and `original_due_date`. | `.schema` |
| WT-F9 | **`parent_id` serves two relationships at once**: 94 `daily → daily` nesting rows and 49 `week → daily` tactic links. `apply_weekly_tactic_selection` (`item_editor.py:1509`) and `SetParentDialog` write the same column, so each silently destroys the other's link. Cause of WT-D11. | `join action_items on parent_id group by item_type` |
| WT-F10 | **WT-INV1/INV2 are already false.** Of the 49 linked items, **24** have a start date and **29** a due date outside their tactic's week. | `count where not between` |
| WT-F11 | **The cascade cannot roll back as currently built.** Every creator ends in its own `commit()` (`vps_manager_planning.py:133, 208, 284, 505, 626`; `vps_manager.py:311, 322`) with no `commit=False` seam, and there are `raise` sites mid-chain (`vps_manager.py:359`, `:421`). A failure at row 6 of 8 leaves 5 committed — which WT-M4.C.5's idempotence then adopts as a complete lineage. | source read |
| WT-F12 | **Ten surfaces move a start date; nine complete an item.** *(Superseded 2026-08-19 by BP4: `reschedule_dialog.py` and `db_manager.complete_and_create` are deleted — nothing in `src/` called either. Nine and eight now; the enumeration below is left as written because it records what was true when the spec was drafted, and the live list is the one in `tests/test_weekly_tactic_surfaces.py`.)* Dates: `today.py`, `upcoming.py`, `all_items.py`, `drag_schedule.py`, `reschedule_dialog.py`, `project_boards.py` (bulk), `item_editor.py`, `timer_window.py`, `calendar_importer.py:177`. Completion: the same list plus `completed.py`, `hierarchical.py`, and `db_manager.complete_and_create`. `bulk_update_action_items` forces `due = start + 1 day` (`db_manager.py:233`), which guarantees a WT-INV2 violation when start lands on a week's last day. | `grep -rln` across `src/` |
| WT-F13 | `assign_ape_to_quarter` / `assign_ape_to_month` return bare booleans, asserted `is True` at `tests/test_vps_hub_crud.py:311` and `:342`, and ignored by all four app callers. Any return-shape change breaks those tests (P22). | source read |
| WT-F14 | The tactic picker only offers weeks in a hardcoded **anchor −21 / +7 day** window (`item_editor.py:512-516`), so a tactic outside ±3 weeks cannot be chosen manually. | source read |

---

## 6. Invariants

These hold for every Action Item **that has a Weekly Tactic attached**, and only
from the moment that item is next attached, re-filed or completed. Pre-existing
violations are repaired by WT-M7.B, not assumed absent. An item with no tactic
(WT-D2) is exempt from all of them.

| ID | Invariant |
|---|---|
| WT-INV1 | `start_date` falls within the attached tactic's `start_date .. due_date`. |
| WT-INV2 | `due_date` falls within the same range. |
| WT-INV3 | `weekly_tactic_start_date` is written once and never changed by any automatic path. |
| WT-INV4 | `weekly_tactic_id` holds at most one tactic, and that row has `item_type='week'`. |
| WT-INV5 | At most one Weekly Tactic exists per (APE, week containing that date). |
| WT-INV6 | An Action Item with no Weekly Tactic is never modified by any rule in this spec. |

---

## 7. Requirements

### WT-M1 — Data model and migrations

- **WT-M1.A** — `action_items` gains `weekly_tactic_start_date TEXT NULL`.
  - **WT-M1.A.1** — Idempotent migration; all existing rows left NULL (WT-D10).
    → `tests/test_weekly_tactic_schema.py::test_wt_m1a1_weekly_tactic_start_date_column_added_null`
  - **WT-M1.A.2** — Survives a create → read → update → read round trip.
    → `::test_wt_m1a2_weekly_tactic_start_date_round_trips`
- **WT-M1.B** — `project_boards` gains `start_date TEXT NULL` and `end_date TEXT NULL` (WT-F4).
  - **WT-M1.B.1** — Idempotent; existing boards read back NULL.
    → `::test_wt_m1b1_project_board_dates_added_null`
  - **WT-M1.B.2** — Round trip, unvalidated (WT-D9).
    → `::test_wt_m1b2_project_dates_round_trip_unvalidated`
- **WT-M1.C** — Unique index enforcing WT-INV5 on the *normalised* week start:
  `UNIQUE(annual_plan_element_id, start_date) WHERE item_type='week'`.
  - **WT-M1.C.1** — A second tactic for the same APE and week start is rejected.
    → `::test_wt_m1c1_duplicate_weekly_tactic_rejected`
  - **WT-M1.C.2** — Created only after WT-M7 succeeds; on a DB still holding duplicates
    the migration fails loudly rather than skipping the index.
    → `::test_wt_m1c2_index_creation_fails_loudly_on_dirty_db`
  - **WT-M1.C.3** — `create_week_action_items_for_ape` guards duplicates with a
    month-prefixed `LIKE` that cannot see an adjacent-month collision. With the index
    in place that becomes an uncaught `IntegrityError` in a screen with no handler.
    The path catches it and reports honestly (WT-F5, non-goal exception).
    → `::test_wt_m1c3_ape_weekly_screen_reports_duplicate_instead_of_crashing`
  - **WT-M1.C.4** — SQLite treats NULLs as distinct, so a week item with a NULL APE
    bypasses the index. Week items require a non-NULL APE, enforced and tested.
    → `::test_wt_m1c4_week_item_requires_ape`
  - **WT-M1.C.5** — Changing `first_day_of_week` re-snaps week starts
    (`_normalize_week_item_dates`, `db_manager.py:1059`) and can collide two weeks onto
    one start date. The collision is reported, not raised out of an ordinary save.
    → `::test_wt_m1c5_first_day_change_collision_reported`
- **WT-M1.D** — `action_items` gains `weekly_tactic_id TEXT NULL REFERENCES action_items(id) ON DELETE SET NULL` (WT-D11, WT-F9).
  - **WT-M1.D.1** — Migration moves every `parent_id` whose parent has `item_type='week'`
    onto `weekly_tactic_id` and NULLs that `parent_id`. On the live shape: 49 rows moved,
    94 nesting rows untouched. Counts are reported.
    → `tests/test_weekly_tactic_link_migration.py::test_wt_m1d1_tactic_links_migrated_nesting_preserved`
  - **WT-M1.D.2** — An item can hold a daily parent **and** a tactic simultaneously; setting
    one never clears the other.
    → `::test_wt_m1d2_parent_and_tactic_coexist`
  - **WT-M1.D.3** — `weekly_tactic_id` pointing at a non-week row is rejected (WT-INV4).
    → `::test_wt_m1d3_tactic_must_be_week_item`
  - **WT-M1.D.4** — Idempotent; a second run moves nothing.
    → `::test_wt_m1d4_link_migration_idempotent`
- **WT-M1.E** — `annual_visions` and `annual_plans` gain `created_by_rollover INTEGER DEFAULT 0` (WT-D13).
  - **WT-M1.E.1** — Idempotent; existing rows read back 0.
    → `::test_wt_m1e1_rollover_flag_added_default_zero`

### WT-M2 — Week identity and numbering

- **WT-M2.A** — `AppSettings` gains `first_week_of_year_rule`: `iso`, `jan1`, `first_full`.
  Default `iso` (preserves today's behaviour).
  - **WT-M2.A.1** — The spec's expected values, asserted verbatim:

    | date | weekday | `iso` | `jan1` | `first_full` |
    |---|---|---|---|---|
    | 2026-12-28 | Mon | 2026-W53 | 2026-W53 | 2026-W52 |
    | 2027-01-01 | Fri | 2026-W53 | 2027-W1 | 2026-W52 |
    | 2027-01-04 | Mon | 2027-W1 | 2027-W2 | 2027-W1 |

    → `tests/test_week_numbering.py::test_wt_m2a1_rule_table_matches_spec`
  - **WT-M2.A.2** — Unknown or empty value falls back to `iso` without raising.
    → `::test_wt_m2a2_unknown_rule_falls_back_to_iso`
  - **WT-M2.A.3** — The helper returns **(year, week)**, never a bare week number (WT-F2b).
    → `::test_wt_m2a3_helper_returns_year_and_week`
- **WT-M2.B** — One helper owns both week **number** and week **boundary**. No caller
  computes either independently (WT-F2a, WT-F2c).
  - **WT-M2.B.1** — A source scan asserts zero `isocalendar()` calls **and** zero
    ad-hoc `weekday()`-based week-start arithmetic outside the helper module. All
    three known sites plus `vps_manager_planning.py:329` / `:677` are converted.
    → `::test_wt_m2b1_no_direct_week_math_callers`
  - **WT-M2.B.2** — Titles use the configured rule; changing the setting changes the
    generated title, including via `item_editor._canonical_weekly_tactic_title`.
    → `::test_wt_m2b2_title_week_number_follows_setting`
  - **WT-M2.B.3** — Dirty state: flipping `first_day_of_week` on a DB with existing
    tactics leaves every `weekly_tactic_start_date` still pointing at a real week start,
    or reports the ones it cannot (P8).
    → `::test_wt_m2b3_first_day_change_on_populated_db`

### WT-M3 — Attaching, changing and detaching a Weekly Tactic

- **WT-M3.A** — Attaching stamps `weekly_tactic_start_date` **only if NULL** (WT-INV3).
  - **WT-M3.A.1** — First attach stamps the tactic's week start.
    → `tests/test_weekly_tactic_linking.py::test_wt_m3a1_first_attach_stamps_original_week`
  - **WT-M3.A.2** — Retargeting leaves the stamp untouched.
    → `::test_wt_m3a2_retarget_preserves_original_week`
  - **WT-M3.A.3** — Manual edit is honoured and persists (WT-D3).
    → `::test_wt_m3a3_manual_override_persists`
  - **WT-M3.A.4** — If the stamped tactic is later deleted (`ON DELETE SET NULL`), the item
    becomes unlinked but keeps its stamp; a later re-attach does **not** overwrite it, and
    the stale stamp is surfaced rather than silently reused.
    → `::test_wt_m3a4_stamp_survives_tactic_deletion_and_is_surfaced`
- **WT-M3.B** — Dates are brought into range by an **ordered** rule: shift `start_date` and
  `due_date` by whole weeks preserving weekday; **then**, if `due_date` still falls outside,
  clamp it to the week end. The clamp overrides weekday preservation (WT-D5).
  - **WT-M3.B.1** — A Thursday item moved one week forward stays a Thursday.
    → `::test_wt_m3b1_whole_week_shift_preserves_weekday`
  - **WT-M3.B.2** — An item spanning more than 6 days has its due date clamped, losing its
    weekday. 5 such items exist today.
    → `::test_wt_m3b2_multi_week_item_due_date_clamped`
  - **WT-M3.B.3** — WT-INV1 and WT-INV2 both hold after any attach or change.
    → `::test_wt_m3b3_invariants_hold_after_retarget`
  - **WT-M3.B.4** — A NULL `start_date` (1 such item exists) or NULL `due_date` is handled
    explicitly, not by arithmetic on None.
    → `::test_wt_m3b4_null_dates_handled`
- **WT-M3.C** — Attaching replaces any existing tactic (WT-INV4); detaching clears
  `weekly_tactic_id` and leaves dates alone.
  - **WT-M3.C.1** — Attaching a tactic to an item that already has a **daily parent**
    leaves that parent intact (the WT-F9 regression).
    → `::test_wt_m3c1_attach_preserves_daily_parent`
  - **WT-M3.C.2** — Calling Set Parent on a tactic-linked item leaves the tactic intact
    (the reverse WT-F9 regression).
    → `::test_wt_m3c2_set_parent_preserves_tactic`
  - **WT-M3.C.3** — Detaching leaves `start_date`, `due_date` and the stamp unchanged.
    → `::test_wt_m3c3_detach_leaves_dates_alone`
- **WT-M3.D** — Items with no tactic are never touched (WT-INV6, WT-D2), asserted at
  **every** mutation path, not only the editor.
  - **WT-M3.D.1** — A single named predicate (`_tactic_of(item)`) is the only way any path
    decides whether an item is week-filed.
    → `::test_wt_m3d1_single_tactic_predicate`
  - **WT-M3.D.2** — For each of `update_action_item`, `reschedule_item` and
    `bulk_update_action_items`: an unlinked item's dates and stamp are unchanged.
    → `::test_wt_m3d2_unlinked_item_untouched_on_every_path`

### WT-M4 — Start-date-driven re-filing and the scaffolding cascade

- **WT-M4.A** — Changing the start date of an item **that has a tactic** re-files it to the
  tactic covering the new week for the same **lineage** — the APE with the same
  `vision_element_id` in the target year. Within a year that is the same APE row; across a
  year it is the corresponding row for that year (WT-M4.C).
  - **WT-M4.A.1** — Moving into a week that already has a tactic for that lineage relinks
    and creates nothing.
    → `tests/test_weekly_tactic_cascade.py::test_wt_m4a1_relink_to_existing_week_creates_nothing`
  - **WT-M4.A.2** — The lineage is inherited from the item's current tactic, never from
    whatever tactic covers today.
    → `::test_wt_m4a2_lineage_inherited_from_current_tactic`
  - **WT-M4.A.3** — `action_items.annual_plan_element_id` on the item itself is reconciled
    to the tactic's APE after any re-file, so the two never disagree.
    → `::test_wt_m4a3_item_ape_reconciled_after_refile`
- **WT-M4.B** — Missing scaffolding is created bottom-up per WT-D6.
  - **WT-M4.B.1** — Same quarter, same month, no week → creates only the Weekly Tactic.
    → `::test_wt_m4b1_creates_week_only_within_month`
  - **WT-M4.B.2** — Crossing a month end → creates the Month Assignment (`mN` flag +
    `month_tactics` row) and the week, reusing the quarter.
    → `::test_wt_m4b2_creates_month_assignment_on_month_cross`
  - **WT-M4.B.3** — Crossing a quarter end → creates the Quarter Assignment (`qN` flag +
    `quarter_initiatives` row), then month, then week.
    → `::test_wt_m4b3_creates_quarter_assignment_on_quarter_cross`
  - **WT-M4.B.4** — Idempotent on a second identical move.
    → `::test_wt_m4b4_cascade_is_idempotent`
  - **WT-M4.B.5** — Where the lookup helpers pick "whatever sorts first"
    (`quarter_rows[0]`, `month_rows[0]`, `ORDER BY created_at LIMIT 1`), the choice is
    deterministic and documented — duplicates at quarter/month level are not deduped by
    WT-D8, so selection must not vary between runs.
    → `::test_wt_m4b5_ancestor_selection_deterministic`
- **WT-M4.C** — Year rollover (WT-D7, WT-D7a, WT-F3).
  - **WT-M4.C.1** — Moving into a year with no structure produces a complete chain and
    **exactly one** row in each of `annual_visions`, `annual_plans`,
    `annual_vision_elements`, `annual_plan_elements`, `annual_initiatives`,
    `quarter_initiatives`, `month_tactics` and the week item — no extras.
    → `::test_wt_m4c1_year_rollover_builds_exactly_one_row_per_table`
  - **WT-M4.C.2** — The new APE keeps the source `vision_element_id` and `key_field`.
    → `::test_wt_m4c2_rollover_preserves_vision_element_lineage`
  - **WT-M4.C.3** — The named editorial fields (WT-D7a) are blank, and `created_by_rollover`
    is 1. This includes making `_get_or_create_annual_plan_for_ape` stop writing
    `title=f"{segment} {year}"` / `theme=f"{segment} {year} Plan"` (WT-F3).
    → `::test_wt_m4c3_editorial_fields_blank_and_flagged`
  - **WT-M4.C.3a** — Structural fields are copied; **year-scoped FKs are re-pointed, not
    copied**. Specifically `annual_plan_elements.annual_vision_element_id` must point at
    the *new* year's `annual_vision_elements` row, asserted as
    `new_ape.annual_vision_element_id == new_ave.id AND new_ave.year == target_year`.
    → `::test_wt_m4c3a_year_scoped_fks_repointed_not_copied`
  - **WT-M4.C.3b** — Stubs are discovered via `created_by_rollover`, never by empty fields.
    Adversarial case: a hand-authored vision with a blank statement is **not** reported.
    → `::test_wt_m4c3b_stub_discovery_uses_flag_not_emptiness`
  - **WT-M4.C.3c** — The four existing callers of `_get_or_create_annual_plan_for_ape`
    (`ape_assignment.py:233,387`; `ape_period_view.py:242,396`) still behave correctly
    after the editorial-field change.
    → `::test_wt_m4c3c_existing_ape_assignment_callers_unaffected`
  - **WT-M4.C.4** — The cascade returns a structured report naming every record created.
    Per WT-F13 this is a **new** function; `assign_ape_to_quarter` / `assign_ape_to_month`
    keep their boolean contract and the tests at `test_vps_hub_crud.py:311` / `:342` stay green.
    → `::test_wt_m4c4_rollover_returns_report_and_bool_callers_unbroken`
  - **WT-M4.C.5** — A second move into the same year reuses the rows and creates no duplicates.
    → `::test_wt_m4c5_second_rollover_is_idempotent`
  - **WT-M4.C.6** — **Partial pre-existing lineage** (3 of 8 rows present) completes the
    chain rather than adopting it as finished.
    → `::test_wt_m4c6_partial_lineage_completed_not_adopted`
  - **WT-M4.C.7** — Backwards (into 2025) and multi-year (2026 → 2028) moves have defined
    behaviour: the target year's chain is built from the item's own lineage; intermediate
    years are not fabricated.
    → `::test_wt_m4c7_backward_and_multi_year_moves`
- **WT-M4.D** — Atomicity and failure. **Built before WT-M4.C** (§8).
  - **WT-M4.D.1** — The whole cascade runs in one transaction. The creators gain a
    `commit=False` seam so their internal `commit()` calls (WT-F11) are suppressed inside it.
    → `::test_wt_m4d1_cascade_runs_in_one_transaction`
  - **WT-M4.D.2** — A failure injected at the **last** row leaves zero rows in all eight
    tables and the item on its original tactic and dates.
    → `::test_wt_m4d2_failure_at_last_row_rolls_back_everything`
  - **WT-M4.D.3** — The real mid-chain raise sites (`resolve_segment_id_by_name` at
    `vps_manager.py:359` / `:421`) are exercised, not just a synthetic exception.
    → `::test_wt_m4d3_missing_segment_rolls_back`
  - **WT-M4.D.4** — A start-date change on an item with **no** tactic runs no cascade (WT-INV6).
    → `::test_wt_m4d4_no_cascade_for_unlinked_item`

### WT-M5 — Completion re-files to the completion week

- **WT-M5.A** — Completing an item **that has a tactic** re-files it to the tactic covering
  the completion date for its lineage, via the WT-M4 cascade.
  - **WT-M5.A.1** — A late completion lands on the completion week's tactic, start date moved
    to match (WT-D1).
    → `tests/test_weekly_tactic_completion.py::test_wt_m5a1_completion_refiles_to_current_week`
  - **WT-M5.A.2** — `weekly_tactic_start_date` still holds the original week (WT-D3).
    → `::test_wt_m5a2_original_week_survives_completion`
  - **WT-M5.A.3** — `completed_at` is a full ISO datetime (`db_manager.py:191`); the range
    check compares `completed_at[:10]`. Fixture completes on the **last day** of the week.
    → `::test_wt_m5a3_completion_on_last_day_of_week_is_in_range`
  - **WT-M5.A.4** — Completing an unlinked item attaches nothing (WT-D2).
    → `::test_wt_m5a4_completion_leaves_unlinked_item_unlinked`
  - **WT-M5.A.5** — Completion in the following year triggers WT-M4.C rather than failing.
    → `::test_wt_m5a5_completion_across_year_boundary`
  - **WT-M5.A.6** — The re-file writes a `reschedule_history` row with
    `reason='completion_refile'`, so the planned start day stays recoverable (WT-F8).
    → `::test_wt_m5a6_completion_refile_records_history`
- **WT-M5.B** — Re-opening does not un-file. The completion-week tactic stays.
  - **WT-M5.B.1** — open → complete → open keeps the tactic.
    → `::test_wt_m5b1_reopen_keeps_completion_week_tactic`
- **WT-M5.C** — `complete_and_create` (`db_manager.py:286`) and `create_followup_item` have
  defined behaviour: the original re-files; the new item inherits the lineage explicitly
  rather than losing it to `duplicate_action_item`'s field-dropping constructor.
  - **WT-M5.C.1** — The follow-up carries `weekly_tactic_id`, `annual_plan_element_id` and
    `segment_description_id`, and its dates satisfy WT-INV1/2.
    → `::test_wt_m5c1_followup_inherits_lineage_and_stays_in_range`

### WT-M6 — Entry points

The hook lives at **one layer**: `db_manager.update_action_item`,
`db_manager.reschedule_item` and `db_manager.bulk_update_action_items`. Screens are not
individually hooked — but each is tested, because a screen that bypasses those three
would bypass the feature (WT-F12, P25).

- **WT-M6.A** — Edit Action → Org tab: the `week_actions`-backed combo (WT-F7) is replaced by
  a read-only tactic display, the existing "Set Wk Tactic" button, and an editable
  `weekly_tactic_start_date` field.
  - **WT-M6.A.1** — Intercepting `vps_manager.get_week_actions*` on the editor records zero calls.
    → `tests/test_item_editor_weekly_tactic_ui.py::test_wt_m6a1_org_tab_never_queries_legacy_table`
  - **WT-M6.A.2** — Shows the linked tactic's title, or an explicit "(none)".
    → `::test_wt_m6a2_org_tab_shows_current_tactic_or_none`
  - **WT-M6.A.3** — Editing the stamp widget and saving reaches `update_action_item` with
    that value (boundary intercepted).
    → `::test_wt_m6a3_manual_stamp_edit_reaches_db_layer`
  - **WT-M6.A.4** — The picker's hardcoded ±3-week window (WT-F14) is replaced by the same
    month/all-weeks filtering the dialog already offers, so any week is reachable.
    → `::test_wt_m6a4_picker_can_reach_any_week`
- **WT-M6.B** — Per-surface wiring. For **each** of `today.py`, `upcoming.py`,
  `all_items.py`, `drag_schedule.py`, `reschedule_dialog.py`, `project_boards.py` (bulk),
  `item_editor.py`, `timer_window.py`: moving a linked item's date through that surface
  re-files it, asserted by intercepting the db_manager boundary.
  - **WT-M6.B.1** — One test per surface; a surface that bypasses the three hooked methods
    fails loudly.
    → `tests/test_weekly_tactic_surfaces.py::test_wt_m6b1_<surface>_refiles` (8 tests)
  - **WT-M6.B.2** — `bulk_update_action_items`' `due = start + 1 day` (`db_manager.py:233`)
    is clamped into the week (WT-F12).
    → `::test_wt_m6b2_bulk_edit_respects_week_bounds`
  - **WT-M6.B.3** — `calendar_importer.py:177` updates dates and re-files **nothing**,
    creating no plan records (WT-D12).
    → `::test_wt_m6b3_calendar_import_does_not_cascade`
  - **WT-M6.B.4** — Completion from each of the 9 completion surfaces re-files (WT-M5).
    → `::test_wt_m6b4_<surface>_completion_refiles` (9 tests)
  - **WT-M6.B.5** — When the cascade creates records the user sees a summary naming them,
    including rollover stubs needing attention (WT-M4.C.4).
    → `::test_wt_m6b5_created_records_summarised_to_user`
- **WT-M6.C** — Project Boards exposes the new date fields.
  - **WT-M6.C.1** — Entering dates and saving reaches the board update call with both.
    → `tests/test_project_board_dates_ui.py::test_wt_m6c1_project_dates_reach_db_layer`
- **WT-M6.D** — Settings exposes the first-week-of-year rule.
  - **WT-M6.D.1** — Selecting a rule and saving persists it.
    → `tests/test_settings_week_rule_ui.py::test_wt_m6d1_week_rule_setting_persists`

### WT-M7 — Data cleanup

- **WT-M7.A** — Merge duplicate Weekly Tactics per (APE, week) (WT-D8, WT-F5).
  - **WT-M7.A.1** — One survivor; every child repointed onto `weekly_tactic_id`.
    → `tests/test_weekly_tactic_dedupe.py::test_wt_m7a1_duplicates_merged_children_repointed`
  - **WT-M7.A.2** — The survivor's title is re-canonicalised through the WT-M2 helper, so
    the merge cannot preserve a mis-numbered title (WT-F5).
    → `::test_wt_m7a2_survivor_title_recanonicalised`
  - **WT-M7.A.3** — `reschedule_history`, `item_links`, `work_logs` and
    `project_board_items` are repointed **before** the loser is deleted; no row count in
    any of them decreases (all four are `ON DELETE CASCADE`).
    → `::test_wt_m7a3_no_cascade_data_lost`
  - **WT-M7.A.4** — Tie-break is defined and tested when both rows have children.
    → `::test_wt_m7a4_tiebreak_when_both_have_children`
  - **WT-M7.A.5** — Reports counts merged and repointed; never a silent pass (P2).
    → `::test_wt_m7a5_dedupe_reports_counts`
  - **WT-M7.A.6** — Idempotent, and correct on dirty state (P8).
    → `::test_wt_m7a6_dedupe_idempotent_and_dirty_state`
- **WT-M7.B** — Repair the 24 start-date and 29 due-date violations (WT-F10).
  - **WT-M7.B.1** — After the migration, zero linked items violate WT-INV1 or WT-INV2.
    → `::test_wt_m7b1_existing_violations_repaired`
  - **WT-M7.B.2** — Repair reports how many items it moved, and by how much, so a large
    silent date rewrite is visible.
    → `::test_wt_m7b2_repair_reports_what_it_moved`
  - **WT-M7.B.3** — Repair writes `reschedule_history` rows with `reason='inv_repair'`.
    → `::test_wt_m7b3_repair_records_history`

---

## 8. Implementation order

| Step | Requirement | Depends on |
|---|---|---|
| 1 | WT-M1.D tactic-link column + migration | — (everything else reads it) |
| 2 | WT-M7.A dedupe | WT-M1.D |
| 3 | WT-M1.A/B/C/E schema | WT-M7.A for WT-M1.C |
| 4 | WT-M2 week identity + numbering | WT-M1 |
| 5 | WT-M4.D atomicity seam | WT-M1 — **before** any cascade code |
| 6 | WT-M3 attach / change / detach | WT-M2, WT-M4.D |
| 7 | WT-M4.A/B cascade within a year | WT-M3 |
| 8 | WT-M4.C year rollover | WT-M4.B, WT-M4.D |
| 9 | WT-M5 completion re-filing | WT-M4 |
| 10 | WT-M7.B invariant repair | WT-M3 |
| 11 | WT-M6 entry points | all of the above |

## 9. Adjacent issues found, not fixed

- **WT-F6 — `week_action_id` is a dead FK.** NULL on all 646 rows. `db_manager.py:723-753`
  keys reschedule propagation off it, so that block never fires. Retiring it is its own change.
- **WT-F8 — push-out tracked twice** (`reschedule_history` + `original_due_date` at day
  grain; `weekly_tactic_start_date` at week grain). Reports must pick one.
- **`_get_or_create_annual_plan_for_ape` hardcodes `end_year = year + 5`** for a new TL
  vision — a magic horizon (P4) this spec leaves alone.
- **No uniqueness at quarter / month / annual level.** WT-D8 dedupes only weekly tactics;
  WT-M4.B.5 makes ancestor selection deterministic but does not prevent the duplicates.
- **`action_items.annual_plan_element_id` has no FK** (`database.py:100`), so a deleted APE
  leaves dangling ids. WT-M4.A.3 reconciles the field but does not add the constraint.
- **Habit items.** `is_habit` and `habit_tracking` exist but are empty (0 rows). A habit
  re-filed to the completion week on every completion is a different feature; out of scope,
  recorded so it is not a surprise later.

## 10. Criteria needing human review

- **WT-M4.C.3 / WT-M4.C.3b / WT-M6.B.5** — the rollover stubs should be eyeballed once on
  the VSP Planning and Vision Planning Hub screens in the running app. An empty
  `annual_visions` row rendering badly, or a stub that reads as a real plan, is not
  something these assertions catch.
- **WT-M7.B** — the repair moves dates on up to 29 existing items. The list should be
  reviewed before the migration runs, in case any violation is deliberate user data rather
  than drift.
