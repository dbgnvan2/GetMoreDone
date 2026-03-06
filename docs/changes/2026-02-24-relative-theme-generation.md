# Handoff Note

- Date: 2026-02-24
- Agent: Code
- Topic: relative-theme-generation

## Summary
Implemented automatic CustomTkinter theme generation from relative HSL differences against a copied base `dark-blue` theme. Added `tools/generate_ctk_themes.py`, copied the base theme to `themes/base_dark_blue.json`, and generated `themes/graphite.json`, `themes/green.json`, `themes/orange.json`, `themes/pink.json`, and `themes/grey.json`. Updated theme integration so app settings and UI theme dropdowns use the requested theme set (`graphite`, `green`, `orange`, `pink`, `grey`) with persisted `appearance_mode` and `theme_name` and startup theme application.

## Files changed
- tools/generate_ctk_themes.py
- themes/base_dark_blue.json
- themes/graphite.json
- themes/green.json
- themes/orange.json
- themes/pink.json
- themes/grey.json
- src/getmoredone/theme.py
- src/getmoredone/app_settings.py
- tests/test_theme_settings.py
- .gitignore
- docs/changes/2026-02-24-relative-theme-generation.md

## Verification
- Command: `./venv/bin/python tools/generate_ctk_themes.py`
- Result: PASS (all requested theme files regenerated)
- Command: `./venv/bin/python -m pytest -q tests`
- Result: PASS (185 passed, 1 skipped)

## Risks / Known gaps
- Some legacy non-theme semantic hard-coded colors still exist in `settings.py` (outside startup/theme selection path).

## Next agent actions
- Optional cleanup: continue migrating remaining settings-screen hard-coded hex values to semantic tokens or theme defaults.
