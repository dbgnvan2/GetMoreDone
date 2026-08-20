# Spec — Renaming must never break a link

**Status:** Draft v1, awaiting approval
**Date:** 2026-08-19
**Spec ID root:** `RN`
**Touches:** the taxonomy (`vision_segments`, `vision_subsegments`,
`vision_categories`, `segment_descriptions`), the VSP chain
(`annual_vision_elements`, `annual_plan_elements`, `annual_initiatives`), and the
Project ↔ Action Item relation.

---

## 1. Goal

A user can rename anything — a segment, a sub-segment, a category, a vision
element's key field, a project, a Weekly Tactic — and **every link survives
unchanged**. A name is a label. It is never the thing that holds two rows
together.

## 2. Why this is a bug and not a wish

Renaming a segment today makes an ordinary date change on a filed Action Item
**raise**, and the item silently does not move:

```
rename_vision_segment("Health" -> "Health Renamed")
  vision_segments        ['Contribution', 'Health Renamed', ...]
  segment_descriptions   ['Contribution', 'Health', ...]        <- not renamed
  APE.segment_name        Health Renamed

move the item's start date to 2026-06-10:
  RAISES ValueError: Segment 'Health Renamed' not found.
  item unchanged: 2026-05-20
```

That `ValueError` is raised from `vps_manager.py:359` / `:421` — the same
mid-chain raise site `WT-M4.D.3` exercises for rollback. So the whole re-filing
cascade is dead for that segment until the name is put back.

## 3. Findings

Measured, not inferred. A full chain was built (segment → sub-segment → category
→ vision element → AVE/APE → annual initiative → quarter → month → Weekly Tactic
→ Action Item, plus a Project linked to the APE and the item linked to the
Project), every link snapshotted by id, then each level renamed in turn.

| ID | Finding | Evidence |
|---|---|---|
| **RN-F1** | **Breakage matrix.** Rename Weekly Tactic title → all links OK. Rename Project title → all OK. Rename **vision element key field** → `APE → annual initiative` breaks. Rename **sub-segment** → same. Rename **segment** → `APE → segment` **and** `APE → annual initiative` both break. | experiment, §2 |
| **RN-F2** | **Two tables for one concept, joined by name.** `vision_segments` (id, name, vision_text) and `segment_descriptions` (id, name, colour, order) have **no foreign key between them**; three queries join them on `LOWER(sd.name) = LOWER(vs.name)` (`vps_manager_taxonomy.py:738`, `:784`, `:813`). `rename_vision_segment` updates `vision_segments` only. | `PRAGMA table_info`, source |
| **RN-F3** | **The APE has no id-link to either thing it depends on.** `annual_plan_elements` carries `segment_name`, `subsegment_name`, `category_name`, `key_field` and no `segment_description_id`, no `annual_initiative_id`. `annual_vision_elements` is the same. | `PRAGMA table_info` |
| **RN-F4** | **The APE ↔ Annual Initiative link is a title string match** — `LOWER(ai.title) = LOWER(ape.key_field)` (`_find_annual_initiative_for_ape`). Renaming updates the APE's `key_field` and its mirror rows but not the initiative's title, so the next assignment builds a **second** Annual Initiative and a **second** Quarter Initiative for the same APE and quarter. | reproduced: `annual_initiatives: 2, quarter_initiatives: 2` |
| **RN-F5** | **Project → Action Item and Weekly Tactic → Action Item are already safe.** Both are id-based (`project_board_items`, `action_items.weekly_tactic_id`). Renaming a Project or a Weekly Tactic breaks nothing. This bounds the work: the Project side needs a regression test, not a fix. | experiment, §2 |
| **RN-F6** | **Nothing dedupes or warns at the quarter/month/annual levels.** WT-D8 gave weekly tactics a uniqueness index; §9 of the weekly-tactic spec deliberately left the levels above unprotected. So RN-F4's duplicates accumulate silently. | `docs/spec_2026-08-18_weekly_tactic_scheduling.md` §9 |
| **RN-F7** | **Scale.** 6 callers of `resolve_segment_id_by_name`; 41 lines that read `segment_name` / `subsegment_name` / `category_name` / `key_field` in a `WHERE` or `JOIN`. Not all of those are link resolution — several are display or filtering — so each needs classifying, not blanket rewriting. | grep |

## 4. Invariants

| ID | Invariant |
|---|---|
| **RN-INV1** | Renaming any entity never changes which rows are linked to which. |
| **RN-INV2** | Renaming never causes a subsequent create path to make a duplicate. |
| **RN-INV3** | A denormalised name column is **display only**. No code path resolves a link through one. |
| **RN-INV4** | After a rename, every stored copy of that name shows the new value. |
| **RN-INV5** | A row whose id-link cannot be resolved is **reported**, never silently skipped or re-created. |

## 5. Decisions

| # | Decision |
|---|---|
| **RN-D1** | **Add real id columns; keep the names for display.** Not "propagate the rename everywhere" — that is the pattern that already failed, since `rename_vision_segment` updates one of the two tables it needs to. Every new denormalised column would reopen the hole. |
| **RN-D2** | **Migrate by matching on the current name once**, write the id, and never match by name again. Rows that cannot be matched are reported, not guessed (RN-INV5). |
| **RN-D3** | **The APE ↔ Annual Initiative link goes on the initiative** (`annual_initiatives.annual_plan_element_id`), because an initiative is created lazily *for* an APE. Nullable, so pre-existing rows migrate rather than block. |
| **RN-D4** | **`vision_segments` and `segment_descriptions` stay two tables**, linked by a new `vision_segments.segment_description_id`. Merging them is a bigger change than this spec and is not required to hold RN-INV1. |
| **RN-D5** | **Name columns are kept and refreshed on rename** (RN-INV4). They are what the UI reads and what the Weekly Tactic title derives from; removing them would be a much wider change for no gain once nothing *links* through them. |
| **RN-D7** | **An Annual Initiative's title stays derived** (2026-08-19, user). A rename refreshes it, the same way a Weekly Tactic's title is re-derived from its APE and week. Nothing in the app treats an initiative title as hand-authored prose, and leaving it stale would put two different names on one thing. |
| **RN-D6** | **Existing broken data is repaired, and reported.** A user who has already renamed has orphaned rows now. The repair matches what it can by id-through-lineage and reports what it cannot — same shape as WT-M7.B. |

## 6. Non-goals

- Merging `vision_segments` into `segment_descriptions` (RN-D4).
- Adding uniqueness constraints at quarter / month / annual level. RN-F6 is real,
  but preventing *new* duplicates is this spec's job; cleaning up existing ones
  is the weekly-tactic spec's §9 territory.
- Renaming behaviour in the UI (dialogs, confirmations). Unchanged.
- `action_items.who` / `group` / `category`, which are free text with no link
  behind them, and `update_organizational_factor`, which already rewrites them.

## 7. Requirements

### RN-M1 — Id columns and their migration

- **RN-M1.A** — `annual_plan_elements` and `annual_vision_elements` gain
  `segment_description_id TEXT NULL REFERENCES segment_descriptions(id)`.
  - **RN-M1.A.1** — Idempotent migration; backfilled by the current name match.
    → `tests/test_rename_safe_links.py::test_rn_m1a1_ape_segment_id_added_and_backfilled`
  - **RN-M1.A.2** — A row whose `segment_name` matches nothing is left NULL and
    **counted in the migration report** (RN-INV5).
    → `::test_rn_m1a2_unmatched_segment_is_reported_not_guessed`
- **RN-M1.B** — `annual_initiatives` gains
  `annual_plan_element_id TEXT NULL REFERENCES annual_plan_elements(id)` (RN-D3).
  - **RN-M1.B.1** — Backfilled from the existing title match, once.
    → `::test_rn_m1b1_initiative_ape_link_backfilled_from_title`
  - **RN-M1.B.2** — Two initiatives matching one APE (the RN-F4 duplicate a user
    may already have) are both reported; the oldest is linked and the other left
    NULL rather than silently dropped.
    → `::test_rn_m1b2_ambiguous_backfill_is_reported`
- **RN-M1.C** — `vision_segments` gains
  `segment_description_id TEXT NULL REFERENCES segment_descriptions(id)` (RN-D4).
  - **RN-M1.C.1** — Backfilled by name; unmatched reported.
    → `::test_rn_m1c1_vision_segment_link_backfilled`
  - **RN-M1.C.2** — A row created by the legacy Vision Segment migration keeps
    the id that migration was **given**, rather than being backfilled from the
    name a moment later. The legacy row carries `segment_id`, so the name
    round trip is a loss: with two descriptions differing only by case it
    resolves to neither. Where two legacy rows collapse into one row and
    disagree about which description they mean, nothing is stamped and the
    ambiguity is reported (RN-INV5).
    → `tests/test_vps_legacy_migration.py::test_rn_m1c_legacy_migration_keeps_the_id_the_legacy_row_carried`
    → `tests/test_vps_legacy_migration.py::test_rn_m1c_two_legacy_rows_that_collapse_are_not_given_one_of_the_two_ids`
    → `tests/test_vps_legacy_migration.py::test_rn_m1c_legacy_migration_does_not_stamp_a_dangling_id`
- **RN-M1.D** — Dirty-state (P8): re-running the migration on a populated
  database changes nothing and reports zeros.
  → `::test_rn_m1d_migration_on_populated_db_run_two`

### RN-M2 — Resolve by id, never by name

- **RN-M2.A** — `_find_annual_initiative_for_ape` resolves through
  `annual_initiatives.annual_plan_element_id`. The title match remains **only**
  as a one-time healing path for a row whose id is still NULL, and when it fires
  it writes the id so it never fires again for that row.
  → `::test_rn_m2a_initiative_found_by_id_after_rename`
  → `::test_rn_m2a1_legacy_row_heals_on_first_lookup`
- **RN-M2.B** — Every caller of `resolve_segment_id_by_name` on a link path (6
  sites) uses the APE's `segment_description_id`. The by-name function stays for
  genuine name lookups (user input, import) and is documented as such.
  → `::test_rn_m2b_cascade_survives_a_segment_rename`
- **RN-M2.C** — The three `LOWER(sd.name) = LOWER(vs.name)` joins use
  `vision_segments.segment_description_id`.
  → `::test_rn_m2c_segment_join_survives_a_rename`
- **RN-M2.D** — **The breakage matrix, asserted.** The RN-F1 experiment becomes a
  test: build the full chain, snapshot every link by id, rename at each of six
  levels, assert every link still resolves.
  → `::test_rn_m2d_no_rename_breaks_any_link` — **written first** (P10; it is the
  whole spec in one test).

### RN-M3 — Names stay correct for display

- **RN-M3.A** — A rename updates every stored copy of that name
  (`annual_vision_elements`, `annual_plan_elements`, and the Annual Initiative's
  title where it was derived from the key field), so RN-INV4 holds.
  → `::test_rn_m3a_rename_refreshes_every_display_copy`
- **RN-M3.B** — A Weekly Tactic's derived title follows a key-field rename the
  next time it is canonicalised, and does **not** change which APE it belongs to.
  → `::test_rn_m3b_tactic_title_follows_rename_without_relinking`

### RN-M4 — The hole cannot reopen

- **RN-M4.A** — A source scan asserts no link resolution goes through a name
  column: no `LOWER(<x>.name) = LOWER(<y>.name)` join between two entity tables,
  and no `WHERE ... = ape.<x>_name` used to find a row that a foreign key could
  find. Display and user-input lookups are allowlisted **by name, with the
  reason written next to them**.
  → `::test_rn_m4a_no_link_resolves_through_a_name`
  → `::test_rn_m4a1_the_scan_can_actually_fire` — the scan must flag the four
  patterns this spec removes, or it is green on the defect and the fix alike
  (P24).

### RN-M5 — Repair what is already broken

- **RN-M5.A** — A user who has already renamed has orphans now. The migration
  reports: APEs with no resolvable segment, initiatives with no APE, and
  duplicate initiatives per (APE, year) — counts and ids, in
  `weekly_tactic_debug.log` and in the migration report.
  → `::test_rn_m5a_existing_breakage_is_reported`
- **RN-M5.B** — Repair never invents a link. Anything ambiguous is reported and
  left alone (RN-INV5, RN-D2).
  → `::test_rn_m5b_ambiguous_data_is_left_alone`

## 8. Implementation order

| Step | Requirement | Depends on |
|---|---|---|
| 1 | RN-M2.D — the breakage matrix test, red | — |
| 2 | RN-M1 schema + backfill migration | — |
| 3 | RN-M2.A/B/C — resolution by id | 2 |
| 4 | RN-M3 — display-copy refresh | 3 |
| 5 | RN-M5 — reporting and repair | 2 |
| 6 | RN-M4 — the scan guard | 3 |

Step 1 first on purpose: it fails today, it is the acceptance criterion for the
whole spec, and it goes green only when the rest is done.

## 9. Adjacent issues found, not fixed

- **Duplicate Annual and Quarter Initiatives already in a user's data** from
  RN-F4. This spec stops new ones (RN-M2.A) and reports existing ones
  (RN-M5.A) but does not merge them — that is the uniqueness work §9 of the
  weekly-tactic spec left open, and it needs its own tie-break decision.
- **`vision_segments` and `segment_descriptions` remain two tables** describing
  one concept (RN-D4).
- **`annual_plan_element_id` on `action_items` still has no foreign key**
  (weekly-tactic spec §9), so a deleted APE leaves dangling ids. Unchanged here.

## 10. Criteria needing human review

- **RN-M3.A — settled (2026-08-19, user): the title stays derived.** A rename
  refreshes the Annual Initiative's title. See RN-D7. The one thing worth a look
  after the first run is the migration report from RN-M5.A: on a database where
  a rename has already happened, it names every APE with no resolvable segment
  and every duplicate initiative. Whether any of those duplicates holds work you
  want to keep is a judgement no assertion can make.
