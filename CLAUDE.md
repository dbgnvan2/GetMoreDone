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
pytest -m "not meta"                            # App behaviour only (911 tests, ~27s)
pytest -m meta                                  # Repo/infra assertions only (198 tests, ~25s)
pytest -v                                       # Verbose
pytest tests/test_vps_integration.py -v        # Single file
pytest --cov=src/getmoredone                   # With coverage

# Three tests build a real on-screen window and take keyboard focus.
# Skip them while working on the machine. CI never sets this.
GETMOREDONE_NO_MAPPED_WINDOWS=1 pytest

# Create demo data
python tools/create_demo_data.py
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

## Working agreements

Work happens on `main`, or on a feature branch merged into it. There are no
per-role branches: the three-agent workflow this section used to describe is
retired — `codex/agent-docs` and `codex/agent-github` never existed as branches,
and `codex/agent-code` was last touched 2026-04-03, 131 commits behind `main`.
See `AGENTS.md` for the full agreements.

**After every batch of work**, write a handoff note at
`docs/changes/<yyyy-mm-dd>-<topic>.md` using template
`.agents/templates/handoff-note.md`. Required fields: summary, files changed,
test/verification status, follow-ups.

If code behavior, UI text, or dependencies changed → docs and the requirements
files must be updated in the same change. Enforced by the docs sync gate
(`.github/workflows/agent-docs-gate.yml`), which treats both `requirements.txt`
and `requirements-dev.txt` as dependency files.

## Review sweeps

A sweep is a review pass over a batch before it is pushed. The rules exist
because passes are not free: every fix is new unreviewed surface, and a fix
pass has been measured introducing defects at roughly the rate it removes them.

**The pass that matters is a cold one, not an extra warm one.** A warm pass is
run by the context that wrote the code and inherits its blind spots — it runs
out of new assumptions to question long before it runs out of defects. A cold
pass gets the diff and the range and none of the narrative.

The budget:

- **At most 2 warm passes per batch.** Beyond two they converge on the
  reviewer's blind spots, not on correctness, and the falling finding count
  reads as progress while it is measuring exhaustion.
- **At least 1 cold pass, always** — not as a third warm pass, and not only
  when a batch "feels risky". This is the requirement, not the optional extra.
- **A further pass only if the previous one produced a high-severity finding.**
  Make it cold too, and prefer a *different failure family* (correctness, UI
  contract, test quality) over repeating the same sweep.
- **Stop when a pass yields no finding of medium or higher severity.**
- **Every finding gets a severity before any fix is written.** Below-medium
  findings go to `BACKLOG.md`; they are not fixed in-loop, because a cosmetic
  fix buys none of the safety it costs.
- **Every in-loop fix is itself in scope for the next pass.** The fix commit is
  the least-reviewed code in any change — written last, fastest, and in the
  most anchored state.

Evidence for the shape of this, both directions, in
`~/.claude/standards/learnings.md` P26:

- One batch ran to **twelve** warm passes. Passes 11 and 12 still produced four
  findings each, but they were meta — guard tests, docstring wording, message
  phrasing. Pass 10's own fix caused a high-severity regression (`2383cbd`).
- A later batch capped warm passes and ran cold ones instead. Round 3 found a
  guard that had been made *worse* by a previous fix; round 4 found a status
  `print` inside a credential `try` that discarded a valid token on a failed
  stdout write — user-facing, every launch. Both were found cold. Neither would
  have been caught by more warm passes, and a warm-only budget of two would
  have shipped the second.

## Test rules

- **Every test must be able to fail.** No returning bools, no assert-free
  bodies. Prove it by mutation — delete or invert the line the test names, run
  it, confirm red, restore — and mutate with the **verbatim** original, never a
  simplified reconstruction.
- **Never modify a test to make it pass** without first stating which applies:
  (a) the code is wrong, (b) the behaviour changed intentionally, (c) the test
  was over-specified or vacuous.
- **Do not assert by grepping source text** unless no behavioural check is
  practical. Where a source-text guard is unavoidable, parse it (walk the AST,
  or anchor the match to a whole line) and assert **exact counts**, never
  `> N` floors — a floor hides the narrowing it was written to catch.
- **Every `DatabaseManager` in a test takes an explicit `tmp_path` database.**
  The default path resolves to the user's real application database, and
  `__init__` runs migrations against it.
- **Commit test changes separately from `src/` changes**, so the ratio stays
  visible in `git log --stat`.

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
