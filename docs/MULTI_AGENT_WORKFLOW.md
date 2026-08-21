# Multi-Agent Workflow (Code + Docs + GitHub)

This project includes a starter setup for running three parallel agents with explicit handoffs.

## Agents

- Code Agent: implement features/fixes and tests
- Docs Agent: update requirements, user guide, and docs index
- GitHub Agent: manage PR quality gates, labels, and merges

Role prompts live in:
- `.agents/prompts/code-agent.md`
- `.agents/prompts/docs-agent.md`
- `.agents/prompts/github-agent.md`

## One-time setup

From repo root:

```bash
tools/agents/setup_worktrees.sh ../daVIPA-agents
```

This creates:
- `../daVIPA-agents/code` on `codex/agent-code`
- `../daVIPA-agents/docs` on `codex/agent-docs`
- `../daVIPA-agents/github` on `codex/agent-github`

## Daily usage

1. Run one agent session in each worktree.
2. Keep each role inside its ownership boundaries from `AGENTS.md`.
3. After each meaningful change, create a handoff note in `docs/changes/`.
4. Open/update PR with `.github/pull_request_template.md`.

## Docs gate behavior

PR workflow `.github/workflows/agent-docs-gate.yml` runs `tools/agents/check_docs_sync.py`.

The gate fails when:
- code/dependency files changed (`src/`, `tools/`, `tests/`, or `requirements.txt`), and
- no documentation update is present, or
- no handoff note exists in `docs/changes/`

## Handoff template

Use:
- `.agents/templates/handoff-note.md`

Recommended filename:
- `docs/changes/YYYY-MM-DD-topic.md`
