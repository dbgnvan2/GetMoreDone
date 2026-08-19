# LEARNINGS — GetMoreDone failure-pattern playbook

Repo-specific companion to the generic catalogue at `~/.claude/standards/learnings.md`
(P1–P25). That file holds the portable patterns; this one holds what *this* repo has
actually been bitten by, plus risks found by review that have not bitten yet.

Prime directive: **make failure loud and make negatives provable.** The costly bugs
here are not crashes — they are green runs that published nothing, status flags with
no row behind them, and checks that cannot fail.

---

## Patterns most live in this repo

Referenced by ID from the global catalogue; listed here because they recur.

- **P2 — Silent drop on failure.** A step warns instead of failing; "produced nothing"
  and "produced the wrong thing" look identical downstream.
  *Ask:* if this produced nothing, would the run go red — or just log a warning?
- **P5 — Inconsistent robustness across sibling calls.** One publisher/producer in a
  pipeline is hardened, its siblings are not.
  *Ask:* are ALL steps of this kind hardened, or only the one that broke?
- **P6 — Trusting a derived/status field without verifying the artifact.** A flag,
  docstring, or doc claim believed without checking the row/file/tag it asserts.
  *Ask:* does this status reflect something that exists now? What proves it?
- **P8 — Dirty-state / second run.** SQLite state persists between runs; migrations and
  cascades must be tested on a DB that already has prior-run content.
  *Ask:* what does run #2 see?
- **P21/P25 — Built but not wired / wired but unreachable from the front end.** A
  capability exists and its unit tests pass, but no caller on the run path — or the
  GUI never passes the argument.
  *Ask:* which entry points exist, and did each one change?
- **P24 — False green from output parsing.** Success judged by scraping a positive
  token that co-occurs with failure. Decide by exit code.
  *Ask:* would this go green on `N failed, M passed`?

---

## Review checklist

1. Does every step that can produce nothing **fail** rather than warn? (P2)
2. Are sibling steps of the same class hardened identically? (P5)
3. Is any status/claim trusted without reconciling to the artifact it names? (P6)
4. Does anything reading persisted SQLite state have a dirty-state test? (P8)
5. For each new capability: is there a caller on the run path, and does every front
   end (GUI, CLI, workflow) actually pass the argument? (P21/P25)
6. Does any success check parse stdout for a pass token instead of the exit code? (P24)
7. **Check the checkers.** Can the new guard fail? What input does it silently skip?

---

## Open risks (found by review, not yet bitten)

- **2026-08-18 — `build-windows` and `build-macos` call `action-gh-release` concurrently
  with the same `tag_name`.** Check-then-create race on the first tagged run. A red job
  does **not** un-publish a Release: if one job wins the create and the other errors,
  the outcome is a public Release carrying one platform's assets — the very thing
  `fail_on_unmatched_files` was added to prevent. Deferred because the window is narrow,
  not because it is harmless. Tracked in `BACKLOG.md`. A serialised `publish` job with
  `needs: [build-windows, build-macos]` removes it.
- **2026-08-18 — the four action major bumps (checkout/setup-python/upload-artifact v7,
  action-gh-release v3) have NOT been executed on a real runner.** Input names and
  defaults were verified against each action's own `action.yml` at v7/v3; runtime
  behaviour was not. The v0.2.0 release build predates the bump
  (`git merge-base --is-ancestor 93d9fab v0.2.0` → false), so it is not evidence about
  this configuration. Unverified until the next `Build binaries` run on a commit that
  contains the bump. (P6)

  An earlier draft of this very bullet claimed the bumps *had* been verified by running
  both workflows. They had not. Recorded rather than quietly corrected: the file that
  opens by warning about trusting a claim without checking the artifact shipped exactly
  that claim within an hour of being created.

---

## Misses

Bugs that got past a Learning-QA review. Record the diagnosis, not just the bug: was the
pattern absent from the catalogue, present but not fired, or outside the reviewed range?

*(none recorded yet)*

---

## Fix log

Newest first. Format:

> **Issue** → **Root cause** (tag the pattern `Pn`) → **What would have caught it** →
> **Fix** → **Rule**

### 2026-08-18 — two publish steps could succeed while publishing nothing

**Issue** → `upload-artifact@v7` defaulted `if-no-files-found` to `warn`, and
`action-gh-release@v3` defaulted `fail_on_unmatched_files` to `false`. A glob matching
nothing would have produced a green run with a missing artifact, or a public, permanent
GitHub Release with correct notes and zero downloadable assets.
**Root cause** → P2/P24 (silent drop; success decided by something that cannot
distinguish pass from fail) and P5 — `tools/extract_release_notes.py`, the *producer*
feeding the very same step, was explicitly hardened to exit non-zero on missing input,
while both *consumers* defaulted to silent. Hardened at one end of the pipeline only.
**What would have caught it** → reading the actions' own `action.yml` defaults instead
of assuming a sensible one, at the moment of the version bump.
**Fix** → `if-no-files-found: error` and `fail_on_unmatched_files: true` on both OS
jobs, each with a comment naming the default it overrides, plus three tests asserting
both keys per job. The two are not equally strict and the docs must not imply they are:
`if-no-files-found` fires only on a total miss of a step's whole path set, whereas
`fail_on_unmatched_files` is per-pattern.
**Rule** → When bumping a third-party action, read its `action.yml` for inputs whose
*default* is permissive. A publish step that can produce nothing must be configured to
fail, not warn — and hardening one step in a pipeline means checking its siblings.

### 2026-08-18 — the staleness guard had a staleness blind spot

**Issue** → `test_no_workflow_uses_a_node20_action_version` skipped any action absent
from a hardcoded four-name table (`if limit is None: continue`) and any version its
regex could not parse. `actions/cache@v3`, `actions/download-artifact@v4`, a bare `4`,
and a SHA-pinned `checkout` v4 all passed green.
**Root cause** → P3/P24. A checker written to prevent silent staleness whose own
unknown-input path was a silent pass. SHA pinning — the standard next hardening step —
would have disabled it entirely.
**What would have caught it** → asking "what does this test do with an input it does
not recognise?" Any answer that is not "fail" is a bug in a guard.
**Fix** → split into three tests: an unlisted action fails, an unparseable version
fails (with `SHA_PINNED_MAJORS` as the deliberate escape hatch), and the comparison
runs only on inputs both other tests have vouched for. Plus an adversarial test that
replays all four previously-skipped cases.
**Rule** → A guard's unknown-input path must be red, never `continue`. Test the guard
with the inputs it will plausibly meet next, not only the ones it was written for.
