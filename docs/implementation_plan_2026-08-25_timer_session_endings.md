# Implementation plan — the timer window's three session endings

Date: 2026-08-25
Status: **awaiting approval — no code written**

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
morning are dated 2026-08-26. Requirement: **today**, start and due.

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

- `work_logs` stays a write-only table. No new UI. Notes reach the Action Item
  description already; time reaches the item already.
- Follow-up **start and due are both today**.
- The Next Steps dialog **stays**; only its date defaults change.
- "Return to the original Action Item" applies from **every** entry point —
  the Action Item editor, Today, Upcoming, All Items.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| T1.1 | `save_and_close_action` leaves `winfo_exists()` false, with the **real** `CompletionNoteDialog` opened and dismissed — not a stub | `tests/test_timer_session_endings.py::test_t11_save_related_closes_the_window_after_a_real_modal` |
| T1.2 | A `destroy()` that fails is reported, not swallowed as "safe to ignore"; the window is not treated as closed | `::test_t12_a_failed_destroy_is_reported_not_swallowed` |
| T1.3 | `cancel_action` still closes (no regression) | `::test_t13_cancel_still_closes` |
| T2.1 | `NextStepsDialog` opens with start **and** due = today | `::test_t21_next_steps_defaults_to_today` |
| T2.2 | Skipping the dialog gives the follow-up start = due = today | `::test_t22_skipped_next_steps_dates_the_followup_today` |
| T3.1 | After Continue, the editor left in front is the **original** item's, from the Action Item editor | `::test_t31_continue_returns_to_the_original_editor` |
| T3.2 | Same from Today / Upcoming / All Items, where no editor is open behind — one test per surface (P25) | `::test_t32_continue_opens_the_original_editor_from_<screen>` |
| T3.3 | Continue still writes the work log, completes the original, and creates the child | `::test_t33_continue_writes_log_completes_original_creates_child` |
| T4.1 | A session ending that writes no work log logs why | `::test_t41_a_silent_ending_says_so` |
| T5.1 | Every timer modal ends up above the timer, proven by stacking order, not by the `-topmost` attribute value | `::test_t51_modals_sit_above_the_timer` — **see risk below** |

## Order

1. **Reproduce T1 and read the traceback.** A pytest that builds a real
   `TimerWindow`, starts and stops it, opens the **real** `CompletionNoteDialog`
   and dismisses it from an `after()` callback, then asserts the window is gone.
   Under `pytest`, per the standing rule against standalone window scripts.
   Nothing else is written until this test is red for the right reason.
2. **T1 fix**, informed by (1). Includes removing the false "safe to ignore".
3. **T4** — the silent-ending log. Small, and it makes the rest observable.
4. **T2** — date defaults. Self-contained.
5. **T3** — return-to-original. Largest change; needs `vps_manager` plumbed into
   `TimerWindow` (see adjacent issues).
6. **T5** — only if (1) shows the stacking is what breaks the close. Otherwise it
   is a separate batch: it is a different failure family and yesterday's attempt
   at it already regressed once.
7. Cold review pass over the whole range, then `/csdp`.

## Risks and things I cannot promise

- **T5.1 may not be testable.** Tk on macOS gives no reliable read of window
  stacking order; `wm attributes -topmost` reports the flag, not the position,
  and asserting the flag is exactly the mistake that let `b748453` ship looking
  fixed. If I cannot find a behavioural assertion I will say so and mark T5 as
  human-verified rather than write a test that cannot fail (P27).
- **T2 and weekends.** "Today" is taken literally. `increment_date` respects the
  include_saturday / include_sunday settings; today does not. If you start a
  timer on a Saturday with weekends off, the follow-up will still be dated
  Saturday. Say if that is wrong.
- **The button label.** "Complete & Open Follow Up" will no longer open the
  follow-up — it returns to the original. Renaming it is a UI-contract change I
  have not assumed. Proposal: "Complete & Create Follow Up".

## Adjacent issues found, not fixed

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
