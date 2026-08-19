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

- **`with self.db.conn:` rolls back the whole connection, not just its block.**
  `_DeferredCommitConnection.__exit__` calls `self._conn.rollback()` on the raw
  connection, which discards everything uncommitted — including an enclosing
  `transaction()`'s work. Harmless today: the two functions that use it
  (`link_item_to_project_exclusive`, `inherit_project_links`) have no caller
  inside `transaction()`, and `transaction()` re-raises anyway. It becomes a
  real bug the day either is called inside a transaction whose exception is
  *caught* — the outer writes would already be gone, silently.
  *Ask:* is this `with conn:` nested inside a `transaction()` whose exception
  the caller swallows?

- **2026-08-18 — `build-windows` and `build-macos` call `action-gh-release` concurrently
  with the same `tag_name`.** Check-then-create race on the first tagged run. A red job
  does **not** un-publish a Release: if one job wins the create and the other errors,
  the outcome is a public Release carrying one platform's assets — the very thing
  `fail_on_unmatched_files` was added to prevent. Deferred because the window is narrow,
  not because it is harmless. Tracked in `BACKLOG.md`. A serialised `publish` job with
  `needs: [build-windows, build-macos]` removes it.
- **RESOLVED 2026-08-19 — the four action major bumps are now verified on real
  runners.** `tests.yml` run `32200605573` (666 passed on 3.11/3.12/3.13) and
  `build-release.yml` run `32200724360` (both OS jobs green) executed on commits
  containing the bump; zero Node 20 deprecation annotations on either; both artifacts
  and both `.sha256` files uploaded by `upload-artifact@v7`, checksum re-verified
  locally.

  Kept here rather than deleted, because of how it read before. An earlier draft of
  this bullet claimed the bumps *had* been verified by running both workflows at a
  point when the v0.2.0 build predated the bump
  (`git merge-base --is-ancestor 93d9fab v0.2.0` → false) and neither commit was even
  pushed. The file that opens by warning about trusting a claim without checking the
  artifact shipped exactly that claim within an hour of being created. (P6)

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

### 2026-08-19 — a test suite that could not fail, and one that opened the live database

**Issue** → `BACKLOG.md` carried "two tests `return` a bool instead of asserting"
as a minor nit. It was 16 tests across four files, and two of them were doing
real damage:
* `test_vps_segments.py::test_enhanced_deletion_protection` **was returning
  False** — a failing test reporting green. It grepped `delete_segment`'s source
  for `vision_count`, a name removed when the return shape changed from
  `tuple[bool, int]` to `tuple[bool, dict]`. The guard for the deletion
  protection had been dead since that refactor, and nobody could tell.
* `test_obsidian_dialogs.py::test_database` constructed `DatabaseManager()`
  **with no path**, which resolves to the user's real application database, and
  `__init__` calls `initialize_schema()` — schema migrations, the Weekly Tactic
  dedupe (which DELETEs rows) and the invariant repair (which moves dates and
  writes `reschedule_history`). Every full-suite run opened production data and
  ran migrations against it. No damage had occurred (the live file's mtime
  predated the runs, and every merge in the log names test fixtures), but the
  same day's BC2 change made the dedupe capable of a merge it could not perform
  before — so the window was about to matter.
**Root cause** → P24 at the suite level. pytest ignores a test's return value, so
`return False` inside `except Exception: return False` makes *any* outcome —
including an exception — a pass. Several checks printed `⚠` and continued, so
they could not fail at all. The files were standalone scripts renamed into the
suite; nothing converted their `if/print/return` verdicts into assertions.
**What would have caught it** → `PytestReturnNotNoneWarning` was in the output of
every single run, 17 times. It was read as noise. A warning that names a test by
path and says it returned a bool is not noise; it is the suite telling you a
verdict was discarded.
**Fix** → all four files rewritten to assert, behaviour exercised instead of
source grepped wherever cheap (`validate_color` now gets real inputs,
`delete_segment` a real linked row). Every database in a test is a temporary
one. `PytestReturnNotNoneWarning` count is now 0, which is the regression guard:
it goes back above zero the moment someone adds another.
**Rule** → **A test that returns is a test that does not assert.** Treat
`PytestReturnNotNoneWarning` as a failure, not a warning. And **never construct a
production object with default arguments in a test** — the default is production:
its path, its database, its config directory. Pass a `tmp_path` explicitly, and
be suspicious of any constructor that does I/O before reading its own arguments.

### 2026-08-19 — the Who field was dead, and Tk hid the reason

**Issue** → Typing in the Item Editor's **Who** box did nothing: no contact dropdown,
no error, no clue. Saving a new item could also fail with only a generic
"Error: …" in the dialog's status label.
**Root cause** → `ItemEditorContactsMixin.on_who_search` opens with
`if self.suggestions_hide_job:`, and nothing ever initialised
`suggestions_hide_job`, `contact_suggestions_frame` or `selected_contact_id`. The
mixin read state that its host dialog was silently expected to create. The first
keystroke raised `AttributeError` **inside a Tk callback**, and Tk's default
`report_callback_exception` prints the traceback to stderr and carries on — so a
hard failure presented as an inert widget. A GUI app launched from a double-click
has nowhere for stderr to go, so the traceback was never seen by anyone.
**What would have caught it** → one test that calls `on_who_search` on a freshly
built dialog. There were 800+ tests and none of them typed in Who: every editor
test either drove `save_item` on a stub that supplied `selected_contact_id`
itself, or asserted a widget *exists* rather than *works* (P25's corollary — a
control that renders is not a control that is wired).
**Fix** → the three attributes are declared as class-level defaults on
`ItemEditorContactsMixin`, where the code that reads them lives, so no future host
class can forget them. Seven tests in `tests/test_item_editor_contacts.py` drive a
real dialog against a real DatabaseManager — typing, filtering, selecting, and
saving with and without a contact.
**Rule** → **A mixin owns its own state.** State a mixin reads must be declared on
the mixin, not assumed to be initialised by whatever class mixes it in.
And: **in a Tk app, an exception inside a callback is invisible** — a widget that
"does nothing" is a raised exception until proven otherwise, so test event handlers
by calling them, not by asserting the widget exists.

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
