"""The reward decision: phase gate, rates, independence, and no magic numbers.

Purpose: RP-3 — prove the two reward channels behave as the protocol requires,
         deterministically rather than by eyeballing a run.
Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#3-config--decision-logic
Tests:   this file

Every rate here is asserted against a *seeded* rng, so these are not flaky and
they are not the single-draw trap either: the thing under test is a declared
probability in this repo's own code, not a sample from a model. The tolerances
are chosen tight enough that nudging a constant one step (0.4 -> 0.3 moves the
rate by 10 points, twice the tolerance) turns them red.
"""

from __future__ import annotations

import ast
import inspect
import random

import pytest

from src.getmoredone import reward_protocol
from src.getmoredone.reward_protocol import (
    CELEBRATION_PROBABILITY,
    CELEBRATION_TYPES,
    PHASE_MAINTAINING,
    PHASE_WIRING,
    SAVOR_PROMPT_P2_PROBABILITY,
    WIRING_THRESHOLD,
    RewardDecision,
    decide_reward,
    phase_for,
)

# Enough draws that a rate is worth asserting on; small enough to stay fast.
DRAWS = 5000
TOLERANCE = 0.05


def _draws(savor_count: int, n: int = DRAWS, seed: int = 20260823) -> list[RewardDecision]:
    rng = random.Random(seed)
    return [decide_reward(savor_count, rng) for _ in range(n)]


def _rate(flags) -> float:
    flags = list(flags)
    return sum(1 for f in flags if f) / len(flags)


def test_rp31_phase_for_boundary_is_exactly_fifteen():
    """RP-3.1 — the boundary sits at the threshold, not one either side of it."""
    assert phase_for(0) == PHASE_WIRING
    assert phase_for(1) == PHASE_WIRING
    assert phase_for(WIRING_THRESHOLD - 1) == PHASE_WIRING
    assert phase_for(WIRING_THRESHOLD) == PHASE_MAINTAINING
    assert phase_for(WIRING_THRESHOLD + 1) == PHASE_MAINTAINING
    assert phase_for(999) == PHASE_MAINTAINING
    # The threshold the spec names, pinned so a silent retune is visible here.
    assert WIRING_THRESHOLD == 15


def test_rp32_phase_one_always_shows_savor():
    """RP-3.2 — continuous reinforcement while the association is being built."""
    decisions = _draws(savor_count=0, n=500)
    not_savored = [d for d in decisions if not d.show_savor]
    assert not not_savored, (
        f"{len(not_savored)} of 500 Phase 1 completions skipped the savor step; "
        "Phase 1 is continuous reinforcement and must skip none"
    )
    assert all(d.phase == PHASE_WIRING for d in decisions)


def test_rp33_phase_two_savor_rate_is_about_forty_percent():
    """RP-3.3 — intermittent once the association exists."""
    rate = _rate(d.show_savor for d in _draws(savor_count=WIRING_THRESHOLD))
    assert abs(rate - SAVOR_PROMPT_P2_PROBABILITY) < TOLERANCE, (
        f"Phase 2 savor rate {rate:.3f}, expected ~{SAVOR_PROMPT_P2_PROBABILITY}"
    )
    assert SAVOR_PROMPT_P2_PROBABILITY == 0.4


def test_rp34_celebration_rate_is_twenty_percent_in_both_phases():
    """RP-3.4 — the celebration channel is not phase-gated."""
    wiring = _rate(d.celebration is not None for d in _draws(savor_count=0))
    maintaining = _rate(
        d.celebration is not None for d in _draws(savor_count=WIRING_THRESHOLD)
    )
    for label, rate in (("wiring", wiring), ("maintaining", maintaining)):
        assert abs(rate - CELEBRATION_PROBABILITY) < TOLERANCE, (
            f"{label} celebration rate {rate:.3f}, expected ~{CELEBRATION_PROBABILITY}"
        )
    assert abs(wiring - maintaining) < TOLERANCE, (
        f"celebration rate differs by phase ({wiring:.3f} vs {maintaining:.3f}); "
        "it is meant to be independent of phase"
    )
    assert CELEBRATION_PROBABILITY == 0.2


def test_rp35_celebration_is_independent_of_savor():
    """RP-3.5 — knowing whether the savor fired tells you nothing about the celebration.

    Phase 2 is the only phase where both outcomes vary, so it is the only place
    the independence is observable at all.
    """
    decisions = _draws(savor_count=WIRING_THRESHOLD)
    with_savor = [d.celebration is not None for d in decisions if d.show_savor]
    without_savor = [d.celebration is not None for d in decisions if not d.show_savor]

    assert len(with_savor) > 500 and len(without_savor) > 500, (
        "not enough of each kind of draw to say anything about independence"
    )
    difference = abs(_rate(with_savor) - _rate(without_savor))
    assert difference < TOLERANCE, (
        f"celebration rate is {_rate(with_savor):.3f} when the savor fired and "
        f"{_rate(without_savor):.3f} when it did not — the two channels are "
        "supposed to be independent"
    )


def test_rp36_celebration_values_come_from_the_declared_tuple():
    """RP-3.6 — nothing outside CELEBRATION_TYPES is ever returned, and all of it is used.

    The expected set is written out rather than taken from ``CELEBRATION_TYPES``.
    Deriving it from the constant makes the test agree with whatever the constant
    happens to say, so deleting a celebration type stays green — checked by
    mutation, and it did.
    """
    expected = {"confetti", "balloon", "tada"}
    assert set(CELEBRATION_TYPES) == expected, (
        f"the spec declares {sorted(expected)}; the module offers {sorted(CELEBRATION_TYPES)}"
    )

    seen = {d.celebration for d in _draws(savor_count=0)}
    stray = seen - expected - {None}
    assert not stray, f"decide_reward produced celebrations outside the declared tuple: {stray}"
    missing = expected - seen
    assert not missing, f"these declared celebration types never fired: {missing}"


def test_rp37_celebration_is_never_guaranteed_in_either_phase():
    """RP-3.7 — a celebration that always fires is a cue, which defeats the point."""
    for savor_count, label in ((0, "wiring"), (WIRING_THRESHOLD, "maintaining")):
        decisions = _draws(savor_count=savor_count, n=500)
        fired = [d for d in decisions if d.celebration is not None]
        assert fired, f"no celebration ever fired in {label}"
        assert len(fired) < len(decisions), (
            f"a celebration fired on every one of 500 {label} completions; "
            "it must never be guaranteed"
        )


def test_rp38_decide_reward_body_has_no_magic_numbers():
    """RP-3.8 — thresholds and probabilities are named config, not literals in the logic.

    Parsed rather than grepped: a substring search would match the numbers in
    the docstring, and the docstring is exactly where they are allowed to be.
    """
    tree = ast.parse(inspect.getsource(decide_reward).lstrip())
    function = tree.body[0]
    body = function.body[1:] if ast.get_docstring(function) else function.body

    numbers = [
        node.value
        for statement in body
        for node in ast.walk(statement)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ]
    assert not numbers, (
        f"decide_reward's body contains numeric literals {numbers}; thresholds and "
        "probabilities belong in module-level named constants"
    )


def test_rp39_same_seed_gives_the_same_sequence():
    """RP-3.9 — the injected rng is the only source of variation."""
    first = _draws(savor_count=WIRING_THRESHOLD, n=200, seed=99)
    second = _draws(savor_count=WIRING_THRESHOLD, n=200, seed=99)
    assert first == second
    different = _draws(savor_count=WIRING_THRESHOLD, n=200, seed=100)
    assert first != different, (
        "two different seeds produced identical sequences — decide_reward is "
        "not actually consuming the injected rng"
    )


def test_rp3_reward_decision_is_immutable():
    """A decision is a record of what was decided; nothing downstream may edit it."""
    import dataclasses

    decision = decide_reward(0, random.Random(1))
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.show_savor = False


def test_rp3_module_exposes_the_names_the_spec_declares():
    """The spec names these five; a rename would silently orphan a caller."""
    for name in (
        "WIRING_THRESHOLD",
        "SAVOR_PROMPT_P2_PROBABILITY",
        "CELEBRATION_PROBABILITY",
        "CELEBRATION_TYPES",
        "RewardDecision",
    ):
        assert hasattr(reward_protocol, name), f"reward_protocol.{name} is missing"
