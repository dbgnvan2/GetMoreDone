"""The reward-contingent chunking protocol: when to savor, when to celebrate.

Purpose: RP-3 — decide, for one completed deliverable, whether the savor step is
         shown and whether a celebration fires, from the board's cumulative
         completion count alone.
Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#3-config--decision-logic
Tests:   tests/test_reward_protocol.py

Two channels, deliberately kept apart:

* **Savor** is phase-gated. Early on (Phase 1, "wiring") it is shown on every
  completion, which is what builds the association in the first place. Once the
  association exists (Phase 2, "maintaining") it drops to intermittent, because
  a reward that arrives every single time stops being informative.
* **Celebration** is *always* random and never guaranteed, in either phase. The
  moment it becomes predictable it turns into a cue rather than a surprise, and
  a cue is the thing this protocol is trying not to build.

The module is pure: no UI, no database, no clock. The random source is injected
so the decision is deterministic under a seed and the rates below can actually
be asserted rather than eyeballed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

# Completions before a project graduates from wiring to maintaining. A count,
# not a duration — the protocol is contingent on delivered work, never on time
# passed, which is the whole point of the feature.
WIRING_THRESHOLD = 15

# Phase 2 only: how often the savor reminder is shown. Intermittent by design.
SAVOR_PROMPT_P2_PROBABILITY = 0.4

# Any phase: how often a celebration fires. Independent of the savor decision.
CELEBRATION_PROBABILITY = 0.2

CELEBRATION_TYPES = ("confetti", "balloon", "tada")

PHASE_WIRING = "wiring"
PHASE_MAINTAINING = "maintaining"


@dataclass(frozen=True)
class RewardDecision:
    """What the timer should do for one completed deliverable.

    ``celebration`` is either ``None`` or a member of ``CELEBRATION_TYPES``;
    it is a bonus on top of the savor step, never a substitute for it.
    """

    phase: str
    show_savor: bool
    celebration: Optional[str]


def phase_for(savor_count: int) -> str:
    """Which phase a board with ``savor_count`` completed deliverables is in.

    Purpose: RP-3.1 — derive the phase rather than storing it, so the counter is
             the single source of truth and the two cannot disagree.
    Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#3-config--decision-logic
    Tests:   tests/test_reward_protocol.py::test_rp31_phase_for_boundary_is_exactly_fifteen
    """
    return PHASE_WIRING if savor_count < WIRING_THRESHOLD else PHASE_MAINTAINING


def decide_reward(savor_count: int, rng: random.Random) -> RewardDecision:
    """Decide the savor and celebration channels for one completion.

    Purpose: RP-3.2 – RP-3.7 — phase-gate the savor prompt; keep the celebration
             random and independent of it in both phases.
    Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#45-reward-sequence-on-done
    Tests:   tests/test_reward_protocol.py::test_rp32_phase_one_always_shows_savor
             tests/test_reward_protocol.py::test_rp35_celebration_is_independent_of_savor

    ``rng`` is required rather than defaulted to the module-level ``random``.
    A default would make it possible to call this with no seam at all, and the
    one thing a probabilistic decision needs is a way to pin it down in a test.
    """
    phase = phase_for(savor_count)

    # Phase 1 short-circuits before touching the rng: every completion savors.
    show_savor = (phase == PHASE_WIRING) or (rng.random() < SAVOR_PROMPT_P2_PROBABILITY)

    # Drawn unconditionally, whatever the savor decision was.
    celebration = (
        rng.choice(CELEBRATION_TYPES)
        if rng.random() < CELEBRATION_PROBABILITY
        else None
    )

    return RewardDecision(phase=phase, show_savor=show_savor, celebration=celebration)
