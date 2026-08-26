# Implementation plan — clear the 2026-08-25 backlog + dated follow-up titles

Date: 2026-08-25
Status: **awaiting approval — no code written**

## Scope question I need answered first

`BACKLOG.md` has 20+ sections going back to 2026-08-19, plus Known Bugs, Feature
Requests, Enhancements and Technical Debt. "Fix items in backlog" cannot
reasonably mean all of it. **This plan covers the five items dated 2026-08-25** —
the ones deferred out of the batch just pushed, which are the ones I told you
were backlogged. The older sections are untouched and listed at the end so you
can say which, if any, to add.

## B0 — Dated follow-up titles

Requested: `"FollowUp - MMDD"` on the title.

- Suffix becomes `" - FollowUp - MMDD"`, e.g. `"Draft the report - FollowUp - 0826"`.
- **MMDD is the day the follow-up is created, not the inherited date.** The
  inherited dates are identical across every follow-up of one item — that is the
  whole reason the titles collide — so dating by them would change nothing.
- A follow-up of a follow-up replaces the previous suffix rather than stacking:
  `"Draft the report - FollowUp - 0827"`, not `"… - FollowUp - 0826 - FollowUp - 0827"`.
- `FOLLOW_UP_SUFFIX` and the once-only rule from the last batch are replaced by a
  regex strip of `" - FollowUp - \d{4}"`.
- **Known limit:** two follow-ups off the same item on the *same day* still
  collide. Continuing the same work twice in one day is not what the button is
  for, and a counter would make the common case uglier. Flagged, not solved.

## B1 — The follow-up lands unfiled from its project

`continue_action` builds its follow-up with a hand-rolled `ActionItem(...)`, so
it skips `_inherit_weekly_lineage`, `inherit_project_links`, and the item-link
copy that `create_followup_item` does. Time that follow-up later and
`session_board_id` resolves to nothing — no reward protocol, no counter, no
phase, no signal.

**Not** by routing `continue_action` through `create_followup_item`: that always
sets `parent_id = source`, while `continue_action` deliberately makes a sibling
when the source already has a parent. Routing through it would silently change
the hierarchy.

Instead: extract the three inheritance steps out of `create_followup_item` into
one helper and call it from both. Two copy paths that must agree, made into one
piece of code rather than two lists that drift (P5 — they already had).

## B2 — A second timer window on the same item

Nothing prevents it at any of the four openers, and `setup_window` puts every
timer at the same saved coordinates, so the second lands exactly on the first.
Each can write its own work log for the same stretch of clock.

- A module-level registry in `timer_window.py`, item id → live window.
- One `TimerWindow.open_for(parent, db_manager, item, ...)` classmethod: returns
  the existing window (deiconified and lifted) if one is live, otherwise builds
  one. Entry removed on destroy.
- **All four openers call it** — `item_editor`, `today`, `upcoming`,
  `all_items`. One test per opener that the second call returns the first window
  (P25: a fix at the class says nothing about the callers above it).

## B3 — The surviving-window detection has no consumer

`_cleanup_and_destroy` logs when the window is still there after `destroy()` and
returns nothing, so all four callers proceed identically. In `continue_action`
the next step opens the follow-up's editor, which lands behind a timer that did
not close. Return a bool; `continue_action` acts on it.

## B4 — `NextStepsDialog` is dead code

No caller since the last batch. Delete the class. Three test references need
updating, including `test_t54`'s exact-set assertion and `test_t31`, which exists
to prove the ending does not build one — that test becomes redundant and goes
with it, since the class it names will not exist.

## B5 — A failing test on an ending path hangs the run

`conftest.py` silences `grab_set`, `lift`, `focus_force` and `-topmost` but not
`tkinter.messagebox`. Every timer ending wraps its body in `except Exception` and
calls `_show_error_dialog`, so a test that raises inside one opens a real
blocking modal and the run stops until someone clicks it. Measured: a two-minute
hang during yesterday's re-sweep.

**This is the riskiest item here.** There are 147 `messagebox` call sites in
`screens/` and 15 tests that already patch it themselves. Neutralising it
suite-wide changes the behaviour of every test that reaches one.

- Autouse session fixture patching the `show*`/`ask*` functions to record and
  return a safe default (`None` / `False`), never to display.
- A `messageboxes` fixture exposing the recorded calls, so a test can assert
  what was shown instead of patching its own.
- The 15 self-patching tests keep working — a local `monkeypatch.setattr` still
  wins over the session patch. Verified per test, not assumed.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| B0.1 | Follow-up title is `"<original> - FollowUp - MMDD"` with today's MM/DD | `tests/test_timer_session_endings.py::test_b01_the_followup_title_carries_the_day_it_was_made` |
| B0.2 | A follow-up of a follow-up replaces the suffix, never stacks | `::test_b02_the_dated_suffix_does_not_stack` |
| B0.3 | Three consecutive days give three distinct titles | `::test_b03_consecutive_days_are_distinguishable` |
| B1.1 | The follow-up keeps the original's project link | `::test_b11_the_followup_stays_filed_under_its_project` |
| B1.2 | …its weekly lineage | `::test_b12_the_followup_keeps_its_weekly_lineage` |
| B1.3 | …and its item links | `::test_b13_the_followup_keeps_its_links` |
| B1.4 | Both copy paths use one helper — no second field list | `::test_b14_both_followup_paths_inherit_through_the_same_helper` |
| B2.1 | A second `open_for` on a live item returns the first window | `::test_b21_a_second_timer_returns_the_first` |
| B2.2 | One test per opener: the screen calls `open_for`, not the constructor | `::test_b22_<screen>_opens_through_the_registry` ×4 |
| B2.3 | The registry entry is released on destroy | `::test_b23_closing_a_timer_frees_the_item` |
| B3.1 | `_cleanup_and_destroy` returns False when the window survives | `::test_b31_cleanup_reports_whether_it_closed` |
| B3.2 | `continue_action` does not open the editor behind a live timer | `::test_b32_the_editor_waits_for_a_timer_that_did_not_close` |
| B4.1 | `NextStepsDialog` no longer exists | `::test_b41_the_dead_dialog_is_gone` |
| B5.1 | A `messagebox` call in a test records instead of displaying | `tests/test_tk_offscreen.py::test_b51_messagebox_never_blocks_a_run` |
| B5.2 | A test raising inside a timer ending completes rather than hanging | `::test_b52_a_failing_ending_does_not_hang_the_run` |
| B5.3 | The 15 tests that patch messagebox themselves still pass | full suite |

## Order

1. **B0** — smallest, self-contained, and the one you asked for by name.
2. **B4** — deleting dead code first means B1/B3 are not written around it.
3. **B1** — the helper extraction; highest user impact of the four.
4. **B3** — small, and B2 depends on the window lifecycle it touches.
5. **B2** — largest; all four entry points.
6. **B5** — last and separately committed, because it is the one that can break
   unrelated tests, and a bad B5 should not force a revert of B0–B4.
7. Two `learning-qa` passes as before: the full range, then the fix commits.

## Risks

- **B5 can break tests I have not read.** 147 call sites. If the full suite goes
  red in a way that is not a one-line fixture fix, I will drop B5 back to the
  backlog rather than chase it into a large diff, and say so.
- **B2 changes a UI contract on four screens.** The `ui-regression.md` standard
  applies and a failure-pattern sweep does not cover it.
- **B0's same-day collision remains.** Stated above, not solved.
- Neither this plan nor its sweeps cover whether the dialog is *visibly* in
  front. That still needs you in the running app.

## Not in scope — the older backlog

Untouched, listed so you can add any: `test_rm3d` order-dependence (08-24),
below-medium from the window-leak sweep (08-24, 8 items), reward-protocol
below-medium + cold-pass findings (08-24, 2 sections), rename-safe-links
low-severity (08-20, 6 sections), test-suite remediation leftovers (08-20), the
retired multi-agent workflow described in four places (08-20), Google auth
adjacent items (08-20), item-editor project-link open items (08-19), the
unreadable-week-start item (08-19), Other known items, Known Bugs, Feature
Requests, Enhancements, Technical Debt.
