# Handoff Note

- Date: 2026-03-18
- Agent: Code
- Topic: docs-tests-sync

## Summary
Updated the main user-facing docs to match the current app state for Scheduler, Projects, List Views, VSP naming, Annual Plan Elements, and Today completion feedback. Also added regression coverage to ensure deleting annual records removes the linked project-board item along with clearing APE links from action items.

## Files changed
- README.md
- docs/USER_GUIDE.md
- docs/DOCUMENTATION_INDEX.md
- tests/test_vps_hub_crud.py

## Verification
- Command: `pytest -q tests/test_vps_hub_crud.py tests/test_database.py tests/test_future_dates.py tests/test_theme_settings.py tests/test_vision_planning_regressions.py`
- Result: PASS
- Command: `rg -n "Annual Vision Segments|docs/User_Guide.md|Visionary Planning System" README.md docs/USER_GUIDE.md docs/DOCUMENTATION_INDEX.md`
- Result: PASS

## Risks / Known gaps
- The main docs are now aligned to the current UI terminology and workflows, but the repo still has older historical docs that may use prior naming.
- UI behavior was verified through targeted tests and doc/code inspection, not through automated GUI interaction tests.

## Next agent actions
- Push the current branch or open a PR once the broader code changes in the worktree are ready to publish together.
- If desired, do a second doc cleanup pass across older archival docs to standardize `VSP`, `Scheduler`, and `Annual Plan Elements`.
