# GEMINI.md

This file provides project-specific instructions and context for Gemini CLI.

## Project Overview
**GetMoreDone** is a Python desktop task management application using CustomTkinter and SQLite. It features a layered architecture and a comprehensive Vision Strategy Plan (VSP) subsystem.

## Core Commands
- **Run App:** `./start.sh` (Mac/Linux) or `start.bat` (Windows)
- **Manual Run:** `python run.py`
- **Tests:** `pytest` (all), `pytest -v` (verbose), `pytest <path_to_test> -v` (single file)
- **Demo Data:** `python ../tools/create_demo_data.py`

## Architecture Summary
- **GUI:** `src/getmoredone/screens/` (CustomTkinter)
- **Logic:** `db_manager.py`, `db_manager_project_boards.py`
- **Models:** `models.py` (Dataclasses like `ActionItem`, `Contact`)
- **Database:** `database.py` (SQLite schema/migrations)
- **Themes:** `/themes/` (JSON themes, managed via `AppSettings` and `theme.py`)

## Development Standards & Mandates

### UI Regression Guardrail
Follow `AGENT_UI_REGRESSION_POLICY.md` for any UI change. Existing user-visible controls (buttons, links, tabs, menus, fields, dialogs) are part of the contract and must not be removed, hidden, renamed, or relocated without explicit approval and regression coverage. Before modifying any existing UI, identify the current user-visible actions and preserve them.

### Theme System (CRITICAL)
- **No hard-coded colors:** Never use hex or named colors directly in widgets. Use semantic tokens from `theme.py`.
- **Accents only:** Category/segment colors from DB are for chips/icons/stripes only, never full-row fills.
- **Centralization:** Add new semantic colors to `theme.py`, not in individual screens.

### File Maintainability (`codex.md`)
- **Single Responsibility:** Files should have one clear purpose.
- **Line Counts:** 200-400 (review), 400-700 (careful review), 700+ (refactor candidate).
- **Refactor Triggers:** Branch-heavy functions, deep nesting, hard to test, or multiple unrelated concerns.

### Multi-Agent Workflow
- **Branching:** Work is typically split between Code, Docs, and GitHub agents.
- **Handoff Notes:** After every task, create a note in `docs/changes/<yyyy-mm-dd>-<topic>.md` using the template in `.agents/templates/handoff-note.md`.
- **Verification:** Changes are incomplete without updated tests and documentation sync.

## Testing Strategy
- Always run `pytest` before finalizing any change.
- New features or bug fixes MUST include corresponding test cases in `tests/`.
- Verify UI alignment in dual-panel layouts; matching columns must use consistent widths.

## Documentation
- Refer to `GetMoreDone_MasterSpec_SQLite_v1.md` for the full technical specification.
- `AGENTS.md` contains detailed multi-agent rules and theme system specs.
- `codex.md` contains the full maintainability policy.
