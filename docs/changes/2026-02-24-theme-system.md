# Handoff Note

- Date: 2026-02-24
- Agent: Code
- Topic: theme-system

## Summary
Implemented a persisted app theme system for CustomTkinter with startup wiring and UI controls. Added `appearance_mode` and `theme_name` to `AppSettings`, created bundled themes (`themes/graphite.json`, `themes/ocean.json`) from CustomTkinter JSON templates, and applied theme settings on app startup before other theme calls. Refactored sidebar nav buttons to use a primary-active + ghost-secondary pattern, and updated list-row styling so VPS segment colors are used as narrow accents (stripe) instead of full-row backgrounds. Added subtle listbox selection tinting and semantic palette helpers to keep color usage centralized.

## Files changed
- src/getmoredone/app.py
- src/getmoredone/app_settings.py
- src/getmoredone/paths.py
- src/getmoredone/theme.py
- src/getmoredone/screens/settings.py
- src/getmoredone/screens/today.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/completed.py
- src/getmoredone/screens/hierarchical.py
- src/getmoredone/screens/weekly_items.py
- themes/graphite.json
- themes/ocean.json
- tests/test_theme_settings.py
- tests/test_upcoming_items.py
- docs/changes/2026-02-24-theme-system.md

## Verification
- Command: `./venv/bin/python -m pytest -q tests`
- Result: PASS (185 passed, 1 skipped)

## Risks / Known gaps
- Some non-sidebar screens still contain legacy hard-coded colors (outside the focused pass), though primary list views and sidebar were migrated to semantic/themed behavior.

## Next agent actions
- Docs agent: update README/USER_GUIDE settings section to document appearance mode + theme selection.
- Optional follow-up: continue replacing remaining ad-hoc hard-coded colors in secondary dialogs/screens with semantic helpers.
