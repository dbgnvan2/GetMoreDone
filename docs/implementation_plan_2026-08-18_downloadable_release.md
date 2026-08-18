# Implementation Plan — Downloadable GitHub Release (v0.1.0)

**Spec:** `docs/spec_2026-08-18_downloadable_release.md`
**Status:** Awaiting approval. No implementation code written yet.
**Date:** 2026-08-18

---

## 0. Baseline (measured, not assumed)

| Check | Result |
|---|---|
| `pytest -q tests/` | 423 passed, 1 skipped — **exit 0** |
| `pytest -q <7 root test files>` | 20 passed — **exit 0** |
| `src/` total | 33,510 LOC / 74 files |
| Local `dist/GetMoreDone.app` contains `apple_grey.json` | **No** — confirms F1 |

The suite is green today. Any red after this work is caused by this work.

---

## 1. Acceptance criteria → test map

Every criterion is verified by a named automated test, a named workflow step, or
is flagged `HUMAN` with a review proposal. No criterion is left as an assertion.

### R-M1 — Frozen-build correctness

| ID | Verified by | File |
|---|---|---|
| R-M1.A.1 | `test_rm1a1_spec_bundles_themes_dir` — parse `GetMoreDone.spec`, assert a `themes` entry in `datas` | `tests/test_packaging_resources.py` (new) |
| R-M1.A.1 | `test_rm1a1_every_selectable_theme_resolves_to_existing_file` — loop every `themes/*.json` stem through `resolve_theme_path`, assert `.exists()` | `tests/test_packaging_resources.py` (new) |
| R-M1.A.2 | `test_rm1a2_unknown_theme_name_falls_back_to_existing_file` — `""`, `"nope"`, `None` all resolve to an existing file | `tests/test_packaging_resources.py` (new) |
| R-M1.A.2 | `test_rm1a2_apply_theme_settings_never_raises_on_bad_name` | `tests/test_packaging_resources.py` (new) |
| R-M1.A.3 | `test_rm1a3_absent_audio_dir_returns_none` — monkeypatch `resource_root` to an empty tmp dir, assert `music_library` returns `None` | `tests/test_packaging_resources.py` (new) |
| R-M1.A.* | `test_rm1a_frozen_mode_resource_root_finds_bundled_themes` — monkeypatch `sys.frozen`/`sys._MEIPASS` to a tmp dir laid out as the spec bundles it; assert theme resolution succeeds. **This is the test that would have caught F1.** | `tests/test_packaging_resources.py` (new) |
| R-M1.B | `test_rm1b_selftest_exits_zero_on_temp_db` — invoke `run.py --selftest` as a subprocess with `GETMOREDONE_DB` set to a tmp path; assert **returncode 0** | `tests/test_selftest_cli.py` (new) |
| R-M1.B | `test_rm1b_selftest_exits_nonzero_when_theme_missing` — point theme dir at an empty tmp dir; assert non-zero. Guards against the selftest being a no-op that always passes | `tests/test_selftest_cli.py` (new) |
| R-M1.B | `test_rm1b_selftest_creates_no_window` — assert no `CTk()` instantiated (patch boundary, capture calls) | `tests/test_selftest_cli.py` (new) |
| R-M1.C | `test_rm1c_build_scripts_do_not_hardcode_venv_pyinstaller` — read both build scripts, assert no `./venv/bin/pyinstaller` literal after a `python3` fallback | `tests/test_packaging_resources.py` (new) |
| R-M1.D | `test_rm1d_spec_uses_onefolder_not_onefile` — assert `COLLECT` present and `onefile` absent in `GetMoreDone.spec` | `tests/test_packaging_resources.py` (new) |

### R-M2 — Licensing

| ID | Verified by | File |
|---|---|---|
| R-M2.A | `test_rm2a_license_file_exists_and_is_referenced` — `LICENSE` exists, non-empty, names the copyright holder and year, and `README.md` links it | `tests/test_release_docs.py` (new) |
| R-M2.A | **`HUMAN`** — license *wording* is a legal question, not a code question. Proposal: I draft it from a source-available template, you review it, and if the app is ever actually sold you have a lawyer review before the first paid sale. I am not a lawyer and this draft is not legal advice. | — |
| R-M2.B.1 | `test_rm2b1_date_picker_public_interface_unchanged` — assert the picker's constructor signature and public methods match the pre-change set (recorded in the test) | `tests/test_date_picker.py` (new) |
| R-M2.B.1 | `test_rm2b1_picker_returns_selected_date` — behavioural: open picker, select a day, assert the returned `date` | `tests/test_date_picker.py` (new) |
| R-M2.B.2 | `test_rm2b2_picker_honours_first_day_of_week` — assert grid column order for `first_day_of_week` 0 and 6 | `tests/test_date_picker.py` (new) |
| R-M2.B.2 | `test_rm2b2_picker_month_grid_matches_stdlib_calendar` — compare rendered grid against `calendar.Calendar(...).monthdayscalendar` for a month with an awkward boundary (Feb of a leap year, and a month starting on Sunday) | `tests/test_date_picker.py` (new) |
| R-M2.B.3 | `test_rm2b3_no_gpl_dependency_anywhere` — grep `src/`, `tests/`, `requirements.txt` for `tkcalendar`; assert zero hits | `tests/test_release_licensing.py` (new) |
| R-M2.B.3 | `test_rm2b3_installed_runtime_deps_have_no_gpl_license` — walk `requirements.txt`, read each installed dist's license metadata, assert none is GPL. **Catches a future GPL dep, not just this one** (meta-rule: fix the class) | `tests/test_release_licensing.py` (new) |
| R-M2.C | `test_rm2c_third_party_notices_covers_every_runtime_dep` — every non-test package in `requirements.txt` appears in `THIRD_PARTY_NOTICES.md`; fails when a dep is added without a notice | `tests/test_release_licensing.py` (new) |
| R-M2.C | `test_rm2c_pygame_lgpl_notice_present` | `tests/test_release_licensing.py` (new) |
| R-M2.D | `test_rm2d_no_audio_files_tracked` — assert `git ls-files audio/` is empty and no audio extension is tracked anywhere | `tests/test_release_licensing.py` (new) |

### R-M3 — Test CI

| ID | Verified by | File |
|---|---|---|
| R-M3.A | Workflow `.github/workflows/tests.yml` runs green on a clean runner | workflow (new) |
| R-M3.B | `test_rm3b_ui_tests_are_not_skipped_headless` — assert the Tk-instantiating tests report `passed`, not `skipped`, under the CI env | `tests/test_ci_contract.py` (new) |
| R-M3.C | `test_rm3c_no_workflow_greps_for_pass_token` — parse every workflow YAML; assert no step decides success by grepping for `passed`/`ok` (P24) | `tests/test_ci_contract.py` (new) |
| R-M3.D | `test_rm3d_all_test_files_are_collected` — assert every `test_*.py` in the repo is under a path pytest collects with the checked-in config | `tests/test_ci_contract.py` (new) |
| R-M3.E | `test_rm3e_workflows_contain_no_inline_assertions` — assert workflow steps only *invoke* the suite (global rule: never put a check only in the workflow) | `tests/test_ci_contract.py` (new) |

### R-M4 — Release pipeline

| ID | Verified by | File |
|---|---|---|
| R-M4.A | `test_rm4a_release_workflow_runs_selftest_on_built_bundle` — assert both OS jobs contain a selftest step that runs the **packaged executable**, not `python run.py` | `tests/test_ci_contract.py` (new) |
| R-M4.A | **`INTEGRATION-ONLY`** — that the packaged bundle genuinely starts can only be proven by the workflow executing on a real Windows/macOS runner. Reported as integration-verified, not unit-tested. Evidence: a green run of `build-release.yml`. | — |
| R-M4.B | `test_rm4b_release_workflow_publishes_checksums` | `tests/test_ci_contract.py` (new) |
| R-M4.C | `test_rm4c_release_body_sourced_from_changelog` | `tests/test_ci_contract.py` (new) |
| R-M4.D | `test_rm4d_archives_include_license_and_notices` — assert both archive steps include `LICENSE` and `THIRD_PARTY_NOTICES.md` | `tests/test_ci_contract.py` (new) |

### R-M5 — First run

| ID | Verified by | File |
|---|---|---|
| R-M5.A | `test_rm5a_google_features_degrade_without_credentials` — with `credentials.json` absent, assert the integration surface reports unavailable and raises nothing | `tests/test_first_run.py` (new) |
| R-M5.A | `test_rm5a_no_error_string_rendered_as_content` — assert the unavailable-state path does not return a sentinel error string that a screen would display as data (P14) | `tests/test_first_run.py` (new) |
| R-M5.B | Covered by R-M1.A.3 | — |
| R-M5.C | `test_rm5c_selftest_on_empty_db_initialises_schema` — fresh tmp DB, assert exit 0 and expected tables exist | `tests/test_first_run.py` (new) |
| R-M5.C | `test_rm5c_selftest_on_existing_populated_db` — **dirty-state test (P8)**: pre-populate a DB, run selftest, assert exit 0 and no data loss | `tests/test_first_run.py` (new) |
| R-M5.D | `test_rm5d_install_doc_documents_gatekeeper_step` — assert `INSTALL.md` contains the quarantine command | `tests/test_release_docs.py` (new) |
| R-M5.D | **`HUMAN`** — that Gatekeeper actually behaves as documented needs one real download on a Mac that has never run GMD. Proposal: you download the first release artifact and confirm; I cannot verify Gatekeeper from this machine, which already trusts the local build. | — |

### R-M6 — Documentation

| ID | Verified by | File |
|---|---|---|
| R-M6.A | `test_rm6a_install_doc_has_required_sections` — assert each required heading present | `tests/test_release_docs.py` (new) |
| R-M6.B | `test_rm6b_readme_leads_with_download_and_links_license` | `tests/test_release_docs.py` (new) |
| R-M6.C | `test_rm6c_standalone_build_doc_has_no_stale_spec_claim` — assert the "add a `.spec` file later" sentence is gone | `tests/test_release_docs.py` (new) |
| R-M6.D | `test_rm6d_changelog_has_v0_1_0_entry` | `tests/test_release_docs.py` (new) |
| R-M6.* | **`HUMAN`** — whether the docs are *good* is not code-testable; the tests above only prove presence and absence of specific strings. Proposal: you read `INSTALL.md` once as a first-time user. | — |

### R-M7 — Hygiene

| ID | Verified by | File |
|---|---|---|
| R-M7.A | `test_rm7a_repo_root_has_no_stray_scripts` — assert no tracked root-level `test_*`/`diagnose_*`/`fix_*`/`debug_*` files | `tests/test_repo_hygiene.py` (new) |
| R-M7.B | `test_rm7b_no_gitignore_copy_file` | `tests/test_repo_hygiene.py` (new) |
| R-M7.B | `test_rm7b_required_json_resources_are_tracked` — assert every JSON the app loads at runtime is tracked by git, so the blanket `*.json` ignore cannot silently drop a shipped resource (the F1 class) | `tests/test_repo_hygiene.py` (new) |
| R-M7.C | `test_rm7c_repo_root_doc_allowlist` — assert root-level `.md` files are within an explicit allowlist | `tests/test_repo_hygiene.py` (new) |

**Totals:** 38 automated tests across 8 new test files; 4 criteria flagged
`HUMAN`; 1 flagged `INTEGRATION-ONLY`.

---

## 2. Implementation order and dependencies

Ordered so the highest-risk, highest-impact fix is tested **first** (P10). Phase
1 is the fix for the bug that makes every existing release artifact dead on
arrival.

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
(F1 fix)    (GPL)       (test CI)   (release)   (docs)      (hygiene)
```

### Phase 1 — Kill the crash (R-M1) · blocks everything

1. Write `tests/test_packaging_resources.py` **first**, including the frozen-mode
   test. Confirm it goes **red** against today's `GetMoreDone.spec` — a test for
   F1 that passes before the fix is not testing F1.
2. Add `themes` to `datas` in `GetMoreDone.spec`; add the `--onefile` prohibition
   comment (R-M1.D).
3. Harden `paths.resolve_theme_path` so the fallback is guaranteed to exist
   (R-M1.A.2).
4. Add `--selftest` to `run.py` + `tests/test_selftest_cli.py` (R-M1.B).
5. Fix the `build_mac.sh` / `build_windows.ps1` fallback (R-M1.C).
6. Rebuild locally, confirm `dist/` now contains `apple_grey.json`, and run the
   packaged binary's `--selftest`.

**Dependency:** none. **Risk:** low. **Est:** half a day.

### Phase 2 — Remove the GPL dependency (R-M2.B) · blocks the license

7. Write `tests/test_date_picker.py` against the **current** tkcalendar-backed
   picker; confirm green. This records the interface contract before the swap.
8. Write `tests/test_release_licensing.py`; confirm
   `test_rm2b3_no_gpl_dependency_anywhere` is **red**.
9. Build the stdlib-`calendar` CTk month grid inside `widgets/date_picker.py`,
   preserving the public interface. Follow the existing pattern at
   `screens/drag_schedule.py:1009`.
10. Re-run the Phase-2 tests — the same interface tests must still pass against
    the new implementation. Remove `tkcalendar` from `requirements.txt`.
11. Reinstall the venv from `requirements.txt` alone and re-run the **full**
    suite, to prove nothing else silently depended on it.

**Dependency:** none on Phase 1, but must land before R-M2.A ships.
**Risk: highest in this plan** — it replaces a working UI widget. This is the
phase most likely to need a second pass. **Est:** 1–1.5 days.

### Phase 3 — Test CI (R-M3) · gives every later phase a blank-machine check

12. Write `tests/test_ci_contract.py`.
13. Add `.github/workflows/tests.yml`: ubuntu, xvfb, install from
    `requirements.txt` only, decide by exit code.
14. Resolve R-M3.D — relocate the 7 root test files into `tests/` (this also
    starts R-M7.A).
15. Push and confirm green on a real runner. Fix whatever the blank machine
    exposes that this Mac hides.

**Dependency:** Phases 1–2, so CI starts green. **Est:** half a day.

### Phase 4 — Release pipeline (R-M4)

16. Extend `tests/test_ci_contract.py` with the R-M4 assertions.
17. Add the packaged-bundle selftest step to both jobs in `build-release.yml`
    (R-M4.A) — the automated guard against F1 recurring.
18. Add checksums, changelog-sourced release body, and LICENSE/NOTICES in the
    archives.
19. Dry-run via `workflow_dispatch` with no tag; download both artifacts.

**Dependency:** Phase 1 (selftest must exist), Phase 3. **Est:** half a day.

### Phase 5 — Licensing text, first run, docs (R-M2.A/C/D, R-M5, R-M6)

20. Draft `LICENSE` and `THIRD_PARTY_NOTICES.md`. **Pause for your review.**
21. Write `tests/test_first_run.py` and `tests/test_release_docs.py`.
22. Fix any first-run degradation gaps the tests expose (R-M5.A).
23. Write `INSTALL.md`, `CHANGELOG.md`; update `README.md` and
    `docs/STANDALONE_BUILD.md`.

**Dependency:** Phase 2 (notices must reflect the post-tkcalendar tree).
**Est:** 1 day.

### Phase 6 — Hygiene, then tag (R-M7)

24. Write `tests/test_repo_hygiene.py`; relocate remaining root clutter.
25. Run `learning-qa` over the whole diff (global process step 5); fix findings.
26. Write the handoff note at `docs/changes/2026-08-18-downloadable-release.md`.
27. Generate `docs/spec_coverage.md` and the completion status report.
28. Tag `v0.1.0` → release workflow → **you download and confirm R-M5.D.**

**Est:** half a day.

**Total: roughly 4 days of focused work.** Phase 2 carries the schedule risk.

---

## 3. Risks

| Risk | Mitigation |
|---|---|
| **The date-picker rewrite regresses date entry** — highest risk in the plan. It touches a widget used across many screens. | Interface tests written against the old widget *first* (step 7), so the new one must satisfy a contract recorded before the swap. Plus a real-app check per the `verify-gui-in-running-app` memory: launch under the venv, exercise the picker, check `app.log`. |
| Tk tests behave differently under xvfb than on macOS | Phase 3 runs before the release pipeline depends on CI. If a test is genuinely display-dependent, it gets marked and reported as such rather than silently skipped (R-M3.B exists to prevent a silent skip). |
| The proprietary license draft is legally weak | Flagged `HUMAN`. It is a template, not legal advice. Real legal review belongs before the first paid sale, not before a free release. |
| A future dependency reintroduces a GPL license | `test_rm2b3_installed_runtime_deps_have_no_gpl_license` checks the whole tree, not just tkcalendar. |
| Windows build unverifiable from this Mac | Explicitly `INTEGRATION-ONLY`. Proven by a green CI run, reported as such — never claimed as locally tested. |

---

## 4. What this plan does not do

- No Railway/Vercel/web work. Out of scope per spec §2.
- No macOS signing or notarization (D2).
- No Linux binary.
- The three adjacent issues in spec §6 are flagged, not fixed (global rule 10).

---

## 5. Approval gate

Per the global planning rules, implementation stops here. Nothing in `src/`,
`tests/`, `.github/`, or the build files has been modified. On approval, work
starts at Phase 1 step 1, and I will pause again at Phase 5 step 20 for your
review of the license text.
