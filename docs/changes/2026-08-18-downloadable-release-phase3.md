# Handoff — Downloadable release, Phase 3 (test CI on a blank machine)

**Date:** 2026-08-18
**Spec:** `docs/spec_2026-08-18_downloadable_release.md` — R-M3
**Plan:** `docs/implementation_plan_2026-08-18_downloadable_release.md` — Phase 3
**Agent:** Code

## Summary

Fixed finding F5: the repo had no test CI. Added
`.github/workflows/tests.yml` — ubuntu, Python 3.11/3.12/3.13, installing only
from `requirements.txt`, running the suite under `xvfb` so the Tk tests execute
instead of skipping, with success decided by pytest's **exit code**.

Two real defects surfaced while doing it, both of the kind a blank machine is
supposed to expose.

### Defect 1 — collection-order dependency

`test_list_view_setting.py` and `test_vps_data_integrity.py` imported
`getmoredone` *before* their own `sys.path` insert ran. They only worked because
`test_auth.py` sorted earlier and had already inserted `src/`. Run alone, both
errored:

```
pytest test_list_view_setting.py  ->  1 error
```

Fixed twice over: a repo-root `conftest.py` puts both the repo root and `src/`
on `sys.path` before collection, and each file's own insert was restored **above**
its imports (they have `__main__` blocks and are run directly, where conftest
does not apply).

### Defect 2 — a diagnostic masquerading as a test

`test_auth.py` contained no test functions at all — just
`check_for_zombie_token()` and `main()`, talking to real Google credentials.
pytest collected it and found nothing (`rc=5` when run alone). Moved to
`tools/diagnose_google_auth.py` and **all 28 references across 13 files** updated
(README, four shell scripts, seven docs, two root diagnostics).

## Files changed

| File | Change |
|---|---|
| `.github/workflows/tests.yml` | **New.** R-M3.A/B/C |
| `conftest.py` | **New.** Repo-root path setup; removes the collection-order dependency (R-M3.D) |
| `tests/test_ci_contract.py` | **New.** 16 tests |
| `tests/test_*.py` × 6 | Relocated from the repo root (R-M3.D, starts R-M7.A) |
| `tools/diagnose_google_auth.py` | Was `test_auth.py` at the repo root |
| `README.md`, `CLEAR_BROWSER_CACHE.md`, `QUICK_FIX_ZOMBIE_TOKEN.md`, `fix_oauth_app_name.md`, `docs/CLIENT_ID_MISMATCH_FIX.md`, `docs/DOCUMENTATION_INDEX.md`, `docs/EMAIL-AUTH-TROUBLESHOOTING.md` | `python3 test_auth.py` → `python3 tools/diagnose_google_auth.py` |
| `verify_auth.sh`, `fix_client_id_mismatch.sh`, `fix_wrong_project.sh`, `fix_zombie_token.sh`, `debug_auth_loading.py`, `diagnose_client_id.py` | Same rename; all four shell scripts re-checked with `bash -n` |

## Test / verification status

| Check | Result |
|---|---|
| Full suite | **526 passed, 2 skipped — exit 0** (+16 new) |
| Every test file collected alone | **All pass** — was 2 errors before `conftest.py` |
| The 4 relocated tests run standalone (`python tests/x.py`) | All OK — verified after restoring their path setup |
| `tools/diagnose_google_auth.py` imports standalone | OK (`main` present; not executed — it performs real Google auth) |
| Stale `test_auth.py` references | Zero, outside the moved file's own docstring |
| Shell scripts re-parse | `bash -n` clean on all four |
| **CI green on a real runner (R-M3.A)** | **Green.** Run `32190623464`: 3.11, 3.12 and 3.13 all `527 passed, 1 skipped`, exit 0 |

## R-M3 criteria

| ID | Status | Verified by |
|---|---|---|
| R-M3.A | done | `test_rm3a_*` (6 tests) assert the workflow's shape; run `32190623464` proves the rest — green on all three Python versions, first attempt |
| R-M3.B | done | `test_rm3b_workflow_provides_a_virtual_display`, `test_rm3b_ui_tests_are_not_skipped_headless` (CI-only, fails loudly there instead of skipping silently) |
| R-M3.C | done | `test_rm3c_no_workflow_greps_for_pass_token`, `test_rm3c_test_step_does_not_swallow_the_exit_code` |
| R-M3.D | done | `test_rm3d_no_test_files_at_the_repo_root`, `test_rm3d_all_test_files_are_collected` (real `--collect-only` subprocess), `test_rm3d_every_test_file_is_importable_on_its_own` |
| R-M3.E | done | `test_rm3e_workflows_contain_no_inline_assertions` + an adversarial test proving the run-block parser is not vacuous |

## Notes on test design

- Workflows are inspected as **text**, not parsed YAML. PyYAML is not a
  dependency and nothing pulls it in, so adding one purely to let tests read CI
  config would be a bad trade. Every assertion is presence/absence, which text
  handles correctly.
- `test_rm3e_run_step_parser_actually_finds_run_blocks` exists because a parser
  that silently returned `[]` would make every workflow check above it pass
  vacuously — the same failure shape as the color test in Phase 2.
- `test_rm3b_ui_tests_are_not_skipped_headless` only runs when `CI` is set. On
  CI a missing display must be a **failure**, not 9 files quietly skipping.

## Follow-ups

- **R-M3.A is proven.** Run `32190623464` was green on 3.11, 3.12 and 3.13 on
  the first attempt, so the README's "Python 3.11+" claim now holds against a
  blank machine rather than against this Mac.
- **The skip count is the evidence for R-M3.B.** Locally the suite reports
  `526 passed, 2 skipped`; on CI it reports `527 passed, 1 skipped`. The extra
  pass is `test_rm3b_ui_tests_are_not_skipped_headless`, which only runs when
  `CI` is set — so a display really was present, and the nine Tk files executed
  instead of skipping. Had xvfb been missing, the skip count would have jumped,
  not stayed at one.
- Phases 4–6 remain: release-pipeline hardening, `LICENSE` /
  `THIRD_PARTY_NOTICES.md` / `INSTALL.md` / `CHANGELOG.md`, hygiene.
- `learning-qa` over the full diff is still scheduled for Phase 6 step 25.

## Adjacent issues found, not fixed

- Carried forward: two tests in `tests/test_vps_segments.py` `return` a bool
  instead of asserting; `themes/base_dark_blue.json` ships but is not in
  `theme.THEME_NAMES`; `requirements.txt` mixes test and runtime dependencies.
- **All three workflows use `actions/checkout@v4` and `actions/setup-python@v5`,
  which GitHub now force-runs on Node 24 with a deprecation annotation.** Not a
  failure yet; it will become one. Flagged, not fixed — it touches
  `build-release.yml` and `agent-docs-gate.yml` as well as `tests.yml`.
- The repo root still holds `debug_auth_loading.py`, `diagnose_calendar.py`,
  `diagnose_client_id.py`, `fix_*.sh`, `verify_auth.sh` and several `*.md`
  troubleshooting docs. R-M7.A/R-M7.C cover these in Phase 6.
