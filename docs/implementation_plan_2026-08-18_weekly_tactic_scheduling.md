# Implementation Plan — Weekly Tactic Scheduling

**Status:** Draft, awaiting approval. **No implementation code written.**
**Date:** 2026-08-18
**Spec:** `docs/spec_2026-08-18_weekly_tactic_scheduling.md` (v2, commit fd3afd5)
**Kickoff:** `docs/changes/2026-08-18-weekly-tactic-scheduling-kickoff.md`
**Spec ID root:** `WT` — every ID below is used verbatim.

**Baseline verified today, before planning:**

```
./venv/bin/python -m pytest -q   →  exit 0, 679 passed, 2 skipped, 22.6s
```

(The kickoff note recorded 652; the tree has moved since. 679/2 is the number
this work must not reduce.)

**Scope:** 83 leaf acceptance criteria across WT-M1..WT-M7, mapping to ~98 test
functions in 11 test files (WT-M6.B.1 is 8 tests, WT-M6.B.4 is 9).

---

## 0. Environment and repo guardrails this build runs inside

These are not in the spec and each one fails in a way that is not obvious.

| Guardrail | What it means here |
|---|---|
| **venv only** | `./venv/bin/python -m pytest -q`. A bare `pytest` resolves elsewhere. |
| **No `tkcalendar`, no `babel`** | Removed deliberately — `tkcalendar` is GPLv3. A `ModuleNotFoundError` for either is **not** fixed by reinstalling. Any date entry this feature adds (WT-M6.A.3 stamp field, WT-M6.C.1 project dates) uses `src/getmoredone/widgets/date_picker.py`, which is stdlib-backed with the same interface. |
| **`.gitignore` ignores `*.json` wholesale** | This feature adds **no** JSON resource — the new `first_week_of_year_rule` is an `AppSettings` dataclass field persisted to the user's settings file outside the repo. If that changes, the file needs a `!` exception **and** an entry in `tests/test_repo_hygiene.py::test_rm7b_required_json_resources_are_tracked`'s list, or it ships missing from every clone and build. |
| **No new root-level files** | No `test_* / diagnose_* / fix_* / debug_* / verify_*` scripts at the repo root (`test_rm7a_repo_root_has_no_stray_scripts`). New root `.md` files need adding to `ROOT_DOC_ALLOWLIST`. **This plan and the spec live in `docs/`, so neither is affected.** |
| **Tests pass in isolation** | `./venv/bin/python -m pytest tests/test_weekly_tactic_cascade.py` alone must pass (`test_rm3d_every_test_file_is_importable_on_its_own`). The root `conftest.py` already puts both import roots on `sys.path`; no test file adds its own. |
| **No new runtime dependency** | This plan adds none. If one became necessary it needs a `THIRD_PARTY_NOTICES.md` entry and must not be GPL — both enforced, and the licensing test walks the whole declared tree. |
| **Never `git add -A`** | Shared working tree, one branch. Every commit stages explicit paths only. |
| **Dirty-state migration test is mandatory** | Every migration in WT-M1 gets a run-#2-against-a-populated-DB test, modelled on `tests/test_first_run.py::test_rm5c_selftest_on_existing_populated_db`. |
| **UI verified in the running app** | DB unit tests are not sufficient for this codebase. WT-M6 work is exercised against real widgets under the venv with `app.log` checked (see §6). |

---

## 1. Decisions needed at approval

Six questions the spec does not settle. Each has a recommended resolution; the
build proceeds on these unless told otherwise. **Q2 and Q4 change user-visible
behaviour and are the two worth a real look.**

**Q1 — Calendar import must opt out of the hook it already calls.**
WT-D12/WT-M6.B.3 require `calendar_importer.py` to move dates without
re-filing. But `calendar_importer.py:177` calls `dbm.update_action_item(...)` —
the very method WT-M6 designates as the hook. Without an opt-out, WT-D12 is
unimplementable.
*Recommended:* `update_action_item(item, normalize_week_dates=True, refile=True)`;
the importer is the only caller passing `refile=False`. WT-M6.B.3 asserts it.

**Q2 — Rollover creates a ninth record the spec does not count.**
The natural rollover primitive, `create_annual_records_from_vision_element`
(`vps_manager.py:221`), ends with `self.db_manager.ensure_project_board_for_ape(ape_id)`
inside a bare `except Exception: pass`. So a year rollover silently creates a
**project board** as well as the eight rows WT-M4.C.1 enumerates as "no extras".
*Recommended:* suppress board creation on the rollover path (explicit flag), and
name the omission in the WT-M4.C.4 report so the user can create the project
deliberately. *Alternative:* keep it and add `project_boards` to WT-M4.C.1's
counted set. **Please pick one.**

**Q3 — WT-M2.B.1's source scan needs a stated boundary.**
The spec names five sites. A scan today finds **twelve** week-math sites:
`isocalendar()` at `vps_manager.py:604`, `:667`, `item_editor.py:559`; week-start
arithmetic at `db_manager.py:1238`, `vps_manager.py:597`,
`vps_manager_planning.py:329`, `:677`, `weekly_items.py:238`,
`item_editor.py:504`, `:509`, `item_editor_weekly_tactic_dialog.py:426`, `:431`,
`:490`. Plus `date_utils.py:41`, `:72`, which use `weekday()` for
business-day skipping — not week identity.
*Recommended:* convert all twelve; the scan test carries an explicit allowlist
naming `date_utils.py` with the reason. A "we only converted the five the spec
listed" outcome would leave WT-F2c's inconsistency alive in the picker.

**Q4 — How WT-M7.B actually runs.** It rewrites dates on 24 + 29 existing rows.
§10 asks the list be reviewed first; WT-M7.B.1 says "after the migration, zero
violations". Those pull in opposite directions.
*Recommended:* WT-M7.A (dedupe — a safe merge) runs automatically inside the
migration, because WT-M1.C's unique index cannot be created until it has.
WT-M7.B ships as `tools/repair_weekly_tactic_invariants.py`, **dry-run by
default**, printing the full before/after list; `--apply` executes. The repair
*function* is unit-tested directly, so all three WT-M7.B criteria stay
code-testable. **Please confirm this split.**

**Q5 — WT-M4.C.3 vs WT-M4.C.3c are only consistent if parameterised.**
WT-M4.C.3 says stop writing `title=f"{segment} {year}"` / `theme=f"{segment} {year} Plan"`.
WT-M4.C.3c says the four existing callers (`ape_assignment.py:233,387`;
`ape_period_view.py:242,396`) still behave correctly. Blank titles would visibly
change those four screens.
*Recommended:* `_get_or_create_annual_plan_for_ape(ape, created_by_rollover=False)`.
False keeps today's text exactly (four callers unchanged); True writes blank
editorial fields and `created_by_rollover=1`. This is the only reading that
satisfies both criteria.

**Q6 — Rollover reads the taxonomy, not last year's row.**
`create_annual_records_from_vision_element` builds the target year's AVE+APE from
`vision_elements` and re-points `annual_vision_element_id` at the new year's AVE.
That satisfies WT-M4.C.2 and WT-M4.C.3a by construction, and its
`UNIQUE(year, vision_element_id)` constraints give WT-M4.C.5 idempotence for
free. *Recommended:* reuse it. If the source vision element is missing, the
cascade fails the transaction with an honest error rather than fabricating a
lineage (WT-M4.D).

---

## 2. Spec facts corrected against the live database today

Read-only snapshot taken at plan time (copy inspected; the live file was never
written to). Two of the spec's fixture claims are wrong, which changes how three
tests are built — none of them changes the design.

| Spec claim | Verified today | Effect |
|---|---|---|
| WT-F10: 24 start / 29 due violations | **24 / 29** — holds | — |
| WT-F5: one duplicate, APE `ape-f28e63eb`, 2026-02-23, older row `W8`, newer `W9`, loser carries 1 `reschedule_history` row | Holds. Older `W8` row holds **all 5 children and 0 history**; newer `W9` row holds **0 children and 1 history row**. 2026-02-23 is ISO 2026-W9, so the newer title is the correct one. | Confirms WT-M7.A.2's need. **WT-M7.A.4's tie-break is not exercised by real data** (only one row has children) — it needs a synthetic fixture. |
| WT-M3.B.4: "a NULL `start_date` (1 such item exists)" | **0** linked items have a NULL start date | Fixture must be synthetic, not sampled. |
| WT-M3.B.2: "5 such items exist today" spanning > 6 days | **1** | Fixture must be synthetic. Assertion unchanged. |
| WT-M1.C.4: week items with NULL APE bypass the index | **0** such rows exist | Enforcing non-NULL APE on week items breaks no existing data. |
| WT-F9: 49 tactic links, 94 daily-nesting rows | **49 / 94** — holds | WT-M1.D.1's counts stand. |
| All four year-scoped tables hold 2026 only | Week items: 2026 only | Rollover has no pre-existing target-year rows to trip over. |

---

## 3. Files: new, and changed

`db_manager.py` is already 1602 lines and `vps_manager.py` 1210. Per
`codex.md` / `standards/file-maintainability.md`, the engine goes in new modules
rather than growing either.

### New source modules

| File | Owns | Est. |
|---|---|---|
| `src/getmoredone/week_calendar.py` | WT-M2. The **single** owner of week identity (which week contains a date) and week numbering (year + number). Pure functions plus a settings-bound `WeekCalendar`. | ~180 |
| `src/getmoredone/weekly_tactic.py` | WT-M3 / WT-M4 / WT-M5. `_tactic_of()` predicate, the date-range rule, the re-file planner, the scaffolding cascade, the rollover, `CascadeReport`. | ~420 |
| `src/getmoredone/weekly_tactic_maintenance.py` | WT-M7.A dedupe + WT-M7.B repair, both returning reports. | ~220 |
| `tools/repair_weekly_tactic_invariants.py` | WT-M7.B operator entry point, dry-run by default (Q4). | ~80 |

### Changed source files

| File | Change | Criteria |
|---|---|---|
| `database.py` | New `_run_weekly_tactic_migrations(conn)` called **after** `VPSSchema.initialize_vps_schema(conn)` (line 253) — the APE tables must exist before the dedupe and the index. Adds `weekly_tactic_start_date`, `weekly_tactic_id`, `project_boards.start_date/end_date`, the partial unique index. | WT-M1.A/B/C/D |
| `vps_schema.py` | New `_extend_annual_visions` / `_extend_annual_plans` following the existing `_extend_*` pattern — `created_by_rollover INTEGER DEFAULT 0`. | WT-M1.E |
| `models.py` | `ActionItem.weekly_tactic_start_date`, `ActionItem.weekly_tactic_id`; `ProjectBoard.start_date/end_date`. | WT-M1.A/B/D |
| `db_manager.py` | `create_action_item` / `update_action_item` / `_row_to_action_item` carry the two new columns; `transaction()` context manager; `refile` kwarg (Q1); the WT-M6 hook in `update_action_item`, `reschedule_item`, `bulk_update_action_items`; `_compute_week_bounds` and `_get_first_day_of_week` delegate to `week_calendar`. | WT-M1.A/D, WT-M4.D, WT-M6 |
| `db_manager_project_boards.py` | Board create/update carry the new dates. | WT-M1.B, WT-M6.C |
| `vps_manager.py` | `commit=False` seam on the cascade path; `_get_or_create_annual_plan_for_ape(..., created_by_rollover=False)` (Q5); `create_week_action_items_for_ape` reports the `IntegrityError` instead of crashing; week numbering via `week_calendar`. `assign_ape_to_quarter` / `assign_ape_to_month` keep their `bool` return **unchanged** (WT-F13). | WT-M1.C.3, WT-M2.B, WT-M4.C/D |
| `vps_manager_planning.py` | `commit=False` seam on `create_tl_vision`, `create_annual_vision`, `create_annual_plan`, `create_annual_initiative`, `create_quarter_initiative`, `create_month_tactic`, `create_week_action`; week-start arithmetic at `:329` / `:677` via `week_calendar`. | WT-M2.B, WT-M4.D |
| `app_settings.py` | `first_week_of_year_rule: str = "iso"` + `_normalize_first_week_of_year_rule` following the existing normalizer pattern. | WT-M2.A |
| `screens/item_editor.py` | Org tab rebuilt (WT-M6.A); `apply_weekly_tactic_selection` writes `weekly_tactic_id`, **never** `parent_id`; `_canonical_weekly_tactic_title` uses `week_calendar`. | WT-M2.B.2, WT-M3.C, WT-M6.A |
| `screens/item_editor_weekly_tactic_dialog.py` | Alignment helpers via `week_calendar`. | WT-M2.B.1 |
| `screens/weekly_items.py` | Alignment at `:238` via `week_calendar`. | WT-M2.B.1 |
| `screens/settings.py` | First-week-of-year rule control. | WT-M6.D |
| `screens/project_boards.py` | Project start/end date fields; bulk-edit path. | WT-M6.B.2, WT-M6.C |
| `calendar_importer.py` | Passes `refile=False` (Q1). | WT-M6.B.3 |
| `screens/hierarchical.py`, `set_parent` dialog | Set Parent writes `parent_id` only, never clearing `weekly_tactic_id`. | WT-M3.C.2 |

### New test files

`tests/test_weekly_tactic_schema.py`, `test_weekly_tactic_link_migration.py`,
`test_week_numbering.py`, `test_weekly_tactic_linking.py`,
`test_weekly_tactic_cascade.py`, `test_weekly_tactic_completion.py`,
`test_weekly_tactic_surfaces.py`, `test_item_editor_weekly_tactic_ui.py`,
`test_project_board_dates_ui.py`, `test_settings_week_rule_ui.py`,
`test_weekly_tactic_dedupe.py` (holds both WT-M7.A and WT-M7.B, per the spec's
own `::` continuation).

### Docs updated in the same change

`CHANGELOG.md`, `docs/USER_GUIDE.md` (the new Settings rule and the Org tab),
`NOTES.md`, `docs/spec_coverage.md` (generated at completion), and a handoff note
at `docs/changes/2026-08-18-weekly-tactic-scheduling-<step>.md` per the
multi-agent workflow.

---

## 4. Build sequence

Eleven steps, following spec §8 exactly. Each step ends with the full suite
green (exit code, not a grepped pass count — P24) before the next begins.

### Step 1 — WT-M1.D: the tactic-link column
*Depends on:* nothing. Everything else reads it.

Add `weekly_tactic_id TEXT NULL REFERENCES action_items(id) ON DELETE SET NULL`.
Migration moves every `parent_id` whose parent has `item_type='week'` onto it and
NULLs that `parent_id` — 49 rows moved, 94 nesting rows untouched, counts
reported (never a silent pass — P2). `weekly_tactic_id` pointing at a non-week
row is rejected in the write path (WT-INV4); SQLite cannot express that as a
`CHECK` on an existing table.

Doing this first is what makes WT-D11 non-negotiable: while one column serves
both relationships, every attach silently destroys a subtask hierarchy (WT-F9).

*Tests:* `tests/test_weekly_tactic_link_migration.py` — WT-M1.D.1..4, plus the
mandatory dirty-state run-#2 case.

### Step 2 — WT-M7.A: dedupe
*Depends on:* Step 1 (children are repointed onto `weekly_tactic_id`).

Merge duplicate `(APE, week start)` weekly tactics. Order matters:
`reschedule_history`, `item_links`, `work_logs` and `project_board_items` are all
`ON DELETE CASCADE`, so every one is repointed to the survivor **before** the
loser is deleted (WT-M7.A.3). Survivor's title is re-canonicalised through the
WT-M2 helper — the real duplicate's older row is titled `W8` for an ISO-W9 week,
so "keep the oldest" alone would preserve a wrong title (WT-M7.A.2).

Tie-break (WT-M7.A.4), stated so it is testable: **most children wins; ties break
on oldest `created_at`.** On the live duplicate that selects the `W8` row (5
children), whose title is then corrected to `W9`, and the loser's single history
row is repointed onto it.

*Tests:* `tests/test_weekly_tactic_dedupe.py` — WT-M7.A.1..6.

### Step 3 — WT-M1.A/B/C/E: remaining schema
*Depends on:* Step 2 for WT-M1.C.

`weekly_tactic_start_date` (all rows NULL — WT-D10, no backfill);
`project_boards.start_date/end_date` (unvalidated — WT-D9);
`created_by_rollover` on `annual_visions` and `annual_plans`; and the partial
unique index `UNIQUE(annual_plan_element_id, start_date) WHERE item_type='week'`.

The index is created **only after** the dedupe reports success; on a DB still
holding duplicates the migration raises rather than skipping the index
(WT-M1.C.2) — a skipped index is exactly the silent-drop failure P2 describes.
`create_week_action_items_for_ape` today guards duplicates with a
month-prefixed `LIKE` that cannot see an adjacent-month collision; with the index
live that becomes an unhandled `IntegrityError` in a screen with no handler, so
that path catches and reports it (WT-M1.C.3).

*Tests:* `tests/test_weekly_tactic_schema.py` — WT-M1.A.1..2, B.1..2, C.1..5,
E.1, plus dirty-state.

### Step 4 — WT-M2: week identity and numbering
*Depends on:* Step 1–3.

`week_calendar.py` becomes the only place that answers "which week contains this
date" and "what is this week called". Returns **(year, week)**, never a bare
number — 2026-12-28 and 2027-01-01 are both ISO 2026-W53, and a bare `53` cannot
say which year (WT-F2b).

Three rules, `iso` (default, preserves today's behaviour), `jan1`, `first_full`.
The WT-M2.A.1 table is asserted verbatim; note the `jan1` and `first_full`
expectations assume `first_day_of_week = 0`, which the test sets explicitly
rather than inheriting.

The WT-M2.B.1 scan is written with the Q3 allowlist.

*Tests:* `tests/test_week_numbering.py` — WT-M2.A.1..3, B.1..3.

### Step 5 — WT-M4.D: the atomicity seam
*Depends on:* Step 1–3. **Before any cascade code exists** — the kickoff note is
right that this looks like extra work and is not. Every creator commits
internally today (WT-F11), so a failure at row 6 of 8 leaves 5 rows permanently
committed, which WT-M4.C.5's idempotence then adopts as a finished lineage.

`DatabaseManager.transaction()` context manager; `commit=False` threaded through
every creator on the cascade path, including the nested ones
(`_get_or_create_annual_initiative_for_ape` → `_get_or_create_annual_plan_for_ape`
→ `create_tl_vision` / `create_annual_vision` / `create_annual_plan`).

A source scan would not prove completeness here — one missed site defeats the
whole thing. So WT-M4.D.1 is tested behaviourally: **monkeypatch
`conn.commit` to raise for the duration of the transaction and run the cascade.**
Anything that commits fails loudly. (Patched state restored via the
`unittest.mock.patch` context manager, per the global testing rules.)

*Tests:* `tests/test_weekly_tactic_cascade.py` — WT-M4.D.1..4. WT-M4.D.3 drives
the **real** mid-chain raise sites (`resolve_segment_id_by_name` at
`vps_manager.py:359` / `:421`), not a synthetic exception.

### Step 6 — WT-M3: attach, change, detach
*Depends on:* Steps 4, 5.

`_tactic_of(item)` is the single named predicate every path uses to decide
whether an item is week-filed (WT-M3.D.1) — WT-INV6 is only enforceable if
there is exactly one such decision.

`weekly_tactic_start_date` stamped once on first attach, never moved
automatically, manually overridable (WT-INV3). The date rule is **ordered**:
shift start and due by whole weeks preserving weekday; then, if due still falls
outside, clamp to week end — the clamp overrides weekday preservation (WT-D5).

*Tests:* `tests/test_weekly_tactic_linking.py` — WT-M3.A.1..4, B.1..4, C.1..3,
D.1..2. WT-M3.B.2 and B.4 use synthetic fixtures (see §2).

### Step 7 — WT-M4.A/B: cascade within a year
*Depends on:* Step 6.

Bottom-up per WT-D6: new Quarter only on a quarter cross with none existing, new
Month only on a month cross with none existing, new Week whenever absent. The
lineage is inherited from the item's **current tactic** — never from whatever
tactic happens to cover today (WT-M4.A.2). `action_items.annual_plan_element_id`
is reconciled to the tactic's APE after every re-file so the two never disagree.

WT-M4.B.5 matters more than it reads: the existing helpers pick
`quarter_rows[0]`, `month_rows[0]`, `ORDER BY created_at LIMIT 1`. Duplicates at
quarter and month level are **not** deduped by WT-D8, so that selection must be
deterministic and documented, or the same move produces different lineages on
different runs.

*Tests:* `tests/test_weekly_tactic_cascade.py` — WT-M4.A.1..3, B.1..5.

### Step 8 — WT-M4.C: year rollover
*Depends on:* Steps 5, 7.

Reuses `create_annual_records_from_vision_element` (Q6), whose
`UNIQUE(year, vision_element_id)` constraints give WT-M4.C.5 idempotence and
whose FK handling gives WT-M4.C.3a. Editorial fields blank and flagged per
WT-D7a/WT-D13, parameterised per Q5. Stubs are discovered by
`created_by_rollover`, **never** by empty fields — WT-M4.C.3b's adversarial case
is a hand-authored vision with a blank statement, which must **not** be reported.

The report is a **new** function; `assign_ape_to_quarter` / `assign_ape_to_month`
keep their bare-boolean contract and the `is True` assertions at
`tests/test_vps_hub_crud.py:311` and `:342` stay green (WT-F13, P22).

*Tests:* `tests/test_weekly_tactic_cascade.py` — WT-M4.C.1, C.2, C.3, C.3a,
C.3b, C.3c, C.4..7.

### Step 9 — WT-M5: completion re-filing
*Depends on:* Step 8.

Completion re-files to the completion week via the WT-M4 cascade, with the
original week preserved in the stamp. `completed_at` is a full ISO datetime
(`db_manager.py:191`), so the range check compares `completed_at[:10]` — and
WT-M5.A.3's fixture completes on the **last day** of the week, where a naive
string compare fails. Re-opening does not un-file.

WT-M5.C.1 is the one that bites: `complete_and_create` routes through
`duplicate_action_item`, whose constructor drops `weekly_tactic_id`,
`annual_plan_element_id` and `segment_description_id` on the floor. The follow-up
inherits them explicitly.

*Tests:* `tests/test_weekly_tactic_completion.py` — WT-M5.A.1..6, B.1, C.1.

### Step 10 — WT-M7.B: invariant repair
*Depends on:* Step 6.

Repairs the 24 start-date and 29 due-date violations, writing
`reschedule_history` rows with `reason='inv_repair'` and reporting how many items
moved and by how much — a silent rewrite of 29 items is exactly the invisible
drop P2 warns about. Shipped dry-run-by-default per Q4.

*Tests:* `tests/test_weekly_tactic_dedupe.py` — WT-M7.B.1..3.

### Step 11 — WT-M6: entry points
*Depends on:* everything above.

The hook lives at **one layer** — `update_action_item`, `reschedule_item`,
`bulk_update_action_items`. Screens are not individually hooked. But every screen
is tested, because P25 is precisely the failure where the library is wired and
the surface the user touches never passes the argument: a `--narrative` flag that
the GUI never sent. Each of the 8 date surfaces and 9 completion surfaces gets
its own test that **intercepts the db_manager boundary and asserts the call
arrives**, not that the widget renders.

`bulk_update_action_items` forces `due = start + 1 day` (`db_manager.py:233`),
which guarantees a WT-INV2 violation whenever start lands on a week's last day —
clamped (WT-M6.B.2).

WT-M6.A.4 note: the `SetWeeklyTacticDialog` **already** offers month and
all-weeks filtering (`_set_month_range`, `_set_all_weeks_range`). WT-F14's
±3-week window is the Org tab combo's `_get_week_window_range`
(`item_editor.py:500-511`), which WT-M6.A replaces wholesale. The criterion is
likely already satisfied by the dialog; the test asserts reachability either way
and the outcome is recorded rather than assumed.

Date entry uses `widgets/date_picker.py` — **not** `tkcalendar` (§0).

*Tests:* `tests/test_item_editor_weekly_tactic_ui.py` (WT-M6.A.1..4),
`tests/test_weekly_tactic_surfaces.py` (WT-M6.B.1 ×8, B.2, B.3, B.4 ×9, B.5),
`tests/test_project_board_dates_ui.py` (WT-M6.C.1),
`tests/test_settings_week_rule_ui.py` (WT-M6.D.1).

---

## 5. Acceptance criteria → test map

Every criterion, its verifying test, and the build step that delivers it.
Test paths are the spec's verbatim; `::` rows continue the file above them.

### WT-M1 — Data model and migrations

| ID | Test | Step |
|---|---|---|
| WT-M1.A.1 | `tests/test_weekly_tactic_schema.py::test_wt_m1a1_weekly_tactic_start_date_column_added_null` | 3 |
| WT-M1.A.2 | `::test_wt_m1a2_weekly_tactic_start_date_round_trips` | 3 |
| WT-M1.B.1 | `::test_wt_m1b1_project_board_dates_added_null` | 3 |
| WT-M1.B.2 | `::test_wt_m1b2_project_dates_round_trip_unvalidated` | 3 |
| WT-M1.C.1 | `::test_wt_m1c1_duplicate_weekly_tactic_rejected` | 3 |
| WT-M1.C.2 | `::test_wt_m1c2_index_creation_fails_loudly_on_dirty_db` | 3 |
| WT-M1.C.3 | `::test_wt_m1c3_ape_weekly_screen_reports_duplicate_instead_of_crashing` | 3 |
| WT-M1.C.4 | `::test_wt_m1c4_week_item_requires_ape` | 3 |
| WT-M1.C.5 | `::test_wt_m1c5_first_day_change_collision_reported` | 3 |
| WT-M1.D.1 | `tests/test_weekly_tactic_link_migration.py::test_wt_m1d1_tactic_links_migrated_nesting_preserved` | 1 |
| WT-M1.D.2 | `::test_wt_m1d2_parent_and_tactic_coexist` | 1 |
| WT-M1.D.3 | `::test_wt_m1d3_tactic_must_be_week_item` | 1 |
| WT-M1.D.4 | `::test_wt_m1d4_link_migration_idempotent` | 1 |
| WT-M1.E.1 | `tests/test_weekly_tactic_schema.py::test_wt_m1e1_rollover_flag_added_default_zero` | 3 |

*Added beyond the spec (mandatory dirty-state cover, P8):*
`tests/test_weekly_tactic_link_migration.py::test_wt_m1d_migration_on_populated_db_run_two` and
`tests/test_weekly_tactic_schema.py::test_wt_m1_migrations_on_populated_db_run_two`.

### WT-M2 — Week identity and numbering

| ID | Test | Step |
|---|---|---|
| WT-M2.A.1 | `tests/test_week_numbering.py::test_wt_m2a1_rule_table_matches_spec` | 4 |
| WT-M2.A.2 | `::test_wt_m2a2_unknown_rule_falls_back_to_iso` | 4 |
| WT-M2.A.3 | `::test_wt_m2a3_helper_returns_year_and_week` | 4 |
| WT-M2.B.1 | `::test_wt_m2b1_no_direct_week_math_callers` | 4 |
| WT-M2.B.2 | `::test_wt_m2b2_title_week_number_follows_setting` | 4 |
| WT-M2.B.3 | `::test_wt_m2b3_first_day_change_on_populated_db` | 4 |

### WT-M3 — Attaching, changing and detaching

| ID | Test | Step |
|---|---|---|
| WT-M3.A.1 | `tests/test_weekly_tactic_linking.py::test_wt_m3a1_first_attach_stamps_original_week` | 6 |
| WT-M3.A.2 | `::test_wt_m3a2_retarget_preserves_original_week` | 6 |
| WT-M3.A.3 | `::test_wt_m3a3_manual_override_persists` | 6 |
| WT-M3.A.4 | `::test_wt_m3a4_stamp_survives_tactic_deletion_and_is_surfaced` | 6 |
| WT-M3.B.1 | `::test_wt_m3b1_whole_week_shift_preserves_weekday` | 6 |
| WT-M3.B.2 | `::test_wt_m3b2_multi_week_item_due_date_clamped` | 6 |
| WT-M3.B.3 | `::test_wt_m3b3_invariants_hold_after_retarget` | 6 |
| WT-M3.B.4 | `::test_wt_m3b4_null_dates_handled` | 6 |
| WT-M3.C.1 | `::test_wt_m3c1_attach_preserves_daily_parent` | 6 |
| WT-M3.C.2 | `::test_wt_m3c2_set_parent_preserves_tactic` | 6 |
| WT-M3.C.3 | `::test_wt_m3c3_detach_leaves_dates_alone` | 6 |
| WT-M3.D.1 | `::test_wt_m3d1_single_tactic_predicate` | 6 |
| WT-M3.D.2 | `::test_wt_m3d2_unlinked_item_untouched_on_every_path` | 6 |

### WT-M4 — Re-filing and the scaffolding cascade

| ID | Test | Step |
|---|---|---|
| WT-M4.A.1 | `tests/test_weekly_tactic_cascade.py::test_wt_m4a1_relink_to_existing_week_creates_nothing` | 7 |
| WT-M4.A.2 | `::test_wt_m4a2_lineage_inherited_from_current_tactic` | 7 |
| WT-M4.A.3 | `::test_wt_m4a3_item_ape_reconciled_after_refile` | 7 |
| WT-M4.B.1 | `::test_wt_m4b1_creates_week_only_within_month` | 7 |
| WT-M4.B.2 | `::test_wt_m4b2_creates_month_assignment_on_month_cross` | 7 |
| WT-M4.B.3 | `::test_wt_m4b3_creates_quarter_assignment_on_quarter_cross` | 7 |
| WT-M4.B.4 | `::test_wt_m4b4_cascade_is_idempotent` | 7 |
| WT-M4.B.5 | `::test_wt_m4b5_ancestor_selection_deterministic` | 7 |
| WT-M4.C.1 | `::test_wt_m4c1_year_rollover_builds_exactly_one_row_per_table` | 8 |
| WT-M4.C.2 | `::test_wt_m4c2_rollover_preserves_vision_element_lineage` | 8 |
| WT-M4.C.3 | `::test_wt_m4c3_editorial_fields_blank_and_flagged` | 8 |
| WT-M4.C.3a | `::test_wt_m4c3a_year_scoped_fks_repointed_not_copied` | 8 |
| WT-M4.C.3b | `::test_wt_m4c3b_stub_discovery_uses_flag_not_emptiness` | 8 |
| WT-M4.C.3c | `::test_wt_m4c3c_existing_ape_assignment_callers_unaffected` | 8 |
| WT-M4.C.4 | `::test_wt_m4c4_rollover_returns_report_and_bool_callers_unbroken` | 8 |
| WT-M4.C.5 | `::test_wt_m4c5_second_rollover_is_idempotent` | 8 |
| WT-M4.C.6 | `::test_wt_m4c6_partial_lineage_completed_not_adopted` | 8 |
| WT-M4.C.7 | `::test_wt_m4c7_backward_and_multi_year_moves` | 8 |
| WT-M4.D.1 | `::test_wt_m4d1_cascade_runs_in_one_transaction` | 5 |
| WT-M4.D.2 | `::test_wt_m4d2_failure_at_last_row_rolls_back_everything` | 5 |
| WT-M4.D.3 | `::test_wt_m4d3_missing_segment_rolls_back` | 5 |
| WT-M4.D.4 | `::test_wt_m4d4_no_cascade_for_unlinked_item` | 5 |

### WT-M5 — Completion re-filing

| ID | Test | Step |
|---|---|---|
| WT-M5.A.1 | `tests/test_weekly_tactic_completion.py::test_wt_m5a1_completion_refiles_to_current_week` | 9 |
| WT-M5.A.2 | `::test_wt_m5a2_original_week_survives_completion` | 9 |
| WT-M5.A.3 | `::test_wt_m5a3_completion_on_last_day_of_week_is_in_range` | 9 |
| WT-M5.A.4 | `::test_wt_m5a4_completion_leaves_unlinked_item_unlinked` | 9 |
| WT-M5.A.5 | `::test_wt_m5a5_completion_across_year_boundary` | 9 |
| WT-M5.A.6 | `::test_wt_m5a6_completion_refile_records_history` | 9 |
| WT-M5.B.1 | `::test_wt_m5b1_reopen_keeps_completion_week_tactic` | 9 |
| WT-M5.C.1 | `::test_wt_m5c1_followup_inherits_lineage_and_stays_in_range` | 9 |

### WT-M6 — Entry points

| ID | Test | Step |
|---|---|---|
| WT-M6.A.1 | `tests/test_item_editor_weekly_tactic_ui.py::test_wt_m6a1_org_tab_never_queries_legacy_table` | 11 |
| WT-M6.A.2 | `::test_wt_m6a2_org_tab_shows_current_tactic_or_none` | 11 |
| WT-M6.A.3 | `::test_wt_m6a3_manual_stamp_edit_reaches_db_layer` | 11 |
| WT-M6.A.4 | `::test_wt_m6a4_picker_can_reach_any_week` | 11 |
| WT-M6.B.1 | `tests/test_weekly_tactic_surfaces.py::test_wt_m6b1_<surface>_refiles` — **8 tests**: `today`, `upcoming`, `all_items`, `drag_schedule`, `reschedule_dialog`, `project_boards`, `item_editor`, `timer_window` | 11 |
| WT-M6.B.2 | `::test_wt_m6b2_bulk_edit_respects_week_bounds` | 11 |
| WT-M6.B.3 | `::test_wt_m6b3_calendar_import_does_not_cascade` | 11 |
| WT-M6.B.4 | `::test_wt_m6b4_<surface>_completion_refiles` — **9 tests**: the 8 above plus `completed`, `hierarchical`, `db_manager.complete_and_create`, less `drag_schedule`/`reschedule_dialog` which have no completion path (final list fixed against the WT-F12 grep at build time and reported if it differs) | 11 |
| WT-M6.B.5 | `::test_wt_m6b5_created_records_summarised_to_user` | 11 |
| WT-M6.C.1 | `tests/test_project_board_dates_ui.py::test_wt_m6c1_project_dates_reach_db_layer` | 11 |
| WT-M6.D.1 | `tests/test_settings_week_rule_ui.py::test_wt_m6d1_week_rule_setting_persists` | 11 |

### WT-M7 — Data cleanup

| ID | Test | Step |
|---|---|---|
| WT-M7.A.1 | `tests/test_weekly_tactic_dedupe.py::test_wt_m7a1_duplicates_merged_children_repointed` | 2 |
| WT-M7.A.2 | `::test_wt_m7a2_survivor_title_recanonicalised` | 2 |
| WT-M7.A.3 | `::test_wt_m7a3_no_cascade_data_lost` | 2 |
| WT-M7.A.4 | `::test_wt_m7a4_tiebreak_when_both_have_children` | 2 |
| WT-M7.A.5 | `::test_wt_m7a5_dedupe_reports_counts` | 2 |
| WT-M7.A.6 | `::test_wt_m7a6_dedupe_idempotent_and_dirty_state` | 2 |
| WT-M7.B.1 | `::test_wt_m7b1_existing_violations_repaired` | 10 |
| WT-M7.B.2 | `::test_wt_m7b2_repair_reports_what_it_moved` | 10 |
| WT-M7.B.3 | `::test_wt_m7b3_repair_records_history` | 10 |

**Coverage: 83 of 83 leaf criteria have a named test. None is unmapped.**

---

## 6. Criteria that cannot be fully proved by code

Three items where the automated test is necessary but not sufficient. Each has a
proposed human-review step, per the global planning rules and §10 of the spec.

| Criteria | What the test cannot see | Proposed human review |
|---|---|---|
| WT-M4.C.3 / WT-M4.C.3b / WT-M6.B.5 | The assertions prove the fields are blank and the flag is 1. They cannot tell whether an empty `annual_visions` row **renders** badly, or whether a stub **reads** to the user as a real plan. | After Step 8: run the app under the venv, trigger a rollover, and look at the VSP Planning and Vision Planning Hub screens. Check `app.log` for exceptions. Record the result in the step's handoff note with a screenshot reference. |
| WT-M7.B | Whether a given violation is **drift or deliberate user data**. The repair cannot know, and 29 items is a large silent rewrite. | Before any `--apply`: run `tools/repair_weekly_tactic_invariants.py` in dry-run, review the before/after list, and get explicit sign-off. This is why Q4 recommends the tool split. |
| WT-M6.A.2 / WT-M6.A.4 | The Org tab renders and the picker reaches any week — assertable at the boundary, but not that the rebuilt tab is *usable*. | After Step 11: open Edit Action → Org on a linked item, an unlinked item, and an item whose tactic was deleted (WT-M3.A.4's stale stamp), in the running app. |

---

## 7. Adjacent issues found while planning, not fixed

Per the global rule: flagged, not silently swept in and not silently left.
The six from spec §9 stand as written. Three more surfaced today:

- **`create_annual_records_from_vision_element` swallows the board-creation
  failure** (`vps_manager.py:274-277`, bare `except Exception: pass`) — a P2
  silent drop. Q2 touches this code; the swallow itself stays for now.
- **`item_editor.load_week_actions` has a fallback that widens silently.** When
  the ranged query returns nothing it falls back to the entire catalogue with
  only a log line. WT-M6.A deletes this path anyway; noting it so the deletion
  is understood as a fix, not a regression.
- **`_get_week_window_range` and `SetWeeklyTacticDialog._set_rolling_window_range`
  duplicate the same ±3-week arithmetic** in two places. Step 11 removes the
  first; the second is converted by Step 4 but not otherwise restructured.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| The `commit=False` seam misses one nested creator, so WT-M4.D.2 passes on the injected failure but a real one leaks rows. | WT-M4.D.1 is tested by making `conn.commit` **raise** inside the transaction, which catches any missed site regardless of call depth — not by a source scan. |
| The hook at `update_action_item` fires on saves that were never meant to re-file (e.g. a title edit on a linked item whose dates are stale). | WT-M7.B repairs pre-existing violations first (Step 10 precedes Step 11); after that a no-op re-file is genuinely a no-op. WT-M3.D.2 asserts unlinked items are untouched on all three paths. |
| WT-M2.B.1's scan is written narrowly and leaves WT-F2c's inconsistency alive. | Q3 fixes the boundary explicitly, with the allowlist named in the test. |
| A GUI test needs a display and skips silently in a headless run, so WT-M6 looks covered when it is not. | `test_rm3b_ui_tests_are_not_skipped_headless` already guards this; the new surface tests are written to run under the workflow's virtual display, not to `importorskip` their way out. |
| Step 11's 17 surface tests are the largest single block and the most likely to be cut short. | They are the P25 protection and the reason the feature reaches users at all. No step is marked done with any surface test missing; a surface with no completion path is **recorded as such**, not quietly dropped from the count. |

---

## 9. Definition of done

Per the global completion standard, the final report lists every one of the 83
criteria as `done` (with file path and test name), `partial` (with what is
missing), or `not done` (with reason). Plus:

- `./venv/bin/python -m pytest -q` → **exit 0**, ≥ 679 passed. Success is read
  from the exit code, never from a grepped pass count (P24).
- Every new test file passes in isolation.
- `docs/spec_coverage.md` generated.
- `learning-qa` run against the full diff before anything is pushed; findings
  fixed in the same session.
- Handoff note per step at `docs/changes/2026-08-18-weekly-tactic-scheduling-<step>.md`.
- `CHANGELOG.md`, `docs/USER_GUIDE.md`, `NOTES.md` updated in the same change as
  the behaviour they describe.
- The three §6 human reviews performed and recorded.
