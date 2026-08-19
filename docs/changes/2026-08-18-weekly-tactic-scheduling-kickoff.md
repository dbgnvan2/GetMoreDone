# Handoff Note

- Date: 2026-08-18
- Agent: Code
- Topic: weekly-tactic-scheduling — spec approved, implementation not started

## Summary

A spec exists and is ready to implement. **No implementation code has been
written.** This note is the cold-start context for the session that builds it.

**Spec:** `docs/spec_2026-08-18_weekly_tactic_scheduling.md` (v2, commit fd3afd5)

The feature: changing an Action Item's start date re-files it into the correct
Weekly Tactic, auto-creating any missing Quarter / Month / Week plan records —
including across a year boundary. Completing an item re-files it to the
completion week. A new `weekly_tactic_start_date` field records the week the
item was *originally* meant to start, so push-out stays visible after the start
date has moved.

The spec is self-contained: 13 decisions (WT-D1..WT-D13), 6 invariants, 14
research findings with `file:line` evidence, ~90 acceptance criteria each naming
the test that proves it, and a dependency-ordered build sequence in §8.

## Files changed

- `docs/spec_2026-08-18_weekly_tactic_scheduling.md` — the spec (v2)
- `docs/changes/2026-08-18-weekly-tactic-scheduling-kickoff.md` — this note

No source files touched.

## Verification

- Command: `./venv/bin/python -m pytest -q`
- Result: PASS — 652 passed, 2 skipped (baseline before any of this work)

## Context the spec does not carry

**Environment.** Use the venv for everything: `./venv/bin/python -m pytest -q`.
A bare `pytest` may resolve to a different interpreter. GUI tests need a display;
they `pytest.importorskip("customtkinter")` and skip cleanly without one.

**Live database** (read-only for inspection, never write to it directly):
`~/Library/Application Support/GetMoreDone/getmoredone.db`
Current shape, verified 2026-08-18: 646 `action_items` (620 daily, 26 week);
49 items linked to a tactic; 94 ordinary `daily → daily` nesting rows; 14 APEs;
2,100 `reschedule_history` rows; all four year-scoped tables hold 2026 only.

**Verify UI work in the running app.** DB unit tests are not sufficient for this
codebase — exercise real widgets under the venv and check `app.log`. §10 of the
spec lists the two criteria that specifically need a human look.

**Spec history.** v1 was reviewed by two independent agents, which found twelve
substantive defects. v2 corrects all of them. Do not "simplify" back toward v1 —
in particular, WT-D11 (the dedicated `weekly_tactic_id` column) and WT-M4.D
(atomicity built *before* the rollover) look like extra work and are not:
without them the feature silently destroys subtask hierarchies and leaves
half-built plan lineages permanently committed.

## Risks / Known gaps

- **WT-M7.B rewrites dates on up to 29 existing items.** §10 asks for the list to
  be reviewed before the migration runs — some violations may be deliberate user
  data rather than drift. Surface the list; do not run it silently.
- **WT-M4.D must be built before WT-M4.C** (§8 step 5 before step 8). Every
  creator in `vps_manager*.py` commits internally today, so the rollback the spec
  requires is unbuildable until the `commit=False` seam exists.
- **WT-M4.C.3 changes shipped behaviour.** `_get_or_create_annual_plan_for_ape`
  currently writes `title=f"{segment} {year}"` and `theme=f"{segment} {year} Plan"`.
  Four existing callers depend on that path — WT-M4.C.3c covers them.
- **WT-F13:** `assign_ape_to_quarter` / `assign_ape_to_month` return bare booleans
  asserted `is True` at `tests/test_vps_hub_crud.py:311` and `:342`. The new
  report-shaped return goes on a *new* function; do not change theirs.
- §9 of the spec lists six adjacent issues deliberately left alone. Do not fix
  them in this change.

## Next agent actions

1. Read `docs/spec_2026-08-18_weekly_tactic_scheduling.md` in full.
2. Produce an implementation plan per the global planning rules: every
   acceptance criterion by its spec ID, the test that verifies it, build order
   with dependencies, and any criterion that cannot be made code-testable
   flagged with a human-review proposal.
3. **Stop after the plan.** Commit it and wait for approval before writing
   implementation code.
