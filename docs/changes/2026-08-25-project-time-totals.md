# Handoff Note

- Date: 2026-08-25
- Agent: Code
- Topic: project-time-totals

## Summary

The Project record now shows how much work has gone into it:

```
Time: 12 sessions | 8h 45m
```

Every timer session against every action item filed under the project, completed
items and follow-ups included — a follow-up inherits its project link, so work
continued across days accumulates where it belongs.

This is **not** `ProjectBoard.savor_count`, which the user reasonably assumed it
might be. That counts *completed deliverables* (Done presses) so `phase_for()` can
pick the reward phase, and carries no time at all.

## Files changed

- `src/getmoredone/db_manager_project_boards.py` — two correlated subqueries in
  `get_project_boards`, plus `get_project_time_totals(board_id)` for the pane's
  single-board fallback.
- `src/getmoredone/utils/duration.py` — new, `format_minutes`.
- `src/getmoredone/screens/project_boards.py` — `project_time_line(row)` and the
  detail-pane line.
- `tests/test_project_time_totals.py` — new, 18 tests.
- `docs/USER_GUIDE.md`, the plan, `BACKLOG.md`.

## Verification

- Command: `taskpolicy -b ./venv/bin/python -m pytest -q`
- Result: PASS — exit code 0, 1595 passed, 2 skipped.
- Seventeen mutations, all red.

## Review

One `learning-qa` pass: 2 medium, 4 low.

- **The fallback path printed a fabricated zero.** `_render_detail` re-fetches a
  board with `SELECT *` when it is not in the filtered list — reachable by
  unticking a status filter while that board is selected — and that row has
  neither aggregate, so the line read `Time: 0 sessions | 0m`. Every other field
  on that path degrades to blank, an honest "unknown"; this was the one asserting
  a number it could not support (P6). It returns `None` now, and the fallback asks
  for the totals so the line does not simply vanish.
- **Two of my tests could not fail.** Both rebuilt the pane's f-string inside the
  test and asserted against their own arithmetic. The reviewer proved it: inverting
  the pluralisation in production, and rendering `linked_item_count` instead of
  `total_minutes`, each left all fourteen tests green. The line is a pure function
  now and the tests call it with a real row.

Cleared by the sweep with evidence: the GROUP BY is sound (both subqueries
correlate on the grouping key, `EXPLAIN QUERY PLAN` shows indexed correlated
scalar subqueries, no fan-out); `minutes` is `INTEGER NOT NULL` with exactly one
writer in the repo; `project_board_items` has a composite primary key so an item
cannot be double-linked to one board; and the two other readers of
`get_project_boards` take named keys only.

A re-sweep of those fixes then found two more, both guard strength rather than
shipped behaviour — the code was correct and the reviewer verified that
empirically. `pt41` claimed to pin two implementations against each other but had
a single-board fixture, so deleting the new query's board filter entirely left
every test green; the same file already records that lesson for the grouped query
one method earlier. And the two AST guards over `_render_detail` passed with their
calls wrapped in `if False:` — they proved a call node existed, not that it was
reachable (P21), on a path that is already conditional (P13). Both are real
screens now, reading what the pane put on screen.

## Risks / Known gaps

- **Failure-pattern sweep only.** Not covered: logic correctness beyond the SQL,
  UI-contract regression across the other screens, concurrency. The plan flagged
  the UI one before the sweep did.
- The board **cards** do not show the Time line — detail pane only. Deliberate;
  the cards are already dense.
- Three low findings deferred to `BACKLOG.md`: shared items count in full on every
  board, sub-minute sessions count as zero, and `format_minutes` clamps negatives.

## Next agent actions

- Nothing outstanding. The user has not yet exercised this in the running app.
