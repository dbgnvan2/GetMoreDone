# Handoff Note

- Date: 2026-02-24
- Agent: Code
- Topic: apple-grey-theme

## Summary
Implemented automatic CustomTkinter theme generation with relative HSL deltas from `themes/base_dark_blue.json` for accent-only themes (`green`, `orange`, `pink`, `grey`) and added `apple_grey` as a neutral-override theme. The generator now applies explicit Apple-grey neutrals (bg/surface/border/text/muted/disabled), then derives accent keys from the Apple-grey button anchor, and enforces explicit Apple-grey CTkButton hover/text values. Updated integration so persisted `theme_name` is constrained to `{green, orange, pink, grey, apple_grey}` and startup/settings use that set.

## Files changed
- tools/generate_ctk_themes.py
- themes/base_dark_blue.json
- themes/green.json
- themes/orange.json
- themes/pink.json
- themes/grey.json
- themes/apple_grey.json
- src/getmoredone/theme.py
- src/getmoredone/app_settings.py
- src/getmoredone/paths.py
- src/getmoredone/screens/settings.py
- tests/test_theme_settings.py
- .gitignore
- docs/changes/2026-02-24-apple-grey-theme.md

## Verification
- Command: `./venv/bin/python tools/generate_ctk_themes.py`
- Result: PASS (all requested theme files generated)
- Command: `./venv/bin/python -m pytest -q tests`
- Result: PASS (185 passed, 1 skipped)

## Risks / Known gaps
- Existing pre-theme hard-coded colors remain in some secondary screens; this change did not introduce new widget-level hard-coded colors in startup theme wiring.

## Next agent actions
- Optional visual QA: manually verify contrast/legibility in light/dark appearance modes on Settings, list rows, input placeholders, disabled text, and segmented selected state.
