# Implementation plan — Renaming must never break a link

**Status:** Draft, awaiting approval. **No implementation code written.**
**Date:** 2026-08-19
**Spec:** `docs/spec_2026-08-19_rename_safe_links.md` (v1)
**Spec ID root:** `RN` — every ID below is used verbatim.

**Baseline, captured before planning:**

```
./venv/bin/python -m pytest -q   →  exit 0, 899 passed, 2 skipped
```

**Scope:** 17 leaf acceptance criteria across RN-M1..RN-M5, in one new test file.
No new dependency, no UI change.

---

## 0. Environment and repo guardrails

| Guardrail | What it means here |
|---|---|
| **venv only** | `./venv/bin/python -m pytest -q`. A bare `pytest` resolves elsewhere. |
| **No `tkcalendar` / `babel`** | Removed deliberately (GPLv3). Not touched by this change — it adds no UI. |
| **`.gitignore` ignores `*.json`** | This change adds no JSON resource. |
| **No new root-level files** | Spec and plan live in `docs/`. |
| **Tests pass in isolation** | `./venv/bin/python -m pytest tests/test_rename_safe_links.py` alone must pass. |
| **Never `git add -A`** | Shared working tree, one branch, another session active in it. Stage explicit paths only, and re-check `git log` before committing — the tree moved three times during the spec work. |
| **Dirty-state test mandatory** | The migration runs on every app start (RN-M1.D). |
| **Verify in the running app** | DB tests are not sufficient here. The VSP Planning and Vision Planning Hub screens read the denormalised names this change refreshes. |

---

## 1. Decisions already taken (spec §5)

All seven are settled; nothing blocks the build.

- **RN-D1** id columns, not rename propagation.
- **RN-D2** migrate by matching the current name **once**, then never by name.
- **RN-D3** the APE↔initiative link goes on `annual_initiatives`.
- **RN-D4** `vision_segments` and `segment_descriptions` stay two tables.
- **RN-D5** name columns kept, refreshed on rename, display only.
- **RN-D6** existing broken data repaired *and reported*; nothing invented.
- **RN-D7** (2026-08-19, user) **an Annual Initiative's title stays derived** — a
  rename refreshes it.

---

## 2. Files

### New

| File | Owns | Est. |
|---|---|---|
| `src/getmoredone/link_integrity.py` | RN-M1 schema + backfill, RN-M5 reporting and repair. Its own `run_link_integrity_migrations(conn)` returning a report, mirroring `weekly_tactic_migrations.py`. | ~260 |
| `tests/test_rename_safe_links.py` | All 17 criteria. | ~450 |

### Changed

| File | Change | Criteria |
|---|---|---|
| `database.py` | Call `run_link_integrity_migrations(conn)` in `initialize_schema` **after** `run_weekly_tactic_migrations` (line 423) — the backfill reads `annual_plan_elements`, which the VSP schema must have created. Same once-per-`Database` guard the weekly-tactic report already uses, or the migration runs twice per launch. | RN-M1 |
| `vps_manager.py` | `_find_annual_initiative_for_ape` (`:493`) resolves by id, healing a NULL row once. `resolve_segment_id_by_name` (`:980`) keeps its contract but stops being the link path; its 6 callers move to the APE's `segment_description_id`. `create_annual_records_from_vision_element` and `_get_or_create_annual_initiative_for_ape` write the new ids on create. | RN-M2.A/B |
| `vps_manager_taxonomy.py` | The three `LOWER(sd.name) = LOWER(vs.name)` joins (`:738`, `:784`, `:813`) use `vision_segments.segment_description_id`. `rename_vision_segment` / `_subsegment` / `_category` and `update_vision_element` refresh every stored name copy. | RN-M2.C, RN-M3.A |
| `weekly_tactic.py` | Its one `resolve_segment_id_by_name` call (in `ensure_tactic`) uses the APE's id. | RN-M2.B |
| `db_manager_project_boards.py` | The two lineage joins (`:117-123`, `:394-400`) match the taxonomy by name. Classify each: if it resolves a link, move to ids; if it is display-only, allowlist it **with the reason written next to it** (RN-M4.A). | RN-M2.C, RN-M4.A |

### Docs at the end

`CHANGELOG.md`, `docs/changes/2026-08-19-rename-safe-links.md`,
`docs/spec_coverage_2026-08-19_rename_safe_links.md`.

---

## 3. Build sequence

Spec §8 order. Each step ends with the full suite green **by exit code**, not by
a grepped pass count (P24).

### Step 1 — RN-M2.D, the breakage matrix, red
The whole spec as one test: build segment → sub-segment → category → vision
element → AVE/APE → annual initiative → quarter → month → Weekly Tactic → Action
Item, plus a Project on the APE and the item on the Project. Snapshot every link
**by id**. Rename at six levels. Assert every link still resolves.

It fails today at three of the six and goes green only when steps 2–4 are done.
Written first because it is the highest-stakes assertion in the change (P10) and
because writing it first stops the implementation defining its own success.

### Step 2 — RN-M1, schema and backfill
Three nullable id columns, added idempotently, backfilled by the **current** name
match, once. Unmatched rows stay NULL and are counted (RN-INV5) — a guess here
would link a user's work to the wrong plan element silently.

`annual_initiatives.annual_plan_element_id` needs a tie-break: two initiatives
can already match one APE (the RN-F4 duplicate). Link the oldest by `created_at`,
leave the other NULL, report both (RN-M1.B.2).

### Step 3 — RN-M2.A/B/C, resolve by id
`_find_annual_initiative_for_ape` reads the id. The title match survives **only**
as a one-time heal for a NULL row, and writes the id when it fires so it never
fires again for that row. The 6 `resolve_segment_id_by_name` link callers and the
3 name-joins move to ids.

This is where step 1 goes green.

### Step 4 — RN-M3, display copies
Every rename refreshes every stored copy of that name, including the Annual
Initiative's title (RN-D7). A Weekly Tactic's title follows on its next
canonicalisation and its APE link does not move (RN-M3.B).

### Step 5 — RN-M5, report and repair
What a user who has already renamed has now: APEs with no resolvable segment,
initiatives with no APE, duplicate initiatives per (APE, year). Counted, listed
by id, logged to `weekly_tactic_debug.log`, and returned in the report. Nothing
ambiguous is repaired (RN-D2, RN-INV5).

### Step 6 — RN-M4, the guard
A source scan asserting no link resolves through a name, with a by-name
allowlist whose entries carry their reason inline. **Plus `RN-M4.A.1`: the scan
must flag the four patterns this change removes.** A scan that is green on the
defect and on the fix alike proves nothing (P24) — that mistake was made twice
in the weekly-tactic work and caught both times by writing this test.

---

## 4. Acceptance criteria → tests

All in `tests/test_rename_safe_links.py`.

| ID | Criterion | Test | Step |
|---|---|---|---|
| RN-M2.D | No rename at any of six levels breaks any link | `test_rn_m2d_no_rename_breaks_any_link` | 1 |
| RN-M1.A.1 | APE + AVE gain `segment_description_id`, backfilled | `test_rn_m1a1_ape_segment_id_added_and_backfilled` | 2 |
| RN-M1.A.2 | An unmatched segment name is reported, not guessed | `test_rn_m1a2_unmatched_segment_is_reported_not_guessed` | 2 |
| RN-M1.B.1 | `annual_initiatives.annual_plan_element_id` backfilled from the title match | `test_rn_m1b1_initiative_ape_link_backfilled_from_title` | 2 |
| RN-M1.B.2 | Two initiatives matching one APE: oldest linked, other left NULL, both reported | `test_rn_m1b2_ambiguous_backfill_is_reported` | 2 |
| RN-M1.C.1 | `vision_segments.segment_description_id` backfilled; unmatched reported | `test_rn_m1c1_vision_segment_link_backfilled` | 2 |
| RN-M1.D | Dirty state (P8): run #2 on a populated DB changes nothing | `test_rn_m1d_migration_on_populated_db_run_two` | 2 |
| RN-M2.A | The initiative is found by id after a rename | `test_rn_m2a_initiative_found_by_id_after_rename` | 3 |
| RN-M2.A.1 | A legacy NULL row heals on first lookup and stays healed | `test_rn_m2a1_legacy_row_heals_on_first_lookup` | 3 |
| RN-M2.B | The re-filing cascade survives a segment rename | `test_rn_m2b_cascade_survives_a_segment_rename` | 3 |
| RN-M2.C | The `vision_segments`↔`segment_descriptions` join survives a rename | `test_rn_m2c_segment_join_survives_a_rename` | 3 |
| RN-M3.A | A rename refreshes every display copy, initiative title included (RN-D7) | `test_rn_m3a_rename_refreshes_every_display_copy` | 4 |
| RN-M3.B | A tactic's title follows a key-field rename without relinking | `test_rn_m3b_tactic_title_follows_rename_without_relinking` | 4 |
| RN-M5.A | Existing breakage is reported with counts and ids | `test_rn_m5a_existing_breakage_is_reported` | 5 |
| RN-M5.B | Ambiguous data is left alone | `test_rn_m5b_ambiguous_data_is_left_alone` | 5 |
| RN-M4.A | No link resolves through a name | `test_rn_m4a_no_link_resolves_through_a_name` | 6 |
| RN-M4.A.1 | The scan flags the four patterns this change removes | `test_rn_m4a1_the_scan_can_actually_fire` | 6 |

**17 of 17 criteria have a named test. None is unmapped.**

### Added beyond the spec

| Test | Why |
|---|---|
| `test_rn_no_duplicate_initiative_after_rename` | RN-F4's second half: after a rename, the next `assign_ape_to_month` must create **no** second Annual or Quarter Initiative. The spec covers the broken link; this covers the duplicate it caused. |
| `test_rn_project_and_tactic_links_are_id_based` | RN-F5 says these are already safe. An assertion, so a future refactor to name-matching fails here instead of in a user's data. |
| `test_rn_migration_runs_once_per_launch` | The weekly-tactic migration ran twice per launch for exactly this reason (two managers, one `Database`). Same trap, same guard. |

---

## 5. Criteria needing human review

| Criterion | What the test cannot see | Review |
|---|---|---|
| RN-M5.A | Whether a duplicate initiative the report names holds work worth keeping. The repair deliberately does not merge (RN-D6). | After the first run on the live database, read the report in `weekly_tactic_debug.log`. |
| RN-M3.A | Whether the refreshed names *render* correctly on VSP Planning and the Vision Planning Hub. | Launch under the venv, rename a segment, look at both screens, check `app.log`. |

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| The backfill links a row to the wrong segment because two segments have similar names. | Exact case-insensitive match only, no fuzzy matching; unmatched stays NULL and is reported (RN-INV5). A wrong link is worse than a missing one. |
| The healing path in `_find_annual_initiative_for_ape` writes an id inside a read. | It writes only when the id is NULL and exactly one title matches; it runs inside the caller's transaction, so a cascade rollback takes it with it. Asserted by `test_rn_m2a1`. |
| Refreshing the initiative title (RN-D7) overwrites something hand-edited. | Settled by the user: titles are derived. Recorded here so the decision is visible if it is ever revisited. |
| **The shared working tree.** Another session is active and has committed six times during this spec's life. | Stage explicit paths; `git log` immediately before every commit; never `git add -A`. |
| The 41 name-reading lines get rewritten wholesale. | Each is classified first — link resolution moves to ids, display and user-input lookups are allowlisted with the reason inline (RN-M4.A). Blanket rewriting would break the display the spec keeps. |

---

## 7. Definition of done

- `./venv/bin/python -m pytest -q` → **exit 0**, ≥ 899 passed.
- `tests/test_rename_safe_links.py` passes in isolation.
- The 17 criteria reported `done` / `partial` / `not done` with the file and test
  name proving each.
- `learning-qa` over the diff before pushing; findings fixed in the same session,
  and the fix commit re-swept.
- Verified in the running app per §5.
- `docs/spec_coverage_2026-08-19_rename_safe_links.md` generated by cross-checking
  the spec's test references against `pytest --collect-only`, not hand-written.
- `CHANGELOG.md` + handoff note.
