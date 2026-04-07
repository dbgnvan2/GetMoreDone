# Handoff Note

- Date: 2026-03-18
- Agent: Code
- Topic: codex-maintainability-policy

## Summary
Added `codex.md` to the repo root and processed it as an active maintainability policy. Reviewed the current codebase against the policy's file-size and cohesion guidance to identify the highest-risk refactor candidates.

Immediate hotspots identified:
- `src/getmoredone/screens/item_editor.py` — 3832 lines
- `src/getmoredone/vps_manager.py` — 3174 lines
- `src/getmoredone/screens/settings.py` — 1936 lines
- `src/getmoredone/db_manager.py` — 1809 lines
- `src/getmoredone/screens/timer_window.py` — 1610 lines
- `src/getmoredone/screens/vps_editors.py` — 1449 lines
- `src/getmoredone/screens/vps_planning.py` — 1283 lines
- `src/getmoredone/screens/project_boards.py` — 1051 lines
- `src/getmoredone/screens/drag_schedule.py` — 1039 lines

## Files changed
- codex.md
- docs/changes/2026-03-18-codex-maintainability-policy.md

## Verification
- Command: `find src tests -name '*.py' -print0 | xargs -0 wc -l | sort -nr | head -n 30`
- Result: PASS
- Command: `find src/getmoredone/screens -name '*.py' -print0 | xargs -0 wc -l | sort -nr | head -n 20`
- Result: PASS

## Risks / Known gaps
- This pass identified maintainability hotspots but did not refactor them yet.
- File length alone is only a prompt; each hotspot still needs responsibility-based review before splitting.

## Next agent actions
- Use `codex.md` as an active review rule for future changes.
- Prioritize responsibility-based refactors for `item_editor.py`, `vps_manager.py`, `settings.py`, `project_boards.py`, and `drag_schedule.py`.
