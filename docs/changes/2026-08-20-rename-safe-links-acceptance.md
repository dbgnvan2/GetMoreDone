# Handoff Note

- Date: 2026-08-20
- Agent: Code
- Topic: rename-safe links — the two outstanding acceptance items, then the
  year-filter veto and the legacy migration's discarded id

## Summary

The previous batch left **one of seventeen criteria unmet** (§5, verify in the
running app) and **one report unread** (the first migration against the real
database). Both are now closed. Two correctness items followed.

### §5 — verified in the running app

Launched under the venv, renamed the life segment **Creative → Creative Work**
in the segment editor, and looked at the screens that read the denormalised
names.

`app.log` clean throughout — no exceptions on either launch.

- **Vision Planning → Segments** — renamed, colour preserved.
- **Vision Planning → Categories** — all three Creative rows re-rendered.
- **Vision Planning → Annual Plan Elements** — both panels, all 14 APEs for
  2026, columns aligned across the paired panels, right-hand panel showing the
  refreshed `segment_name`. The two rows whose segment could not be resolved
  render with a fallback colour rather than blank or a crash.

Done against a **copy** of the real database, not the real one, so a defect
could not damage real data.

The remaining sub-screens were then rendered **headlessly** — real
CustomTkinter widgets in a transparent, withdrawn root, the same way
`conftest.py` hides them — because driving the GUI by clicking was repeatedly
stealing focus from the user. All five Vision Planning Hub sub-screens build
without raising; four of five show the new name and **none shows the old one**.
APE Weekly shows neither, correctly: the affected plan elements are assigned to
months 1–3 and the current week is in August.

`screens/vps_planning.py` and the Vision Planning Hub are the **same screen**
from the user's side — `app.show_vps_planning` is a shim that redirects to
`show_vision_planning_hub`. The plan's §5 names them as two.

### The first migration report on the real database

Backed up first (`getmoredone.db.pre-rename-migration.bak`). What it wrote:

```
2 apes_without_segment need a human: ape-126929ec / ape-4422170b, 'Wellness', 2026
backfill_annual_plan_elements   linked 12, 2 unresolved
backfill_annual_vision_elements linked 12, 2 unresolved
backfill_vision_segments        linked 11, 1 unresolved
backfill_initiative_ape         linked 2
```

**No orphaned initiatives and no duplicate pairs** — checked against the tables,
not inferred from the log's silence: 2 initiatives, both with an APE, no
`(ape, year)` group above one. So spec §10's "does any duplicate hold real
work" had nothing to judge.

Every unresolved row was the same cause: five rows pointing at a life segment
named **Wellness**, which is not in `segment_descriptions`. It had been renamed
to **Health** back when the link was by name, so the link broke then.

Resolved on the user's instruction, through the app's own methods — no raw
`UPDATE` of rows the app owns. Trialled on a throwaway copy first, then run on
the real database behind a second backup:

1. `create_vision_subsegment("Health", "Physical")`, carrying the original's
   colour and text.
2. `update_vision_element(...)` for each of the two elements — the path the
   Vision Element editor uses, which syncs `annual_vision_elements`,
   `annual_plan_elements` (names, `key_field` **and** `segment_description_id`)
   and the derived initiative title.
3. `update_vision_category(...)` to carry each category's colour across.
4. `delete_vision_segment_admin(...)` for the now-empty shadow row.

Verified after: quarter/month flags intact, action-item links intact, no orphan
subsegments or categories, row counts unchanged (16 vision elements, 14 APEs,
645 action items), `report_existing_breakage` now **zero on all three counts**.

`action_items.who`, three completed action-item titles and two project-board
titles still read "Wellness". A real segment rename in this app does not touch
any of them, so neither did this — matching what the code path would have done
is the point. All six action items are `completed` Q1 history.

### The year filter — it does not belong

`_find_annual_initiative_for_ape` resolved by `annual_plan_element_id`, then
filtered `AND ap.year = ape.year` through a join on `annual_plans`. **An APE id
identifies one APE and an APE carries one year**, so that predicate can never
select a *different* initiative. It can only hide the right one.

The year is stored independently on `annual_plans`, `annual_plan_elements` and
`annual_initiatives`, so any path writing one without the others drifts them.
On drift the lookup returned `None`, `_get_or_create_annual_initiative_for_ape`
built a second initiative, and **RN-F4's duplicate reappeared through the
function written to close RN-F4**. Measured: the test reports a genuinely
different initiative id, not a count.

Same predicate at the two title-match sites. There `ai.year` is the identifying
comparison — the initiative's own year against the APE's. `ap.year` is a third
copy of that one fact, contributing no identifying power and able only to drop
a candidate that would have linked correctly. A heal that finds nothing does
not fail safe: the caller then creates the duplicate. All three moved together,
so the backfill's documented claim to reproduce the heal stays true.

### `vps_schema.py` — the fourth INSERT, and why it was not the same fix

The backlog called this "the last of four `INSERT INTO vision_segments` sites
that still omits `segment_description_id`". **It could not be hardened like its
three siblings**: the column does not exist at that point. `CREATE TABLE
vision_segments` does not declare it, `link_integrity` adds it, and that runs
*after* `initialize_vps_schema`. Adding the column to the INSERT as written
raises `no such column`. Confirmed by tracing the live call, not by reading.

It is also a different problem. The siblings resolve the id from a name because
a name is all they have. This one is **handed the real id** by the legacy row
(`l.segment_id`) and discarded it, inserted by name, and let the backfill
re-derive the id from that name moments later. That round trip is lossy: with
two descriptions differing only by case — legal, because SQLite's `UNIQUE` is
case-sensitive — the name resolves to neither, the row comes out NULL, and the
report asks a human about something the data already answered. Reproduced end
to end before writing the fix.

The migration now calls the same idempotent column adder first, and stamps
`sd.id` from the LEFT JOIN — never `l.segment_id`, because the legacy table's
FK is not enforced retroactively and writing the raw value through raises
`FOREIGN KEY constraint failed` inside schema init. Measured, by mutation.

## Files changed

**Changed**
- `src/getmoredone/vps_manager.py` — `_find_annual_initiative_for_ape` and
  `_heal_annual_initiative_link` drop the `annual_plans` join and `ap.year`.
- `src/getmoredone/link_integrity.py` — `backfill_initiative_ape_links` the same.
- `src/getmoredone/vps_schema.py` — the legacy migration adds the column, then
  stamps the id the legacy row carried.
- `tests/test_rename_safe_links.py` — four tests, `_drift_annual_plan_year`.
- `tests/test_vps_legacy_migration.py` — two tests, a case-colliding fixture.
- `BACKLOG.md` — two items closed, one corrected, four new ones recorded.

**Data (the user's real database, on their instruction)**
- Five rows merged from the orphaned Wellness segment into Health. Backups at
  `getmoredone.db.pre-rename-migration.bak` and `.pre-wellness-merge.bak` in
  `~/Library/Application Support/GetMoreDone/`.

## Verification

- `nice -n 19 ./venv/bin/python -m pytest tests/test_vps_legacy_migration.py
  tests/test_rename_safe_links.py tests/test_vps_data_integrity.py
  tests/test_vps_segments.py tests/test_vps_hub_crud.py
  tests/test_weekly_tactic_schema.py tests/test_vps_integration.py
  tests/test_weekly_tactic_cascade.py tests/test_vps_fixes.py
  tests/test_database.py -q`
- Result: **PASS — 212 passed, exit 0**, read from the exit code. Zero
  `GUARD:` lines, so no test reached the real database.
- The full suite was **not** run locally, by instruction. CI runs it on three
  Python versions.

**Every test proved able to fail, by mutation with the verbatim original:**

| Test | Mutation that makes it red |
|---|---|
| `..._initiative_survives_an_annual_plan_year_drift` | the `ap.year` join back in `_find_annual_initiative_for_ape` |
| `..._year_drift_does_not_duplicate_the_initiative` | same — reports a different initiative id |
| `..._heal_survives_an_annual_plan_year_drift` | the `ap.year` join back in `_heal_annual_initiative_link` only |
| `..._backfill_survives_an_annual_plan_year_drift` | the `ap.year` join back in `backfill_initiative_ape_links` only |
| `test_rn_m1c_legacy_migration_keeps_the_id...` | the whole `vps_schema` change reverted to HEAD |
| `test_rn_m1c_legacy_migration_does_not_stamp_a_dangling_id` | stamping `row["legacy_segment_id"]` — red with `FOREIGN KEY constraint failed` |

Each of the first four was mutated **one site at a time**, confirming each test
guards its own site and not a neighbour's.

A seventh test was written and **deleted rather than kept green**: it asserted
the `Uncategorized` fallback stays NULL and passed with the branch it named
removed, because the LEFT JOIN already yields NULL for that input. The branch
was redundant, so the branch went instead of the test being kept as decoration.

## Risks / Known gaps

- **The user's real database was modified.** Five rows re-pointed from Wellness
  to Health, on their explicit instruction, through the app's own methods, with
  two backups taken. Reversible by restoring `.pre-wellness-merge.bak`.
- **`vps_schema.py` runs against every user database at launch.** The change is
  inside schema initialization, which is the highest-blast-radius code here. It
  is guarded by `_table_exists(conn, "vision_segments_legacy")` and so is inert
  on any database that is not legacy-shaped, and the column adder it calls is
  idempotent. Exercised on legacy, non-legacy and second-launch paths.
- **`initialize_vps_schema` runs twice per launch** and is not behind the
  once-per-`Database` guard its two sibling migrations use. Idempotent today.
  Recorded in `BACKLOG.md`, not fixed — it is wasted work, not a defect.
- **Segment names over 15 characters are clipped** in every VSP chip
  (`_clip_label`). Pre-existing, not a rename regression, but found while
  verifying §5 and worth knowing before renaming anything descriptively.
- **I repeatedly stole focus from the user** while driving the GUI, by
  activating the app before each click. The headless render harness does the
  same job without it and is the approach to use next time.

## Next agent actions

- The eleven remaining low findings in `BACKLOG.md`, four of them new.
- Decide whether `action_items.who` and the two project-board titles should
  follow the Wellness → Health merge. The app's own rename path does not touch
  them, so this is a product decision, not a bug.
