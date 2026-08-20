# Handoff Note

- Date: 2026-08-19
- Agent: Code
- Topic: backlog-batch-2

## Summary

Batch 2 of [`docs/implementation_plan_2026-08-19_backlog_clearance.md`](../implementation_plan_2026-08-19_backlog_clearance.md):
the project-link model, plus everything five sweep passes found on top of it.

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

Five passes: **7, 10, 6, 6, 3** — and every pass found a defect inside its
predecessor's fix. That is now eight consecutive passes across two batches with
the same result. The count finally fell on the fifth, and so did the severity:
the last pass found one real defect and two accuracy problems, against seven
and ten data-affecting ones at the start.

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
- Result: PASS — 1019 passed, 2 skipped, exit code 0
- `PytestReturnNotNoneWarning`: 0. No `GUARD:` line — nothing touched the real
  database or settings file.
- **Verified in the running app, not only in tests.** Both changed screens were
  built against a copy of the real database with a 3-linked item seeded, and the
  banner reads "1 action item is filed under more than one project … Aunt Ellen
  Memoir (3 projects)". The app itself starts clean.
- Driving the **real** Link dialog is what found a defect the stub tests had
  passed: the confirmation read "This item is filed under 1 projects … removes
  it from the other 0" for the ordinary one-link case. That dialog is now a test.

## Risks / Known gaps

- **Five passes were run; a sixth was not.** The curve finally turned on the
  fifth — 3 findings against 6, and only one of them a real defect. That is the
  first genuine sign of diminishing returns across two batches. It is a
  judgement call, not a proof: every pass so far has found something in its
  predecessor's work, and pass 5's own fixes are unswept. If a sixth pass is
  run, the place to look is `describe_bulk_clear` and `_apply_unlinked_filters`
  — the two functions that have now been rewritten by three consecutive passes.
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
