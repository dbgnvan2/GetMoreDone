# Implementation plan — the timer window's three session endings

Date: 2026-08-25
Status: **approved; in progress.** Revised 2026-08-25 after the user tested the
flow and after step 1 failed to reproduce T1 as written — see "What step 1
actually found".

## The report

> On the timer window "Save Related - Close Timer" appears to do nothing — no
> related record and the screen doesn't close. Cancel seems to work. "Complete &
> Open Follow-up" does open Next Steps, but it's hidden behind the timer window
> that should have closed.

## What the database says actually happened

From the live `getmoredone.db`, item `a5e2082c` ("BTA - Create Workplow - post
processing video"), the morning of 2026-08-25:

| Time | Row |
|---|---|
| 08:00:53 → 08:02:00 | `work_logs` row written. 0 min, `note` NULL, `deliverable_snapshot` = "sign off that the files are complete", `deliverable_completed` = 0 |
| 08:07:03 | item → `completed`; child `c9f8a008` created, start/due 2026-08-26 |
| 08:07:59 | child updated from the Next Steps dialog |

That is the signature of `save_and_close_action` followed, five minutes later
and **from the same still-open window**, by `continue_action`. So:

- Save Related **did** write its record. It did not close the window.
- The Continue that followed wrote **no** work log.

A second item, `4a66daf8` at 08:15, shows `continue_action` again — completed
plus a child dated 2026-08-26 — with no `work_logs` row for it at any point. I
cannot account for that one from the data alone; it is consistent with a session
whose log had already been written, or one that never started. That it is
unaccountable is itself finding **T4** below.

## What step 1 actually found

The plan's first task was to reproduce the close failure and read its traceback
rather than guess. There is no traceback. `save_and_close_action` destroys the
window correctly in all three configurations that could be built
(`tests/test_timer_session_endings.py`, commit `d60ff38`): with the real
`CompletionNoteDialog`, launched from the Action Item editor with its real
`on_close`, and with `-topmost` genuinely set past conftest's patch.

A stacked second timer window reproduced the database state and was wrong. The
user then tested the flow and reported the deciding detail:

> the Next Step Note pops and then is hidden. **No buttons work on the Timer
> window.** When I "red dot" close the window, the Next Step Note appears.

That is the modal's `grab_set()`, held by a dialog behind the always-on-top
timer. **T5 is the defect**, and it is also the whole of T1 — Save Related was
never failing to close, it was never getting past its own modal. T1 is folded
into T5; what remains of it is the false "safe to ignore" on a failed
`destroy()`, which is worth removing on its own terms but was never this bug.

The stacked-window finding stands as a real defect in its own right (nothing
guards a second timer on one item, and they open at identical coordinates) but
is **not** what was reported. It goes to `BACKLOG.md`, not into this batch.

## Findings

**T1 — Save Related does not close the window.**
`cancel_action` and `save_and_close_action` end at the same `_close_and_return()`
(`timer_window.py:1054`). Cancel closes; Save Related does not. The only
difference between the two paths is that Save Related opens the
`CompletionNoteDialog` modal first. The work log committed, so execution reached
`_close_and_return()`, and every failure point past that is inside a `try` that
swallows — ending at the `destroy()` itself:

```python
except Exception as e:
    # Ignore errors during destruction (e.g., customtkinter scaling tracker race condition)
    print(f"[DEBUG] Window destruction completed with minor error (safe to ignore): {e}")
```

`timer_window.py:1344`. "Safe to ignore" is false: if `destroy()` raised, the
window is still on screen and the code continues as though it closed. **The
mechanism is not yet proven** — the traceback went to the terminal running
`run.py` (PID 1136) and is not recoverable from here. Step 1 of the work is to
reproduce it and read it, not to guess.

**T2 — the follow-up gets tomorrow's dates.**
`NextStepsDialog` defaults both entries to tomorrow
(`timer_window_dialogs.py:352`), and `continue_action`'s skip branch computes
`increment_date(..., 1)` (`timer_window.py:1189`). Both children created this
morning are dated 2026-08-26. Requirement: **the original Action Item's own
start and due dates**, carried across unchanged.

Note that `continue_action` already builds `new_item` with
`start_date=item.start_date, due_date=item.due_date` — and then overwrites both,
either from the dialog or from the `+1` skip branch. The fix is to stop
overwriting them, not to compute a new date.

**T3 — Continue lands on the wrong item.**
`continue_action` step 7 opens the editor for the *new* item
(`timer_window.py:1226`). Requirement: return to the **original** Action Item.

**T4 — a session ending can write nothing and say nothing.**
`save_work_log` returns early when `start_timestamp` is falsy, and only warns if
Done was pressed (`timer_window.py:1252`). Every other ending goes quiet. This is
why `4a66daf8` cannot be explained.

**T5 — modals open behind the always-on-top timer.**
The timer sets `-topmost` at construction and never drops it
(`timer_window.py:141`). `raise_above_parent` fires one `lift()` at +10ms with no
retry (`timer_window_dialogs.py:19`). Yesterday's fix `b748453` is demonstrably
not holding — the user watched Next Steps open behind the timer today.

## Decisions taken (from the user, this session)

- `work_logs` stays a write-only table. No new UI.
- **The Next Steps dialog is removed** from Complete & Create Follow Up. The
  follow-up is created with `Add your next steps and set the dates and priority`
  as its description, and its editor is opened so the user fills it in there.
  (The user wrote "priorty"; spelled correctly here, as it is on-screen text.)
- The follow-up **inherits the original Action Item's start and due dates**.
  Confirmed after I raised that this can create a follow-up already past its due
  date. That is the intended behaviour.
- **Complete & Create Follow Up ends on the follow-up's editor.** The original's
  editor stays open behind it. This supersedes the earlier "return to the
  original", which the user revised while testing.
- Button renamed to **"Complete & Create Follow Up"**.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| T5.1 | A modal opened over the timer leaves the timer **not** topmost while it is up | `tests/test_timer_session_endings.py::test_t51_a_modal_drops_the_timers_always_on_top` |
| T5.2 | The timer's topmost is restored once the modal closes | `::test_t52_the_timer_is_topmost_again_afterwards` |
| T5.3 | Restored even when the modal's handler raises | `::test_t53_topmost_is_restored_when_the_ending_fails` |
| T5.4 | Every timer modal goes through the same helper — no sibling left unhardened (P5) | `::test_t54_every_timer_modal_suspends_the_parents_topmost` |
| T1.1 | `save_and_close_action` leaves `winfo_exists()` false (already green; kept as the regression floor) | `::test_t11_save_related_closes_the_window_after_a_real_modal` |
| T1.2 | A `destroy()` that fails is reported, not swallowed as "safe to ignore" | `::test_t12_a_failed_destroy_is_reported_not_swallowed` |
| T2.1 | The follow-up carries the original's start and due dates unchanged — no `+1` shift | `::test_t21_the_followup_keeps_the_items_dates` |
| T2.2 | An original dated in the past yields a follow-up with those same past dates | `::test_t22_a_past_dated_item_yields_a_past_dated_followup` |
| T2.3 | The follow-up's description is the prompt, not a copy of the original's notes | `::test_t23_the_followup_description_is_the_prompt` |
| T3.1 | No `NextStepsDialog` is constructed anywhere in the ending | `::test_t31_the_next_steps_dialog_is_gone` |
| T3.2 | The ending opens the **follow-up's** editor, carrying `vps_manager` | `::test_t32_the_followup_editor_opens_with_a_vps_manager` |
| T3.3 | The work log is written, the original completed, the child created | `::test_t33_continue_writes_log_completes_original_creates_child` |
| T4.1 | A session ending that writes no work log logs why | `::test_t41_a_silent_ending_says_so` |
| T6.1 | The button reads "Complete & Create Follow Up" | `::test_t61_the_button_says_what_it_does` |

## Order

1. ~~Reproduce T1.~~ Done — see above. T1 folded into T5.
2. **T5** — suspend the timer's `-topmost` for the life of every modal.
   The existing `raise_above_parent` fights the flag with `lift()`; dropping the
   flag removes the fight. Both are kept: the drop is the fix, the lift is belt.
3. **T4** — the silent-ending log. Small, and it makes the rest observable.
4. **T2 + T3** — dates, description prompt, dialog removal, editor target.
5. **T6** — the rename.
6. **T1.2** — the false "safe to ignore".
7. Cold review pass over the whole range, then `/csdp`.

## Risks and things I cannot promise

- **T5 is now testable, where the stacking order was not.** The fix is "the
  parent is not topmost while a modal is up", and topmost is a flag that can be
  read back. conftest neuters `attributes('-topmost', ...)` on all four window
  classes, so the tests set and read it through `window.tk.call("wm", ...)`,
  past the patch in both directions — otherwise the test would be measuring
  conftest, which is the mistake that let `b748453` ship looking fixed.
- **Stacking order itself remains unverifiable from Tk**, so "the dialog is
  visibly in front" stays human-verified. What is asserted is the mechanism that
  makes it so.
- **T2 creates overdue follow-ups by design.** Inheriting the original's dates
  means a follow-up off a late item is born late. Raised and confirmed; recorded
  here so it does not get "fixed" by a later pass that reads it as a bug.
  `NextStepsDialog.save` rejects due < start (`timer_window_dialogs.py:445`) —
  that validation is untouched, and an original with due < start would be
  refused. No such row exists today; the plan does not add a migration for it.
- ~~**The button label.**~~ Approved: **"Complete & Create Follow Up"**.
- **`NextStepsDialog` becomes dead code.** Removing the class is a bigger diff
  than this batch needs and it has its own tests; it is left in place, unused,
  and logged in `BACKLOG.md`. T3.1 asserts the *ending* no longer builds one.

## Adjacent issues found, not fixed

- **Nothing guards a second timer window on one item.** All four entry points
  construct one unconditionally, and `setup_window` puts every timer at the same
  saved `timer_window_x/y`, so they stack exactly. Two timers on one item can
  each write a work log for the same stretch of clock. Found while chasing T1,
  reproduced in `test_t14_two_timers_on_one_item_reproduce_the_reported_symptom`
  — and it is **not** the reported bug. Backlogged, not fixed here.
- `TimerWindow` has no `vps_manager`, so the editor it opens
  (`timer_window.py:1226`) is built without one, while every list screen passes
  `self.app.vps_manager`. Weekly-tactic features degrade silently in an editor
  reached through the timer. T3 needs this plumbed through all four
  `TimerWindow(...)` call sites regardless, so it will be fixed as part of T3
  rather than left — noted here because it is a pre-existing defect, not
  something T3 introduced.
- `tests/test_reward_protocol_timer.py:1649` asserts the work log and the
  refresh callback but never that the window closed, and stubs out the modal
  that is the only difference between Save Related and Cancel. The bug had no
  way to fail a test. T1.1 replaces that gap; the existing test stays.
- `_show_error_dialog` (`timer_window.py:467`) uses `tkinter.messagebox`, which
  under the always-on-top timer would itself open behind it — an error the user
  cannot see, blocking on a grab they cannot reach. Same family as T5. Not in
  this batch.
