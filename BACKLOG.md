# GetMoreDone Backlog

Last Updated: 2026-08-19 (Batch 1 complete)

## Deferred — found by review, deliberately not fixed

### Release workflow: concurrent release creation (2026-08-18)

`build-windows` and `build-macos` both call `softprops/action-gh-release` with the
same `tag_name`, so the first tagged run is a check-then-create race between two
jobs. **Not fixed**, but the original reason given here was wrong: a red job does
not un-publish a Release. If one job wins the create and the other errors, the
result is a public, permanent Release carrying one platform's assets only — the
same outcome `fail_on_unmatched_files` was added to prevent. The real reason to
defer is that the window is narrow and we accept it for now, not that it is
harmless. `fail_on_unmatched_files: true` makes a red publish job *more* likely,
so do not dismiss one as "the known race" without checking which it is.
(v0.2.0 published cleanly, but that run predates the action bump and is one draw
of a timing window, so it is not evidence either way.)
Fix when convenient: a `publish` job with
`needs: [build-windows, build-macos]` that downloads both artifacts and makes a
single release call. Recorded in `LEARNINGS.md` under Open risks.

### Item editor Project link: deferred decisions (2026-08-19)

Surfaced while adding "Set Project" to the item editor. All deliberately not
fixed; each is a decision, not an oversight.

- **Two surfaces disagree about how many projects an item may have.** The
  Scheduler drag-drop and the item editor use the exclusive
  `link_item_to_project_exclusive`; the Projects screen's "link existing items"
  dialog uses the additive `link_action_item_to_project_board`. The editor
  tolerates both — it shows "(+N more)" and now confirms before an exclusive
  re-link drops the extras — but nothing reconciles the two models. Decide
  which one is the rule.
- **`weekly_items.py` still composes prefixed titles.** Creating an Action Item
  from a Weekly Tactic builds `<tactic context> - <title>` while no screen
  offers a Context field any more. Measured: with a canonical tactic title
  (`PW|LS|Blog - W34`) the splitter finds no context and nothing is prefixed;
  it only fires for the legacy shape that carries a body after the week number.
  Narrow, cosmetic, left alone.
- **`get_unlinked_action_items` has no `LIMIT`**, so the Projects screen's link
  dialog loads every open unlinked item.
- **`complete_and_create` has no caller in `src/`.** Its PL12 project-link
  inheritance is precautionary. Either wire it or retire it.
- **`save_item` and `save_item_if_needed` assemble a new item's fields twice.**
  They have now drifted twice (the project link, then the APE ordering). Factor
  the new-item assembly out so they cannot drift a third time.

### Other known items

- [x] **Done 2026-08-19 (BC3).** It was 16 tests across four files, not two, and
  one of them (`test_enhanced_deletion_protection`) was *returning False* — a
  failing test reporting green since `delete_segment`'s return shape changed.
  Another opened the user's real database. All four files now assert;
  `PytestReturnNotNoneWarning` count is 0. See `LEARNINGS.md`.
- `requirements.txt` mixes test-only and runtime dependencies, forcing
  `tests/test_release_licensing.py` to carry a hardcoded `TEST_ONLY_PACKAGES` set.
  A `requirements-dev.txt` split would remove the guesswork.
- `GoogleCalendarManager.__init__` creates `~/.getmoredone` before reading its own
  arguments, so merely constructing it touches the real home directory; tests
  redirect `Path.home()` to work around it.
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
