# Handoff Note

- Date: 2026-08-20
- Agent: Code
- Topic: Retire the multi-agent workflow docs; add review-sweep and test rules; extend the global learnings catalogue

## Summary

Docs-only. No `src/` or `tests/` changes.

Acts on the 2026-08-20 external audit. Three things:

1. **The three-agent branch workflow is retired** in `CLAUDE.md` and
   `AGENTS.md`. It described branches that do not exist.
2. **New `Review sweeps` and `Test rules` sections** in `CLAUDE.md`, encoding
   the sweep budget and the test-quality rules the audit asked for.
3. **`~/.claude/standards/learnings.md` gains P27–P29** plus corollaries on
   P19 and P26, and five new review-checklist items so the patterns are
   actually consulted rather than merely recorded.

## Claims verified before writing

The audit's cited commits were checked with `git log -1 --format=%b` rather
than taken on trust. All three exist and their messages support the claims:

| Commit | Claim | Verdict |
|---|---|---|
| `3892159` | 16 vacuous tests; one opened the production DB | **Confirmed.** Message: "It was sixteen across four files, and two of them were doing real harm." `test_enhanced_deletion_protection` was `return False` over a guard dead since `delete_segment`'s return shape changed; `test_database` called `DatabaseManager()` with no path, and `__init__` runs migrations, a row-deleting dedupe and a date-moving repair |
| `2383cbd` | Pass 10's fix caused a high-severity regression caught at pass 11 | **Confirmed.** Pass 10 changed `count` to exclude the target board and left the sentence deriving from the old meaning, understating a deletion by exactly one link |
| `eac201f` | A `> 20` floor hid a 154 → 127 narrowing | **Confirmed**, with the direction worth stating precisely: the scan had narrowed *to* 127 and the fix restored it *to* 154. The floor was satisfied throughout |

Two corrections to the prompt's assumptions:

- **`learnings.md` is at P26, not "at least through P8".** New entries are
  P27–P29.
- **Three of the five proposed entries duplicated existing patterns**, so per
  the prompt's own instruction they extend rather than add numbers:
  *fix passes create defects* → a new corollary on **P26**;
  *source-grep assertions go stale* → a new corollary on **P19**;
  *floor assertions* was distinct enough from P9 to earn **P29** of its own.

## Files changed

- `CLAUDE.md` — `Multi-agent workflow` → `Working agreements`; new
  `Review sweeps` and `Test rules` sections; Commands block documents
  `pytest -m "not meta"` (marked PENDING) and
  `GETMOREDONE_NO_MAPPED_WINDOWS=1 pytest`.
- `AGENTS.md` — the workflow half replaced. **Not** reduced to a pointer: the
  second half is the live UI Theme System spec, which `CLAUDE.md` references,
  and it is preserved verbatim. The handoff-note requirement, docs-sync rule,
  merge gates and UI-regression guardrail are retained — none of them was ever
  about the agent split.
- `~/.claude/standards/learnings.md` (separate repo `dbgnvan2/claude-standards`,
  pulled before editing, committed `1263158`, pushed) — P27, P28, P29;
  corollaries on P19 and P26; checklist items 28–32.

## Verification

- `git diff --name-only` in this repo: `AGENTS.md`, `CLAUDE.md` only. No
  `src/`, no `tests/`.
- The standards repo was pulled before editing and pushed after, per the
  two-Mac sync rule in `~/.claude/CLAUDE.md`.
- Suite untouched and still green from the Batch 3 push: 1108 passed,
  5 skipped, exit 0.

## Risks / Known gaps

- **I disagree with the two-pass sweep cap, and implemented it anyway.** It is
  written in `CLAUDE.md` as specified. The counter-evidence, from the batch
  that finished immediately before this one:

  | Round | Found |
  |---|---|
  | 3 | The pip guard, "de-duplicated", went blind to `pip install --pre <pkg>` and five siblings |
  | 4 | A status `print` inside a credential `try` discarded a valid token on a failed stdout write — user-facing, every launch |

  A two-pass cap ships round four's bug. The audit's evidence is equally real
  (Batch 2's passes 11 and 12 found only meta-defects), and the two datasets
  disagree. The variable that separates them is not the pass *count* but the
  pass *kind*: Batch 3's later rounds were **cold** — given the diff and none
  of the history — and each covered a different failure family. Batch 2's were
  warm repeats of one reviewer.

  So the rule as written is followed by a paragraph making the distinction
  explicit: *cap warm self-review at two, require one cold pass regardless.*
  If that reads as hedging the instruction, delete the paragraph — but the
  measurement behind it is in `LEARNINGS.md` and P26.

- **The retirement is not complete.** Four files still describe the dead
  workflow and were left alone, because rewriting them is not this task:
  `docs/MULTI_AGENT_WORKFLOW.md`, `.agents/prompts/{code,docs,github}-agent.md`,
  and `tools/agents/setup_worktrees.sh` (which creates the three branches).
  `tools/agents/check_docs_sync.py` is live and correct and stays.
  Recorded in `BACKLOG.md`.

- **`pytest -m "not meta"` is documented but does not work yet.** Marked
  PENDING in the Commands block; it lands with the test-suite remediation
  batch. Documenting an invocation before it exists is a small P21 risk —
  the PENDING marker is what stops it reading as available.

## Next agent actions

- The test-suite remediation batch (`prompt-test-suite-remediation.md`): the
  `meta` marker, source-grep elimination, the live-data conftest guard, and the
  vacuous-test scan. Ten tests from Batch 3 are already recorded in
  `BACKLOG.md` as unable to fail; they belong in that batch's task 4.
