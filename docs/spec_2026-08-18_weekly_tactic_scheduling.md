# Spec — Weekly Tactic Scheduling for Action Items

**Status:** Draft, awaiting approval
**Date:** 2026-08-18
**Spec ID root:** `WT`
**Supersedes:** nothing. Extends the VSP subsystem (`vps_manager.py`, `weekly_items.py`, `item_editor.py`).

---

## 1. Goal

An Action Item's week membership is managed by the app, not by hand. Moving an
item's start date re-files it into the correct Weekly Tactic and creates any
missing Quarter / Month / Week scaffolding along the way — including across a
year boundary — so the user never has to build plan records just to reschedule a
task. A new `weekly_tactic_start_date` on the Action Item preserves the week the
item was *originally* supposed to start, so push-out is visible after the start
date has moved on.

## 2. Model

Two independent axes on an Action Item, **both optional** (WT-D2):

- **What** — Action Item → Project → Annual Plan Element
- **When** — Action Item → Weekly Tactic (the week bucket) + its own start date (the day)

A Weekly Tactic may also hang off a Project, so both axes can agree without
being the same link.

## 3. Non-goals

- Retiring `action_items.week_action_id` (dead legacy FK — see §9).
- Any validation or auto-derivation of Project start/end dates (WT-D9).
- Adherence reporting built on `weekly_tactic_start_date`. This spec stores the
  field; reports come later.
- Changing how Weekly Tactics are created from the APE Weekly screen.

## 4. Decisions taken (2026-08-18, user)

| # | Decision |
|---|---|
| WT-D1 | The Action Item's **start date moves with the Weekly Tactic**. It must land inside the attached tactic's date range. The goal is organising tasks, not tracking adherence. |
| WT-D2 | Weekly Tactic and Project links are both **optional**. One-off items, and users not running APE/VSP at all, must work untouched. |
| WT-D3 | `weekly_tactic_start_date` is a **new field on the Action Item**, stamped once on first attach, never moved automatically, manually overridable. |
| WT-D4 | **One** Weekly Tactic per Action Item at a time. The last one is the week it was completed. |
| WT-D5 | The item's **due/end date must also fall inside** the tactic's date range. An Action Item never spans weeks. |
| WT-D6 | "Make a new one" walks the chain back from the APE: new Quarter only when the move crosses a quarter end and none exists; new Month only when it crosses a month end and none exists; new Week whenever absent. |
| WT-D7 | Rolling into a **new year is allowed**. Copy the APE lineage forward and build Quarter / Month / Week. |
| WT-D8 | Exactly **one Weekly Tactic per week per APE**. Existing duplicates are cleaned up and their children repointed. |
| WT-D9 | Project start/end dates are **informational and manually edited**. No validation, no auto-extension. |
| WT-D10 | The **first week of a year** is a user setting with a choice of rules. No backfill of `weekly_tactic_start_date` on existing items (follows from WT-D2). |

## 5. Findings from spec research (grounded in the live DB and source)

| ID | Finding | Evidence |
|---|---|---|
| WT-F1 | The quarter→month get-or-create cascade **already exists** and works. Only the week step and the year rollover are new. | `assign_ape_to_quarter()` / `assign_ape_to_month()`, `vps_manager.py:343-434` |
| WT-F2 | Week numbers are hardcoded to ISO (`isocalendar().week`), which WT-D10 makes configurable. Under ISO, the week starting 2026-12-28 is W1 **of 2027** — a rollover can produce a "W1" tactic dated December. | `vps_manager.py:604`, `vps_manager.py:667` |
| WT-F3 | Creating a next-year APE requires **eight** rows, four of them editorial year-level records (`annual_visions`, `annual_plans` carry vision statements, themes, objectives). The DB currently holds 2026 only in all four year tables. | `.schema`; `select distinct year` across the four tables |
| WT-F4 | `project_boards` has **no date columns** at all. | `pragma_table_info('project_boards')` |
| WT-F5 | One existing duplicate violates WT-D8: APE `ape-f28e63eb` has two Weekly Tactics for week 2026-02-23. | `group by ape, start_date having count(*) > 1` |
| WT-F6 | `action_items.week_action_id` is NULL on all 3,000+ rows and points at the empty legacy `week_actions` table. Every real link uses `parent_id`. | `select count(*) where week_action_id is not null` → 0 |
| WT-F7 | The Edit Action → Org tab "Wk Tactic" combo reads the empty `week_actions` table, so it can never show anything. | `item_editor.py:465` |
| WT-F8 | Push-out is already tracked at the day grain by `reschedule_history` (2,100 rows) and `original_due_date`. `weekly_tactic_start_date` overlaps it at the week grain. | `.schema reschedule_history` |

---

## 6. Invariants

These hold for every Action Item **that has a Weekly Tactic attached**. An item
with no tactic (WT-D2) is exempt from all of them.

| ID | Invariant |
|---|---|
| WT-INV1 | `start_date` falls within the attached tactic's `start_date .. due_date`. |
| WT-INV2 | `due_date` falls within the same range. |
| WT-INV3 | `weekly_tactic_start_date` is written once and never changed by any automatic path. |
| WT-INV4 | An Action Item has at most one Weekly Tactic. |
| WT-INV5 | At most one Weekly Tactic exists per (APE, week start). |
| WT-INV6 | An Action Item with no Weekly Tactic and no Project is never modified by any rule in this spec. |

---

## 7. Requirements

### WT-M1 — Data model and migrations

- **WT-M1.A** — `action_items` gains `weekly_tactic_start_date TEXT NULL`.
  - **WT-M1.A.1** — The migration is idempotent and leaves all existing rows NULL (WT-D10/E).
    → `tests/test_weekly_tactic_schema.py::test_wt_m1a1_weekly_tactic_start_date_column_added_null`
  - **WT-M1.A.2** — `ActionItem` carries the field, and it survives a create → read → update → read round trip.
    → `::test_wt_m1a2_weekly_tactic_start_date_round_trips`
- **WT-M1.B** — `project_boards` gains `start_date TEXT NULL` and `end_date TEXT NULL` (WT-F4).
  - **WT-M1.B.1** — Migration is idempotent; existing boards read back NULL.
    → `::test_wt_m1b1_project_board_dates_added_null`
  - **WT-M1.B.2** — Dates round trip through `ProjectBoard` create/update. No validation is applied (WT-D9).
    → `::test_wt_m1b2_project_dates_round_trip_unvalidated`
- **WT-M1.C** — A partial unique index enforces WT-INV5:
  `UNIQUE(annual_plan_element_id, start_date) WHERE item_type='week'`.
  - **WT-M1.C.1** — Inserting a second Weekly Tactic for the same APE and week raises.
    → `::test_wt_m1c1_duplicate_weekly_tactic_rejected`
  - **WT-M1.C.2** — The index is created only after WT-M7 cleanup succeeds; on a DB
    still holding duplicates the migration reports an honest failure and does not
    silently skip the index.
    → `::test_wt_m1c2_index_creation_fails_loudly_on_dirty_db`

### WT-M2 — Week identity and numbering

- **WT-M2.A** — `AppSettings` gains `first_week_of_year_rule`, one of `iso`,
  `jan1`, `first_full`. Default `iso` (preserves today's behaviour, WT-F2).
  - **WT-M2.A.1** — Each rule returns the documented week number for 2026-12-28,
    2027-01-01 and 2027-01-04, and the three rules do not all agree on those dates.
    → `tests/test_week_numbering.py::test_wt_m2a1_three_rules_differ_at_year_boundary`
  - **WT-M2.A.2** — An unknown or empty setting value falls back to `iso` without raising.
    → `::test_wt_m2a2_unknown_rule_falls_back_to_iso`
- **WT-M2.B** — All week-number generation routes through one helper. No caller
  computes `isocalendar().week` directly (WT-F2).
  - **WT-M2.B.1** — A source scan asserts zero `isocalendar()` calls outside the helper module.
    → `::test_wt_m2b1_no_direct_isocalendar_callers`
  - **WT-M2.B.2** — Weekly Tactic titles (`X - Wnn`) use the configured rule; changing
    the setting changes the generated title for the same week.
    → `::test_wt_m2b2_title_week_number_follows_setting`

### WT-M3 — Attaching, changing and detaching a Weekly Tactic

- **WT-M3.A** — Attaching a tactic to an item stamps `weekly_tactic_start_date`
  with that tactic's week start **only if it is currently NULL** (WT-INV3).
  - **WT-M3.A.1** — First attach stamps the field.
    → `tests/test_weekly_tactic_linking.py::test_wt_m3a1_first_attach_stamps_original_week`
  - **WT-M3.A.2** — A later change to a different tactic leaves the stamp untouched.
    → `::test_wt_m3a2_retarget_preserves_original_week`
  - **WT-M3.A.3** — A manual edit of the field is honoured and persists across a save (WT-D3).
    → `::test_wt_m3a3_manual_override_persists`
- **WT-M3.B** — Attaching or changing a tactic shifts `start_date` and `due_date`
  by whole weeks, preserving day-of-week, so both land in range (WT-INV1/2).
  - **WT-M3.B.1** — A Thursday item moved one week forward stays a Thursday.
    → `::test_wt_m3b1_whole_week_shift_preserves_weekday`
  - **WT-M3.B.2** — An item whose due date would leave the week is clamped to the week end (WT-D5).
    → `::test_wt_m3b2_due_date_clamped_into_tactic_week`
  - **WT-M3.B.3** — After any attach or change, WT-INV1 and WT-INV2 both hold.
    → `::test_wt_m3b3_invariants_hold_after_retarget`
- **WT-M3.C** — Attaching replaces any existing tactic link (WT-INV4); detaching
  clears it and leaves dates where they are.
  - **WT-M3.C.1** — An item linked to tactic A then attached to B is linked to B only.
    → `::test_wt_m3c1_single_tactic_link_enforced`
  - **WT-M3.C.2** — Detaching leaves `start_date`, `due_date` and the stamp unchanged.
    → `::test_wt_m3c2_detach_leaves_dates_alone`
- **WT-M3.D** — Items with no tactic are never touched (WT-INV6, WT-D2).
  - **WT-M3.D.1** — Saving an unlinked item through the editor changes no dates and
    leaves `weekly_tactic_start_date` NULL.
    → `::test_wt_m3d1_unlinked_item_untouched`

### WT-M4 — Start-date-driven re-filing and the scaffolding cascade

- **WT-M4.A** — Changing the start date of an item **that has a tactic** re-files it
  to the tactic covering the new week for the *same APE* (inherited from its
  current tactic — never a different APE).
  - **WT-M4.A.1** — Moving into a week that already has a tactic for that APE relinks
    to it and creates nothing.
    → `tests/test_weekly_tactic_cascade.py::test_wt_m4a1_relink_to_existing_week_creates_nothing`
  - **WT-M4.A.2** — The APE is inherited from the item's current tactic, not from
    whatever tactic covers today.
    → `::test_wt_m4a2_ape_inherited_from_current_tactic`
- **WT-M4.B** — Missing scaffolding is created bottom-up per WT-D6.
  - **WT-M4.B.1** — Same quarter, same month, no week → creates only the Weekly Tactic.
    → `::test_wt_m4b1_creates_week_only_within_month`
  - **WT-M4.B.2** — Crossing a month end with no Month Assignment → creates the Month
    Assignment (APE `mN` flag + `month_tactics` row) and the week, reusing the quarter.
    → `::test_wt_m4b2_creates_month_assignment_on_month_cross`
  - **WT-M4.B.3** — Crossing a quarter end with no Quarter Assignment → creates the
    Quarter Assignment (APE `qN` flag + `quarter_initiatives` row), then month, then week.
    → `::test_wt_m4b3_creates_quarter_assignment_on_quarter_cross`
  - **WT-M4.B.4** — Nothing is created when the corresponding record already exists
    (idempotent on a second identical move).
    → `::test_wt_m4b4_cascade_is_idempotent`
- **WT-M4.C** — Year rollover (WT-D7, WT-F3). Structural rows are copied forward from
  the prior year's lineage; editorial year-level rows are created as **empty stubs**
  and the user is told.
  - **WT-M4.C.1** — Moving an item into a year with no plan structure produces a
    complete chain: `annual_visions` → `annual_plans` → `annual_vision_elements` →
    `annual_plan_elements` → `annual_initiatives` → `quarter_initiatives` →
    `month_tactics` → week item.
    → `::test_wt_m4c1_year_rollover_builds_full_chain`
  - **WT-M4.C.2** — The new APE keeps the same `vision_element_id` and `key_field` as
    the source year, satisfying `UNIQUE(year, vision_element_id)`.
    → `::test_wt_m4c2_rollover_preserves_vision_element_lineage`
  - **WT-M4.C.3** — `annual_visions.vision_statement` / `key_priorities` and
    `annual_plans.theme` / `objective` are created **empty**, never copied or invented.
    → `::test_wt_m4c3_editorial_year_rows_created_empty`
  - **WT-M4.C.4** — The caller receives a structured report naming every record created,
    so the UI can tell the user which stubs need filling in. It is not a bare boolean.
    → `::test_wt_m4c4_rollover_returns_created_record_report`
  - **WT-M4.C.5** — A second move into the same new year reuses the year rows and creates
    no duplicates.
    → `::test_wt_m4c5_second_rollover_is_idempotent`
- **WT-M4.D** — Failure is loud, never silent (P2/P15).
  - **WT-M4.D.1** — If any step of the cascade fails, the whole re-file is rolled back,
    the item keeps its previous tactic and dates, and the error surfaces to the caller.
    → `::test_wt_m4d1_cascade_failure_rolls_back_and_raises`
  - **WT-M4.D.2** — A start-date change on an item with **no** tactic runs no cascade
    at all (WT-INV6).
    → `::test_wt_m4d2_no_cascade_for_unlinked_item`

### WT-M5 — Completion re-files to the completion week

- **WT-M5.A** — Completing an item **that has a tactic** re-files it to the tactic
  covering the completion date for its APE, running the same WT-M4 cascade.
  - **WT-M5.A.1** — An item planned for an earlier week and completed later ends up on
    the completion week's tactic, with `start_date` moved to match (WT-D1).
    → `tests/test_weekly_tactic_completion.py::test_wt_m5a1_completion_refiles_to_current_week`
  - **WT-M5.A.2** — `weekly_tactic_start_date` still holds the original week, so push-out
    is computable after completion (WT-D3).
    → `::test_wt_m5a2_original_week_survives_completion`
  - **WT-M5.A.3** — `completed_at` falls inside the resulting tactic's range.
    → `::test_wt_m5a3_completion_date_inside_tactic_range`
  - **WT-M5.A.4** — Completing an item with **no** tactic attaches nothing (WT-D2).
    → `::test_wt_m5a4_completion_leaves_unlinked_item_unlinked`
  - **WT-M5.A.5** — Completion in the following calendar year triggers the WT-M4.C
    rollover rather than failing.
    → `::test_wt_m5a5_completion_across_year_boundary`
- **WT-M5.B** — Re-opening a completed item does not un-file it. The tactic set at
  completion stays until something else moves it.
  - **WT-M5.B.1** — Status open → complete → open leaves the completion-week tactic in place.
    → `::test_wt_m5b1_reopen_keeps_completion_week_tactic`

### WT-M6 — UI surfaces

Every front end that can set these values must actually pass them (P25).

- **WT-M6.A** — Edit Action → Org tab: the broken `week_actions`-backed combo (WT-F7)
  is replaced by a read-only display of the current tactic plus the existing
  "Set Wk Tactic" button, and a visible, editable `weekly_tactic_start_date` field.
  - **WT-M6.A.1** — The Org tab no longer queries `week_actions`.
    → `tests/test_item_editor_weekly_tactic_ui.py::test_wt_m6a1_org_tab_does_not_query_legacy_table`
  - **WT-M6.A.2** — The tactic display shows the linked tactic's title for a linked item
    and an explicit "(none)" for an unlinked one.
    → `::test_wt_m6a2_org_tab_shows_current_tactic_or_none`
  - **WT-M6.A.3** — Editing the `weekly_tactic_start_date` widget and saving reaches
    `update_action_item` with that value (boundary intercepted, not just widget rendered).
    → `::test_wt_m6a3_manual_stamp_edit_reaches_db_layer`
- **WT-M6.B** — Changing the start date in the editor triggers the WT-M4 re-file on save,
  and the resulting tactic change is visible without reopening the dialog.
  - **WT-M6.B.1** — Saving a moved start date calls the re-file path with the new date.
    → `::test_wt_m6b1_start_date_change_invokes_refile`
  - **WT-M6.B.2** — When the cascade creates records, the user sees a summary naming them
    (from the WT-M4.C.4 report), including year-rollover stubs needing attention.
    → `::test_wt_m6b2_created_records_summarised_to_user`
- **WT-M6.C** — Project Boards screen exposes the new start/end date fields (WT-M1.B).
  - **WT-M6.C.1** — Entering dates and saving reaches the board update call with both values.
    → `tests/test_project_board_dates_ui.py::test_wt_m6c1_project_dates_reach_db_layer`
- **WT-M6.D** — Settings exposes the first-week-of-year rule (WT-M2.A).
  - **WT-M6.D.1** — Selecting a rule and saving persists it to `AppSettings`.
    → `tests/test_settings_week_rule_ui.py::test_wt_m6d1_week_rule_setting_persists`

### WT-M7 — Duplicate cleanup

- **WT-M7.A** — A one-shot migration merges duplicate Weekly Tactics per (APE, week),
  keeping the oldest by `created_at` and repointing children (WT-D8, WT-F5).
  - **WT-M7.A.1** — On a fixture seeded with the real duplicate shape, one tactic survives
    and every child Action Item points at the survivor.
    → `tests/test_weekly_tactic_dedupe.py::test_wt_m7a1_duplicates_merged_children_repointed`
  - **WT-M7.A.2** — The migration reports how many duplicates it merged and how many
    children it repointed — never a silent pass (P2).
    → `::test_wt_m7a2_dedupe_reports_counts`
  - **WT-M7.A.3** — Running it twice is a no-op the second time.
    → `::test_wt_m7a3_dedupe_idempotent`
  - **WT-M7.A.4** — Dirty-state case: a DB already containing the post-cleanup shape plus a
    newly introduced duplicate is cleaned correctly (P8).
    → `::test_wt_m7a4_dedupe_on_dirty_state`

---

## 8. Implementation order

| Step | Requirement | Depends on |
|---|---|---|
| 1 | WT-M7 duplicate cleanup | — (must precede the unique index) |
| 2 | WT-M1 schema + migrations | WT-M7 for WT-M1.C |
| 3 | WT-M2 week numbering helper + setting | WT-M1 |
| 4 | WT-M3 attach / change / detach + invariants | WT-M1, WT-M2 |
| 5 | WT-M4.A/B cascade within a year | WT-M3 |
| 6 | WT-M4.C year rollover | WT-M4.B |
| 7 | WT-M4.D failure handling | WT-M4.C |
| 8 | WT-M5 completion re-filing | WT-M4 |
| 9 | WT-M6 UI surfaces | all of the above |

## 9. Adjacent issues found, not fixed

Per the global rule on old code: found while specifying, deliberately left alone.

- **WT-F6 — `action_items.week_action_id` is a dead FK.** NULL on every row, pointing
  at the empty legacy `week_actions` table. `db_manager.py:723-753` keys reschedule
  propagation off it, so that block never fires. Retiring it is its own change.
- **WT-F8 — Push-out is tracked twice.** `reschedule_history` + `original_due_date` at
  the day grain, `weekly_tactic_start_date` at the week grain. Reports must pick one.
- **The `SetWeeklyTacticDialog` palette fix** (blank picker) is in the working tree,
  uncommitted, and is a prerequisite for any manual testing of WT-M6.

## 10. Criteria needing human review

- **WT-M4.C.3 / WT-M6.B.2** are code-testable for content and messaging, but the
  resulting year-rollover stubs should be eyeballed once on the VSP Planning and
  Vision Planning Hub screens in the running app — an empty `annual_visions` row
  rendering badly is not something these assertions would catch.
