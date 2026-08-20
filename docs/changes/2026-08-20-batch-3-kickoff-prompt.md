# Batch 3 kickoff prompt

Self-contained handoff for a fresh session. Paste the block below.

---

Start Batch 3 of the backlog clearance in ~/ProjectsLocal/GetMoreDone.

State: on main, everything pushed (HEAD eac201f), suite green at 1062 passed / 2
skipped. The only untracked file is visact_rebrand_prompt.md — not mine, leave it
alone. Another Claude session also commits to main in this repo, so pull before
you start and expect commits you didn't write.

The plan: docs/implementation_plan_2026-08-19_backlog_clearance.md. Batches 1 and
2 are done and ticked off. Batch 3 is three items, BI1–BI3. Read that file first,
plus docs/changes/2026-08-19-backlog-batch-2.md — not for the project-link work,
but for the section on what twelve review passes cost and why.

I verified all three items against the code before writing this, so these are
facts, not the plan's claims:

- **BI1** — `.github/workflows/release.yml` calls `softprops/action-gh-release@v3`
  twice, at lines 120 and 307, once inside `build-windows` and once inside
  `build-macos`. Replace both with one `publish` job that `needs: [build-windows,
  build-macos]`, downloads both artifacts and makes a single release call.
- **BI2** — only `requirements.txt` exists. `tests/test_release_licensing.py:34`
  hardcodes `TEST_ONLY_PACKAGES = {"pytest", "pytest-cov"}` and reads it at :174
  and :275. Split `requirements-dev.txt` out and delete that set, so the test
  reads the two files instead of a hand-maintained copy of the answer.
- **BI3** — `src/getmoredone/google_calendar.py:47-48` does
  `self.data_dir = Path.home() / ".getmoredone"` then `.mkdir(exist_ok=True)`
  **before** looking at `credentials_file` / `token_file`, so constructing it with
  explicit paths still creates `~/.getmoredone`. Read the arguments first, only
  create the directory when the defaults are actually used, and use
  `paths.app_data_dir_path()` like the rest of the app.

## Decisions you need to make before you start

**BI1 and BI2 cross the multi-agent ownership boundaries in CLAUDE.md.**
`.github/` belongs to the GitHub Agent and `requirements.txt` to the Docs Agent.
Ask me whether to do them here on main anyway (Batches 1 and 2 both went straight
to main) or to route them properly. Don't guess — this is the first batch that
touches another agent's files.

## Things a fresh context will get wrong

- **Never construct a production object with default arguments in a test.**
  `DatabaseManager()` with no path opens the user's real database and runs
  migrations on it; `AppSettings.load()/.save()` writes the real settings file.
  `conftest.py` redirects both and fingerprints the real files — if a run ends
  with `GUARD:` in the output, a test escaped. Pass `tmp_path` explicitly.
- **`GoogleCalendarManager.__init__` calls `self._authenticate()` at the end.**
  A test that constructs it does real OAuth unless you stop it. The BI3 test has
  to prove `~/.getmoredone` is *not* created without ever reaching the network —
  and asserting on a real home directory is itself a trap, so assert on a
  redirected one and never monkeypatch `Path.home()` globally.
- **CI is the one thing you cannot test by running it.** BI1's only check is a
  contract test over the YAML (`tests/test_ci_contract.py`), and a wrong release
  workflow has a *public* consequence: per BACKLOG.md, a failed job does not
  un-publish a Release, so a half-succeeded run leaves a permanent public release
  carrying one platform's assets. Say plainly in the status report that the
  workflow itself is untested until a real tagged run.
- **Tk tests: windows are withdrawn by an autouse fixture in `conftest.py`.**
  A test that needs real geometry or drives real events must request the
  `mapped_windows` fixture. `winfo_width()` on a withdrawn window returns 1, and
  `event_generate` on one does **not** fail — it *deadlocks*, with no output and
  no clue which test did it. `tests/test_tk_offscreen.py` guards this;
  `tests/test_traceability_refs.py` guards that every `Tests:` docstring
  reference resolves, so any new one you write must point at something real.
- **Two module identities.** The repo supports both `import getmoredone.x` and
  `import src.getmoredone.x`, and Python loads those as different modules with
  different class objects. Patching one does not patch the other. Prefer
  `src.getmoredone.*` in tests.
- **A test that returns a value is a test that does not assert.** pytest ignores
  the return; `PytestReturnNotNoneWarning` is at 0 and should stay there.
- **Mutation-check every guard you write.** In Batch 2, three separate tests
  passed with the code they named deleted outright — including one written to
  fix that exact class. Delete the line, run the suite, confirm red, put it back.
- The running app serves code from memory — restart GetMoreDone to see any
  change, and don't conclude an edit didn't work until you have.

## How to finish

Finish with /csdp. Batch 2 took **twelve** review passes (7, 10, 6, 6, 3, 2, 11,
8, 9, 2, 4, 4) and every single one found a defect inside its predecessor's fix.
Two passes is the working minimum; fix every finding with a test and prove each
test fails without its fix.

The most important thing Batch 2 learned is now P26 in
`~/.claude/standards/learnings.md`: **a falling finding count from self-review is
not a stopping condition.** Six warm passes had the count down to 2 and looked
converged; a cold pass — given only the diff and none of the history — plus one
covering a different failure family then independently found the same two
high-severity defects all six had walked past. Run at least one cold pass before
you call anything clean, and remember the failure-pattern sweep does not cover
logic correctness, UI-contract regression or test quality.

Batch 3 is small and mostly mechanical, so it should not need twelve passes — but
BI1 is the one item in the whole plan whose mistakes are public.

LEARNINGS.md and BACKLOG.md are both current. Don't touch LICENSE (needs a
lawyer) or refactor item_editor.py / db_manager.py (D6, its own batch, later).
Two known-minor items are recorded at the top of BACKLOG.md; leave them unless
they get in your way.
