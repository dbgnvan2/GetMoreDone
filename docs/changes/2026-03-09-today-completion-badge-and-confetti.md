# Handoff Note

- Date: 2026-03-09
- Agent: Code
- Topic: today-completion-badge-and-confetti

## Summary
Updated the Today List View so completed items show a larger bright-green completion mark by default, or an uploaded image badge when configured in Settings. Added new persisted settings for `completion_badge_path` and `completion_confetti_threshold`, exposed them in Settings -> Appearance, and added a lightweight confetti overlay on the Today screen that triggers every N successful completions in the current app session.

## Files changed
- src/getmoredone/app_settings.py
- src/getmoredone/screens/settings.py
- src/getmoredone/screens/today.py
- src/getmoredone/utils/icon_loader.py
- tests/test_theme_settings.py
- tests/test_future_dates.py

## Verification
- Command: `python3 -m py_compile src/getmoredone/screens/today.py src/getmoredone/screens/settings.py src/getmoredone/app_settings.py src/getmoredone/utils/icon_loader.py`
- Result: PASS
- Command: `pytest -q tests/test_theme_settings.py tests/test_future_dates.py`
- Result: PASS

## Risks / Known gaps
- The confetti animation is a simple Tk canvas overlay and is scoped to the Today screen only.
- The confetti count is session-based and does not persist across app restarts.
- The uploaded badge path is trusted as a local file path; there is no thumbnail preview in Settings yet.

## Next agent actions
- If needed, add a small preview swatch for the uploaded completion badge in Settings.
- If needed, make the confetti overlay visually lighter or more celebratory with better transparency handling.
