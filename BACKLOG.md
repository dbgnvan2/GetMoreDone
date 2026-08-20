# GetMoreDone Backlog

Last Updated: 2026-08-20 (Batch 3 complete — BI1 release workflow, BI2 dev requirements, BI3 calendar paths)

## Deferred — found by review, deliberately not fixed

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
