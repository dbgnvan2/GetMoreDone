# Handoff Note

- Date: 2026-08-21
- Agent: Code
- Topic: daVIPA rebrand — Phases 1–5, and two theme-selection bugs it exposed

## Summary

The app is called **daVIPA**, tagline *Vision - Planning - Action*. Done in the
brief's phases, with Phase 1 reported and approved before any edit.

**The first commit was not a rename.** Three surfaces showed the name — window
title, sidebar wordmark, `--selftest` banner — and each held its own copy of
the literal. `paths.APP_NAME` already existed as the single source of truth for
the *data directory*, but nothing on the display side read it. So the name was
centralised into `branding.APP_DISPLAY_NAME` first, with tests proving all
three follow it. The rename itself was then a one-line value change instead of
a hunt, and a future drift is now a red build.

## The Phase 3 decisions, and why

| Question | Decision |
|---|---|
| User-data directory | **Keep `GetMoreDone` permanently.** Migration is the highest-risk change available and protects exactly one user. A test now fails if anyone wires the display name to it. |
| Python package, env vars | **Unchanged.** `getmoredone` is an internal identifier — 378 imports, and `GETMOREDONE_DB` is how the app finds its database. Phase 3e's own rule. |
| Obsidian subfolder defaults | **Unchanged.** Not in the brief. They are written into user settings; changing the default would split new installs to a different vault folder. |
| macOS bundle identifier | **Nothing to decide** — `bundle_identifier=None`. Worth setting before any distribution. |
| Windows `.exe` rename | **Done.** SmartScreen reputation only accrues from distribution, and there has been none. |
| Auto-update feed | **None exists.** Phase 3d moot. |

## Two bugs the new theme exposed

Neither was caused by adding a theme; neither was findable without one.

**Picking daVIPA gave Apple Grey.** `app_settings._normalize_theme_name` held a
**second hardcoded copy** of the theme names and rewrote anything outside it to
`"apple_grey"`. So a new theme appeared in the picker, was written to
`settings.json`, and was silently reverted on the next load — nothing logged,
nothing failing. It now delegates to `theme.normalize_theme_name`, the list the
picker is built from. The guard is parametrised over `THEME_NAMES`, so a tenth
theme cannot repeat this.

**The window background was always one launch behind.** CustomTkinter colours
each widget as it is *created*, and the root is a widget —
`apply_theme_settings` ran after `super().__init__()`. Measured across three
themes in sequence, each window carried the colours of the run before it.
Pre-existing, affecting every theme; it showed as a window background that
never matched its own sidebar.

## The palette

`brand.py` transcribes `daVIPA-colour-system.pdf`: eight core colours, eight
eleven-step ramps, three gradients, every value measured from the icon.
`themes/davipa.json` is built from those constants and registered in
`THEME_NAMES`.

Contrast was **computed, not copied**. Ten text-on-fill pairings across both
appearance modes: worst 4.90:1, nine of ten at AAA. White-on-Indigo 12.51,
white-on-Violet 7.59 and white-on-Crimson 4.90 reproduce the document's
published table exactly — which is the check that the transcription and the
measurement describe the same colours.

**It does not repaint the app**, per the ruling. The existing semantic tokens
still drive the UI; the document is explicit that it is "an extraction, not a
decision".

Three bugs in my own theme were caught by its tests before commit:
`hover_color` set on `CTkSwitch`, `CTkOptionMenu` and `CTkComboBox`, none of
which read that key, and twelve greys inherited from the reference theme that
are not brand colours.

## Icons

From `davipa-icons.zip`, the `full-bleed` variant its README recommends.
Verified rather than assumed: corner pixels are alpha 0 on full-bleed and
opaque navy on `as-is`, which is why `as-is` would read as a hard rectangle in
the Dock.

**One deviation from the brief**, following the asset README over the prompt:
the prompt calls the Windows icon "square, full-bleed, opaque, no rounding",
but the shipped `davipa.ico` has transparent corners and the zip's own README
recommends it. Flagged rather than silently reshaping the artwork.

`EXE()` had no `icon=` at all, so every Windows build until now shipped
PyInstaller's default. Now branched on `sys.platform`.

## Files changed

- **New** — `src/getmoredone/branding.py`, `src/getmoredone/brand.py`,
  `themes/davipa.json`, `assets/icons/davipa.{icns,ico,png}`,
  `tests/test_branding.py`, `tests/test_brand_palette.py`
- **Renamed** — `GetMoreDone.spec` → `daVIPA.spec`
- **Removed** — `assets/icons/app_icon.{icns,png}`
- **Changed** — `app.py`, `app_settings.py`, `selftest.py`, `theme.py`,
  `utils/app_icon.py`, the workflow, both build scripts, six release-contract
  test files, and 29 documentation files

## Verification

- `nice -n 19 ./venv/bin/python -m pytest -q` → **1369 passed, 2 skipped,
  exit 0**, zero `GUARD:` lines. Read from the exit code.
- The full suite was run locally rather than only targeted files, because
  `conftest.py`, `app.py` and `theme.py` are reached by every test.
- Every test mutation-proved with the verbatim original: putting each literal
  back reddens its own assertion; restoring the second theme list reddens
  three; moving `apply_theme_settings` back after `super().__init__()` reddens
  one.
- The app object and its screens were built headlessly against a copy of the
  real database — no window on screen, no focus taken.

## Risks / Known gaps

- **The GitHub URLs still point at `/GetMoreDone`.** GitHub redirects old to
  new and never new to old, so renaming the link before the repo breaks it
  today. They follow the repo rename — README, INSTALL and the `git clone`
  line.
- **The local folder is still `~/ProjectsLocal/GetMoreDone`.** Renaming it
  touches this session's scratchpad, the memory directory and the two-Mac
  sync; better done deliberately and last.
- **The app is not repainted in brand colours.** The theme is opt-in.
- **`base_dark_blue.json` is not in `THEME_NAMES`** — an orphan theme file
  that predates this work. Recorded, not fixed.
- **Two staging mistakes**, both caught before pushing and re-split: a `git mv`
  and a `git rm` each stayed staged across later `git add <path>` calls and
  rode into the wrong commit. The brief asks for icon, string and build
  changes to be separate, and they now are.

## Next agent actions

- After the GitHub rename: update the remote, the README/INSTALL links and the
  `git clone` line, in one commit.
- Decide whether to set a `bundle_identifier` before any distribution.
- The 36 items in `BACKLOG.md`.
