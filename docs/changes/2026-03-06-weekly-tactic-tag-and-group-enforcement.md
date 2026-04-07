# Handoff Note

- Date: 2026-03-06
- Agent: Code
- Topic: weekly-tactic-tag-and-group-enforcement

## Summary
Implemented requested follow-ups for Weekly Tactic visibility and filtering:
- Added a visible `WT` chip beside title text for weekly items (`item_type='week'`) in:
  - Today
  - Upcoming
  - All Items
- Enforced weekly tactic grouping for filtering/reporting:
  - Weekly items are normalized to `group = "Weekly Tactic"` in `DatabaseManager.create_action_item` and `DatabaseManager.update_action_item`.
  - Added startup backfill in database migrations to update existing weekly items to the same group value.
- Added/updated regression assertions to ensure weekly records are grouped as `Weekly Tactic`.

## Files changed
- src/getmoredone/screens/today.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/all_items.py
- src/getmoredone/db_manager.py
- src/getmoredone/database.py
- tests/test_weekly_item_filters.py
- tests/test_weekly_title_cleanup.py
- docs/changes/2026-03-06-weekly-tactic-tag-and-group-enforcement.md

## Verification
- Command: `python3 -m py_compile src/getmoredone/db_manager.py src/getmoredone/database.py src/getmoredone/screens/today.py src/getmoredone/screens/upcoming.py src/getmoredone/screens/all_items.py tests/test_weekly_item_filters.py tests/test_weekly_title_cleanup.py`
- Result: PASS
- Command: `pytest -q tests/test_weekly_item_filters.py tests/test_weekly_title_cleanup.py tests/test_vision_planning_regressions.py tests/test_vps_hub_crud.py tests/test_vps_legacy_migration.py`
- Result: PASS

## Risks / Known gaps
- `WT` chip behavior is visually validated at runtime; no dedicated UI widget test exists for chip rendering.

## Next agent actions
- Docs Agent: add short note in user docs that weekly tactics now show a `WT` tag in list views and are grouped under `Weekly Tactic`.
