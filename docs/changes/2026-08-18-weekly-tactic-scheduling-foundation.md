# Handoff Note

- Date: 2026-08-18
- Agent: Code
- Topic: weekly-tactic-scheduling — steps 1-4 (WT-M1, WT-M2, WT-M7.A)

## Summary

The foundation layer of `docs/spec_2026-08-18_weekly_tactic_scheduling.md`, built to
`docs/implementation_plan_2026-08-18_weekly_tactic_scheduling.md`. Schema, week
calendar and tactic dedupe are done; the re-filing engine is not started.

**Complete:** WT-M1.A, WT-M1.B, WT-M1.C, WT-M1.D, WT-M1.E, WT-M2.A, WT-M2.B, WT-M7.A
— 33 of 83 leaf criteria.

**Not started:** WT-M3 (attach/change/detach), WT-M4 (cascade + atomicity), WT-M5
(completion re-filing), WT-M6 (entry points), WT-M7.B (invariant repair).

## Plan deviations, and why

The plan's step order had a circular dependency the build had to break:

1. **`week_calendar.py` was built before the dedupe**, not at step 4. WT-M7.A.2 requires
   the survivor's title to be re-derived "through the WT-M2 helper", so the helper has
   to exist first. The *call-site conversion* (WT-M2.B) still happened after the schema
   work, as planned.
2. **WT-M1.C's index was split from WT-M1.A/B/E** and created after the dedupe, per the
   spec's own ordering constraint.
3. **`created_by_rollover` lives in `weekly_tactic_migrations.py`**, not in
   `vps_schema.py` as the plan said. Ordering is load-bearing across all of these
   migrations, and keeping them in one function is the only way to read that order.
4. **Two shared modules were extracted that the plan did not name**:
   `weekly_tactic_titles.py` (the canonical title, needed by the dedupe and the editor
   without importing `VPSManager`) and `weekly_tactic_logging.py` (see below).

## Behaviour changes to shipped paths

- **Week items must now name an Annual Plan Element.** SQLite treats NULLs as distinct,
  so a NULL-APE week item would slip past the WT-INV5 index. No live row was affected
  (0 of 26). One existing test fixture, `test_vps_hub_crud.py::test_delete_weekly_action_item_removes_children`,
  gained a real lineage; its assertions are unchanged.
- **`normalize_week_dates=False` no longer suppresses week-item snapping.** A Weekly
  Tactic's dates *are* its week. The flag claimed to preserve day-level dates while the
  start-up normaliser snapped them back anyway.
- **`update_action_item`, `reschedule_item` and `complete_action_item` return a bool**
  saying whether the item holds the dates it was given.

## Files changed

New: `week_calendar.py`, `weekly_tactic_migrations.py`, `weekly_tactic_maintenance.py`,
`weekly_tactic_titles.py`, `weekly_tactic_logging.py`, `screens/week_collision_notice.py`.

Changed: `database.py`, `db_manager.py`, `db_manager_project_boards.py`, `models.py`,
`app_settings.py`, `vps_manager.py`, `vps_manager_planning.py`, `screens/item_editor.py`,
`screens/item_editor_weekly_tactic_dialog.py`, `screens/weekly_items.py`,
`screens/today.py`, `screens/upcoming.py`, `screens/all_items.py`,
`screens/reschedule_dialog.py`, `BACKLOG.md`, `CHANGELOG.md`.

Tests: `test_weekly_tactic_link_migration.py` (5), `test_weekly_tactic_schema.py` (19),
`test_week_numbering.py` (9), `test_weekly_tactic_dedupe.py` (15), plus
`tests/weekly_tactic_fixtures.py`.

## Verification

- `./venv/bin/python -m pytest -q` → **exit 0, 727 passed, 2 skipped**. Baseline before
  this work was 679 passed, 2 skipped.
- Each new test file also passes in isolation.
- **Real data:** the migration has run against the live database. Outcome verified on a
  read-only copy — the WT-F5 duplicate merged onto the row holding all five children,
  its title corrected from `W8` to `PW|LS|Blog - W9`, the loser's single
  `reschedule_history` row repointed onto the survivor, all 2,100 history rows and all
  94 nesting links intact, unique index present.
- **learning-qa run twice**: 9 findings on the feature commit, then 10 on the fix
  commit — of which two showed that the first round's headline fix had only relocated
  the crash it was meant to remove. All resolved except finding 8, recorded in
  `BACKLOG.md` for WT-M7.B.

## Follow-ups

- **WT-M7.B must consume `week_start_normalization["collisions"]`** (BACKLOG.md). A week
  item that cannot snap to its boundary is currently reported once and never repaired.
- **The migration log is `weekly_tactic_debug.log`** in the app data directory, not
  `app.log` — that is where the record of merged and deleted rows goes, and where the
  WT-M7.B audit will need to look.
- **Not verified in the running app.** No GUI run was made. The four screens that gained
  a collision notice, and the weekly-items drag path, are covered by handler-level tests
  only.
