# Handoff Note

- Date: 2026-08-25
- Agent: Code
- Topic: backlog-clearance + dated follow-up titles

## Summary

The five items deferred out of the timer-endings batch, plus the dated
follow-up title the user asked for. Plan and acceptance criteria in
`docs/implementation_plan_2026-08-26_backlog_clearance.md`.

**B0 — dated titles.** Two follow-ups of one item were indistinguishable: same
inherited dates, same prompt description, same title. The title now carries the
day the follow-up was made — `"Draft the report - Follow up 08-26"` — because
that is the only thing that differs between them. The stamp is replaced rather
than appended, and the strip is anchored so an item legitimately called
"Follow up 08-26 with Legal" keeps its name.

**B1 — the follow-up landed unfiled from its project.** Two places build an item
out of an existing one and they disagreed about what "out of" means:
`create_followup_item` inherited the weekly lineage, project links and item
links; the timer's ending built its row inline and inherited none of them.
`inherit_project_links`' own docstring names the timer's path as a case it
covers, and nothing on that path ever called it. One shared helper now.

**B2 — a second timer on one item.** All four openers go through
`TimerWindow.open_for`.

**B3 — a window that did not close now changes what happens next.**
`_cleanup_and_destroy` returns the answer, and the ending lowers a stuck timer
before raising the follow-up's editor.

**B4 — `NextStepsDialog` deleted.**

**B5 — `tkinter.messagebox` neutralised for the test run.** It was the hole in
the guard that already silenced `grab_set`, `lift`, `focus_force` and
`-topmost`.

## Files changed

- `src/getmoredone/screens/timer_window.py`, `timer_window_dialogs.py`
- `src/getmoredone/db_manager.py` — `inherit_derived_item_context`
- `src/getmoredone/screens/{today,upcoming,all_items,item_editor}.py`
- `conftest.py`, and tests in `test_timer_session_endings.py`,
  `test_weekly_tactic_completion.py`, `test_tk_offscreen.py`,
  `test_item_editor.py`, `test_reward_protocol_timer.py`
- `BACKLOG.md`, this note, the plan

## Verification

- Command: `GETMOREDONE_NO_MAPPED_WINDOWS=1 pytest -q`
- Result: PASS — exit code 0, 1560 passed, 7 skipped.
- Forty-one mutations across five source files, all red, all restored.

Four mutations that stayed **green** were treated as findings against the test,
not as a pass:

- `test_b22` passed against "hand back ANY live timer" in a full-file run and
  failed when run alone — the module-level registry leaked between tests (P8).
  Fixed with an autouse fixture that clears it.
- `test_b23` could not see a missing release, because the liveness check
  downstream hides it. It asserts the registry entry directly now.
- `test_b24` could not see the liveness check removed, because `deiconify()` on
  a dead window raised into the same `except`. `open_for` was restructured so
  liveness is its own guarded question.
- B5's restore-on-teardown is unobservable within a run and is kept anyway, with
  that stated in the code.

One mutation **hung** rather than failing: removing the messagebox patch
entirely stopped a run for ten minutes. That is the defect demonstrating itself.

## Review

Four `learning-qa` passes. Each of the first three found a defect inside the
previous pass's fixes — the pattern P26 documents, observed three times running.

| Pass | Range | Findings | Worst |
|---|---|---|---|
| 1 | the 12-commit batch | 9 | 2 high |
| 2 | the 3 fix commits | 8 | 1 high |
| 3 | the 3 fix commits | 5 | 1 high |
| 4 | the 2 fix commits | 2 | none ≥ medium — **stop** |

The high findings, in order:

- **Two fixes from this batch were defeating each other.** `_cleanup_and_destroy`
  released the item from the registry four lines *before* attempting `destroy()`,
  and never put it back when the destroy failed — so B2's guard was void on
  exactly the path B3 was written for.
- **`open_for` discarded every argument on reuse**, including the editor's
  `on_close`. That callback is what reloads the editor's fields, so without it
  the editor kept stale values and saving from it overwrote what the timer had
  just written — the clobber `_current_timer_field_values` exists to prevent.
- **The fix for one clobber installed its mirror image.** Refreshing `self.item`
  without the notes box left `_save_notes_to_item` comparing a fresh description
  against a stale textbox, so every ending wrote the old text back over the
  editor's save. Silent data loss, introduced by this batch, on the flow the fix
  was written for.

**One six-line branch was wrong three times.** `open_for`'s error path: first it
fell through and built a duplicate timer at identical coordinates; then it
destroyed the live window, losing a running session's work log — measured at 17
minutes elapsed and zero work logs; now it logs and returns the live window. The
fourth pass's recommendation to stop rests on the branch's *shape* rather than on
having been reviewed: it makes no call out, constructs nothing, destroys nothing,
and can only return an object `winfo_exists()` affirmed two lines earlier. There
is no action left in it that can lose anything.

Findings below medium went to `BACKLOG.md` rather than into the loop — eight of
them across the four passes.

## Risks / Known gaps

- **Two follow-ups of one item on the same day still collide.** Accepted: the
  user does not expect more than two follow-ups, "an Action Item is supposed to
  be a discrete chunk of work".
- **B2 changes a UI contract on four screens.** `ui-regression.md` applies and a
  failure-pattern sweep does not cover it. Not run.
- **The UI-contract review has still not been run.** Every pass above is the
  failure-pattern family. B2 changed the opener on four screens and
  `ui-regression.md` covers that; three of the four sweeps said so explicitly in
  their NOT COVERED line.
- Nothing verifies the dialog is *visibly* in front. Still needs a human.

## Next agent actions

- `/csdp` — this batch is committed and unpushed, and has had no sweep.
- The older backlog (2026-08-24 and earlier, plus Known Bugs / Feature Requests
  / Enhancements / Technical Debt) is untouched and was explicitly out of scope.
