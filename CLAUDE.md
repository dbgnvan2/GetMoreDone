# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run application (recommended — auto-creates venv, installs deps, launches app)
./start.sh          # Linux/Mac
start.bat           # Windows

# Manual run
python run.py

# Tests
pytest                                          # All tests
pytest -v                                       # Verbose
pytest tests/test_vps_integration.py -v        # Single file
pytest --cov=src/getmoredone                   # With coverage

# Create demo data
python create_demo_data.py
```

## Architecture

**GetMoreDone** is a Python desktop task management app using CustomTkinter + SQLite.

### Layered structure

- **GUI** — `src/getmoredone/screens/` — 50+ CustomTkinter screen modules
- **Business logic** — `db_manager.py` (primary CRUD + logic hub) + `db_manager_project_boards.py` (split-off project board logic)
- **Data models** — `models.py` — dataclasses: `ActionItem`, `Contact`, `WorkLog`, `TimeBlock`, etc.
- **Database** — `database.py` (schema init + migrations) + SQLite at:
  - macOS: `~/Library/Application Support/GetMoreDone/getmoredone.db`
  - Windows: `%APPDATA%/GetMoreDone/getmoredone.db`
- **Utilities** — `theme.py`, `paths.py`, `validation.py`, `date_utils.py`, `color_contrast.py`, `utils/`

### Entry point

`run.py` → `getmoredone.app.GetMoreDoneApp` → `AppSettings` loaded first (theme applied before UI) → sidebar drives navigation between 13 screens.

### Key data relationships

- `ActionItem` → `Contact` (who field), `ActionItem` (parent_id, hierarchical), `AnnualPlanElement`, `ProjectBoard`, `WorkLog`, `ItemLink`, `RescheduleHistory`
- `Contact` → `Defaults` (per-client settings)

### VSP (Vision Strategy Plan) subsystem

Strategic planning hierarchy: vision → annual plans → quarterly → monthly → weekly tactics.

- Managers: `vps_manager.py`, `vps_manager_taxonomy.py`, `vps_manager_planning.py`
- Schema: `vps_schema.py`
- UI: `screens/vps_planning.py`, `screens/vps_editors.py`, `screens/vps_segment_editor.py`, `screens/vision_planning_hub.py`

### Theme system

CustomTkinter JSON themes in `/themes/`. Loaded at startup via `AppSettings` before any widgets are created.

**Rules — enforce these when writing or reviewing UI code:**
- No hard-coded hex or named colors in widgets. Use theme defaults or semantic tokens from `theme.py`.
- Segment/category colors from DB (`segment_descriptions.color_hex`) are allowed **only** as small accents (chip/stripe/icon), never as full-row fills.
- Only one "primary" color for main action emphasis; success/warning/danger colors are for status only.
- To add a semantic color, centralize it in `theme.py` — do not scatter one-off constants across screen files.

## Multi-agent workflow

Three agents operate on separate branches/worktrees:

| Agent | Branch | Owns |
|---|---|---|
| Code Agent | `codex/agent-code` | `src/`, `tests/`, `tools/` |
| Docs Agent | `codex/agent-docs` | `README.md`, `docs/`, `CHANGELOG.md`, `requirements.txt` |
| GitHub Agent | `codex/agent-github` | `.github/` |

**After every task**, write a handoff note at `docs/changes/<yyyy-mm-dd>-<topic>.md` using template `.agents/templates/handoff-note.md`. Required fields: summary, files changed, test/verification status, follow-ups.

PRs must pass: tests + docs sync gate (`.github/workflows/agent-docs-gate.yml`).

If code behavior, UI text, or dependencies changed → docs and `requirements.txt` must be updated in the same PR (or a linked Docs Agent PR).

## Global standards

Read the relevant file from `~/.claude/standards/` before starting work:

| Standard | When |
|---|---|
| `file-maintainability.md` | Any new file or significant refactor (replaces the inline policy previously here) |
| `ui-regression.md` | Any change to the 50+ CustomTkinter screens — treat every screen's controls as a contract |
| `security.md` | SQLite parameterised queries, input validation, no secrets in code |
| `learnings.md` | P6 (trust status fields only after verifying the DB row), P8 (dirty-state tests for SQLite reads) |

In tabular/dual-panel UIs, aligned columns are a design goal — matching columns must use consistent widths across rows and paired panels.

## Key files

| File | Purpose |
|---|---|
| `codex.md` | Full file maintainability policy — read before any refactor |
| `AGENTS.md` | Multi-agent workflow rules + theme system spec |
| `GetMoreDone_MasterSpec_SQLite_v1.md` | Complete technical spec |
| `docs/USER_GUIDE.md` | User documentation |
| `BACKLOG.md` | Development priorities |
| `NOTES.md` | Recent changes and known issues |
| `.agents/templates/handoff-note.md` | Handoff note template |
