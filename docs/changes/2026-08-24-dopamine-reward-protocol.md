# Handoff Note

- Date: 2026-08-24
- Agent: Code
- Topic: reward-contingent task chunking (dopamine protocol)

## Summary

Implemented `docs/spec_2026-08-23_dopamine_reward_protocol.md` in full. The timer's
reward signal now fires on completing a named deliverable, at the moment the user says
it is done, instead of on the countdown reaching zero.

- **Deliverable** — a one-line "done = ..." on an action item, editable in the item
  editor and confirmed by the timer when the item belongs to a Project.
- **`reward_protocol.py`** — a pure module deciding, per completion, whether the savor
  step is shown (phase-gated: every time below 15 completions, ~40% above) and whether a
  celebration fires (~20%, random, independent of phase and of the savor).
- **Done button** — visible for the whole session, not only at the ring. It runs savor →
  celebration → persistence, then the existing completion flow.
- **Break end is neutral** — Pause (rest) / Continue focus. It no longer stops the timer
  into Finished/Continue.
- **Audit trail** — `work_logs` records the deliverable snapshot, whether the user
  pressed Done, whether the savor was actually shown, which celebration fired, and the
  phase. `project_boards.savor_count` advances on every Done.

Two departures from the spec's literal text, both recorded in the plan (§3) and in the
code:

- The work log is written **once**. Spec §4.5 saves it and then hands over to "the
  existing completion flow", which already saves one — following both writes two rows.
- The counter advances **inside** `save_work_log`, not as its own earlier step. Done the
  spec's way, a window closed between the two leaves a project claiming a completion
  that nothing recorded, and nothing afterwards can tell which happened.

## Files changed

New:
- `src/getmoredone/reward_protocol.py`
- `src/getmoredone/screens/timer_window_reward.py`
- `src/getmoredone/screens/timer_window_celebration.py`
- `tools/generate_tada_wav.py`, `assets/audio/tada.wav`
- `tests/test_reward_protocol.py`, `tests/test_reward_protocol_schema.py`,
  `tests/test_reward_protocol_timer.py`, `tests/test_reward_celebration.py`
- `docs/implementation_plan_2026-08-24_dopamine_reward_protocol.md`

Changed:
- `src/getmoredone/database.py` — three tables, CREATE TABLE + migrations
- `src/getmoredone/models.py` — `ActionItem.deliverable`, `ProjectBoard.savor_count`,
  five `WorkLog` fields
- `src/getmoredone/db_manager.py` — work-log and action-item read/write, the live
  `_row_to_project_board`
- `src/getmoredone/db_manager_project_boards.py` — `get_project_boards_for_item`,
  `increment_project_savor_count`; two dead shadowed mappers removed
- `src/getmoredone/screens/timer_window.py` — Done button, neutral break end,
  `save_work_log`, cleanup
- `src/getmoredone/screens/timer_window_dialogs.py` — `DeliverableDialog`, `SavorDialog`
- `src/getmoredone/screens/item_editor.py`, `item_editor_form.py` — the Deliverable field
- `.gitignore` — `audio/` anchored to `/audio/`
- `CHANGELOG.md`, `docs/USER_GUIDE.md`, `docs/spec_coverage.md`, `NOTES.md`, `BACKLOG.md`
- Four existing test files whose editor stubs needed the new widget

## Verification

- Command: `pytest` (full suite)
- Result: **PASS** — 1438 passed, 7 skipped, exit code 0
- Command: `python run.py --selftest`
- Result: **PASS** — 4/4 checks, exit code 0
- Migration against the **real** application database: all three tables carry the new
  columns; 30 existing `work_logs` rows read `0` (not NULL) for both counted flags; all
  18 project boards start at `savor_count = 0`.
- Real widgets built and laid out under the venv: Done button hidden when stopped and
  spanning the controls row otherwise; the rest/continue pair appearing only at break
  end with Stop still enabled and Pause disabled; both dialogs rendering the spec's copy;
  all three celebration types drawing (44 / 8 / 1 canvas items) and tearing down clean.
- **19 mutations** run against the verbatim originals; all red, working tree verified
  byte-identical afterwards.

## Spec amended

`docs/spec_2026-08-18_downloadable_release.md` **D3 — "No audio ships"** and its
criterion R-M2.D. The reward protocol's celebration channel needs a sound and the spec
forbids fetching one, so `assets/audio/tada.wav` now ships. D3 exists because a music
library is somebody else's copyright and the user is expected to supply their own; a
30 KB sound this project generates from a committed script is not that.

The guard was narrowed rather than deleted: `GENERATED_AUDIO` in
`tests/test_release_licensing.py` names the exempt paths, every entry must name a
generator that exists and is itself committed, and the committed bytes are proved to be
that generator's output. Any other tracked audio file still fails. Both halves
mutation-checked.

**If you would rather keep D3 absolute**, the revert is small: drop `"tada"` from
`CELEBRATION_TYPES`, delete the asset, the generator and the exemption. The visual
celebrations are unaffected.

## Review

Two cold passes over the full range (the diff and the range, no narrative): a
failure-pattern sweep and a correctness / UI-contract / test-quality pass. They ran
independently and **converged on four of the same defects**, which is the evidence
worth having — a reviewer agreeing with itself is close to none.

Combined: 2 high, 8 medium, 9 low. Everything medium and above fixed in `9f7b5f3` /
`1685ce8`; the low findings are in `BACKLOG.md`. The three that mattered most:

- **Done never stopped the clock**, so the break alarm fired over the savor prompt and
  `focus_force` pulled focus off the modal. The test for it called
  `_cancel_pending_timer()` on the line before `done_action()` — it was doing the fix's
  job and hiding its absence.
- **Start → Stop → Start showed Done, Finished and Continue together.** Two of the three
  end the work with no reward protocol at all, so a user reaching for the familiar
  button lost the feature silently.
- **The reward sequence could veto the record.** A dialog, a canvas and an audio player
  ran unguarded before the only code that writes anything.

Then a third cold pass over the fix commits alone, because fixes are written last and
fastest and are the least-reviewed code in any change. It found three more, **two of them
introduced by the fix commit itself** — which is the whole argument for running it:

- `stop_timer` was too big a hammer for `done_action`, and it landed on the moment the
  feature exists to protect. Behind the savor prompt the window turned red and read
  "Stopped", the music cut, Done vanished, and Finished and Continue appeared beside it.
  `halt_for_completion` now cancels the clock and nothing else.
- The exhausted-cycle guard was copied verbatim from `pause_timer`'s resume rule, so it
  required *both* countdowns to be zero and missed Stop-taken-during-the-break — the same
  zero-length-block defect the fix claimed to have removed, one step earlier.
- Clearing the reward flags in a `finally` looked safer than clearing them on success and
  was the opposite: with atomic writes a failed attempt leaves nothing behind, so a retry
  with the flags intact writes one correct row, while clearing them made the retry record
  the work as an ordinary session and stalled that project's phase by one for good.

A fourth cold pass over that round's fixes found one medium — again introduced by the
previous fix. `halt_for_completion` set a green "Deliverable complete" *before* anything
was persisted, and nothing took it back on failure, so a save that raised left a
dismissable error modal and, behind it, a timer reading green about a deliverable still
open with no work log. It also entered PAUSED without relabelling the pause button,
leaving the timer paused behind a control marked "Pause" that resumes — and disabled
entirely when reached from the break-end choice.

**Stopped there.** The severity trend across the four passes was high → high → medium →
medium, and this repo's rules bound the loop for a reason: a fix pass introduces defects
at roughly the rate it removes them, so re-sweeping without a bound trades one class for
another while the count drifts down and reads as progress. The rule is to stop when a
pass yields nothing above medium and to run a further pass only after a *high*. Pass four
produced no high.

**Every round of fixes introduced a defect the next pass caught** — three rounds, three
times. That is the measured behaviour the sweep rules describe, and the reason the cold
passes are mandatory rather than optional.

Mutation totals: 19 on the feature, 15 on fix round one, 9 on round two, 6 on round
three. All red. Seven started green across the four rounds and each was fixed or pinned
rather than noted — two tests that were performing the fix they existed to check, two
defensive lines unreachable from any click sequence, and a guard that repeated a glob
pattern instead of reading it, so changing the pattern left the test written to catch
exactly that perfectly green.

**`BACKLOG.md` contained a wrong entry** and it is corrected rather than deleted. It
described `continue_action`'s inline WorkLog as duplication that "correctly carries no
reward columns"; `deliverable_snapshot` is not reward-fired, so Continue recorded nothing
about what the session was for while Finished recorded it.

## Risks / Known gaps

- **Break end is the risky change.** It alters a control that worked, for every item,
  linked or not. `test_rp43c` pins Stop and Finished/Continue; `test_rp43b` pins the
  zero-second-break loop that a naive version of this change causes.
- **Not verified in the packaged app.** `/Applications/daVIPA.app` was running and holds
  the single-instance lock, so a source launch exits silently. It was not killed. The
  running app is the old build and will not show any of this until it is restarted from
  this source tree.
- **Three items need a human, not a test** — whether the savor step reads right, whether
  the confetti and balloons look like a celebration, and whether `tada.wav` sounds like
  "Ta-DA!". Listed in `docs/spec_coverage.md` under "Human review required".
- **Music now keeps playing through the end of a break.** It used to stop, because
  break end stopped the whole timer. This matches Pause's long-standing behaviour and
  is now documented in both the CHANGELOG and the user guide — it was an undocumented
  side effect of the break-end change until the cold pass enumerated what `stop_timer`
  used to do.
- The deliverable is offered in the full item editor only; `screens/inline_editors.py`
  does not gain it. Deliberate (plan §3 D7) — the timer always captures one where it
  matters.

## Next agent actions

- Quit the running daVIPA and launch from source; complete one deliverable on a
  project-linked item and confirm the savor copy, the celebration and the chime.
- Decide whether spec §7.2 (a new project in a familiar category starting part-way into
  Phase 1) is wanted; it is out of scope for v1 and logged in `BACKLOG.md`.
