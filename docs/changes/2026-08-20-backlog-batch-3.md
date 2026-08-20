# Handoff Note

- Date: 2026-08-20
- Agent: Code
- Topic: Backlog clearance Batch 3 — BI1 release workflow, BI2 dev requirements, BI3 calendar paths

## Summary

Batch 3 of [`docs/implementation_plan_2026-08-19_backlog_clearance.md`](../implementation_plan_2026-08-19_backlog_clearance.md).
Three infrastructure items, all three done.

**BI1 (D1) — one release call instead of two.** `build-windows` and `build-macos`
each called `softprops/action-gh-release`, so a tagged run published twice.
Whichever job finished first created the public Release; if the other then
failed, that Release stayed up carrying one platform's assets, because a failed
job does not un-publish a Release another job already created. A single
`publish` job now runs `needs: [build-windows, build-macos]`, downloads both
artifacts into one directory and makes one release call. Release notes are
generated once rather than once per platform.

**BI2 (D3) — `requirements-dev.txt` split out.** `requirements.txt` is now the
runtime set: the list that ships inside the binary and the list
`tests/test_release_licensing.py` checks the GPL rule against. There were **two**
hardcoded copies of "which packages are test-only", not the one the backlog
recorded: `TEST_ONLY_PACKAGES = {"pytest", "pytest-cov"}` in the licensing test,
and `grep -v -E '…^pytest\b|^pytest-cov\b'` in `start.sh`. Both are gone.

**BI3 (D4) — `GoogleCalendarManager` reads its arguments first.** It did
`Path.home() / ".getmoredone"` then `.mkdir()` *before* looking at
`credentials_file` / `token_file`, so constructing it with two explicit paths
created a folder that nothing then used.

## Decision taken before starting

BI1 touches `.github/` (GitHub Agent) and BI2 touches `requirements.txt` (Docs
Agent) — the first items in this plan that cross the ownership boundaries in
`CLAUDE.md`. Raised with the user rather than guessed. **Decision: all three on
`main`**, as Batches 1 and 2 were.

The supporting fact: those agents are dormant. `codex/agent-docs` and
`codex/agent-github` have never existed as branches; `codex/agent-code` is 131
commits behind `main` and was last touched 2026-04-03. Routing to a branch
nobody reads would be ceremony, not review.

**Follow-up worth taking:** `CLAUDE.md` and `AGENTS.md` describe a three-agent
branch workflow that is not how this repo has been worked for months. Left
unchanged here — rewriting the contributor docs is not a Batch 3 item — but it
will keep producing this question.

## Files changed

**BI1**
- `.github/workflows/build-release.yml` — release steps removed from both OS
  jobs; new `publish` job (`needs`, tag gate, two `download-artifact@v8` steps,
  one notes step, one release call).
- `tests/test_ci_contract.py` — `PUBLISH_JOB` / `BUILD_ARTIFACTS` /
  `RELEASE_ARCHIVES` constants; nine new `test_bi1_*`; four existing R-M4.B/C
  tests retargeted from "every OS job" to the publish job; the release-step
  count assertion changed from 2 to 1.

**BI2**
- `requirements.txt` — pytest/pytest-cov removed, header rewritten.
- `requirements-dev.txt` — new; `-r requirements.txt` plus the two test packages.
- `tests/test_release_licensing.py` — `TEST_ONLY_PACKAGES` deleted;
  `_parse_requirements()` reads either file; eight new `test_bi2_*`.
- `start.sh` — installs `requirements.txt` directly; the grep is gone.
- `.github/workflows/tests.yml` — installs `requirements-dev.txt`.
- `tests/test_ci_contract.py` — the dependency-file assertion accepts either
  file and now also rejects installing any package by name.

**BI3**
- `src/getmoredone/paths.py` — new `google_auth_dir()`, returning
  `legacy_dot_dir()`. (An intermediate version took a `create` flag and fell
  back to the app data directory; the reviews removed both — see below.)
- `src/getmoredone/google_calendar.py` — all three default-path sites go through
  `paths.google_auth_dir()`; token save extracted to `_save_token()`, which
  creates its parent directory and reports whether the token reached disk.
- `src/getmoredone/screens/calendar_dialog.py` — the "credentials not found"
  message names the path that was actually checked.
- `tools/diagnose_google_auth.py` — shares the resolver instead of hardcoding
  the path. It is the tool README and INSTALL point users at.
- `tests/test_google_calendar_paths.py` — new, 13 tests.
- `tests/test_first_run.py` — two tests that asserted the *old* behaviour
  (`assert (fake_home / ".getmoredone").exists()`) inverted.

**Incidental — raised by the user mid-session**
- `conftest.py` — `GETMOREDONE_NO_MAPPED_WINDOWS` makes the three geometry
  tests skip instead of mapping a window. The suite was throwing focus-stealing
  windows over the user's work on every run.
- `tests/test_ci_contract.py` — two guards: no workflow may set that variable,
  and it must stay read-from-environment (off by default).

**Docs**
- `CHANGELOG.md`, `BACKLOG.md`, `LEARNINGS.md`, `README.md`, `INSTALL.md`,
  the plan (Batch 3 marked complete; a Batch 4 pointer to rename-safe-links
  added at the user's request).

## Verification

- Command: `GETMOREDONE_NO_MAPPED_WINDOWS=1 ./venv/bin/python -m pytest -q`
- Result after both review rounds: **1099 passed, 6 skipped, exit code 0.**
  (1090 after the original work, 1098 after round one.) The window-mapping
  tests were additionally run unsuppressed: 14 passed, exit 0.
  Baseline was 1062 passed / 2 skipped. The three extra skips are the geometry
  tests suppressed by the variable above; a run without it is required before
  this is called green, and is recorded in the status report.
- Success read from the **exit code**, not from parsing stdout. An early
  command in this session used `${PIPESTATUS[0]}`, which is empty in zsh
  (`pipestatus`, 1-indexed) — it printed `EXIT=` and the harness reported
  success while the suite had one failure. Textbook P24, in the verification
  rather than the code.

### Mutation checks

Every guard was confirmed to fail against the defect it names:

| Mutation | Goes red |
|---|---|
| Restore the eager `mkdir` in `__init__` | 2 BI3 tests |
| Revert `has_credentials` to the hardcoded legacy path | `test_bi3_the_three_default_path_sites_resolve_to_one_directory` |
| Delete `makedirs` from `_save_token` | 2 BI3 tests |
| Put `pytest` back in `requirements.txt` | 2 BI2 tests |
| Drop `-r requirements.txt` from the dev file | `test_bi2_dev_requirements_pulls_in_the_runtime_set` |
| Restore `start.sh`'s grep | `test_bi2_no_module_hardcodes_a_list_of_test_only_packages` |
| Add a second release call to `build-windows` | 3 BI1 tests |
| Narrow `needs:` to one build job | 2 BI1 tests |
| Delete the macOS download step | `test_bi1_publish_job_downloads_every_build_artifact` |

The workflow YAML was also parsed with PyYAML to confirm the job graph, the
`needs:` list, the four attached files and the absence of any release step in
either OS job. PyYAML was then uninstalled — this repo deliberately has no
PyYAML dependency, and the contract tests read the workflows as text.

## What the reviews added

**Three passes in parallel: `learning-qa`, a cold pass given only the diff, and
a correctness/regression pass.** All three independently found the same top
defect. That is the P26 signal — one reviewer agreeing with itself is close to
no evidence; two orthogonal reviews converging is strong.

**The defect was mine, introduced by BI3.** `google_auth_dir()` preferred the
app data directory on a machine that had never had `~/.getmoredone`, and the
legacy directory once one existed. The choice was re-evaluated on every call
and keyed on a directory *other code creates as a side effect*:
`gmail_importer._load_creds` does an unconditional `token_path.parent.mkdir()`
before it checks anything, and that runs from Settings → Integrations and from
a launchd timer. A user who set the calendar up in the app data directory and
later ran a Gmail import had the resolver flip underneath them — "credentials
not found", a second trip through OAuth, and a working token orphaned where
nothing looked for it. The correctness pass reproduced it against the real
modules.

It is fixed by deleting the fallback rather than patching around it. Six of the
reports' other findings were consequences of that one choice, and went with it.

**Two of my own new guards could not fail.** Both found by the cold pass, and
this is the more useful half of the result:

* `_shell_code_only()` truncated each line at its first `#`. The `start.sh`
  grep it exists to catch has a `#` *inside its quoted regex*, so the line was
  cut to `grep -v -E '^\s*` and the word `pytest` was gone before the search
  ran. **My own mutation check passed it** — because I mutated with a
  simplified reconstruction of the grep instead of the verbatim original line.
  That is the lesson worth keeping: a mutation test is only as good as the
  fidelity of the mutation. Re-run with the original line, it now goes red.
* `test_the_mapped_window_opt_out_is_off_by_default` matched substrings, so it
  passed with the condition **inverted** — which would have skipped the three
  geometry tests on every machine including CI, leaving a skip count as the
  only signal. It now drives a real subprocess and asserts the outcome.

**Also found and fixed:** the disjointness test's docstring claimed a check it
could not make; `_parse_requirements` silently dropped `-e` editable
dependencies from both the GPL and notices checks; `_save_token` reported
"failed to save" while a world-readable token sat on disk if only the chmod
failed; the calendar dialog's message hardcoded a path the docs promised it
named; the publish job attached checksums it never verified against the
archives it downloaded; nothing tied the download `path:` to the release
`files:` prefix, and nothing stopped an `always()` being added to the publish
job's `if:` — which would restore the exact defect BI1 removed;
`GETMOREDONE_NO_MAPPED_WINDOWS=0` turned the opt-out *on*; the docs-sync gate
did not know `requirements-dev.txt` exists, in the commit that created it.

### Round two — the fix commit swept as its own range

P26's corollary says the fix commit is the least-reviewed code in a change.
Two more passes over it found **two more of my own tests that could not fail**:

* `test_bi1_download_path_matches_the_release_file_prefix` used a substring
  test, and `release-assets/GetMoreDone-mac.zip` **is a substring of**
  `release-assets/GetMoreDone-mac.zip.sha256`. Reproduced: delete both plain
  `.zip` lines from `files:`, leaving only the checksums, and it passes.
  `fail_on_unmatched_files: true` is satisfied, so that publishes a public,
  permanent Release with correct notes, two `.sha256` files and **no
  downloadable archives** — the exact BI1 failure, through the guard written to
  prevent it.
* `test_bi2_the_docs_sync_gate_knows_about_both_dependency_files` asserted a
  string that also appears in the **comment the same commit added**, so the
  gate could be fully reverted and the test stayed green.

Both are the same shape as the `_shell_code_only` miss in round one: a text
match that hits the explanation rather than the code. Three instances in one
batch is a pattern, not three accidents — recorded in `LEARNINGS.md`.

The pip guard was also found to have become **narrower** than the regex it
replaced (blind to `python3 -m pip install X`, `pip3 install X`,
`sudo pip install X`), and the subprocess test written to replace a
string-matching one was itself scraping stdout for `"1 passed"` — the practice
its own file's docstring forbids (P24).

## Risks / Known gaps

- **BI1 is untested until a real tagged run, and its mistakes are public.**
  This is the one item in the plan that cannot be verified by running it. A
  GitHub Release is public and permanent the moment it exists. The only check
  that exists before a real `v*` tag is `test_bi1_*` reading the YAML — those
  tests are mutation-proven to fail on the defect, which proves the *tests* work,
  not the workflow. **Watch the first tagged run.** If the `publish` job fails,
  no Release is created: that is the intended behaviour, not a regression.
- **`actions/download-artifact@v8`** is new to this repo. Verified against the
  action's own releases: v8.0.1 is latest, the `v8` major tag exists, and v8
  errors on a download hash mismatch by default. It has never run here.
- **The three geometry tests did not run in this session's iteration loop.**
  They were suppressed to stop the suite stealing focus. See the status report
  for the full-run result.
- **`permissions: contents: write` is still workflow-level**, so both build jobs
  hold write access they no longer need — only `publish` creates anything now.
  Adjacent, deliberately **not** fixed: narrowing it is a change to a workflow
  that cannot be tested here, bundled with the change that already cannot be
  tested here. Worth doing on its own.
- **`~/.getmoredone` vs the app data directory.** The plan said use
  `paths.app_data_dir_path()`. Taken literally that moves the credentials
  directory and breaks every existing install, `README.md`, `INSTALL.md` and
  `tools/import_gmd_from_gmail.py`, which all name `~/.getmoredone` — this
  machine has one, with live credentials in it. `google_auth_dir()` therefore
  prefers the legacy directory **whenever it exists** and uses the app data
  directory only on a machine that has never had one. Both documented.
- **Adjacent, found and not fixed:** `check_token_validity()` and
  `has_credentials()` are `@staticmethod`s reached without constructing the
  manager, so they cannot honour an instance's explicit paths. Unchanged
  behaviour; noted because they now share a resolver with `__init__` and the
  asymmetry is easier to mistake for a bug.

## Next agent actions

- Batch 4: rename-safe links. Spec, plan and kickoff all exist and are approved;
  nothing is built. Start with RN-M2.D, which fails at three of six renames
  today and must not be weakened to get an early green.
- Watch the first `v*` tag for BI1.
