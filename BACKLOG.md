# daVIPA Backlog

Last Updated: 2026-08-25 (the five deferred from the timer-endings batch are cleared; older sections from 08-24 and earlier remain)

## ✅ Cleared 2026-08-25 — the five deferred from the timer-endings batch

All five fixed and pushed the same day they were recorded. Kept as a list
rather than deleted, so the entries below can be read as a record of what was
deferred and for how long, not only of what is outstanding.

- **A test failing on a timer ending path hung the run.** conftest silenced
  `grab_set`/`lift`/`focus_force`/`-topmost` and left `tkinter.messagebox`,
  which is the same class. Neutralised for the run; the fifteen tests that
  patch it themselves still win.
- **The complete-and-create follow-up landed unfiled from its project.** The two
  copy paths disagreed about what "made from an item" means; they share
  `inherit_derived_item_context` now.
- **`_cleanup_and_destroy` detected a surviving window and told nobody.** It
  returns the answer, and the ending lowers a stuck timer before raising the
  follow-up's editor over it.
- **Nothing guarded a second timer window on one item.** `TimerWindow.open_for`
  plus a weak registry, wired through all four openers.
- **`NextStepsDialog` was dead code.** Deleted.

## Deferred — found by review, deliberately not fixed

### An item on two projects gives its full time to both (2026-08-25)

`project_board_items` is many-to-many, so the Time line on each board counts the
whole of a shared item's sessions. Project totals therefore do not sum to a
person's real time. Defensible — each project genuinely absorbed that work — and
it matches the user-guide wording, but the semantics are pinned nowhere, and this
same screen's `_refresh_multi_link_notice` treats multi-board items as an anomaly
to be re-filed. One test asserting the chosen behaviour would stop a later change
flipping it silently. Found by the csdp sweep (low 3).

### A session under a minute counts as zero time (2026-08-25)

`save_work_log` stores `work_seconds_elapsed // 60`, so two 40-second sessions
render "2 sessions | 0m". Pre-existing, but the Time line is the first surface to
present the sum as "total time" and the user guide does not mention it. Either
store seconds or say so in the guide. Found by the csdp sweep (low 5).

### `format_minutes` clamps a negative total to "0m" (2026-08-25)

Only reachable by direct SQL or an import — the one writer cannot produce a
negative — but a negative row would silently offset positive sessions in the same
project before the clamp ever applies. Recorded so it is not mistaken for a live
defect later, and so the clamp is not read as validation. Found by the csdp sweep
(low 4).


### The topmost-suspension helper lives in the wrong module (2026-08-25)

`week_collision_notice` now lowers an always-on-top parent before showing a
notice, but it has to import `parent_topmost_suspended` from
`timer_window_dialogs` *inside the function* — a top-level import would be a
cycle, since `timer_window_dialogs` imports the notice module. The helper is
generic and belongs in `utils/`, with `timer_window_dialogs` re-exporting it for
the AST guards that scan that file by name (`test_t54`, `test_t55`). Deferred
because moving it at the end of a batch risks those guards for no behavioural
gain. Found by the csdp re-sweep (M1).

### `test_n26`'s strftime count gives wrong advice when it fires (2026-08-25)

It asserts exactly one `.strftime` call in `timer_window.py`. Correct today and
mutation-proved, but any future *legitimate* `strftime` in that module goes red
with "the date format is written in N places; it belongs in day_stamp alone",
which would be misleading. It is also blind to a duplicate written as an f-string
format spec (`f"{d:%m-%d}"`). Anchoring on the literal `"%m-%d"` as an AST
`Constant` would be both stricter and better-worded. Found by the csdp re-sweep
(L4).


### `_append_session_note`'s empty-string guard is unreachable (2026-08-25)

It reads `if not note or not note.strip(): return`, but `CompletionNoteDialog.save`
already normalises an empty box to `None`, so `dialog.result` is never `""`.
Mutation-proved during the csdp sweep: weakening the guard to `if note is None`
leaves every test green, and `test_n23` covers only the Skip → `None` path. Its
docstring claims more than it shows. Either drop the unreachable half or add a
direct call with `"   "` and pin it. Found by the csdp sweep (F9).


### `adopt_opener` is unguarded directly above the guard that explains why (2026-08-25)

`open_for` wraps its `deiconify`/`lift`/`focus_force` in a try, with a comment
saying an escape from there reaches a screen that has no handler. One line
above it, `live.adopt_opener(...)` is unguarded, and it calls
`db_manager.get_action_item`, which can raise on a DB error — the same P5 shape
on the adjacent line. Likelihood is low (both openers fetched the item
successfully moments earlier) and the consequence is a traceback plus an
unraised timer, not data loss. It cannot leave a half-updated item: the
`setattr` loop over `dataclasses.fields` has nothing in it that can throw.
Found by the csdp fourth pass.


### The callback dedupe only catches the immediately-previous opener (2026-08-25)

`adopt_opener` compares `on_close == self.on_close_callback`, which stops one
screen chaining itself repeatedly. Once a *second* opener chains,
`self.on_close_callback` is the `both` closure and the first opener's bound
method no longer compares equal to it — so alternating openers grow the chain
again. Measured: two screens alternating over five presses ran
`['A','B','A','B','A']` for one close. Duplicated refreshes, no data loss, so
below medium. Fix shape: keep an ordered list of adopted callbacks and test
membership with `in`, instead of nesting closures. Found by the csdp third pass.

### The pop-out notes window is not refreshed by a timer reuse (2026-08-25)

`adopt_opener` refreshes the timer's own notes box but not
`NextActionWindow.notes_text`, which is filled once at construction. With the
pop-out open across a reuse it shows the pre-edit description, and pressing
Save there writes that stale text over the editor's save. Narrower than the bug
it neighbours — the user has to press Save on visibly stale text, and closing
the pop-out does not auto-save. `refresh_notes()` already exists; calling it
under the same untouched rule closes it. Found by the csdp third pass.

### `_save_notes_to_item` strips one side of its comparison (2026-08-25)

`notes` is stripped and `self.item.description` is not, so a stored value with
surrounding whitespace never compares equal and every ending fires a redundant
`update_action_item` plus `notify_weekly_tactic_changes`. Content-preserving.
One-line fix: `if notes != (self.item.description or "").strip():`. Pre-existing,
but the reuse path now re-seeds the box from an unstripped DB value, so it is
reachable where it was not before. Found by the csdp third pass.


### Reusing a timer does not update its clock (2026-08-25)

`adopt_opener` re-reads the item, but `time_block_minutes`,
`work_seconds_remaining` and the time-block entry are set in `__init__` and are
not touched on a reuse. So editing planned minutes from 30 to 90 and pressing
Timer again gives a window whose data says 90 and whose clock still counts 30.
Measured during the csdp re-sweep (finding 8). Not fixed in that batch because
changing the clock underneath a session that may already be running is a
behavioural decision, not a repair: a reuse mid-session should probably leave
the clock alone and only adopt the new duration when the timer is stopped.


### Legacy `" - Followup"` titles stack once under the new stamp (2026-08-25)

Rows already in the user's database carry the old undated `" - Followup"`
suffix, which `FOLLOW_UP_SUFFIX_RE` does not match. A follow-up of one of those
becomes `"X - Followup - Follow up 08-25"`. It stacks exactly once and then
stabilises, because the second stamp *is* matched next time. Cosmetic and
bounded, but it is the stacking the once-only rule existed to prevent. Fix is
either a second alternation in the regex or a one-off title migration. Found by
the csdp sweep of the backlog-clearance batch.

### Three hand-kept lists of messagebox names must agree, and do not (2026-08-25)

`conftest._MESSAGEBOX_DEFAULTS` neutralises 8 functions;
`test_tk_offscreen.ALLOWED_NEUTRALISED_DIALOGS` names 4; the `window_makers`
seed set in the same file names 7, omitting `askyesnocancel` which conftest does
patch. A future test calling `messagebox.showinfo` — patched, recorded, entirely
safe — turns `test_no_helper_builds_a_window_the_suite_cannot_reach` red with a
false alarm, on a guard people are meant to trust. It is the "two lists that
drift" defect B1 was written to remove, reintroduced one file over in the same
batch (P5). Fix: derive both sets from `_MESSAGEBOX_DEFAULTS`. Found by the csdp
sweep (F7).

### The `messageboxes` fixture yields the whole session's history (2026-08-25)

`yield _MESSAGEBOXES` hands over every record since session start, and only
tests that *request* the fixture truncate; `test_b51b` does not, and leaks three
records that survive to session end. So `any(f == "showerror" ...)` searches
everything every earlier test recorded. Latent rather than live today — measured
`showerror=0` at the moment `test_b52` runs, and its mutation still goes red —
but the first test that records a `showerror` without requesting the fixture
makes `test_b52` permanently unfalsifiable. Fix: yield a per-test slice. Found by
the csdp sweep (F8).

### `test_b25`'s docstring claims more than it checks (2026-08-25)

It says "a fifth opener added without going through `open_for` fails here". It
parses four hardcoded modules, so a fifth screen constructing `TimerWindow(...)`
is invisible to it. The claim is true by accident today — only those four files
reference `TimerWindow` in `src/` — which is exactly the condition under which it
goes stale unnoticed. Fix: glob `src/getmoredone/screens/*.py`, keep the
exact-set assertion. Found by the csdp sweep (F9).


### test_rm3d's importability probe is order-dependent (2026-08-24)

`test_rm3d_every_test_file_is_importable_on_its_own` strips the repo root from
`sys.path` before importing each test file, then walks them alphabetically. A
file that imports `conftest` to re-establish the path only passes if an earlier
file already put the root back — so the guarantee holds for most files by
ordering luck rather than by each file being self-contained. Found by adding
`tests/test_after_tracker.py`, which sorts first and therefore failed where
`tests/test_connection_leak.py`, doing exactly the same thing, passed. The
probe should re-insert nothing and every file should bootstrap its own path, or
the probe should reset `sys.path` to a known state between files.

### Below-medium from the window-leak sweep (2026-08-24)

- **`_init` runs twice for every CTk/CTkToplevel.** `CTk.__init__` calls
  `tkinter.Tk.__init__` before setting `_window_exists`, and `CTk.withdraw`
  reads it — so the first withdraw raises `AttributeError` into the swallow.
  Harmless (the outer one succeeds) and completely invisible.
- **conftest's restore path does not actually un-patch.** `cls.attributes`
  resolves to the inherited `Wm.wm_attributes`, so `setattr` on teardown leaves
  an own attribute on each class. Semantically identical; pre-existing shape,
  shared by `lift`/`focus_force`/`grab_set`/`deiconify`/`update`.
- **The sweeper discards its count.** A single long test can still hold many
  windows at once with no signal (P2).
- `timer_window.py` still prints `[ERROR] Save & Close failed` after the rename.
- `test_clearing_the_notes_box_clears_it_on_every_ending` covers 2 endings of 5
  while its name and docstring say every/four.
- `test_the_sweeper_survives_a_root_destroyed_with_its_children` relies on
  `WeakSet` iteration order to reach the exception path.
- `test_deiconify_puts_the_window_back_out_of_sight` is parametrized over the
  ctk pair only, not the newly patched `tk.Tk`/`tk.Toplevel`.
- The `_WINDOWS_MAY_BE_MAPPED` escape in `_deiconify` is only covered by the
  three `mapped_windows` tests — the ones developers are told to skip locally,
  so that guard exists only in CI.
- **Cancel Timer discards typed notes with no in-app signal.** The behaviour is
  as specified ("Cancel means nothing happened") and the user guide says so
  explicitly, but the other three endings persist them, and the label names the
  timer rather than the notes. A dirty-check confirmation would close it.

### ~~What else may be leaking~~ — FIXED 2026-08-24

All four are closed. Kept rather than deleted, because the reasoning is the
useful part: the window leak was a resource hidden rather than released (P30),
and these are the same question asked of every other finite resource.

- ~~**`pygame.mixer.init()` is never matched by `mixer.quit()`.**~~ Fixed:
  `utils/audio_playback.release_audio_device()`, called from
  `daVIPAApp.on_closing`. At app shutdown rather than when a timer window
  closes — the mixer is process-global, so a per-window release would cut the
  music of any other timer still open. Unloads before quitting; `quit()` alone
  leaves the loaded track's file handle held.
- ~~**24 uncancelled `after(...)` callbacks.**~~ Fixed: `utils/after_tracker.
  TrackedAfterMixin` gives a window `tracked_after`, and its `destroy()`
  cancels whatever is still pending. Applied to the four sites that schedule
  seconds into the future on a window the user can close first — the timer's
  flash chain and save-notes reset, `NextActionWindow`'s reset, and the item
  editor's error-label reset. A test parses for any *discarded* `self.after`
  handle of a second or more, which is the real signal; the timer tick keeps
  its handle in `update_timer_id` and is cancelled by a different mechanism.
- ~~**11 test sites holding an open SQLite connection.**~~ Fixed by a net
  rather than 11 edits, for the same reason as the window sweeper: it covers
  the helpers, the failure paths, and the twelfth. conftest registers every
  `DatabaseManager` and `VPSManager` at construction and closes any left open
  at the end of the test, with a session-scoped assertion that none outlives
  the run.
- ~~**`VPSManager` teardown unaudited.**~~ Covered by the same net; five
  functions built one without closing it.

Original text follows for the reasoning:

- **`pygame.mixer.init()` is never matched by `mixer.quit()`.** One call, in
  `screens/timer_window.py:1490`; `quit` appears nowhere in `src/`. The audio
  device is opened for the life of the process. Strongest sibling of the window
  bug: a finite OS resource acquired and never returned, invisible because
  nothing about it is on screen.
- **24 uncancelled `self.after(...)` callbacks across the screens.**
  `_flash_window` schedules four out to +1300 ms, `save_notes` a +2000 ms button
  reset in both the timer and the pop-out notes window. Only the celebration set
  and `update_timer_id` are tracked and cancelled. A window destroyed inside one
  of those intervals leaves the callback firing at a dead widget — the "invalid
  command name" the celebration module's docstring exists to avoid, at every
  site that was not hardened.
- **11 test sites build a `DatabaseManager` and never `close()` it**, holding an
  open SQLite connection and its file handle: `test_defaults_regression`,
  `test_scheduler_project_attach::_build_screen`, `test_settings_isolation`,
  `test_today_pin_drag::_make_screen`, `test_today_screen` (×2) and the
  `test_live_data_guard` self-checks. Harmless at this scale — a few dozen fds —
  but it is the same shape and would bite on a suite ten times the size.
- **`VPSManager` is constructed 28 times in tests** and its teardown was not
  audited. Worth the same check.


### reward protocol: below-medium findings and deferred scope (2026-08-24)

Graded below medium and kept out of the change, per the review-sweep rules — a
cosmetic fix is new unreviewed surface and buys none of the safety it costs.

- ~~`continue_action` builds its own `WorkLog` inline~~ — **fixed, and this entry
  was wrong.** It said the inline row "correctly carries no reward columns".
  That is true of `deliverable_completed`, `savor_delivered` and `phase`, but
  `deliverable_snapshot` is not reward-fired: the sibling Stop → Finished path
  writes it with `deliverable_completed=0`, so the identical session ended the
  other way recorded nothing about what it was for. The duplicate item it
  creates was also missing `deliverable` entirely. Both fixed in `9f7b5f3`;
  `continue_action` now routes through `save_work_log`. Kept here rather than
  deleted, because a backlog entry that mischaracterises a gap is worse than no
  entry — it reads as a decision already taken.
- **`tests/test_timer.py`'s `db_manager` fixture uses `tempfile`, not `tmp_path`.**
  Explicit, so it does not reach the user's real database, but it leaks the file
  if a test raises between `yield` and `unlink`.
- **Two dead `.gitignore` lines**, `./audio/` and `./venv/`. A pattern containing
  a slash is anchored to the file's own directory, so both look for a directory
  literally named `.` and neither has ever matched anything. Left alone while
  fixing the `audio/` rule beside them, rather than widening that diff.
- **Spec §7.2 — phase generalisation.** A new project in a familiar category
  ideally starts part-way into Phase 1 (partial transfer). Out of scope for v1;
  would be a manual `phase_override` or a `savor_count` seed.
- **Spec §7.1 — multi-board savor counting.** An item filed under several boards
  counts towards the oldest link only. In practice filing is exclusive on every
  surface, so this affects rows created before that.
- **The Deliverable field is not on `screens/inline_editors.py`.** A recorded
  decision, not an oversight — the timer captures one at start where it matters.

### reward protocol: low findings from the two cold review passes (2026-08-24)

Graded low and deferred. Everything medium or above from those passes was fixed
in `9f7b5f3`.

- **A project deleted mid-session writes a row indistinguishable from an
  unlinked one** (`timer_window_reward.py`). Both produce `phase=NULL`,
  `savor_delivered=0`, `celebration_type=NULL`. Only a log line — gone on the
  next launch — separates "the protocol could not run" from "there was no
  protocol". A distinguishable `phase` value would make the audit trail able to
  answer the question it exists for.
- **`finished_action`'s window-already-destroyed branch returns without
  `_cleanup_and_destroy`**, so `cancel_celebration()` is skipped. Latent, not
  live: the only route into that branch comes through `on_window_close`, which
  has already cancelled.
- **The sibling `after` chains are still untracked** — `_flash_window` schedules
  four callbacks out to +1300 ms, and `save_notes` (in both the timer and the
  pop-out notes window) schedules a +2000 ms button reset. None is registered
  and none is cancelled on destroy. Pre-existing, but P5-shaped: the celebration
  hardened one member of the class and left the siblings.
- **The celebration is largely occluded.** `CompletionNoteDialog` opens
  milliseconds later, topmost and centred on the same window, so ~1.5 s of
  confetti animates behind it. Fixing it means either delaying the dialog or
  drawing the celebration somewhere else — both bigger than the finding.
- **`test_rp45f_celebration_length_is_short` takes `host` and `monkeypatch` and
  uses neither**, building a real Toplevel for a constant comparison.
- **The Deliverable placeholder is 60 characters** in a single-line entry in the
  narrow left column of the item editor. May clip; not verified either way,
  since it needs a real window manager.
- **`save_work_log`'s early return leaves the flags set.** Every other exit
  clears them. Not reachable today — Done is hidden when the timer is stopped,
  and Start clears them anyway — but the asymmetry is what turns into a bug when
  a new caller appears.
- **A transient database error at Start silently downgrades a tracked session.**
  `prepare_reward_session` catches, logs, and returns True with
  `session_board_id` still None, so the whole session runs with no deliverable
  dialog, no snapshot and no counter. Deliberate — the alternative is a Start
  button that does nothing — but it is the transient-becomes-terminal shape
  (P1), and only a log line records it.
- **Four of the newer timer tests have no `try/finally: timer.destroy()`**,
  unlike the rest of the file; they lean on the `root` fixture to clean up. One
  also restores a patched method on a plain line rather than in a `finally`, and
  names the good method `broken`.
- **`self.item` is never reloaded while the timer is open.** If another screen
  edits the description and the user then changes the timer's notes box, the
  timer's stale in-memory copy overwrites the external edit on save. Pre-existing
  for any differing edit; clearing the box is one more trigger now that a
  deletion is persisted like any other change.
- **The savor copy lives in Python source** (`timer_window_dialogs.py`), with
  tests pinning the literals. Global rule 9 says content requiring editorial
  judgement belongs in a config file. The same applies to `WIRING_THRESHOLD` and
  the two probabilities — defensible as constants today, but they are the knobs
  a user will eventually want.


### rename-safe links: low-severity findings (2026-08-20)

From the third review round, not fixed in-loop:

- **`update_segment`'s `vision_segments` lookup is invisible to the RN-M4
  scan.** The insert half of this is done — all four `INSERT INTO
  vision_segments` sites now stamp `segment_description_id` (`vps_manager.py`
  in the third round, `vps_schema.py` in `af9a88e`). What remains is that the
  RN-M4 guard cannot see this lookup at all, so a regression here would not
  be caught by the scan that exists to catch it.
- **`_commit_heal` is safe only inside `DatabaseManager.transaction()`.** Four
  raw `conn.execute("BEGIN")` blocks exist (the three renames and
  `delete_entity_cascade`). No healer is reachable from them today — the code
  now returns early rather than committing when a transaction was already
  open — but the interaction is worth removing rather than guarding.
- **The four `COALESCE` clauses are two redundant copies.** `update_vision_element`
  delegates to its sibling now, so its own mirror `UPDATE`s are dead work.
- **`test_rn_deleting_a_segment_with_plan_elements_is_refused`'s
  `assert ok is False` is weak on its fixture** — the delete already refuses via
  four other tables. Only the `"Annual Plan Elements" in counts` assertion has
  teeth.
- **`backfill_segment_ids` runs its candidate query twice per NULL row** —
  the pre-existing `matches` query was left beside `resolve_segment_id_exact`.
- **`create_segment` allows two life segments whose names differ only by case.**
  That is the root cause of every ambiguity this batch had to handle; a
  case-insensitive guard there would remove the class.


Graded below medium by the two reviews of Batch 4 and deliberately not fixed
in-loop, per the sweep rules — each fix is new unreviewed surface.

- **`link_integrity.add_segment_description_id_columns` returns `False` for
  both "column already there" and "table absent",** so the report cannot tell
  a no-op from a missing table. `test_rn_m1d` is satisfied by either.
- **`counts["duplicate_initiatives"]` counts GROUPS, not rows,** and
  `_log_report` then says "%d duplicate_initiatives need a human" using it.
- **`test_vps_data_integrity.py::test_comprehensive_count` asserts
  `len(tables) >= 6`** — a P29 floor over an enumerable set. This change added
  two qualifying tables and the floor absorbed it silently.
- **`_collected_files`'s `lru_cache` returns a mutable `set`.** No caller
  mutates it today; `frozenset` would keep it that way.
- **`rename_vision_segment` writes `segment_descriptions.name` (UNIQUE) but
  checks for duplicates only against `vision_segments`.** Confirmed again by
  the pre-push re-sweep, which also could not produce a collision through it:
  `sync_vision_segments_with_settings` mirrors every description into
  `vision_segments` at manager init, so the `vision_segments` check covers
  `segment_descriptions` by proxy. It is the **third** writer of that column;
  the other two now share `_refuse_case_collision`. Not guarded here because
  the guard would be unfalsifiable on a synced database, and this batch has
  shown what an untestable guard costs. What makes it worth revisiting is the
  proxy's own weak point: the `UPDATE segment_descriptions … WHERE id =
  (SELECT segment_description_id FROM vision_segments WHERE id = ?)` matches
  nothing when that id is NULL — the state the migration deliberately leaves
  for an ambiguous row — so the two tables diverge silently rather than
  erroring. That silent no-op is the falsifiable part, and the better fix.
- **Whether an Annual Plan Element should block a segment delete** is now
  answered yes (it does), but `annual_vision_elements` blocking too may be
  stricter than intended. Worth a look the first time it refuses.


### Found while closing the rename-safe-links acceptance items (2026-08-20)

Graded below medium and deliberately not fixed in-loop.

- **Segment names longer than 15 characters are clipped with an ellipsis in
  every VSP chip.** `_clip_label(name, 15)` — "Health and Fitness" renders as
  "Health and Fit…". Pre-existing display behaviour, not a rename regression,
  but a user who renames a segment to something descriptive cannot read it
  back. The same static method is copy-pasted into six screen modules
  (`vision_segments`, `vision_elements`, `annual_vision_segments`,
  `ape_assignment`, `ape_period_view`, `weekly_items`) with three different
  limits (15, 18, 20), so widening it is six edits.
- **`screens/vps_planning.py` (51 KB, `VPSPlanningScreen`) has no caller on
  the run path.** `app.show_vps_planning` is a compatibility shim that
  redirects to `show_vision_planning_hub`; the only import is in
  `tests/test_vps_fixes.py`. P21: a component kept alive by its own test.
- **`VPSSchema.initialize_vps_schema` runs twice per launch.** `DatabaseManager`
  and `VPSManager` share one `Database` and both call `initialize_schema`. The
  weekly-tactic and link-integrity migrations are behind a once-per-`Database`
  guard for exactly this; the VSP schema is not. Idempotent today — the second
  legacy pass returns early because `vision_segments_legacy` is gone — so this
  is wasted work rather than a defect. Observed directly by tracing the call.
- **`segment_descriptions.name` permits an empty or whitespace-only name.**
  `NOT NULL` does not exclude `''`. Nothing produces one today, and the branch
  that would have defended against it in the legacy migration was removed
  rather than left untestable (see `a79aeca`). A validation guard in
  `create_segment`/`update_segment` would close it at the source.


### Found by the second cold pass (2026-08-20)

Below medium, or bigger than this batch. Not fixed in-loop.

- **The legacy migration still collapses two case-colliding segments into one
  `vision_segments` row.** Withholding the id stamp stops the row *asserting* a
  life segment it is only half entitled to, and the ambiguity now reaches the
  report — but both sub-segments still hang off the one row, and the second
  one's `vision_elements.key_field` still spells the segment the other way, so
  the tree and the key field disagree. Fixing it means keying `segment_cache`
  by description id rather than lowered name, which changes the shape of
  migrated data. No test covers the residual mis-filing.
- **`backfill_initiative_ape_links` does not guard `_table_exists` for
  `annual_plans`**, which its candidate query joins. Unreachable today —
  `VPSSchema.initialize_vps_schema` runs before it — but a direct call on a
  partial database raises `no such table` inside `initialize_schema`.
- **An initiative whose `annual_plan_id` names no surviving plan is invisible
  to the title match**, because the candidate query inner-joins `annual_plans`.
  It needs a database corrupted by another build: the FK is `NOT NULL
  REFERENCES annual_plans(id) ON DELETE CASCADE` and `PRAGMA foreign_keys` is
  ON at the one connection site.
- **The plan-year tie-break can prefer the wrong initiative.** When two
  initiatives match one plan element by title, the one whose annual plan agrees
  about the year is preferred — a heuristic, not evidence. If the plan element's
  *own* initiative is the drifted one, the tie-break takes the stale twin. The
  batch's base commit did the same; what changed is that the demoted candidate
  is now named in the report instead of being dropped silently
  (`test_rn_m1b1_backfill_surfaces_the_candidate_the_tie_break_demoted`). The
  runtime heal has no report channel, so there it is still silent. Telling the
  two apart needs something the data does not currently hold.


### Found by the pre-push failure-pattern sweep (2026-08-20)

The one medium finding — `update_segment` having no case-collision guard — was
fixed (`2d97da3`). These four were graded below medium and recorded.

- **`NAME_LOOKUP_ALLOWLIST`'s keys are unchecked editorial data.**
  `test_rn_m4a_no_link_resolves_through_a_name` pins `PERMITTED_NAME_LOOKUPS` to
  an exact count, but the allowlist beside it is only checked with
  `len(reason) > 40`. Nothing verifies a key's `file.py::symbol` still exists,
  so renaming or deleting the function rots the entry green — the same failure
  the exact-count comment was written to avoid. Fix by parsing each key's file
  with `ast` and asserting the named function is defined there.
- **`_find_annual_initiative_for_ape` returns two different row shapes.** The
  id path returns `SELECT ai.*`; the heal path returns a row from
  `find_initiative_candidates_by_title`, whose `SELECT ai.*, ap.year AS
  annual_plan_year` carries an extra key that is not a column of the table. All
  four consumers read only `["id"]`, so there is no live defect — but it is an
  implicit contract difference between two branches of one function.
- **A whitespace-only difference in a stored segment name defeats the abstain
  logic.** `_agreed_description_id` strips its bucket key; `resolve_segment_id_exact`
  strips only the needle, not the stored side. So `'Health'` and `'Health '`
  disagree in the bucket — stamp correctly withheld — and then resolve to
  exactly one match in the backfill, which links silently, producing no
  `ambiguous` entry. Needs a legacy database holding an untrimmed name; no
  current app path writes one, and `update_segment` now strips before writing.
- **An initiative whose `annual_plan_id` names no surviving plan is invisible
  to the title match**, and `backfill_initiative_ape_links` does not
  `_table_exists`-guard `annual_plans`, which its candidate query joins. Both
  need a database another build corrupted; the FK is `NOT NULL … ON DELETE
  CASCADE` with `PRAGMA foreign_keys` ON.


### Found by the pre-push re-sweep of the fix commits (2026-08-20)

Its high finding — `update_segment`'s guard freezing a pre-existing collided
pair — was fixed (`897a16c`). Its medium on the untested strip was fixed
(`b5276dc`). These are the rest.

- **`update_vision_segment_admin` is annotated `-> bool` but can now raise.**
  `update_segment` raises a `ValueError` on a colliding rename and on a blank
  name; this caller does not catch, so the exception propagates through a
  `bool` signature to `screens/vision_segments.py::save`, which does catch it
  and shows an inline message. The behaviour is right and the annotation
  under-describes it. Nothing tests that propagation.
- **The blank-name raise is an untested contract change.** `update_segment`
  previously wrote a blank name into `segment_descriptions` and the
  vision-rename branch silently skipped. Raising is better; no test says so.
- **The widget test drives `save_segment()` directly**, so it does not assert
  the Save button is wired to it — only a `callable(getattr(...))` existence
  check covers that seam. One seam short of a full front-end assertion.
- **`_refuse_case_collision`'s message can name a segment the user cannot
  see**: the collision query does not filter `is_active`, so a retired segment
  can be quoted back as the blocker. Pre-existing in `create_segment` and
  inherited by `update_segment`.
- **`exclude_id: str = None` should be `Optional[str]`.**


### Found by the final reviews of the collision guard (2026-08-20)

Its four highs and its medium were fixed. These were graded low and recorded.

- **`update_segment`'s `rollback()` is not gated on an outer transaction.**
  `_DeferredCommitConnection` gates `commit()` but lets `rollback()` through
  to the raw connection, so if a caller ever wrapped `update_segment` in
  `DatabaseManager.transaction()`, the rollback would discard that caller's
  work. Checked: all three call sites (`vps_manager_taxonomy.py:913`, `:948`,
  `screens/vps_segment_editor.py:221`) are outside any `transaction()` block
  and outside the four raw `BEGIN` sites, so this is latent. Same status the
  repo already records for `_commit_heal`, and the same fix would serve both.
- **Renaming a broken row into a *different* existing pair is refused**, even
  though it strictly reduces the number of unresolvable names. That is what
  the stated rule mandates and permitting it would be worse policy, but it is
  the one place the guard is stricter than the harm it prevents.
- **`RENAME_VERDICTS` names its temp database with `abs(hash(...))`**, which is
  not stable across runs. Harmless only because pytest already numbers `tmp_path`
  per test; a stable key would be better.
- **A SQL query split across adjacent string literals is invisible to RN-M4's
  scan**, which regexes the source while Python concatenates at compile time.
  An AST walk over `src/` found exactly one real occurrence hidden this way and
  it was fixed by writing the query as one literal — but nothing stops the next
  one. The scan should parse string constants rather than raw text. Note the
  mirror lookup in `update_segment` is still two literals; no current pattern
  matches it in either spelling, so nothing is hidden today.


### Test-suite remediation leftovers (2026-08-20)

- **Random-order testing is untested.** `pytest-randomly` is not a dev
  dependency and one was not added for this batch. The suite was run with every
  file in reverse order (identical result, no order-dependence), which catches
  gross ordering problems but not seed-sensitive interactions.
- **Two fixtures are named `test_*`** — `test_item` and `test_contact` in
  `tests/test_obsidian_integration.py`. Legal, but a trap: every scanner for
  vacuous tests has to special-case them, and a reader sees a test that returns
  a value. Rename to `sample_*`.
- **Ten tests recorded above from Batch 3 remain unable to fail.** The vacuous
  scan does not catch them — they assert *something*, just not the thing their
  name claims. They need individual attention rather than a scan.


### The retired multi-agent workflow is still described in four places (2026-08-20)

`CLAUDE.md` and `AGENTS.md` were corrected. These still describe branches that
do not exist, and were left alone because rewriting them was out of scope:

- `docs/MULTI_AGENT_WORKFLOW.md`
- `.agents/prompts/code-agent.md`, `docs-agent.md`, `github-agent.md`
- `tools/agents/setup_worktrees.sh` — creates `codex/agent-{code,docs,github}`

`tools/agents/check_docs_sync.py` is live and correct; it is not part of this.


### Batch 3 final gate: test-quality findings (2026-08-20)

The fifth review round found **no defect reaching a user** — control flow was
proven unchanged across all seven `_authenticate` paths and every release guard
was mutation-proved still firing. These are the test-quality findings from the
same pass, recorded rather than fixed in-loop. They are squarely in scope for
the test-suite remediation batch (`prompt-test-suite-remediation.md`, task 4).

Each was demonstrated by a mutation, not argued for:

- **`test_bi3_a_failed_status_print_does_not_discard_a_valid_token` passes with
  its own defect reintroduced.** Move the status line back inside the `try`
  *and* drop `OSError` from `_say`, and it still passes: the except-handler's
  own `_say` raises the fixture's `OSError` first, so the run never reaches
  `FileNotFoundError`. It asserts two negatives and never asserts the token
  survived. **The tenth test in this batch that could not fail.**
- **`_say`'s `OSError` arm is untested** — the arm the helper exists for
  (closed pipe, `--noconsole`). Removing it passes 19/19.
- **Adding `-e`/`--editable` to `PIP_OPTIONS_TAKING_A_VALUE` opened a hole**:
  `pip install -e requests` is now invisible to the "every dependency comes
  from a requirements file" guard. Pip-semantically correct, but a widening of
  the guard.
- **Three improvements are unlocked**: the `- run: <cmd>` branch in
  `_run_step_lines`, the pip global-options regex, and `_code_only()` on the
  `-r requirements` findall each work but have no test, so reverting any of
  them stays green.
- **`test_the_opt_out_values_are_not_duplicated_across_modules` scans only its
  own file**, despite the name. A duplicate in another test module is not
  caught.
- **Two `.gmd-optout-probe` changes contradict each other**: the `finally`
  block's comment justifies loud cleanup because a leftover breaks
  `test_rm3d_all_test_files_are_collected`, but the same commit excluded the
  directory from that test. The premise is now false and the exclusion is inert.
- **The `else:` relocations in `_authenticate` are untested** — moving the
  status prints back inside the `try` passes, because the load-bearing fix is
  `_say` swallowing. Correct defence-in-depth, unlocked.

### Pre-existing, found by the same pass

- **`_authenticate()` accepts an expired token with no refresh_token.**
  `if not creds:` is false for a truthy `Credentials` object, so re-auth is
  skipped, `_save_token` re-saves the dead token, and the user is told
  "Google Calendar service initialized successfully" before every API call
  fails. Verified identical before and after this batch — not a regression, but
  a real defect.


### Google auth: adjacent items from the Batch 3 reviews (2026-08-20)

Found by the three reviews of Batch 3, recorded rather than fixed because each
is outside BI3 and none is a regression from it.

- **`gmail_importer._load_creds` creates `~/.getmoredone` unconditionally**
  (`src/getmoredone/gmail_importer.py:81`) before it checks anything, and
  hardcodes `legacy_dot_dir()` rather than sharing `paths.google_auth_dir()`.
  Harmless now that the auth directory is one fixed location, but it is the
  side effect that made the removed fallback dangerous. Route it through the
  resolver when that file is next touched.
- **Five diagnostic scripts still hardcode `~/.getmoredone`**:
  `tools/diagnostics/verify_auth.sh:69`, `fix_client_id_mismatch.sh:23`,
  `fix_zombie_token.sh:16`, `debug_auth_loading.py:29`,
  `diagnose_client_id.py:135,157`. Correct today; they would all be wrong
  together if the location ever moves. `tools/diagnose_google_auth.py` — the one
  README and INSTALL point users at — was fixed.
- **`gmail_importer` writes `gmail_token.json` with no `chmod 600`**
  (`:99`), next to a `token.pickle` that is `0600`. Verified world-readable on
  this machine. Pre-existing, and a real credential-exposure item.
- **`test_bi3_saving_a_token_sets_owner_only_permissions` is skipped on
  Windows.** `os.chmod` there only toggles the read-only bit, so the token this
  repo's Windows binary writes has no equivalent protection and nothing checks
  it.
- **`python-dotenv` is declared in `requirements.txt` and imported nowhere** in
  `src/`. Either a real unused dependency or an undeclared runtime need.
- **The docs-sync gate's `CODE_PREFIXES` is still incomplete.**
  `tools/agents/check_docs_sync.py:12` covers `src/`, `tools/`, `tests/` plus
  the two dependency files. A PR touching only `conftest.py`, `pytest.ini`,
  `.github/` or `start.sh` reports "no code/dependency changes detected" — the
  same P3 shape as the `requirements-dev.txt` miss that was just fixed. Not
  changed here because widening a merge gate is a process decision, not a
  defect fix: adding `.github/` would make every workflow tweak require a docs
  update.
- **`test_bi2_no_test_tooling_is_declared_as_a_runtime_dependency` is a prefix
  list, so it is not exhaustive.** `freezegun`, `responses` or `factory-boy` in
  `requirements.txt` would still reach the notices check rather than failing
  there. It narrows the hole rather than closing it.
- **A failed token save is only a `print()`.** In a double-clicked GUI build
  stdout goes nowhere, so "signed in but the token was not saved" is invisible
  and the user simply gets asked to sign in again every launch. Surfacing it in
  the calendar dialog needs a UI decision.


### Release workflow: concurrent release creation — FIXED 2026-08-20 (BI1)

`build-windows` and `build-macos` both called `softprops/action-gh-release` with
the same `tag_name`, so a tagged run was a check-then-create race between two
jobs, and a red job does not un-publish a Release: if one job won the create and
the other errored, the result was a public, permanent Release carrying one
platform's assets only — the same outcome `fail_on_unmatched_files` was added to
prevent.

Fixed as the entry proposed: a single `publish` job with
`needs: [build-windows, build-macos]` downloads both artifacts and makes one
release call, so a half-succeeded run publishes nothing at all. The release notes
are generated once instead of once per platform.

**Still untested against a real tagged run.** CI is the one thing that cannot be
verified by running it here; the guarantee rests on
`tests/test_ci_contract.py::test_bi1_*` reading the YAML. The first `v*` tag after
this change is the real test — watch it, and if the `publish` job fails, no
Release is created, which is the intended behaviour rather than a regression.

### Item editor Project link: deferred decisions — all resolved in Batch 2 (2026-08-19)

Surfaced while adding "Set Project" to the item editor, deferred as decisions
rather than oversights. Batch 2 of
[`docs/implementation_plan_2026-08-19_backlog_clearance.md`](docs/implementation_plan_2026-08-19_backlog_clearance.md)
took each decision and closed it. Kept here as the record of what was decided.

- ~~**Two surfaces disagree about how many projects an item may have.**~~
  **Decided: an Action Item belongs to exactly one Project (BP1).** The
  Projects screen's "link existing items" dialog is exclusive too now. Because
  that dialog can therefore delete links, all three surfaces — the editor, the
  Scheduler's drag-drop and this dialog — ask the same question through
  `screens/project_link_notice.confirm_exclusive_relink` before anything is
  unfiled, and the same question covers the Annual Plan Element that clearing
  a project also destroys.
- ~~**`weekly_items.py` still composes prefixed titles.**~~ **Stopped (BP6).**
  A related Action Item is titled what the user typed. Confirmed first that
  `lineage_for_item` resolves an item's lineage from its Annual Plan Element
  and then its parent, and that these rows carry both, so the title prefix was
  a third choice that was never reached.
- ~~**`get_unlinked_action_items` has no `LIMIT`.**~~ **Capped at 500 (BP5),**
  with `count_unlinked_action_items` for the callers that wanted a number, and
  the Scheduler saying "showing N of M" when the cap bites. A lineage-filtered
  view fetches up to `UNLINKED_FILTERED_LIMIT` (5000) instead, because those
  filters cannot go into SQL and truncating before them would drop rows the
  filter would have kept.
- ~~**`complete_and_create` has no caller in `src/`.**~~ **Retired (BP4),**
  along with `RescheduleDialog` and `screens/reschedule_dialog.py`.
- ~~**`save_item` and `save_item_if_needed` assemble a new item's fields
  twice.**~~ **Factored into `screens/item_editor_form.py` (BP3).** Both paths
  share one field assembly, one validation and one insert sequence, and a test
  compares the rows they produce field by field.

### Open — found while clearing Batch 2 (2026-08-19)

- **`duplicate_action_item` has no caller in `src/`.** BP4 deleted
  `complete_and_create`, which was its only one; `create_followup_item` builds
  its copy independently. It is a public DB API with three tests of its own, so
  removing it was outside the decision taken. Either wire it or retire it, the
  same call BP4 made.
- ~~**`ProjectBoardsScreen.create_action_item_from_board` still uses the
  additive `link_action_item_to_project_board`.**~~ **Fixed** — it is exclusive
  now. Verified the switch is a genuine no-op there: `_apply_defaults` never
  touches `annual_plan_element_id`, so the item's plan element is the board's
  either way.
- ~~**Deleting an Annual Plan Element leaves any Weekly Tactic on it
  unsaveable.**~~ **Decided and fixed (2026-08-19):** an Annual Plan Element is
  deleted only when it has no child records. `delete_annual_records_for_vision_element`
  raises `ActionItemsAttachedError` naming the items, and destroys nothing on
  the way to the refusal.
- **A project's Annual Plan Element is synced onto its items only at link
  time.** `update_project_board` changes a board's plan element and touches
  none of its items; `delete_project_board` removes the board and leaves every
  ex-member carrying the dead board's. So editing a project's plan element
  reproduces exactly the stale state that filing was fixed to prevent. Not
  fixed here — it is a resync question about a different writer, with its own
  blast radius.
- **The raw APE `UPDATE` in `link_item_to_project_exclusive` bypasses
  `_stamp_segment_from_relationships`**, so `segment_description_id` stays
  derived from the previous plan element until the next `update_action_item`.
  Reasoned from the code, not reproduced.
- **`ProjectBoardsAttachedError`'s message lists every attached board with no
  cap**, while its sibling `ActionItemsAttachedError` caps at ten. Bounded in
  practice by boards-per-APE, so left alone — noted because the cap was added
  to one of two sibling handlers.
- **`test_app_icon._tk_available` leaks a Tk root** if `Tk()` succeeds but
  `withdraw()` raises. Not reachable in practice.
- **`LinkProjectActionItemsDialog` renders up to 200 rows eagerly** on open,
  each with four widgets, and does it again on every keystroke in Search. On a
  real database this takes long enough to notice.
- ~~**The Projects screen's "Unlink" button and every other unfiling path
  disagree.**~~ **Decided and fixed (2026-08-19):** removing an item from a
  project removes only the link; its Annual Plan Element stays, because the
  user may be on the way to a different project. Unlink was right all along —
  `clear_item_project_links` was the one overreaching.
- **`build_item_from_form` canonicalises a Weekly Tactic title from the item's
  *stored* start date**, before the form's start date is written onto it. That
  is the order `save_item` used before BP3 and was preserved deliberately; it
  looks wrong and should be checked against what WT-M6 intends.
- **Four Who-filter predicates on one screen, two of them different.** The
  Scheduler's project and unlinked branches now share one rule
  (`DragScheduleScreen._matches_who` / `_who_values_matching`): a blank filter
  matches nothing. Its date-filter and default branches go through
  `get_all_items` / `get_upcoming_items`, whose
  gate on `if who_filter:`, so the two blank forms behave differently *there*
  as well. Measured, because a first draft of this entry got it wrong:

  | filter | project / unlinked branches | `get_all_items` / `get_upcoming_items` |
  |---|---|---|
  | `"   "` | matches nothing | matches owner-*less* rows |
  | `""` | matches nothing | filter dropped — returns **everything** |

  So one blank selection produces three different answers on one screen. Not
  fixed here because those two methods are shared with other screens; changing
  them is its own change with its own blast radius. Reachable because
  `get_distinct_who_values` returns blank owners verbatim into the dropdown.
- **`get_distinct_who_values` has no `WHERE who IS NOT NULL`**, unlike its
  `group` and `category` siblings, and `who` is nullable — so a `None` can
  reach `CTkComboBox(values=...)`. Pre-existing; same family as the entry
  above.

### delete_segment coverage — resolved, and the entry was wrong (2026-08-19)

This was recorded as "cannot be exercised: every VSP table has a NOT NULL
foreign key to its parent, so an orphan cannot be inserted". That reasoning
confused *orphan* with *linked*. `delete_segment` counts
`WHERE segment_description_id = ?`, and an ordinary chain built through the
manager's own API sets that column on all seven tables — no orphan required.

Now covered by `tests/test_vps_segments.py::test_bc3_delete_segment_counts_every_vsp_table`
(all seven at once) and a parametrised companion that hangs the parents off a
second segment so each non-vision table blocks deletion on its own. Kept here as
a record of the wrong call, not as outstanding work.

### An unreadable week start disables WT-INV5 database-wide, with only a log line (2026-08-19)

If two week items on one Annual Plan Element share a `start_date` that is not a
date, they are duplicates as far as the unique index is concerned but belong to
no week. The dedupe reports them under `unmergeable` and deliberately does not
merge them — merging would be irreversible and `''` means "no start date", not
"the same week". The consequence is that `create_weekly_tactic_unique_index`
raises, is caught, and the index is **never created**, so WT-INV5 is unenforced
for *every* APE and week in the database from then on, not just for the bad rows.

`unique_index_enforced` has no consumer outside the migration and its tests, and
`unmergeable_groups` reaches only `weekly_tactic_debug.log`. There is no in-app
way to find the offending ids or clear the state.

Mitigating: `normalize_week_item_starts` falls back to `due_date`, so the
empty-start case is rescued whenever the due date parses; the genuinely stuck
case is a non-empty unparseable string. Not reachable on the live database today
(25 week rows, all Monday-aligned).

Wanted: a startup banner or a Settings diagnostic naming the rows, rather than a
log line nobody reads. Needs a UI decision, which is why it is here.

### Other known items

- [x] **Done 2026-08-19 (BC3).** It was 16 tests across four files, not two, and
  one of them (`test_enhanced_deletion_protection`) was *returning False* — a
  failing test reporting green since `delete_segment`'s return shape changed.
  Another opened the user's real database. All four files now assert;
  `PytestReturnNotNoneWarning` count is 0. See `LEARNINGS.md`.
- [x] **Done 2026-08-20 (BI2).** `requirements-dev.txt` split out; `TEST_ONLY_PACKAGES`
  deleted and `start.sh`'s `grep -v '^pytest'` with it — there were **two** hardcoded
  copies of the answer, not one. The split is asserted as set disjointness rather than
  by naming pytest, so a third test-only package cannot land in the wrong file.
- [x] **Done 2026-08-20 (BI3).** `GoogleCalendarManager.__init__` reads its arguments
  first and creates nothing. The default location moved into
  `paths.google_auth_dir()`, shared by the constructor and the two static checks that
  each hardcoded it — fixing only the constructor would have left `has_credentials()`
  looking in a different directory. `~/.getmoredone` still wins when it exists.
- The `LICENSE` is an unreviewed draft. It carries a warning header protected by
  `test_rm2a_license_carries_the_unreviewed_draft_warning`; have a lawyer review it
  before the first paid sale, then delete the header and that test together.


## ✅ Recently Completed (2026-01-24)

### VPS Segment Management

- [x] Added VPS Life Segments tab to Settings
- [x] Create new segments with color picker
- [x] Edit existing segments (name, description, color, order, active status)
- [x] Delete segments with enhanced protection:
  - Reports exact count of linked visions
  - Shows detailed error message with removal instructions
  - Prevents accidental deletion of segments with data
- [x] Visual color preview in segment list
- [x] Active/Inactive status toggle
- [x] Comprehensive test coverage (9 new tests)

### VPS Bug Fixes

- [x] Fixed New Vision button crash (CTkMessageBox error)
- [x] Fixed empty year field validation with sensible defaults
- [x] Added multi-select checkbox dialog for life segments
- [x] Segment filter now shows count of selected segments

## ✅ Recently Completed (2026-01-23)

### Item Editor Enhancements

- [x] Save button keeps window open after saving
- [x] New "Save & Close" button added
- [x] Duplicate button saves changes before duplicating and opens in new window
- [x] "Create Tasks" feature - creates child items from Next Action field (one per line)

### Timer Improvements

- [x] Independent music controls (separate Play/Pause buttons)
- [x] Music continues when timer is paused
- [x] Visual distinction with purple buttons for music controls

## 🐛 Known Bugs

- [x] Today listing shows all completed items (should only show today's).
  **Not reproducible 2026-08-19 (BC1)** — already fixed in both the SQL and the
  Python search path, which restrict completed items to
  `DATE(completed_at) = today`. Verified against a real database, then pinned by
  `tests/test_today_completed_filter.py` so the entry cannot come back untested.
- [x] Item editor: `save_and_close` / `save_and_new` / `duplicate_item` inferred save success from the error-label text, so they closed/proceeded even on a validation error. Fixed 2026-07-26 — all three now gate on the `save_item()` bool, with tests.
- [x] Item editor: the ⏱ Timer button stayed enabled if the timer completed the item, allowing a re-open on a done item. Fixed 2026-07-26 — `_on_timer_closed` disables the button once the reloaded item is completed (guard also added in `start_timer`).
- [x] Item editor + timer non-modal reload could clobber edits: editing the editor's Description/Next Action *while* the timer is open was overwritten by the on-close reload. Fixed 2026-07-26 — `start_timer` snapshots the editable fields and the on-close reload only refreshes fields the user left untouched (their in-flight edit wins); untouched fields still pick up the timer's DB changes.

## 🎯 Feature Requests

### Obsidian Integration (In Progress)

- [x] Phase 1: Basic note linking (DONE)
- [x] Add notes section to Action Items (DONE)
- [x] Create note dialog (DONE)
- [x] Link existing note dialog (DONE)
- [ ] Phase 2: Add notes section to Contacts
- [ ] Phase 3: Bulk note operations
- [ ] Phase 4: Note templates

### Future Features

- [ ] Dark mode support
- [ ] Export tasks to CSV/Excel
- [ ] Recurring tasks
- [ ] Task dependencies
- [ ] Calendar view for time blocks
- [ ] Keyboard shortcuts (Ctrl+N for new task, etc.)
- [ ] Search across all notes
- [ ] Bulk operations (complete multiple tasks at once)
- [ ] Task templates
- [ ] Weekly/monthly reports

## ✨ Enhancements

- [ ] Add tooltips to all buttons
- [ ] Improve error messages (more user-friendly)
- [ ] Add confirmation dialogs for delete operations
- [ ] Better date picker widget
- [ ] Auto-save drafts when editing
- [ ] Undo/redo support
- [ ] Obsidian "Create Note" export writes `Prev`/`Next`/`tags` as empty (bare `key:`), which renders as List/Tags only in a vault where those property types are already registered. In a brand-new vault an empty property defaults to Text until its type is set once. If needed, emit `[]` to force List typing everywhere (trade-off: diverges from Obsidian's own empty-list serialization). Noted 2026-08-06.

## 🔧 Technical Debt

- [ ] Item editor timer merge: a whitespace-only edit to a notes field while the timer is open is treated as "untouched" (the merge compares stripped values) and gets reloaded from the DB. Cosmetic — `save_item` strips anyway, so no substantive data is lost. Known, deliberate property (2026-07-26 learning-qa sweep).
- [ ] Add GUI automation tests (PyAutoGUI)
- [ ] Refactor item_editor.py (currently 1800+ lines)
- [ ] Add type hints to all functions
- [ ] Add docstrings to all public methods
- [ ] Performance testing with 10,000+ tasks
- [ ] Database migration system
- [ ] Logging framework

## 📖 User Stories

### Epic: Advanced Planning

- [ ] US: As a user, I want to see weekly task overview in calendar view
- [ ] US: As a user, I want to track task dependencies (task A blocks task B)
- [ ] US: As a user, I want to see task timeline/Gantt chart
- [ ] US: As a user, I want to estimate vs actual time reports

### Epic: Collaboration

- [ ] US: As a user, I want to share tasks with team members
- [ ] US: As a user, I want to assign tasks to others
- [ ] US: As a user, I want to sync across devices

### Epic: Integrations

- [x] US: As a user, I want to link Obsidian notes to tasks (DONE)
- [ ] US: As a user, I want to import tasks from Todoist
- [ ] US: As a user, I want to sync with Google Calendar
- [ ] US: As a user, I want to create tasks from email

## 📝 Notes

### Testing Strategy

- Backend tests: pytest (21 tests passing)
- GUI tests: Manual + PyAutoGUI (to be added)
- User should test all GUI buttons after each change

### Virtual Environment Issue

- Need to activate venv each session: `source venv/bin/activate`
- Consider adding to shell startup or creating alias

### Obsidian Integration Status

- Phase 1 complete and tested
- All 21 integration tests passing
- User needs to manually verify GUI dialogs work correctly

---

## Weekly Tactic scheduling — carried forward

### 2026-08-18 - Type: Bug

**Title:** A week item that cannot snap to its week start is never repaired
**Description:** `normalize_week_item_starts` (`weekly_tactic_maintenance.py`) snaps
every week item onto its week boundary at start-up. On the very first run the
WT-INV5 unique index does not exist yet, so a collision simply happens and the
dedupe merges the pair. On every run afterwards the index does exist, the UPDATE
raises, the row is left mid-week, and it is counted in the returned `collisions`
list. `dedupe_weekly_tactics` will never see it, because it groups by the raw
`start_date` the row still holds — so the WT-INV5 violation is permanent and its
only trace is a warning in `weekly_tactic_debug.log`.
**Priority:** Medium
**Effort:** Small
**Status:** [x] **Done 2026-08-19 (BC2).** The stated cause had moved on: the
repair *does* consume `week_start_normalization["collisions"]`, but only to mark
that tactic's children unrepairable. The real gap was that
`find_duplicate_weekly_tactics` grouped by the raw `start_date`, so a tactic left
mid-week formed a group of one and was never merged. It now groups by the *week*
each row belongs to, and the survivor is snapped onto its week start once the
duplicate holding that date is gone. Tests:
`tests/test_weekly_tactic_dedupe.py::test_bc2_*` (three, including a dirty-state
and an idempotency case).
**Notes:** Found by the learning-qa sweep of commit 55f1b36 (finding 8, P1/P3 — a
repairable condition recorded as a terminal one).

### 2026-08-18 - Type: Enhancement

**Title:** `RescheduleDialog` has no caller in `src/`
**Description:** `src/getmoredone/screens/reschedule_dialog.py` defines
`RescheduleDialog`, but nothing in `src/` constructs it — the only references are
the class statement itself and two tests. The live "push to next day" path
(`today.py`, `upcoming.py`) calls `reschedule_item` directly instead. So a
dialog that offers a reason field and a date picker is unreachable from the app.
**Priority:** Low
**Effort:** Small
**Notes:** Found by the learning-qa sweep of ca802ff (finding 6, P21 —
built-but-not-wired). Either wire it to a Reschedule action or delete it; a
surface reachable only from a test inflates the WT-M6 coverage claim. Left alone
in this change because it is out of scope for the weekly-tactic spec, and it was
already like this before.

---

## Quick Add Template

```markdown
### [Date] - [Type: Bug/Feature/Enhancement]

**Title:**
**Description:**
**Priority:** [Low/Medium/High/Critical]
**Effort:** [Small/Medium/Large]
**Notes:**
```
