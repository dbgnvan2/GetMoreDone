# Handoff Note

- Date: 2026-02-24
- Agent: Code
- Topic: in-memory-vps-compat

## Summary
Fixed test isolation regressions by preserving SQLite in-memory DB targets (`:memory:` and memory URIs) instead of resolving them to a filesystem path. Updated database connection handling so URI targets are opened correctly. Also restored VPS backward compatibility for quarter initiative creation when callers pass only `annual_plan_id` (auto-resolves/creates an annual initiative), preserved explicit quarter titles, and restored TL Vision deletion guard behavior when child annual visions exist. Adjusted breadcrumb traversal to keep the legacy 7-level shape expected by current tests/UI paths.

## Files changed
- src/getmoredone/paths.py
- src/getmoredone/database.py
- src/getmoredone/vps_manager.py
- tests/test_database.py
- docs/changes/2026-02-24-in-memory-vps-compat.md

## Verification
- Command: `./venv/bin/python -m pytest -q tests`
- Result: PASS (181 passed, 1 skipped)

## Risks / Known gaps
- The deprecation warning from `pygame/pkg_resources` remains and is unrelated to these fixes.

## Next agent actions
- Docs agent: update high-level docs if desired to mention `:memory:` support and quarter-initiative backward compatibility behavior.
