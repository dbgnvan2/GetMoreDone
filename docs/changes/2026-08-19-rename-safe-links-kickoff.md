# Handoff Note

- Date: 2026-08-19
- Agent: Code
- Topic: rename-safe-links — spec and plan approved, implementation not started

## Summary

A spec and an implementation plan exist and are ready to build.
**No implementation code has been written.** This note is the cold-start context
for the session that builds it.

- **Spec:** `docs/spec_2026-08-19_rename_safe_links.md` (v1)
- **Plan:** `docs/implementation_plan_2026-08-19_rename_safe_links.md`

The feature: renaming anything — a segment, sub-segment, category, vision element
key field, project, Weekly Tactic — must leave every link intact. Today three of
those six renames break a link, and the segment case makes an ordinary date
change on a filed Action Item **raise**.

17 leaf acceptance criteria, each naming the test that proves it, in one new test
file. No new dependency, no UI change, no schema change beyond three nullable id
columns.

## Files changed

- `docs/spec_2026-08-19_rename_safe_links.md` — the spec
- `docs/implementation_plan_2026-08-19_rename_safe_links.md` — the plan
- `docs/changes/2026-08-19-rename-safe-links-kickoff.md` — this note
- `docs/implementation_plan_2026-08-19_item_editor_project_link.md` — one
  cross-reference added in the Phase C adjacent-issues section

No source files touched.

## Verification

- Command: `./venv/bin/python -m pytest -q`
- Result: PASS — 899 passed, 2 skipped (baseline before any of this work)

## Context the spec does not carry

**Environment.** Use the venv for everything: `./venv/bin/python -m pytest -q`.
A bare `pytest` may resolve to a different interpreter. `tkcalendar` and `babel`
are deliberately absent (GPLv3) — a `ModuleNotFoundError` for either is not fixed
by reinstalling. GUI tests need a display and skip cleanly without one.

**The working tree is shared and another session is active in it.** It moved six
times while the spec was being written, twice mid-command. Before every commit:
`git status --porcelain`, `git log --oneline -3`, and stage **explicit paths**.
Never `git add -A` — that has already swept one session's work into another's
commit in this repo.

**Live database** (read-only for inspection, never write to it directly):
`~/Library/Application Support/GetMoreDone/getmoredone.db`

**Verify UI work in the running app.** DB unit tests are not sufficient for this
codebase. VSP Planning and the Vision Planning Hub read the denormalised names
this change refreshes.

**The evidence behind the spec was measured, not inferred.** A full chain was
built and every link snapshotted by id, then each level renamed. If you doubt a
finding, rebuild that experiment rather than reading the code — §2 and §3 of the
spec have the exact output.

## Risks / Known gaps

- **RN-M2.D is written first and fails today.** That is intentional: it is the
  whole spec as one test. Do not weaken it to get an early green.
- **The backfill must never guess.** Exact case-insensitive match only. An
  unmatched row stays NULL and is reported. A wrong link is worse than a missing
  one, and it would be silent.
- **`annual_initiatives` may already hold duplicates per APE** from the bug this
  fixes. The backfill links the oldest and reports the rest; it does not merge
  them. Merging needs its own tie-break decision and is out of scope (spec §9).
- **The 41 name-reading lines are not all link resolution.** Several are display
  or filtering. Classify each before changing it — blanket rewriting breaks the
  display the spec deliberately keeps (RN-D5).
- **RN-D7 is settled:** an Annual Initiative's title stays derived and a rename
  refreshes it. Do not re-open it.
- **The guard test must be able to fail.** `RN-M4.A.1` exists because a scan that
  is green on the defect and the fix alike proves nothing. That mistake was made
  twice in the weekly-tactic work.

## Next agent actions

1. Read the spec and the plan in full.
2. Build in the plan's §3 order — RN-M2.D red first, then schema, then
   resolution, then display, then reporting, then the guard.
3. `learning-qa` over the diff before pushing, and re-sweep the fix commit.
