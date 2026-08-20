# Handoff Note

- Date: 2026-08-19
- Agent: Code
- Topic: backlog-batch-2

## Summary

Batch 2 of [`docs/implementation_plan_2026-08-19_backlog_clearance.md`](../implementation_plan_2026-08-19_backlog_clearance.md):
the project-link model, plus everything eight review passes found on top of it.

**BP3 — one builder for a new Action Item.** `save_item` (the Save button) and
`save_item_if_needed` ("Create Note", "Link Note", the calendar dialog) both
insert a new row and had assembled its fields separately. They had already
drifted twice in one session, so which button the user pressed could change what
was stored. Both now go through `ItemEditorFormMixin`
(`src/getmoredone/screens/item_editor_form.py`): one field assembly, one
validation, one insert sequence. The insert order is the part that mattered —
the weekly-tactic re-file writes its own Annual Plan Element onto the row, so
the project link goes last.

**BP1/BP2 — an Action Item belongs to exactly one Project.** The Projects
screen's "link existing items" dialog was the last additive surface. It is
exclusive now, which means it can *delete* links, so all three surfaces (that
dialog, the item editor, the Scheduler's drag-drop) ask the same question
through one helper before anything is unfiled. Rows written before the rule
existed are reported and named — on the Projects screen and at start-up — and
never cleaned up behind the user's back. On the live database that count is 0.

**BP4 — retired.** `complete_and_create`, `RescheduleDialog` and
`screens/reschedule_dialog.py`. Neither had a caller in `src/`; both were kept
alive by their own tests, which is how the weekly-lineage work came to harden
`complete_and_create` twice for a path no user could reach.

**BP5 — the unlinked query is capped.** `get_unlinked_action_items` has a
default `LIMIT` of 500 and a `count_unlinked_action_items` sibling, so the
Scheduler stopped loading every unlinked row to render a count. What the cap
drops is announced, not silent.

**BP6 — titles.** Creating an Action Item from a Weekly Tactic no longer
prefixes the title with the tactic's context. Confirmed with the user before
doing it, as the plan required, and confirmed in the code first: `lineage_for_item`
resolves lineage from the Annual Plan Element and then the parent, and these
rows carry both, so the prefix was a third choice that was never reached.

## What the sweeps added

**Twelve passes: 7, 10, 6, 6, 3, 2, then 11 across two independent reviews,
then 8, 9, 2, 4.** Every warm pass found a defect inside its predecessor's fix.

The number that matters is the seventh. After six warm passes had the findings
down to two cosmetic ones, a **cold** review — given the diff and no knowledge
of the six passes — and a **correctness/UI** review covering the families the
failure-pattern sweep explicitly does not, were run in parallel. They
independently found the *same two high-severity defects*, both of which every
warm pass had walked past:

* the item editor reporting **"✓ Saved" while discarding every edit** when the
  row behind it had been deleted elsewhere — a regression BP3 introduced, which
  turned an `AttributeError` the user could see into a success message;
* a search in "Link Action Items" leaving items **selected but invisible**,
  which BP1 turned from harmless into destructive.

Six passes by the context that wrote the code did not find either. That is the
cost of self-review, measured, and the argument for running a cold pass on
anything that matters.

- Pass 1's two worst: the Scheduler's drag-drop deleted project links with no
  confirmation while the Projects dialog asked — BP1's own docstring justified
  itself with "the Scheduler already relinks exclusively", which was true of
  the link and false of the consent. And `create_followup_item` copied *every*
  project link, so a follow-up of a legacy multi-filed row was itself a new
  multi-filed row: the BP2 count could go **up** while the notice beside it
  promised the number only falls.
- Pass 2 found that pass 1's `who_filter` SQL compared `LOWER(TRIM(ai.who))`
  against a value Python had already lowered. SQLite's `LOWER` is ASCII-only,
  so a stored "JOSÉ" stopped matching and the whole "No Project" box read zero
  with no log line — and the fix's own comment claimed the two forms were
  equivalent. It also found that clearing a project destroys the item's Annual
  Plan Element, which nothing asked about when the item had no board link.
- Pass 3 found that pass 2's widened loss definition had been applied to the
  single-item sentence and not the bulk one, and that the cap fix had replaced
  `limit=None`'s bug with a test that asserted a constant instead of the
  behaviour — a regression back to `limit=None` would have stayed green.
- Pass 4 found that pass 3 had added a `clears_ape` parameter with a default of
  `False` and updated one of its two call sites, deleting the Annual Plan
  Element warning from the *only* dialog a multi-filed item gets.
- Pass 5 found that pass 4's fix for that had **turned an over-warning into an
  under-warning**, which is the wrong direction: the bulk-clear sentence
  counted only the items whose *sole* loss was an Annual Plan Element, so
  dragging two ordinary filed items onto "No Project" promised to remove the
  project link and then cleared both plan elements too. It also found a test
  from pass 4 whose assertion could not fail — it queried for a row the fixture
  never contained.
- Pass 6 found that pass 5's docstring — written to stop an inaccurate claim —
  was itself inaccurate: a blank Who filter produces **three** different
  answers across the Scheduler, not two.
- The cold and correctness passes found the two above plus nine more, including
  filing silently replacing an item's Annual Plan Element, a board with no plan
  element leaving the previous board's behind, and two assertions lost with a
  deleted test while the note replacing it claimed to have carried them over.
- A second cold pass, over the commit that fixed the first one, found that the
  "a board decides the plan element, including when it has none" fix **created
  database rows the application refuses to save**: filing a Weekly Tactic under
  a project with no plan element nulled the tactic's own, and
  `update_action_item` then raises on that row. A value no supported path can
  create, written by a supported path. It also found that the test I had
  written for "files it exclusively" passed with the link call deleted
  outright, and that my "exhaustive" branch walk had an escape hatch over
  exactly the case the live caller hits.

The Annual Plan Element clause in the confirmation went wrong **three times in
a row** — promised unconditionally, then only for the clearing direction, then
"replaces" for a board with nothing to replace it with. Each was found by
reading one live message. It is now pinned by an exhaustive walk of every
`(count, direction, outcome)` combination, including the ones no caller
produces today, because "no caller produces it today" is what the next caller
changes.

Every fix has a test proven to fail against the exact commit it fixes, checked
in a worktree at that commit.

## Files changed

- `src/getmoredone/screens/item_editor_form.py` — new; the shared new-item builder
- `src/getmoredone/screens/project_link_notice.py` — new; one wording and one
  confirmation for every surface that unfiles an item
- `src/getmoredone/screens/item_editor.py`, `item_editor_notes.py` — both save
  paths delegate to the builder; the clear path confirms
- `src/getmoredone/screens/project_boards.py` — exclusive linking, atomic bulk
  link, the multi-link banner
- `src/getmoredone/screens/drag_schedule.py` — confirmation before a drag
  unfiles; the capped, filter-aware unlinked list
- `src/getmoredone/screens/weekly_items.py`, `title_format.py` — no title prefix,
  and the builder it left dead
- `src/getmoredone/db_manager.py`, `db_manager_project_boards.py` —
  `complete_and_create` removed; the multi-link and unlinked queries
- `src/getmoredone/app.py` — the start-up report
- `src/getmoredone/screens/reschedule_dialog.py` — **deleted**
- Tests: `test_item_editor_new_item_builder.py`, `test_project_multi_link.py`,
  `test_weekly_items_title.py`, `test_bp4_retired_code.py` (new);
  `test_db_project_drag.py`, `test_item_editor_project_link.py`,
  `test_item_editor_weekly_tactic_ui.py`, `test_weekly_tactic_*.py`,
  `test_ui_presence.py` (changed)
- Docs: `CHANGELOG.md`, `BACKLOG.md`, `README.md`, `LEARNINGS.md`, the plan

## Verification

- Command: `venv/bin/python -m pytest -q`
- Result: PASS — 1061 passed, 2 skipped, exit code 0
- `PytestReturnNotNoneWarning`: 0. No `GUARD:` line — nothing touched the real
  database or settings file.
- **Verified in the running app, not only in tests.** Both changed screens were
  built against a copy of the real database with a 3-linked item seeded, and the
  banner reads "1 action item is filed under more than one project … Aunt Ellen
  Memoir (3 projects)". The app itself starts clean.
- Driving the **real** Link dialog is what found a defect the stub tests had
  passed: the confirmation read "This item is filed under 1 projects … removes
  it from the other 0" for the ordinary one-link case. That dialog is now a test.

## Two decisions the user took mid-review

Both were surfaced as inconsistencies I would not resolve unilaterally, and
both turned out to *remove* a class of problem rather than fix an instance:

- **Removing an item from a project removes only the link.** Its Annual Plan
  Element stays, because the user may be on the way to a different project. The
  confirmation sentence that had to describe two losses — and was wrong three
  passes running — now describes one.
- **An Annual Plan Element is deleted only when it has no child records.** That
  replaced a silent detach (and, for a Weekly Tactic, a row the app refuses to
  save) with a refusal that names what is in the way.

The second one immediately produced a defect of its own, which I found before
the sweep did: the screen that deletes an Annual Plan Element caught the
*projects* refusal and not the new *items* one, so it would have escaped a Tk
callback — the same failure this batch has been closing all day, in the fix for
it.

## Risks / Known gaps

- **The test suite used to throw dozens of modal windows over the user's
  desktop**, because proving a control is wired means building a real window
  (P25). They are withdrawn now, with an explicit opt-out for the three tests
  that read real geometry — `winfo_width()` on a withdrawn window returns 1,
  and `event_generate` on one does not fail, it deadlocks. Two hangs found by
  bisecting a suite that stopped at 27% and then 68%.
- **The warm-pass curve was misleading.** Findings fell 7 → 10 → 6 → 6 → 3 → 2
  and looked converged. A cold pass then found two high-severity defects
  immediately. Do not read a falling count from self-review as evidence that
  the code is clean; it is evidence that the reviewer has run out of new
  assumptions to question, which is not the same thing.
- **The confirmation logic is the most-rewritten code here** — seven passes
  have touched `project_link_notice.py`. It is now covered by an exhaustive
  branch walk rather than by examples, but it is still where I would look
  first.
- **Two guards were added late because nothing was checking a whole class.**
  `tests/test_traceability_refs.py` asserts every `Tests:` reference in `src/`
  resolves — CLAUDE.md makes them load-bearing for review and nothing verified
  them. It found six broken on its first run: one file that never existed, two
  tests renamed out from under their reference, one moved to another file, and
  a matcher blind spot. `tests/test_tk_offscreen.py` does the same for the
  window guard.
- **No decisions are left open.** Both that were — the "Unlink" inconsistency
  and Annual Plan Element deletion — were taken by the user mid-review and are
  implemented; see the section above.
- **The Who filter is unified on two of the Scheduler's four branches, not
  all four.** The project and unlinked branches share one rule; the
  date-filter and default branches go through `get_all_items` /
  `get_upcoming_items`, which are shared with other screens. Recorded in
  `BACKLOG.md` rather than changed, and the docstrings say so rather than
  claiming screen-wide parity — an earlier draft of them did, which is what
  pass 5 caught.
- **The Projects dialog now asks on every move between boards**, including the
  ordinary 1→1 case. That is deliberate — "Link" does not read as "move", and
  the user may not know the item is filed elsewhere — but it is a new
  interruption on a common action and may want revisiting after use.
- **`inherit_project_links` now copies one link instead of all of them.** A
  follow-up of one of the older multi-filed rows lands on the first board by
  `created_at`, and the drop is logged. Blast radius on the live database is
  zero: no item is multi-filed today.
- Adjacent issues found and deliberately **not** fixed — all recorded in
  `BACKLOG.md`: `duplicate_action_item` is now dead;
  `create_action_item_from_board` still uses the additive link function (
  provably identical there, since the item is new);
  `LinkProjectActionItemsDialog` renders up to 200 rows eagerly and is slow on
  a real database; `build_item_from_form` canonicalises a weekly title from the
  item's *stored* start date before the form's is applied, which is the order
  `save_item` used before BP3 and was preserved rather than changed.

## Next agent actions

- Batch 3 (infra: BI1 the release workflow, BI2 the dev requirements split,
  BI3 `GoogleCalendarManager.__init__`) is next in the plan.
- `docs/implementation_plan_2026-08-19_backlog_clearance.md` D6 — the
  `item_editor.py` / `db_manager.py` refactor — is still its own batch, and
  BP3 has now taken the highest-value piece of it out.
