# Spec — Reward-Contingent Task Chunking (Dopamine Protocol)

**Date:** 2026-08-23
**Status:** Draft for implementation
**Scope:** daVIPA timer + action items + project boards

---

## 1. Summary

Give the timer a **reward protocol** grounded in reward-prediction / wanting-vs-liking
neuroscience. The goal is to train the brain's craving system (mesolimbic dopamine) to
fire on **deliverable completion + effort**, not on time-passed, and to re-couple wanting
to genuine satisfaction rather than cheap novelty.

The mechanism, in one line: **the reward signal must fire on *deliverable completion*, never
on the timer ring, and it must be *earned*, not granted.**

Two reward channels, kept separate:

| Channel | Type | Schedule | Purpose |
|---|---|---|---|
| **Savor** | internal, hedonic (opioid/endocannabinoid "liking") | Phase 1: every completion. Phase 2: intermittent (~40%). | Aim the felt "good" signal at the artifact/effort, so dopamine's wanting attaches to the work. |
| **Celebration** | external, novelty (dopamine) | **Always random (~20%), never guaranteed**, independent of phase. | A surprise "win" that keeps wanting alive without becoming a predictable cue. |

Rationale (primary sources): dopamine encodes reward *prediction error*, not reward magnitude
(Schultz 1998/2016); dopamine fires on the *cue that predicts* the reward and migrates off the
reward itself (cue transfer); dopamine mediates "wanting"/incentive salience, not "liking"
(Berridge & Robinson 2016); dopamine *ramps* during anticipation/approach toward proximal goals
(Howe 2013); continuous reinforcement acquires an association, partial (intermittent)
reinforcement maintains it — reward every time is "a path to failure" (Huberman Lab ep.39).

---

## 2. Data model changes

All migrations must be added to **both** the `CREATE TABLE` definitions in
`src/getmoredone/database.py` **and** the existing-DB migration list (the code path near
"Run migrations for existing databases"). Guard each `ALTER TABLE ... ADD COLUMN` against
the column already existing (e.g. check `PRAGMA table_info`).

### 2.1 `action_items` — add `deliverable`

```sql
ALTER TABLE action_items ADD COLUMN deliverable TEXT;
```

The crisp "done = …" definition of this task. A **checkable artifact**, not a time-box.
Good: "Draft section 2's opening paragraph". Bad: "Work on the report for 25 min".

### 2.2 `work_logs` — add reward-protocol audit columns

```sql
ALTER TABLE work_logs ADD COLUMN deliverable_snapshot TEXT;
ALTER TABLE work_logs ADD COLUMN deliverable_completed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE work_logs ADD COLUMN savor_delivered        INTEGER NOT NULL DEFAULT 0;
ALTER TABLE work_logs ADD COLUMN celebration_type       TEXT;   -- NULL | 'confetti' | 'balloon' | 'tada'
ALTER TABLE work_logs ADD COLUMN phase                  TEXT;   -- NULL | 'wiring' | 'maintaining'
```

`deliverable_snapshot` is the deliverable text as it stood at session start (preserves history
if the action's `deliverable` is later edited). `deliverable_completed` is 1 only when the user
hit "Done". `savor_delivered` is 1 only when the savor step was actually shown.

### 2.3 `project_boards` — add the phase counter

```sql
ALTER TABLE project_boards ADD COLUMN savor_count INTEGER NOT NULL DEFAULT 0;
```

Cumulative count of **completed deliverables** on this board. Phase is *derived* from it
(see §3). Counter advances on every "Done", regardless of whether the savor prompt was shown.

---

## 3. Config & decision logic

New module `src/getmoredone/reward_protocol.py` (pure, no UI):

```python
WIRING_THRESHOLD = 15              # completions before a project graduates to Phase 2
SAVOR_PROMPT_P2_PROBABILITY = 0.4  # Phase 2: savor reminder shown on ~40% of completions
CELEBRATION_PROBABILITY = 0.2      # celebration fires on ~20% of completions, any phase
CELEBRATION_TYPES = ("confetti", "balloon", "tada")

def phase_for(savor_count: int) -> str:
    return "wiring" if savor_count < WIRING_THRESHOLD else "maintaining"

def decide_reward(savor_count: int, rng) -> RewardDecision:
    phase = phase_for(savor_count)
    # Savor is phase-gated
    show_savor = (phase == "wiring") or (rng.random() < SAVOR_PROMPT_P2_PROBABILITY)
    # Celebration is ALWAYS random and independent of phase (never guaranteed)
    celebration = rng.choice(CELEBRATION_TYPES) if rng.random() < CELEBRATION_PROBABILITY else None
    return RewardDecision(phase=phase, show_savor=show_savor, celebration=celebration)
```

`RewardDecision` is a small dataclass. Use a seeded/ injectable `rng` so the logic is
unit-testable deterministically.

**Rule:** `savor_count += 1` on **every** "Done" (deliverable complete). The *prompt* is
phase-gated; the *counter* is not.

---

## 4. UX flow (hook points into `screens/timer_window.py`)

### 4.1 Deliverable field on the item (Step 1 — scope)

Add a "Deliverable" input to the item editor (`screens/item_editor.py`) and the `ActionItem`
dataclass (`models.py`). Optional for unlinked items; **required** for the reward path.

### 4.2 Timer start — confirm deliverable (in `start_timer`, ~line 407)

If the item is **project-linked** (resolves via `project_board_items`), before starting:

1. Resolve the linked `project_board` and compute the current phase.
2. Show a **Deliverable dialog** prefilled with `item.deliverable`. If empty, require entry
   with hint: *"What does 'done' look like? A checkable artifact, not time spent."*
3. Store on the session: `session_deliverable` (snapshot), `session_board_id`, `session_phase`.

Items **not** project-linked run the existing timer with **no reward protocol** (unchanged).

### 4.3 Break-end is neutral (in `tick`, ~line 537–551)

Currently break-end calls `stop_timer()` → shows Finished/Continue. **Change:** break-end must
**not** auto-stop into the completion flow. Instead offer **Pause (rest)** / **Continue focus**
— a neutral loop. This is the user's "pause or continue". The reward never fires on the ring.

> ⚠️ UI-regression guardrail (AGENTS.md): the Stop button and the Finished/Continue completion
> frame are existing user-visible controls and must remain. Only the *auto-trigger on break-end*
> changes; the controls themselves are preserved (Stop still works; Finished/Continue still
> appear after a manual Stop).

### 4.4 "Done" button (new — deliverable complete)

Add a **"Done"** button visible whenever the timer is `running`, `in_break`, or `paused`
(available *any* time, not only at the ring — completion, not time, is the contingency).

On "Done":
1. If not project-linked → fall back to the existing completion flow (no reward protocol).
2. If project-linked → run the reward sequence (§4.5), then the existing completion flow.

### 4.5 Reward sequence (on "Done")

```
d = reward_protocol.decide_reward(board.savor_count, rng)

# 1) Savor step (phase-gated)
if d.show_savor:
    show SavorDialog(snapshot=session_deliverable)
    wait for acknowledgment ("Finished")

# 2) Celebration (always random, AFTER savor)
if d.celebration:
    fire_celebration(d.celebration)   # confetti | balloon | "Ta-DA!" sound

# 3) Advance counter (every completion)
db.increment_project_savor_count(session_board_id)

# 4) Persist session
save_work_log(..., deliverable_snapshot=session_deliverable,
              deliverable_completed=1, savor_delivered=int(d.show_savor),
              celebration_type=d.celebration, phase=d.phase)
# 5) Existing completion flow (completion note → complete_action_item → close)
```

**SavorDialog copy** (exact — this is the heart of the feature):

- Title: **"Deliverable complete"**
- WHAT: *"You set out to: {deliverable_snapshot}. It's done."*
- HOW: *"Pause 5 seconds. Look at what you just made. Notice the physical sense of 'closed.'
  You did something hard and leaned in — feel the effort, not just the finish."*
- Button: **"Finished"**

No "good job" narration — the copy directs attention to the *artifact* and the *felt sense*,
never a hollow verbal pat.

**Celebration** (lightweight overlay, ~1–2s, non-blocking): a canvas confetti burst, an emoji
balloon float, or a short "Ta-DA!" audio clip (reuse `utils/audio_playback.py` where possible).
It is a *surprise bonus on top of* the savor, never a substitute for it. **No "inspiring quote"**
in the core flow (defer as an optional caption *under* the savor if ever desired).

---

## 5. Implementation checklist

1. `models.py` — add `deliverable` to `ActionItem`; `savor_count` to `ProjectBoard`; new
   fields to `WorkLog`.
2. `database.py` — add columns to `CREATE TABLE` for `action_items`, `work_logs`,
   `project_boards`; add idempotent `ALTER TABLE` migrations for existing DBs.
3. `db_manager.py` — extend `create_work_log`/`_row_to_work_log` for new columns; add
   `increment_project_savor_count(board_id)`; add `get_project_boards_for_item(item_id)`
   (returns the linked board(s) — see Open Decisions for the multi-board rule).
4. `reward_protocol.py` — new pure module (§3).
5. `screens/item_editor.py` — add the Deliverable field.
6. `screens/timer_window.py` — deliverable-confirm dialog at start (§4.2); break-end neutral
   (§4.3); "Done" button (§4.4); SavorDialog + celebration + counter increment (§4.5);
   extend `save_work_log` to write new fields.
7. `screens/timer_window_dialogs.py` — add `DeliverableDialog` and `SavorDialog` (mirror the
   existing `CompletionNoteDialog` pattern).
8. Celebration assets — confetti/balloon/sound (tiny, local, no network).

---

## 6. Testing & acceptance criteria

Unit (seeded rng):
- `phase_for`: `< 15 → wiring`, `≥ 15 → maintaining`.
- `decide_reward`: Phase 1 always `show_savor=True`; Phase 2 `show_savor` ≈ 40% over many
  draws; `celebration` ≈ 20% in **both** phases and is **independent** of `show_savor`.
- Migration: new columns exist with correct defaults; re-running migration is idempotent.

Integration:
- Unlinked item → existing timer flow, **no** reward protocol, **no** `savor_count` change.
- Linked item, "Done" in Phase 1 → savor shown every completion; `savor_count` increments.
- After 15 completions → Phase 2 → savor intermittent (~40%).
- Celebration never fires *instead of* savor; it fires only after it, and only ~20% of the time.
- `work_logs` row carries `deliverable_snapshot`, `deliverable_completed=1`, `savor_delivered`,
  `celebration_type`, `phase`.

UI regression (per `docs/AGENT_UI_REGRESSION_POLICY.md`): Start/Pause/Stop/Finished/Continue,
music controls, notes, and the Next Action window all still behave as before.

---

## 7. Open decisions

1. **Multi-board items** (`project_board_items` is many-to-many). MVP: use the *first* linked
   board (ordered by `created_at`). Decide whether to support multi-board savor counting later.
2. **Phase generalization** — a *new project in a familiar category* ideally starts part-way
   into Phase 1 (partial transfer). Out of scope for v1; note a manual `phase_override` or a
   `savor_count` seed as a future refinement.
3. **Celebration asset specifics** — exact confetti/balloon/sound implementations.
4. **"Inspiring quote"** — dropped from core (see §1/§4.5); optional caption deferred.

---

## 8. Source references

- Schultz, W. (1998/2016) — dopamine reward prediction error / cue transfer.
- Berridge, K.C. & Robinson, T.E. (2016) — "wanting" (dopamine) vs "liking" (opioid/endocannabinoid).
- Robinson, T.E. & Berridge, K.C. (2008; 2024) — incentive sensitization; wanting grows while liking is flat.
- Howe, M.W. et al. (2013) — dopamine ramps during approach to proximal goals.
- Huberman Lab ep.39 — "Controlling Your Dopamine": peaks/baselines, intermittent reward,
  attach dopamine to effort, "don't reward every time".
