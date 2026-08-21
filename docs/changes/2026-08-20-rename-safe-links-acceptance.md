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

At the two **title**-match sites — the heal and the migration's backfill, both
reached only by a row that has no id yet — the same predicate turned out to be
doing something different, and removing it outright was a mistake. See below.

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

### What the cold pass found — three regressions I introduced

Per `CLAUDE.md`'s budget: two warm passes at most, one cold pass always, a
further pass only after a high-severity finding. The cold pass was given the
diff and the range and no narrative. It produced **one high and two medium**,
and **all three were inside my own fixes**. Each was reproduced against the
pre-fix source before being believed.

**The plan year at the title-match sites is a tie-break, not a veto.** My
reasoning — "`ai.year` already does the identifying, `ap.year` adds no
identifying power" — was true about identifying power and false about
*narrowing*, and narrowing is what those two sites depend on.

| With a twin initiative on a drifted-year plan | Before this batch | After my fix |
|---|---|---|
| backfill | links the APE's own initiative, `ambiguous=[]` | links the **twin** (older, wins `created_at ASC`); the real one left NULL and reported as the loser |
| heal | heals; 2 initiatives → 2 | returns None on 2 candidates; `_get_or_create` builds a **third**; 2 → 3 |

The heal's own docstring argued against what I did to it: a heal that finds
nothing does not fail safe, because the caller then creates the duplicate.

`find_initiative_candidates_by_title` now prefers candidates whose plan year
agrees and widens **only when there are none**. That is identical to the old
behaviour whenever the old behaviour found anything, and different only where
it found nothing — so no regression is possible. Both tiers are load-bearing,
proved by mutation: return only the wide set and the two "prefers" tests
redden; return only the narrow set and the two drift tests redden. It also
collapses the two copies of the title match into one query, which is why
RN-M4's exact count moves a lookup out of `vps_manager.py`.

**The legacy migration must not pick a side (high).** `segment_cache` is keyed
by *lowered* name, so two legacy rows pointing at two descriptions differing
only by case collapse into one `vision_segments` row. Stamping the first row's
id asserted a link that is false for the other row's work, and the backfill's
ambiguity report — which had named both candidates — came back clean:

```
pre-fix : ('vsg-…','Health', None)   ambiguous=[{candidates: [seg-upper, seg-lower]}]
post-fix: ('vsg-…','Health','seg-upper')   ambiguous=[]
```

That inverts the rule stated at the top of `link_integrity.py` — a wrong link
is worse than a missing one, because the missing one is visible in the report.
It was also irreversible: `vision_segments_legacy` is dropped in the same
function, and the backfill only revisits rows that are still NULL. Stamping now
requires that every legacy row collapsing into a name agrees on which
description it means.

My own test could not have caught it: it seeded **one** legacy row and then
asserted `ambiguous == []` — asserting the silence without exercising the
collision its fixture name advertised.

### The second cold pass — required, and it earned it

The budget allows a further pass only after a high-severity finding, and the
first cold pass produced one. This second pass was given the two **fix**
commits and a different set of failure families. It produced **one medium-high
and one medium**, again inside my own work.

Its headline finding was real but its baseline was wrong: it compared against
my mid-batch commit rather than the batch base. Measured on the mirror fixture
— the plan element's *own* initiative on the drifted plan, a stale twin on an
agreeing one:

| | links | reports |
|---|---|---|
| `ddcea71`, the batch base | the stale twin | nothing |
| `48bfe57`, mid-batch | the right one | the twin |
| my tie-break, as first written | the stale twin | nothing |

So preferring the agreeing candidates does not regress the base — it returns
the base's answer whenever the base had one, and answers only where the base
returned nothing. **What was genuinely wrong is the silence.** Both
orientations are reachable and nothing in the data separates them, so the
preference is a guess, and RN-INV5 — stated at the top of `link_integrity.py`
— does not permit making one quietly.

The helper now returns the preferred candidates *and* all of them. The backfill
links the preferred one and reports every other candidate, including the ones
the tie-break demoted; previously it reported only the losers inside the
winning tier, which is what made the tie-break invisible. The heal takes only
the preferred list: it has no report channel, and refusing there is not safe.

The second finding was my own test. `..._prefers_the_candidate_whose_plan_year_agrees`
asserted `ambiguous == []` — pinning the silence, so the correct fix above
would have turned it red for doing the right thing. A test that rejects the fix
for a defect is worse than no test. It now asserts the link *and* that the twin
is named.

Also corrected: five written claims the code did not do, including the heal's
"EXACTLY ONE initiative matches" (it is one *candidate*, after a choice this
path cannot report) and RN-M4's allowlist entry for a title match that no
longer lives in `vps_manager.py`.

Four further findings were graded low and recorded in `BACKLOG.md` rather than
fixed: the residual mis-filing the legacy collapse still causes, a missing
`_table_exists` guard for `annual_plans`, an orphaned-plan initiative being
invisible to the title match, and the tie-break's remaining silence in the heal.

### The pre-push sweep — one medium, and it falsified my own prose

`learning-qa` over all ten commits. **11 of 29 patterns applicable, 5 findings,
one at medium.**

The medium is **P5**, the pattern about a guard applied to one door into a
class. `create_segment` refuses a life segment whose name differs from another
only by case. `update_segment` had no collision check at all, so *renaming* one
created exactly the state creating one could not:

```
create_segment('zeta')            refused: 'Zeta' already exists
update_segment(other, name='zeta') -> True
segment_descriptions now holds:    ['Zeta', 'zeta']
resolve_segment_id_exact('Zeta')   -> None
```

Once the pair exists both spellings resolve to None, so every link resolution
refuses forever and the migration reports the rows at every launch. Reachable
from the running app — the segment editor's Save passes the typed name through.

It also **falsified a sentence I wrote in this batch**: the legacy fixture's
docstring said "`create_segment` refuses to make a new one now; it cannot
un-make the ones already there." The first half was false, and the whole
`_agreed_description_id` mechanism is premised on collisions being a legacy-only
artefact. They were creatable today.

The guard is now `_refuse_case_collision` with an `exclude_id`, so a row is
never a collision with itself. `update_segment` also strips the name before both
the check and the write — it had been writing the raw spelling to
`segment_descriptions` while `vision_segments` got the stripped one, so one
segment could sit in two tables under two names.

Three writers of `segment_descriptions.name` exist. Two are now guarded. The
third, `rename_vision_segment`, checks `vision_segments` for the same collision
and the sync keeps the two tables 1:1 — a guard there would be unfalsifiable
today, so it is recorded rather than written.

Two tests, both mutation-proved: one at the manager, and one driving the real
`VPSSegmentEditorDialog` widget (**P25** — a guard the library enforces is worth
nothing if Save swallows it). The widget test asserts the table is unchanged,
the reason reaches the user, the dialog is still open, and their typing is still
in the field. Without the guard it fails on "the editor saved or failed
silently".

Four further findings graded below medium are in `BACKLOG.md`.

**What this sweep did not assess**, in its own words: logic correctness beyond
the link-resolution paths, concurrency, UI-contract regression across the 50+
screens, security, performance, dependency risk, API compatibility, and
architecture. It is a pass against one failure family, not a clean bill.

### The re-sweep of the fix commits — one high, in the fix itself

The workflow re-sweeps the fix commits because they are the least-reviewed code
in any change. It found **one high**, and it is the same shape this repo has
already recorded once: a guard written to protect data made existing data fail
hard.

`_refuse_case_collision` was called whenever the update carried a `name` key,
not when the name **changed**. Both segment editors always send the unchanged
name alongside whatever the user actually edited, so on a database that already
holds a case-colliding pair, **both rows became completely uneditable**:

```
colour-only save (name unchanged)    -> RAISED ... 'health' already exists
deactivate       (name unchanged)    -> RAISED ... 'health' already exists
description-only (name unchanged)    -> RAISED ... 'health' already exists
colour after: #4CAF50 (wanted #FF0000)
```

The message told the user to pick a different name when they had changed no
name, and there was no way to retire either row. That population is exactly the
one the guard exists alongside — it can stop new pairs, it can never un-make the
ones already there, and the legacy migration in this same batch is written for
databases that hold them.

**Both of my tests for the guard were blind to it**, because both used a clean
fixture in which a collision cannot pre-exist. The guard's docstring said "a row
is never a collision with itself, so a segment can keep its own name" —
`exclude_id` makes it not collide with *itself*, but the pre-existing sibling
still collided, so "keep its own name" was false exactly where a collision
already existed. The claim looked proved because nothing tested the case.

Now gated on the case-folded name actually changing. The new test seeds the pair
by direct `INSERT`, because `create_segment` refuses to make one — which is
precisely why the earlier tests could not reach it.

The re-sweep's medium was a second hole in my own test: deleting
`updates["name"] = clean` left **86 tests green**. The collision guard cannot
cover the strip, because a *padded* name that collides raises before the write is
reached — only a padded name that does **not** collide exercises it. Now
asserted against both tables, since the bug is that they diverge.

Its third finding, that `rename_vision_segment` is a **third** unguarded writer
of `segment_descriptions.name`, is recorded rather than fixed. It could not
produce a collision through it either — the sync keeps the two tables 1:1, so
the `vision_segments` check covers the other table by proxy — and a guard there
would be unfalsifiable today. The falsifiable part is the proxy's weak point:
the `UPDATE … WHERE id = (SELECT segment_description_id …)` matches nothing when
that id is NULL, which is the state the migration deliberately leaves for an
ambiguous row, so the tables diverge silently. That is the better fix and it is
in `BACKLOG.md`.

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
  plus `tests/test_traceability_refs.py` and `tests/test_no_vacuous_tests.py`.
- Result: **PASS — 223 passed, exit 0**, read from the exit code. Zero
  `GUARD:` lines, so no test reached the real database. The eight meta files
  pass separately: 206 passed, 1 skipped.
- The full suite was **not** run locally, by instruction. CI runs it on three
  Python versions.

**End-to-end against a copy of the real database**, with the app object and all
13 screens built headlessly — transparent, withdrawn windows, so nothing
appeared on screen and nothing took focus:

- `GetMoreDoneApp()` constructs; **all 13 screens build**; **zero WARNING+ log
  lines**.
- The migration is a **byte-for-byte no-op** on that copy, over two successive
  `initialize_schema()` runs, and the breakage report is zero on all three
  counts.
- One real downstream effect appears only on a launch, and is worth expecting:
  `[VSP] Backfilled segment ids on 6 action item(s)`. Those are the six
  completed Q1 items under the two merged plan elements; they now resolve to
  **Health** (`seg-1`) through their APE link, where before the merge they had
  no segment at all. The second launch prints nothing, so it settles.
- Their `who` and `title` still read "Wellness". A real segment rename does not
  touch either field, so neither did this.

**Every test proved able to fail, by mutation with the verbatim original:**

| Test | Mutation that makes it red |
|---|---|
| `..._initiative_survives_an_annual_plan_year_drift` | the `ap.year` join back in `_find_annual_initiative_for_ape` |
| `..._year_drift_does_not_duplicate_the_initiative` | same — reports a different initiative id |
| `..._heal_survives_an_annual_plan_year_drift` | the `ap.year` join back in `_heal_annual_initiative_link` only |
| `..._backfill_survives_an_annual_plan_year_drift` | the `ap.year` join back in `backfill_initiative_ape_links` only |
| `test_rn_m1c_legacy_migration_keeps_the_id...` | the whole `vps_schema` change reverted to `ddcea71` |
| `test_rn_m1c_legacy_migration_does_not_stamp_a_dangling_id` | stamping `row["legacy_segment_id"]` — red with `FOREIGN KEY constraint failed` inside `initialize_schema` |
| `..._heal_prefers_the_candidate_whose_plan_year_agrees` | `return _matches(False)` — the narrow tier removed |
| `..._backfill_prefers_the_candidate_whose_plan_year_agrees` | the same |
| `..._two_legacy_rows_that_collapse_are_not_given_one_of_the_two_ids` | stamping `row["description_id"]` instead of the agreed one |

The two drift tests redden on the opposite mutation, `return _matches(True)` —
so neither tier of the tie-break is decoration.

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
- **The finding count is not the reassuring part.** Every fix commit in this
  batch contained a defect found by the next pass, and the highest-severity
  finding overall was created by a fix rather than found in the original code.
  Across two cold passes, one failure-pattern sweep and one re-sweep of the
  fixes: **eight findings at medium or above, all eight inside code this batch
  wrote**, two of them high. One disproved a sentence written two commits
  earlier; the last was in a guard added three commits earlier and was
  invisible to both tests written for it. Every round of fixes in this batch
  produced a defect the next round found. Reviewing stopped on the budget's
  rule, never because the count fell.
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
