# Multi-Agent Workflow (GetMoreDone)

This repository supports a 3-agent workflow:
- `Code Agent`: ships code + tests.
- `Docs Agent`: updates requirements/user guide/changelog and doc index.
- `GitHub Agent`: manages PR lifecycle, labels, release notes, and merge gates.

## Ownership boundaries

`Code Agent` may edit:
- `src/**`
- `tests/**`
- `tools/**`
- small supporting docs under `docs/` only when needed for technical accuracy

`Docs Agent` may edit:
- `README.md`
- `requirements.txt` (dependency narrative updates and pin alignment)
- `GetMoreDone_MasterSpec_SQLite_v1.md`
- `docs/USER_GUIDE.md`
- `docs/DOCUMENTATION_INDEX.md`
- `docs/ROADMAP.md`
- `docs/*.md`
- `CHANGELOG.md`

`GitHub Agent` may edit:
- `.github/**`
- release/changelog metadata files
- no feature code unless explicitly requested

## Required handoff artifact

Each agent must write a handoff note in:
- `docs/changes/<yyyy-mm-dd>-<topic>.md`

Use template:
- `.agents/templates/handoff-note.md`

Minimum fields:
- Summary of change
- Files changed
- Test/verification status
- Follow-ups for next agent

## Branch/worktree model

Use one branch/worktree per role:
- `codex/agent-code`
- `codex/agent-docs`
- `codex/agent-github`

Bootstrap with:
- `tools/agents/setup_worktrees.sh`

## Merge gates

PRs must satisfy:
- tests pass (project test workflow)
- docs sync gate passes (`.github/workflows/agent-docs-gate.yml`)
- PR checklist completed

## Rule of thumb

If code behavior, UI text, CLI flags, or dependencies changed, docs and requirements must be updated in the same PR (or linked follow-up PR owned by Docs Agent).
