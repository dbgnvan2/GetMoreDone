# Working agreements (daVIPA)

> **The three-agent branch workflow this file used to describe is retired.**
> `codex/agent-docs` and `codex/agent-github` were never created as branches,
> and `codex/agent-code` was last touched 2026-04-03, 131 commits behind
> `main`. Work happens on `main`, or on a feature branch merged into it. The
> requirements below are retained because they were never about the agent
> split — they are about not losing context between sessions.

## Required handoff artifact

Every batch of work writes a handoff note at:
- `docs/changes/<yyyy-mm-dd>-<topic>.md`

Use template:
- `.agents/templates/handoff-note.md`

Minimum fields:
- Summary of change
- Files changed
- Test/verification status
- Follow-ups for the next session

## Docs sync

If code behaviour, UI text, CLI flags, or dependencies changed, docs and the
requirements files must be updated in the same change. Enforced by
`.github/workflows/agent-docs-gate.yml`, which treats both
`requirements.txt` and `requirements-dev.txt` as dependency files.

## Merge gates

- tests pass (`.github/workflows/tests.yml`)
- docs sync gate passes (`.github/workflows/agent-docs-gate.yml`)
- UI regression coverage satisfied (per `docs/AGENT_UI_REGRESSION_POLICY.md`)

## UI Regression Guardrail

Follow `docs/AGENT_UI_REGRESSION_POLICY.md` for any UI change. Existing
user-visible controls are part of the contract and must not be removed, hidden,
renamed, or relocated without explicit approval and regression coverage. Before
modifying any existing UI, identify the current user-visible actions and
preserve them.

---

# daVIPA — UI Theme System (CustomTkinter)

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