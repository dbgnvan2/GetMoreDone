# Handoff — Downloadable release, Phase 4 (release pipeline hardening)

**Date:** 2026-08-18
**Spec:** `docs/spec_2026-08-18_downloadable_release.md` — R-M4
**Plan:** `docs/implementation_plan_2026-08-18_downloadable_release.md` — Phase 4
**Agent:** Code

## Summary

`build-release.yml` now proves every bundle starts before publishing anything
(R-M4.A) and ships a SHA-256 checksum beside each archive (R-M4.B). The first
dry-run caught a real Windows defect on its first outing — details below.

**R-M4.C and R-M4.D are deferred to Phase 5, not done.** R-M4.C sources the
release body from `CHANGELOG.md`; R-M4.D puts `LICENSE` and
`THIRD_PARTY_NOTICES.md` inside every archive. All three files are Phase 5
deliverables and do not exist yet. Their contract tests are deliberately absent
from `tests/test_ci_contract.py` rather than sitting red — a red build people
learn to ignore is worse than no CI. The workflow header records the gap.

Writing a `LICENSE` and shipping it inside a distributed archive without the
copyright holder reading it first is not a call this agent should make, which is
the other reason R-M4.D waits for the Phase 5 review gate.

## The defect the guard caught

Dry-run `32191324517`, Windows job, "Verify the packaged bundle starts":

```
22:10:12.076  Packaged build failed its selftest (exit )      <- the throw
22:10:12.360  selftest: 4/4 checks passed, 0 failed           <- 284ms LATER
```

`GetMoreDone.exe` is built `console=False` (windowed subsystem). PowerShell's
`&` operator does **not** wait for such a process and never sets
`$LASTEXITCODE`, so `$LASTEXITCODE -ne 0` compared against an empty value and
was always true. The step failed a perfectly healthy build, and the selftest
output only arrived after the shell had already moved on.

Fixed with `Start-Process -Wait -PassThru` and `$proc.ExitCode`, with stdout and
stderr redirected to files because a windowed process has no console to write
to. `build_windows.ps1` carried the identical bug and was fixed the same way —
one instance of this is evidence of a class, not a typo (P5).

Worth keeping in mind beyond CI: **`GetMoreDone.exe --selftest` will not behave
like a normal CLI when a user runs it from a Windows console** — the prompt
returns immediately and output may not appear. That is inherent to `console=False`
and is not worth changing for a GUI app, but `INSTALL.md` should not tell users
to run it that way.

## Files changed

| File | Change |
|---|---|
| `.github/workflows/build-release.yml` | Selftest step in both jobs before any publish; SHA-256 checksums as artifacts and release assets; PyInstaller invoked as a module (R-M4.A, R-M4.B) |
| `build_windows.ps1` | Same windowed-exe fix |
| `tests/test_ci_contract.py` | +13 tests, incl. 3 guarding the windowed-exe bug and a `_code_only` helper |

## Test / verification status

| Check | Result |
|---|---|
| Full suite | **538 passed, 2 skipped — exit 0** (+13 new) |
| Dry-run 1 (`32191324517`) | macOS green end to end; **Windows failed at the selftest step** — the bug above |
| Dry-run 2 (`32191656386`) | **Both jobs green** |
| Selftest ran in-band on both platforms | macOS `4/4 checks passed`; Windows `4/4 checks passed`, output now captured in the log where it belongs |
| `themes/` inside the Windows archive | `_internal/themes/apple_grey.json` and 8 more — **F1 fixed in a real release artifact** |
| `themes/` inside the macOS archive | `GetMoreDone.app/Contents/Resources/themes/apple_grey.json` and 8 more |
| Checksums | Both verify with `shasum -a 256 -c`, **including the PowerShell-generated one** — confirms the two-space format claim |
| Downloaded artifact executed | Unzipped `GetMoreDone-mac.zip` from the CI run and ran it: `4/4 checks passed, exit 0` |
| Downloaded artifact GUI | Launched, alive 10s, clean log |

The last two lines are the ones that matter: this is the full round trip — CI
build → zip → upload → download → unzip → run — on the same class of artifact
that has been dead on arrival for the whole life of this workflow.

## R-M4 criteria

| ID | Status | Verified by |
|---|---|---|
| R-M4.A | **done** | `test_rm4a_*` (7 tests); dry-run `32191656386` with 4/4 selftest output on both platforms |
| R-M4.B | **done** | `test_rm4b_*` (3 tests); both `.sha256` files verified locally against the downloaded zips |
| R-M4.C | **not done** — deferred to Phase 5 | Needs `CHANGELOG.md` |
| R-M4.D | **not done** — deferred to Phase 5 | Needs `LICENSE` and `THIRD_PARTY_NOTICES.md`, and the review gate on the licence text |

## Notes on test design

- `_code_only()` strips `#` comments before matching, because the comment
  explaining why `$LASTEXITCODE` is wrong contains the string `$LASTEXITCODE`.
  Without it the test flags its own explanation, which pressures the next person
  into deleting the reasoning. This is the third time in this project a
  presence-check has caught prose instead of code.
- `test_rm4_job_splitter_finds_both_os_jobs` exists so an empty job splitter
  cannot make every R-M4 assertion pass vacuously.
- `test_rm4a_selftest_runs_before_anything_is_published` checks *ordering*, not
  just presence: a selftest after the upload step would not stop a broken build
  from being published.

## Follow-ups

- **Phase 5 must close R-M4.C and R-M4.D** and re-run a dry-run afterwards. They
  are listed in the workflow header so the gap is visible at the point of change.
- The Node 20 deprecation annotation now names `actions/upload-artifact@v4` as
  well as `checkout@v4` and `setup-python@v5`, across all three workflows. Still
  flagged, still not fixed.
- No release has been tagged. `v0.1.0` is Phase 6 step 28.
- `learning-qa` over the full diff remains scheduled for Phase 6 step 25.

## Adjacent issues found, not fixed

- Carried forward: two tests in `tests/test_vps_segments.py` `return` a bool
  instead of asserting; `themes/base_dark_blue.json` ships but is not in
  `theme.THEME_NAMES` (it is in both archives, unreachable from Settings);
  `requirements.txt` mixes test and runtime dependencies; repo-root clutter
  (R-M7).
