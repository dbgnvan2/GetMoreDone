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
- UI regression coverage satisfied (per `AGENT_UI_REGRESSION_POLICY.md`)
- PR checklist completed

## UI Regression Guardrail

Follow `AGENT_UI_REGRESSION_POLICY.md` for any UI change. Existing user-visible controls are part of the contract and must not be removed, hidden, renamed, or relocated without explicit approval and regression coverage. Before modifying any existing UI, identify the current user-visible actions and preserve them.

## Rule of thumb

If code behavior, UI text, CLI flags, or dependencies changed, docs and requirements must be updated in the same PR (or linked follow-up PR owned by Docs Agent).


# GetMoreDone — UI Theme System (CustomTkinter)

## Goal
Implement a cohesive UI color system with low runtime overhead by:
1) using CustomTkinter custom theme JSON for global widget defaults, and
2) using a small set of semantic color tokens for UI states (selection, danger, etc.)

## Tech constraints
- UI framework: CustomTkinter.
- Use CustomTkinter custom theme JSON files loaded via:
  customtkinter.set_default_color_theme("path/to/theme.json")
- Appearance mode values must be one of: "system", "dark", "light".

## Theme architecture
- Create /themes directory with >= 2 theme json files (e.g., graphite.json, ocean.json).
- Add user settings:
  - appearance_mode: "system" | "dark" | "light"
  - theme_name: string mapped to a theme json path
- On app startup:
  - load AppSettings first
  - call set_appearance_mode(settings.appearance_mode)
  - call set_default_color_theme(path_for_theme_name)

## Semantic color rules
- Reduce color noise: only 1 “primary” color for main action emphasis.
- “Success/Warning/Danger” colors are for status only (not decoration).
- Segment/category colors from data (e.g., segment_descriptions.color_hex) are allowed ONLY for small accents (chip/stripe/icon), not full-row fills.

## Refactor policy
- No new hard-coded colors in widgets (hex or named colors) except:
  - data-driven segment colors
  - very rare one-off brand assets (must be centralized)
- Replace existing hard-coded fg_color/hover_color/text_color with:
  - theme defaults OR
  - a small semantic style helper (e.g., ui/theme_tokens.py)

## Definition of done
1) Theme can be switched via Settings screen (and persists).
2) Sidebar buttons no longer hard-code greens/teals; they follow theme.
3) Row selection highlight is subtle (not a saturated full-row fill).
4) Timer/Edit/Push button hierarchy is consistent (primary/secondary/ghost).
5) Grep shows near-zero hard-coded color strings in UI code.