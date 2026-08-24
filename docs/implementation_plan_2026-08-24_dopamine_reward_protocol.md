# Implementation plan — Reward-Contingent Task Chunking (Dopamine Protocol)

**Date:** 2026-08-24
**Spec:** `docs/spec_2026-08-23_dopamine_reward_protocol.md`
**Status:** Awaiting approval — no implementation code written yet.

The spec numbers its sections but assigns no IDs. This plan adopts the spec's own
section numbers verbatim, prefixed `RP`: `RP-2.1` is spec §2.1, `RP-4.5` is §4.5.
Every test name carries its ID (`test_rp21_…`).

---

## 0. What I read before planning

| File | Why it matters |
|---|---|
| `src/getmoredone/database.py:141` `initialize_schema`, `:439` `_run_migrations` | Both halves of every column add (RP-2.x) |
| `src/getmoredone/db_manager.py:1287` `create_work_log`, `:2132` `_row_to_work_log` | Work-log write/read pair |
| `src/getmoredone/db_manager.py:2048` `_row_to_project_board` | **The live board mapper** — see §7 finding A1 |
| `src/getmoredone/db_manager_project_boards.py:347` `get_project_board_ids_for_item` | Already exists; RP-5.3's `get_project_boards_for_item` builds on it |
| `src/getmoredone/screens/timer_window.py` (1154 lines) | `start_timer:407`, `tick:498`, `stop_timer:476`, `finished_action:589`, `save_work_log:828` |
| `src/getmoredone/screens/timer_window_dialogs.py:18` `CompletionNoteDialog` | The dialog pattern RP-5.7 mirrors |
| `src/getmoredone/screens/item_editor.py:300`, `item_editor_form.py:50` | Where a new item field is rendered *and* where it is read back |
| `tests/test_ui_presence.py`, `tests/test_timer.py`, `tests/test_no_vacuous_tests.py`, `tests/test_traceability_refs.py` | The guards any new code has to satisfy |
| `codex.md:99-102` | `timer_window.py` is already over 700 lines — new logic goes in a new module |

---

## 1. Acceptance criteria → tests

Every row is verifiable by a named automated test. Rows marked **HUMAN** in §2
are the only exceptions and are listed separately.

### RP-2 — Data model

| ID | Criterion | Test |
|---|---|---|
| RP-2.1 | `action_items.deliverable TEXT` exists on a **freshly created** DB | `tests/test_reward_protocol_schema.py::test_rp21_fresh_db_has_deliverable_column` |
| RP-2.1a | Migration adds it to a DB created **without** it, idempotently (run twice) | `…::test_rp21a_migration_adds_deliverable_to_legacy_db_and_is_idempotent` |
| RP-2.2 | `work_logs` has all five columns with the spec's exact types/defaults on a fresh DB | `…::test_rp22_fresh_db_has_all_five_work_log_reward_columns` |
| RP-2.2a | Migration adds all five to a legacy `work_logs`, idempotently; existing rows read `deliverable_completed=0`, `savor_delivered=0` | `…::test_rp22a_migration_backfills_work_log_defaults_on_existing_rows` |
| RP-2.3 | `project_boards.savor_count INTEGER NOT NULL DEFAULT 0` on fresh DB + migration, idempotent | `…::test_rp23_savor_count_column_and_migration` |
| RP-2.3a | `savor_count` survives a `get_project_board` round-trip | `…::test_rp23a_savor_count_round_trips_through_get_project_board` |
| **RP-2.3b** | `update_project_board` does **not** write `savor_count` — saving a board loaded before an increment cannot roll the counter back | `…::test_rp23b_update_project_board_cannot_clobber_savor_count` |
| RP-2.4 | `WorkLog` dataclass carries the five fields; `create_work_log` → `get_work_logs` round-trips every one | `…::test_rp24_work_log_reward_fields_round_trip` |
| RP-2.5 | `ActionItem.deliverable` round-trips through `create_action_item`/`get_action_item` **and** `update_action_item` | `…::test_rp25_deliverable_round_trips_on_create_and_update` |

> RP-2.3b is not in the spec. It is in this plan because `update_project_board`
> currently rewrites every column it knows about; adding `savor_count` to that
> UPDATE would make a stale in-memory board silently undo completions (P18 —
> ordering/state read while another path mutates it).

### RP-3 — `reward_protocol.py` (pure, no UI)

| ID | Criterion | Test |
|---|---|---|
| RP-3.1 | `phase_for`: `0,1,14 → "wiring"`; `15,16,999 → "maintaining"` | `tests/test_reward_protocol.py::test_rp31_phase_for_boundary_is_exactly_fifteen` |
| RP-3.2 | Phase 1: `show_savor is True` on **every** draw across 500 seeded draws | `…::test_rp32_phase_one_always_shows_savor` |
| RP-3.3 | Phase 2: `show_savor` rate within ±5pp of 0.40 over 5000 seeded draws | `…::test_rp33_phase_two_savor_rate_is_about_forty_percent` |
| RP-3.4 | `celebration` rate within ±5pp of 0.20 in **both** phases | `…::test_rp34_celebration_rate_is_twenty_percent_in_both_phases` |
| RP-3.5 | Celebration is **independent** of `show_savor`: in Phase 2, the celebration rate among `show_savor=True` draws and among `show_savor=False` draws differ by < 5pp | `…::test_rp35_celebration_is_independent_of_savor` |
| RP-3.6 | Every non-`None` celebration is a member of `CELEBRATION_TYPES`, and all three appear over many draws | `…::test_rp36_celebration_values_come_from_the_declared_tuple` |
| RP-3.7 | Celebration is never guaranteed: over 500 Phase-1 draws at least one has `celebration is None` **and** at least one has a celebration — it is not phase-locked either way | `…::test_rp37_celebration_is_never_guaranteed_in_either_phase` |
| RP-3.8 | Thresholds/probabilities are module-level named constants, not literals inside `decide_reward` (P4). Asserted by **AST**: `decide_reward`'s body contains no numeric literal | `…::test_rp38_decide_reward_body_has_no_magic_numbers` |
| RP-3.9 | `decide_reward` is deterministic for a given seed — same seed, same sequence | `…::test_rp39_same_seed_gives_the_same_sequence` |

Rates are asserted with a **seeded** `random.Random`, so RP-3.3/3.4/3.5 are
deterministic, not flaky. They are not the P23 single-draw trap: the thing under
test is a declared probability, not a model sample, and the tolerance is chosen
so the assertion fails if a constant is changed by one step (0.4→0.3 moves the
rate 10pp, twice the tolerance).

### RP-4 — Timer UX

| ID | Criterion | Test |
|---|---|---|
| RP-4.1 | `ActionItem.deliverable` renders in the item editor (`deliverable_text` widget) and its value reaches the saved item (P25: the boundary is asserted, not the widget) | `tests/test_ui_presence.py::test_rp41_item_editor_has_deliverable_field`, `tests/test_item_editor_new_item_builder.py::test_rp41_deliverable_from_form_reaches_the_saved_item` |
| RP-4.2 | Project-linked item: `start_timer` opens `DeliverableDialog` prefilled from `item.deliverable`, and on save stores `session_deliverable` / `session_board_id` / `session_phase` | `tests/test_reward_protocol_timer.py::test_rp42_linked_start_captures_the_session_deliverable` |
| RP-4.2a | Empty deliverable is **required**: the dialog refuses to save blank and shows the spec's hint verbatim | `…::test_rp42a_deliverable_dialog_refuses_blank_and_shows_the_hint` |
| RP-4.2b | Cancelling the dialog **aborts the start** — `timer_state` stays `"stopped"`, no music, no tick scheduled | `…::test_rp42b_cancelling_the_deliverable_dialog_does_not_start_the_timer` |
| RP-4.2c | **Unlinked** item: no dialog, `session_board_id is None`, timer starts exactly as before | `…::test_rp42c_unlinked_item_starts_with_no_reward_protocol` |
| RP-4.3 | Break end no longer calls `stop_timer`: state becomes `"awaiting_choice"` and the neutral frame is shown | `…::test_rp43_break_end_does_not_auto_stop` |
| RP-4.3a | "Continue focus" begins a fresh work+break cycle (both counters reset, state `"running"`) | `…::test_rp43a_continue_focus_starts_a_fresh_cycle` |
| RP-4.3b | "Pause (rest)" halts, and **resuming** from it starts a fresh cycle rather than re-entering a 0-second break (the current resume rule would loop) | `…::test_rp43b_resume_after_rest_does_not_re_enter_a_zero_second_break` |
| RP-4.3c | **UI-regression guardrail:** Stop button and the Finished/Continue frame still exist and still work after a manual Stop | `…::test_rp43c_stop_and_completion_frame_survive_the_break_change` |
| RP-4.4 | A `Done` button exists and is visible in `running`, `in_break`, `paused`, and `awaiting_choice`; hidden in `stopped` — asserted over **every** state, not the happy one | `…::test_rp44_done_button_visibility_across_every_timer_state` |
| RP-4.4a | Done on an **unlinked** item runs the existing completion flow with no savor, no celebration, and no `savor_count` change | `…::test_rp44a_done_on_unlinked_item_skips_the_reward_protocol` |
| RP-4.5 | Order on Done: savor dialog acknowledged **before** celebration fires; celebration **after**; both before persistence | `…::test_rp45_savor_precedes_celebration` |
| RP-4.5a | Celebration never replaces savor: over 2000 seeded decisions there is no case with `celebration and not show_savor` in Phase 1, and in Phase 2 a celebration with no savor never *suppresses* a savor that was due | `…::test_rp45a_celebration_never_substitutes_for_savor` |
| RP-4.5b | The `work_logs` row written by Done carries `deliverable_snapshot`, `deliverable_completed=1`, `savor_delivered`, `celebration_type`, `phase` | `…::test_rp45b_done_writes_every_reward_column` |
| RP-4.5c | `savor_count` increments on **every** Done regardless of whether savor was shown | `…::test_rp45c_counter_advances_even_when_savor_is_not_shown` |
| RP-4.5d | Counter and work log are written **together or not at all** — if the work log cannot be written the counter does not advance | `…::test_rp45d_counter_never_advances_without_a_work_log` |
| RP-4.5e | SavorDialog copy matches the spec **verbatim** (title, WHAT, HOW, button) | `…::test_rp45e_savor_dialog_copy_is_verbatim` |
| RP-4.5f | Celebration is non-blocking and self-cancelling: closing the timer mid-celebration cancels every pending `after` id and raises nothing | `…::test_rp45f_celebration_cleans_up_on_window_close` |
| RP-4.5g | The snapshot is frozen at start: editing `item.deliverable` after the timer starts does not change `deliverable_snapshot` | `…::test_rp45g_snapshot_survives_a_later_edit_of_the_deliverable` |

### RP-6 — Integration / phase transition

| ID | Criterion | Test |
|---|---|---|
| RP-6.1 | 15 consecutive Dones on one board: savor shown all 15 times, `savor_count == 15` | `tests/test_reward_protocol_timer.py::test_rp61_fifteen_completions_all_savor` |
| RP-6.2 | Completion 16 is Phase 2 — `phase` written as `"maintaining"`, savor now probabilistic | `…::test_rp62_sixteenth_completion_is_phase_two` |
| RP-6.3 | Multi-board item uses the **first** linked board by `created_at` (spec §7.1 MVP) | `tests/test_reward_protocol_schema.py::test_rp63_first_linked_board_by_created_at_wins` |

### Existing behaviour that must not regress

| ID | Criterion | Test |
|---|---|---|
| RP-R1 | Whole existing timer suite green | `tests/test_timer.py` (unchanged file) |
| RP-R2 | Item editor screen contract intact | `tests/test_ui_presence.py` (existing assertions unchanged) |
| RP-R3 | Music controls, notes, pop-out Next Action window unchanged | `tests/test_timer.py::test_play_music_*`, `tests/test_ui_presence.py` |

---

## 2. Criteria that cannot be made code-testable

Three, all flagged rather than quietly dropped:

1. **The savor step actually produces the felt sense the spec is aiming at**
   (§1, §4.5). Untestable by definition. What *is* tested is the copy verbatim
   (RP-4.5e) and that it is shown before the celebration (RP-4.5). **Proposed
   human review:** run the app, complete one project-linked deliverable, confirm
   the dialog reads as intended and does not feel like a "good job" pat.
2. **Celebration looks like a celebration** (§4.5, §7.3). Tests cover that it
   fires, that it is non-blocking, and that it tears down cleanly — not that the
   confetti is pleasant. **Proposed human review:** trigger each of the three
   types with a forced seed and look at them.
3. **The audio clip sounds like "Ta-DA!"** — see §5 decision D3. Tests assert the
   file is a valid, small, local WAV and that playback is attempted; a human has
   to listen to it once.

---

## 3. Design decisions where I depart from the spec's literal text

Each is a deliberate call, and each is listed so it can be overruled.

**D1 — One work-log row, written once.**
Spec §4.5 lists the counter increment (step 3), then `save_work_log(...)` (step 4),
then "existing completion flow" (step 5) — but the existing flow (`finished_action`)
*already* calls `save_work_log`. Following the spec literally writes two rows.
Instead: `done_action()` runs savor → celebration, stashes the `RewardDecision` on
`self._pending_reward`, then calls `finished_action()`; the existing
`save_work_log` is extended to write the five reward columns and to increment the
counter **in the same call**. Same observable outcome, one row, and no window in
which the counter has advanced but nothing was logged (P6). RP-4.5d is the test.

**D2 — Break end enters a new named state, `"awaiting_choice"`.**
`pause_timer`'s resume rule is `running if work_seconds_remaining > 0 else in_break`.
At break end both counters are 0, so a naive "just pause instead of stop" makes
Resume drop straight back into a zero-second break and re-fire the break-over
branch every tick. The neutral loop therefore gets its own state and a shared
`_begin_new_focus_cycle()` used by both "Continue focus" and resume-from-rest.
RP-4.3b is the test that would catch the loop.

**D3 — The "Ta-DA!" asset is generated, not sourced.**
No suitable clip exists in the repo, and the spec forbids network. I will add
`tools/generate_tada_wav.py` (stdlib `wave` only, ~40 lines, a two-note major-third
chime with an envelope) and commit its output at `assets/audio/tada.wav` (~30 KB).
`assets/` is already bundled by `daVIPA.spec:40` and is not touched by
`tools/packaging_filters.py`, so the packaged app gets it for free. A test asserts
regenerating produces byte-identical output, so the committed asset is provably
the script's real output and not something hand-waved in. Playback reuses
`utils/audio_playback.play_audio_file_async`, falling back to `play_system_beep()`
with a logged reason when no player exists (P2 — the drop is surfaced, not silent).
*Alternative if you'd rather not commit a binary:* drop the audio type and ship
`CELEBRATION_TYPES = ("confetti", "balloon")` plus an on-screen "Ta-DA!" — say the
word and I will.

**D4 — Confetti and balloon are drawn, not image assets.**
A `tk.Canvas` overlay inside the timer window, ~1.5 s, driven by `after()` and
cancelled in `_cleanup_and_destroy`. No files, no dependency, works frozen.

**D5 — New logic lives in a new module, not in `timer_window.py`.**
That file is 1154 lines — `codex.md:102` calls anything over 700 a strong refactor
candidate. The reward sequence goes in `screens/timer_window_reward.py` as a mixin
(`TimerRewardMixin`), the same shape as `DBManagerProjectBoardsMixin` and
`ItemEditorFormMixin` already used here. `timer_window.py` gains the button, the
state, and the mixin — roughly +40 lines, not +300.

**D6 — `phase` persisted is the one decided at Done, not at start.**
`session_phase` is captured at start (spec §4.2.3) and used for display only. The
value written to `work_logs.phase` comes from `decide_reward` at Done, which is what
§4.5 specifies. Documented in the docstring so the two are not confused later.

**D7 — Deliverable is offered in the full item editor only.**
`screens/inline_editors.py` edits items in place on the list screens and will not
gain the field. That is a decision, not an oversight (P25 says an entry point that
deliberately does not offer a capability must have that recorded) — the deliverable
is also always capturable at timer start, which is the moment it matters.

---

## 4. Implementation order

Each step is committable on its own; later steps depend only on earlier ones.
Per `CLAUDE.md`, **test changes commit separately from `src/` changes.**

1. **`reward_protocol.py`** (RP-3) — pure module, zero dependencies. Tests first.
   *Depends on: nothing.*
2. **Schema** (RP-2.1/2.2/2.3) — `database.py` `CREATE TABLE` + `_run_migrations`,
   each `ALTER TABLE` guarded by `PRAGMA table_info`.
   *Depends on: nothing.*
3. **Models** (RP-2.4/2.5) — `ActionItem.deliverable`, `ProjectBoard.savor_count`,
   `WorkLog` × 5 fields.
   *Depends on: 2.*
4. **`db_manager`** (RP-5.3) — extend `create_work_log`, `_row_to_work_log`,
   `_write_new_action_item`, `_update_action_item`'s UPDATE, `_row_to_action_item`,
   and **`db_manager.py:2048` `_row_to_project_board`** (the live one — see §7 A1).
   Add `increment_project_savor_count(board_id)` and
   `get_project_boards_for_item(item_id)`.
   *Depends on: 3.*
5. **`item_editor`** (RP-4.1) — Deliverable field + `build_item_from_form` read-back.
   *Depends on: 3.*
6. **Dialogs** (RP-5.7) — `DeliverableDialog`, `SavorDialog` in
   `timer_window_dialogs.py`, mirroring `CompletionNoteDialog`.
   *Depends on: 1.*
7. **Celebration** (D3/D4) — `tools/generate_tada_wav.py`, `assets/audio/tada.wav`,
   and `screens/timer_window_celebration.py`.
   *Depends on: nothing.*
8. **`timer_window_reward.py` + wiring** (RP-4.2 – RP-4.5) — the mixin, the Done
   button, the neutral break-end loop.
   *Depends on: 1, 4, 6, 7.*
9. **Docs** — `docs/USER_GUIDE.md`, `CHANGELOG.md`, `NOTES.md`,
   `docs/changes/2026-08-24-dopamine-reward-protocol.md` (handoff note, template at
   `.agents/templates/handoff-note.md`), and `docs/spec_coverage.md`.
   *Depends on: all.*

Every function satisfying a criterion gets the `Purpose: / Spec: / Tests:`
docstring block `CLAUDE.md` requires — and `tests/test_traceability_refs.py` will
fail the build if any `Tests:` reference names something that does not exist.

---

## 5. Review plan

Per `CLAUDE.md` "Review sweeps": at most **2 warm passes**, at least **1 cold
pass**, every finding graded before any fix, below-medium to `BACKLOG.md`.
Given the size, I would run the cold pass over the whole batch and expect it to
find something in the break-end change specifically — that is the riskiest edit
here, because it alters a control users already rely on.

Verification is not just the suite. Per the standing note that DB unit tests are
not enough for this app's UI, step 8 ends with launching the real app under the
venv, running a project-linked item through start → Done, and checking `app.log`.

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| **Break-end change is user-visible and touches a control that works today.** A wrong move here breaks the timer for every item, linked or not. | RP-4.3c pins Stop + Finished/Continue explicitly; RP-4.3b pins the resume loop D2 identifies. |
| `work_logs` gains `NOT NULL DEFAULT 0` columns; SQLite allows this in `ALTER TABLE` only *with* a default. | Defaults are in the spec and in the test (RP-2.2a asserts existing rows read 0, not NULL). |
| Reward path silently doing nothing because the item's board never resolves. | RP-4.2c pins the unlinked case as *intended* behaviour; a linked item that fails to resolve a board logs a warning rather than skipping quietly (P2). |
| `timer_window.py` growth. | D5 — new mixin module. |
| Only the item editor offers the Deliverable field. | D7 — recorded decision, and timer start always captures it. |

---

## 7. Adjacent issues found, not fixed

Found while tracing the code; **not** part of this change unless you say so.

**A1 — `_row_to_project_board` exists twice, and one copy is dead and has
drifted.** `DatabaseManager` (`db_manager.py:2048`) shadows the identically named
method on `DBManagerProjectBoardsMixin`
(`db_manager_project_boards.py:693`). The live copy hydrates `start_date`/
`end_date`; the dead copy does not. `_row_to_project_board_link` is duplicated the
same way. Verified by running a real round-trip, not by reading — the dates do
survive, because the mixin copy never executes.
*Impact on this change:* `savor_count` must be added to the copy at
**`db_manager.py:2048`**. Adding it only to the mixin would compile, pass a
casual reading, and do nothing.
*Proposal:* delete both dead mixin copies in a separate commit. Say the word.

**A2 — `continue_action` builds its own `WorkLog` inline**
(`timer_window.py:742`) rather than calling `save_work_log`, so the two paths can
drift. It will not carry reward columns after this change — correct per spec (the
reward fires on Done, not Continue), but it is a second writer of the same row
shape (P5).

**A3 — `test_timer.py`'s `db_manager` fixture** uses `tempfile` rather than
`tmp_path`. It is explicit, so it does not hit P28, but it leaks the file if a
test raises between `yield` and `unlink`.

---

## 8. Stopping here

No implementation code has been written. Awaiting approval — in particular on
**D3** (commit a generated WAV, or drop the audio celebration) and on **A1**
(whether to delete the dead mapper copies in this batch).
