# Handoff Note

- Date: 2026-08-19
- Agent: Code
- Topic: backlog-batch-1

## Summary

Batch 1 of [`docs/implementation_plan_2026-08-19_backlog_clearance.md`](../implementation_plan_2026-08-19_backlog_clearance.md):
the bugs that bite, plus everything two sweep passes found on top of them.

**BC1 — "Today shows all completed items".** Not reproducible. Both the SQL path
and the Python search path already restrict completed items to
`DATE(completed_at) = today`; verified against a real database before writing
any fix. Six tests now pin it, including the boundary (yesterday is not today)
and the search path, which computes the same list in a second place.

**BC2 — a Weekly Tactic left mid-week was never repaired.** When
`normalize_week_item_starts` could not snap a tactic onto its week start because
a duplicate held that date, it left the row mid-week and reported a collision.
`find_duplicate_weekly_tactics` grouped by the raw `start_date` column, so the
stray formed a group of one and was never merged: the WT-INV5 violation survived
every restart with only a log warning to show for it. Grouping is now by the
week a row belongs to, and once the duplicate is merged away the survivor is
snapped onto the week start.

**BC3 — sixteen tests that could not fail.** The backlog called this "two tests
that return a bool". It was sixteen across four files, and two were doing harm:
one was *returning False* — a failing test reporting green since
`delete_segment`'s return shape changed — and one constructed `DatabaseManager()`
with no path, opening the user's real database and running migrations on it.

## What the sweeps added

The first pass found 9, the second found 8 — **two of them inside the first
pass's own fixes**, which is the whole argument for the second pass:

- A fix that grouped unparseable dates so they would *merge* traded a loud
  recoverable failure for a silent irreversible one (`''` means "no start date",
  not "the same week"). Now reported, never merged.
- The settings-isolation fixture **did not work, and its guard test said it
  did**: five test files import `getmoredone.app_settings` while the fixture
  patched `src.getmoredone.app_settings` — two module objects, two classes. The
  guard imported the patched twin and passed while the real file went on being
  written. Closed by unifying the imports, patching both classes, and stamping
  the real file's mtime at session start/finish.
- Two new tests did not exercise what they claimed (children inside the week; an
  assertion that could never be false).

## Verification

- Command: `venv/bin/python -m pytest -q`
- Result: PASS — 949 passed, 2 skipped, exit code 0
- `PytestReturnNotNoneWarning`: 17 → **0**
- Real settings file: mtime unchanged across a full run (checked before/after),
  and a probe test that writes it makes the run error — the guard fires.
- Every substantive fix has a test proven to fail without it: the mid-week
  survivor, the unreadable pair, the false "could not be snapped" skip on three
  children, and the settings escape.

## Risks / Known gaps

- **The last fix commit (5cdb7a9) was not itself swept.** The loop ran
  sweep → fix → sweep → fix, and the second round of fixes is unreviewed code.
  Given the second pass found two defects in the first round, a third pass is
  not unreasonable; it was not run.
- ~~`delete_segment`'s multi-table check cannot be exercised.~~ **That claim was
  wrong** and a third sweep pass caught it. It confused *orphan* with *linked*:
  the check counts `WHERE segment_description_id = ?`, and an ordinary chain
  through the manager's API sets that column on all seven tables. Now covered by
  a test for all seven plus a parametrised one proving each non-vision table
  blocks on its own.
- The dedupe can now merge and delete rows it previously left alone. Blast
  radius on the live database today is zero (25 week rows, all Monday-aligned,
  no same-week groups), and every merge is logged with survivor and deleted ids.
- Two adjacent pre-existing issues the sweep flagged and I did not fix:
  `_repoint_children` moves rows before discovering a blocking table and then
  reports 0 repointed; `AppSettings.save()` swallows exceptions and prints.

## Next agent actions

- Batch 2 (the project-link model) is next in the plan.
- Consider a third sweep pass over 5cdb7a9 before Batch 2 starts.
