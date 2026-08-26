# Implementation plan — session count and total time on the Project record

Date: 2026-08-25
Status: approved to implement without a second gate ("proceed to plan and then
just implement it")

## What was asked

> Display a Time Record "count" and Total Time Value on the Project record. I
> think you are doing the count in order to do the "celebration" event, right?

Half-right, and the half that is wrong is why this is a feature rather than a
display change. `ProjectBoard.savor_count` counts **completed deliverables**
(Done presses) and exists only so `phase_for()` can pick the reward phase —
under 15 is "wiring", 15+ is "maintaining". It is incremented in exactly one
place, `save_work_log`, and only when a reward decision exists. It is not a
session count and carries no time at all.

What is being asked for is derivable but stored nowhere: `work_logs` has
`item_id` and `minutes`, and `project_board_items` links items to boards.

## Design

**Derive, do not store.** A second counter on `project_boards` would be a status
field that can disagree with the rows it summarises — the failure this repo has
already been bitten by (P6). Both numbers are a query over `work_logs`.

**Scalar subqueries, not another JOIN.** `get_project_boards` already builds
`linked_item_count`, `open_item_count` and `completed_item_count` in one grouped
query. Adding `LEFT JOIN work_logs` there would fan out one row per work log per
item, and while `COUNT(DISTINCT pbi.item_id)` survives that,
`SUM(CASE WHEN ai.status = 'open' ...)` does **not** — every open item would be
counted once per session logged against it. That is the defect to avoid, and it
would be invisible on any board whose items have zero or one session each. Two
correlated scalar subqueries in the SELECT list cannot fan out.

**What counts as the project's time.** Every work log against every item linked
to the board — completed items and follow-ups included. Follow-ups inherit their
project link, so a run of work continued across days accumulates against the
project it belongs to.

**Where it shows.** The detail pane's meta block, which is the Project record
view. The cards are already dense; a line there is a separate decision and is not
in this change.

**Formatting.** `750` reads worse than `12h 30m`. A `format_minutes` helper, new,
because the repo has none.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| PT1.1 | `get_project_boards` returns `session_count` and `total_minutes` per board | `tests/test_project_time_totals.py::test_pt11_a_board_reports_its_sessions_and_minutes` |
| PT1.2 | Both are 0 for a board with no sessions, never NULL | `::test_pt12_a_board_with_no_sessions_reports_zero` |
| PT1.3 | Sessions on items of *other* boards are not counted | `::test_pt13_only_this_boards_items_count` |
| PT1.4 | **The new columns do not corrupt the existing counts** — an item with several sessions must not inflate `open_item_count` / `completed_item_count` / `linked_item_count` | `::test_pt14_the_existing_counts_survive_multiple_sessions_per_item` |
| PT1.5 | Time on a completed item and on a follow-up still counts toward the project | `::test_pt15_completed_items_and_follow_ups_still_count` |
| PT2.1 | `format_minutes` renders 0, minutes-only, hours-only and mixed | `::test_pt21_minutes_render_the_way_a_person_reads_them` |
| PT3.1 | The detail pane shows both values | `::test_pt31_the_project_record_shows_the_session_count_and_total` |

## Order

1. `format_minutes` + its test.
2. The two subqueries in `get_project_boards` + PT1.1–PT1.5, PT1.4 first — it is
   the one that can silently corrupt data already on screen.
3. The detail-pane line + PT3.1.
4. Docs, then `/csdp`.

## Risks

- `get_project_boards` is read by `drag_schedule.py` and
  `item_editor_project_dialog.py` as well as the boards screen. Adding columns is
  additive, but PT1.4 exists because *changing* the existing ones would not be.
- A project with many items and many sessions runs two correlated subqueries per
  board. At this data scale that is nothing; noted rather than measured.
- This is a new display on one surface. UI-contract regression across the other
  screens is not covered by the failure-pattern sweep that will follow.
