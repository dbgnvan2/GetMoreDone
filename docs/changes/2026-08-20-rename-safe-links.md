# Handoff Note

- Date: 2026-08-20
- Agent: Code
- Topic: rename-safe links — RN-M1..RN-M5 implemented, all 17 criteria met

## Summary

`docs/spec_2026-08-19_rename_safe_links.md` built in the plan's §3 order.
**17 of 17 leaf criteria have a passing test; none was descoped.**

Renaming anything — a segment, sub-segment, category, vision element key
field, Project or Weekly Tactic — now leaves every link intact. Four nullable
id columns hold the links that a name used to hold, backfilled once from the
current name and never matched by name again.

## Verification

- `nice -n 19 GETMOREDONE_NO_MAPPED_WINDOWS=1 ./venv/bin/python -m pytest -q`
- **1172 passed, 6 skipped, exit 0.** Baseline before this batch: 1163.
- `tests/test_rename_safe_links.py` alone: **35 passed**, as the plan requires.
- Success read from the exit code throughout.
- Spec coverage generated mechanically by cross-checking the spec's `::test_`
  references against `pytest --collect-only`:
  `docs/spec_coverage_2026-08-19_rename_safe_links.md` — 17 criteria, 0
  missing, 13 further tests beyond the spec.

## One correction to the spec, made before any code was written

**RN-F1 says three of six rename levels break links. It is four.** Renaming a
**category** breaks the APE→initiative link through the same
`LOWER(ai.title) = LOWER(ape.key_field)` match, and the spec does not list it.
The two already-safe levels (Project, Weekly Tactic) are confirmed safe, so
"six levels" is right and only the failing count was wrong. Measured by the
matrix test on its first red run.

## What the reviews found — three regressions this change introduced

Two reviews ran in parallel, one failure-pattern sweep and one cold. Between
them: **3 high, 5 medium.** Three of the highs were created by this change.

| Defect | Why it mattered |
|---|---|
| `delete_segment` did not count `annual_plan_elements` | The new column was `ON DELETE SET NULL`, so deleting a segment reported "no child records", silently nulled every plan element's link, and the next cascade raised the **exact spec §2 error this change exists to remove** |
| `update_vision_element` did not move `segment_description_id` | Re-pointing a vision element left the plan element on the OLD segment — whose id columns are `ON DELETE CASCADE`, so deleting it destroys work the UI shows under the new one. The name-based code it replaced got this right |
| The derived-title refresh was unconditional | The Annual Initiative editor has a Title field. A rename silently discarded whatever the user had typed |

Plus: `resolve_segment_id_by_name` is a bare `fetchone()` with no ambiguity
check, and `segment_descriptions.name` is UNIQUE but **case-sensitive** — so
the migration reported a row as ambiguous and left it NULL, and
`sync_vision_segments_with_settings` wrote a guess into the same row seconds
later at every manager init. **The logged report was false about the database
it had just described.** One resolver now serves every link write.

And a fifth name-based link path the guard could not see:
`db_manager._segment_from_annual_plan`, which runs on every
`create_action_item` and derived `None` for a plan element carrying the correct
id and a drifted name.

## My headline test could not fail

The cold review mutated the code and found **RN-M2.D — "the whole spec in one
test" — green against the defects it names**:

- Making all three rename functions **complete no-ops** left all six
  parametrisations green. `_rename()` ignored every return value and nothing
  asserted the new name was stored, so `before == after` held trivially.
- Making `_segment_id_for_ape` **ignore the stored id and always resolve by
  name** — the original defect restored — left all 27 tests green, because
  RN-M3.A now renames `segment_descriptions` too, so the name lookup succeeds
  again. Nothing proved the id column was load-bearing.
- Restoring the **verbatim** deleted line
  `segment_id = self.resolve_segment_id_by_name(segment_name)` left the RN-M4
  guard green, because my offender sample used the `ape[...]` spelling rather
  than the code actually removed.

All three now fail. The guard was widened from alias-pinned regexes and sees
**13 real occurrences across four files where it previously saw 2** — the
comment claiming the other patterns were "gone from src/ entirely" was prose,
not a finding.

## Files changed

**New**
- `src/getmoredone/link_integrity.py` — schema, backfill, the shared
  `resolve_segment_id_exact`, and RN-M5 reporting.
- `tests/test_rename_safe_links.py` — 35 tests.
- `docs/spec_coverage_2026-08-19_rename_safe_links.md` — generated.

**Changed**
- `database.py` — runs the migration after the weekly-tactic ones, behind the
  same once-per-`Database` guard.
- `vps_manager.py` — `_segment_id_for_ape`, `_heal_annual_initiative_link`,
  `_commit_heal`; `delete_segment` counts the two new tables.
- `vps_manager_taxonomy.py` — three name joins → id; renames refresh every
  stored copy; `update_vision_element` delegates to the shared sync.
- `weekly_tactic.py`, `db_manager.py` — link callers moved to ids.
- `tests/test_weekly_tactic_cascade.py` — one test re-pointed, classified
  **(b) behaviour intentionally changed**: it induced a mid-chain failure by
  patching `resolve_segment_id_by_name`, which no longer breaks anything. The
  rollback contract it guards is unchanged.

## Risks / Known gaps

- **NOT verified in the running app.** The plan's §5 requires launching the app
  and renaming a segment while watching VSP Planning and the Vision Planning
  Hub, which read the names this change refreshes. Not done — the user asked
  for no more windows on their machine mid-session. **This is the one
  outstanding acceptance item**, and it is the check most likely to surface a
  display problem the database tests cannot see.
- **The migration runs against the user's real database at next launch.** It
  only adds nullable columns and writes ids it can resolve unambiguously, and
  the dirty-state test asserts a second run changes nothing. The first run's
  report is worth reading: spec §10 asks a human to judge whether any duplicate
  initiative it names holds work worth keeping.
- **`annual_vision_elements` now blocks a segment delete** as well as
  `annual_plan_elements`. That may be stricter than intended; recorded in
  `BACKLOG.md`.
- **Eight low-severity findings** from the reviews are in `BACKLOG.md`, not
  fixed in-loop, per the sweep rules.
- The final cold pass over the fix commits had not reported when this note was
  written; its findings are recorded separately if any.

## Next agent actions

- Verify in the running app per §5, and read the first migration report.
- The eight low findings in `BACKLOG.md`.
