# Handoff Note

- Date: 2026-08-25
- Agent: Code
- Topic: timer-session-endings

## Summary

The timer window's session buttons appeared dead. Reported as "Save Related -
Close Timer appears to do nothing" and "Complete & Open Follow-up does open Next
Steps, but it's hidden behind the timer window".

The cause is a modal holding `grab_set()` behind its always-on-top parent: it
takes every click while showing the user nothing, so the timer underneath looks
unresponsive. The user's own test named it — *"No buttons work on the Timer
window. When I 'red dot' close the window, the Next Step Note appears."*

`raise_above_parent` had tried to win that fight by re-asserting `-topmost` on
the dialog and lifting it. That is two windows both claiming the top, and it
lost: the timer sets `-topmost` at construction and never drops it. The fix
drops the **parent's** flag for the life of the modal and restores it on the
dialog's `<Destroy>`, which ends the argument rather than competing in it.

Alongside it, Complete & Create Follow Up was rebuilt to the user's spec: no
Next Steps dialog, the follow-up carries a prompt in its description and the
original item's own dates, and its editor is where the flow ends.

Corrected after a first pass: **"Complete" in that button's name is the timer
record, not the task.** The ending no longer calls `complete_action_item` — only
"Done" closes an Action Item — and the follow-up is titled
`"<original> - Followup"`. The correction carried a consequence the user did not
have to name: the pending state from a failed Done was deliberately carried into
this ending so it would record the completion, and an ending that now leaves the
item open must not do that, or the project counter advances for a task that is
still open. It is discarded here as `save_and_close_action` discards it.

## Files changed

- `src/getmoredone/screens/timer_window_dialogs.py` — `suspend_parent_topmost`,
  wired into all four dialogs that hold a grab (P5).
- `src/getmoredone/screens/timer_window.py` — Next Steps dialog removed from the
  ending; the Action Item is no longer completed; follow-up keeps the item's
  dates, gets `FOLLOW_UP_PROMPT` and a `" - Followup"` title suffix applied at
  most once; a failed Done is not counted by this ending; button renamed;
  `vps_manager` carried; a silent ending now logs why; a failed `destroy()` is
  checked against the window instead of called "safe to ignore".
- `src/getmoredone/screens/{item_editor,today,upcoming,all_items}.py` —
  `vps_manager` passed to `TimerWindow` from every opener.
- `tests/test_timer_session_endings.py` — new, 17 tests.
- `tests/test_reward_protocol_timer.py`, `tests/test_item_editor.py` — three
  tests the change invalidated, each with its reason recorded in the commit.
- `docs/USER_GUIDE.md`, `docs/action-timer-requirements.md`, `BACKLOG.md`,
  `docs/implementation_plan_2026-08-25_timer_session_endings.md`.

## Review

Two `learning-qa` passes, both against the full range rather than the parts I
thought needed it.

**First sweep** (17 commits): 11 findings, 3 high.

- **12.4 MB of binaries in history.** A `git add -A` had committed a PDF and a
  zip that were never part of this work; a later commit removed them from the
  tree, not from history. Pushing would have made them permanent on a branch
  shared between two machines. Stripped with `filter-branch` over the unpushed
  range; the resulting tree is byte-identical to the backup ref.
- **A guard that reported green over a live defect.** `test_t31` patched
  `NextStepsDialog` on `timer_window_dialogs`, but the defect resolved the name
  through `timer_window`'s own globals. I had "mutation-checked" it with a
  function-local import — a paraphrase, which is the P27 corollary exactly. It
  was green against a verbatim restoration of the defect.
- **The P5 sweep stopped at the file boundary.** `tkinter.messagebox` is a modal
  that grabs, and three of its four sites are the `except` handler of a timer
  ending — so the symptom this batch exists to remove was still live precisely
  where something has already gone wrong.

**Re-sweep** (the 4 fix commits): 4 more findings, every one inside code written
in response to the first sweep. The new AST guard had three blind spots, two
proved by mutation: it matched only dotted `messagebox.showerror` so a bare name
slipped past its exact-count assertion, it used `ast.walk` so a deferred call
inside the `with` counted as guarded, and it never compared the suspended window
to the `parent=` window.

Stopped there. The re-sweep's worst finding was medium-high, not high, and this
repo's budget is one further pass only after a high-severity finding — each fix
pass is new unreviewed surface, and one of the re-sweep's own findings was a
guard I had added an hour earlier.

## Verification

- Command: `GETMOREDONE_NO_MAPPED_WINDOWS=1 pytest -q`
- Result: PASS — exit code 0, 1533 passed, 7 skipped.
- Every new test mutation-checked with the verbatim original: twenty-six
  mutations across the two source files and conftest, all red, all restored
  green. Two mutations that stayed *green* were treated as findings against the
  test, not the code: `test_t31` (fixed) and an idempotency flag guarding a path
  Tk cannot reach (removed rather than left untestable).

## Risks / Known gaps

- **Stacking order itself is not asserted.** Tk gives no reliable read of it, so
  what the tests prove is the mechanism (the parent is not topmost while a modal
  is up), not the pixels. That the dialog is *visibly* in front needs a human.
  This is the one thing to check first in the running app.
- **conftest silences `grab_set` and `-topmost` for the whole run**, so the
  symptom cannot occur in a test at all. The T5 tests reach `wm attributes`
  through `window.tk.call` to get past that patch in both directions; the helper
  is safe past it because it can only lower the flag or restore what it read,
  asserted by `test_t53_a_parent_that_was_not_topmost_is_left_alone`.
- **Follow-ups inherit late dates.** An item already past its due date produces a
  follow-up already past its due date. Raised, confirmed as intended, pinned by
  `test_t22_a_past_dated_item_yields_a_past_dated_followup`.
- Five findings deferred to `BACKLOG.md`: the unguarded second timer window,
  `NextStepsDialog` now being dead code, the follow-up never inheriting its
  project links or weekly lineage, `_cleanup_and_destroy`'s surviving-window
  detection having no consumer, and a test that fails on an ending path hanging
  the run on a real modal.
- **Open, needs a decision:** an item continued on three consecutive days now
  produces three siblings all titled `"<original> - Followup"`, all with the
  same inherited dates and the same prompt description, all visible together in
  Today. Each ingredient was confirmed separately; the combination was not. A
  date or counter in the suffix would resolve it.

## Next agent actions

- One **cold** review pass over `fabc273..HEAD` — the diff and the range, not
  this note. Warm passes are spent: the batch has had two.
- The three fix commits are the least-reviewed code here; sweep them as their
  own range.
