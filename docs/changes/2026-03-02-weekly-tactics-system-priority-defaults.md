# Handoff Note

- Date: 2026-03-02
- Agent: Code
- Topic: Weekly tactic creation uses system priority defaults

## Summary
- Updated weekly tactic creation (`create_week_action_items_for_ape`) so newly created week items copy priority factors from system defaults.
- Applied fields: `importance`, `urgency`, `size`, `value`.
- Kept `apply_defaults=False` for weekly tactic creation to avoid pulling who-specific defaults; only system priority factors are explicitly applied.
- Added regression test confirming week item creation uses the system default priority factors and computes priority score accordingly.

## Files changed
- src/getmoredone/vps_manager.py
- tests/test_weekly_title_cleanup.py

## Verification
- Command: `pytest -q tests/test_weekly_title_cleanup.py tests/test_weekly_item_filters.py tests/test_vision_planning_regressions.py`
- Result: PASS (9 passed)
- Command: `pytest -q`
- Result: PASS (216 passed, 1 skipped)

## Risks / Known gaps
- If system defaults are unset, weekly tactics still create with unset priority factors (existing behavior fallback).

## Next agent actions
- Visual QA: create new week tactics from APE Period View and confirm Priority tab opens with system default I/U/S/V values.
