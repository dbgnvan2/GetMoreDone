#!/usr/bin/env python3
"""Generate the celebration chime bundled at ``assets/audio/tada.wav``.

Purpose: RP-7 / spec D3 — the reward protocol wants a short "Ta-DA!" for its
         audio celebration. Nothing suitable exists in the repo and the spec
         forbids fetching one, so the clip is synthesised here and its output is
         committed. The script is what makes the committed binary reviewable:
         anyone can regenerate it and compare.
Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#45-reward-sequence-on-done
Tests:   tests/test_reward_celebration.py::test_rp7_committed_tada_wav_is_this_scripts_output

Stdlib only, no network, no third-party audio library. Two notes — a short
upbeat and a longer resolving note a fourth above it — each a fundamental with
two quiet harmonics under an exponential decay, which is roughly what a struck
metal bar does and reads as a chime rather than a beep.

Run with no arguments to rewrite the committed asset:

    python tools/generate_tada_wav.py
"""

from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

SAMPLE_RATE = 22050          # plenty for a chime, and keeps the file ~30 KB
SAMPLE_WIDTH_BYTES = 2       # 16-bit signed
CHANNELS = 1
PEAK = 0.72                  # headroom, so the sum of harmonics cannot clip

# (frequency Hz, start second, duration seconds, relative loudness)
# C5 then G5: the "ta" and the "DA".
NOTES = (
    (523.25, 0.00, 0.16, 0.85),
    (783.99, 0.14, 0.55, 1.00),
)

# Harmonic, relative amplitude. A quiet octave and twelfth over the fundamental.
HARMONICS = ((1.0, 1.00), (2.0, 0.30), (3.0, 0.12))

DECAY_RATE = 5.5             # e-folds per second; higher is more percussive
ATTACK_SECONDS = 0.006       # short ramp in, so the note does not start on a click

TOTAL_SECONDS = max(start + duration for _f, start, duration, _a in NOTES)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "audio" / "tada.wav"


def _envelope(t: float, duration: float) -> float:
    """Fast attack, exponential decay, forced to zero at the note's end.

    The final taper matters: cutting a still-ringing note dead is the click
    that makes a synthesised chime sound cheap.
    """
    if t < 0.0 or t > duration:
        return 0.0
    attack = min(1.0, t / ATTACK_SECONDS) if ATTACK_SECONDS > 0 else 1.0
    decay = math.exp(-DECAY_RATE * t)
    taper = min(1.0, (duration - t) / 0.05)
    return attack * decay * taper


def samples() -> list[int]:
    """The whole clip as 16-bit signed integers."""
    frame_count = int(SAMPLE_RATE * TOTAL_SECONDS)
    out: list[int] = []
    for frame in range(frame_count):
        now = frame / SAMPLE_RATE
        value = 0.0
        for frequency, start, duration, loudness in NOTES:
            level = _envelope(now - start, duration) * loudness
            if level == 0.0:
                continue
            phase = 2.0 * math.pi * frequency * (now - start)
            for harmonic, weight in HARMONICS:
                value += level * weight * math.sin(harmonic * phase)
        # Clamped rather than trusted: PEAK plus the harmonic weights is chosen
        # to stay inside range, but a later edit to either must not wrap round
        # into a burst of noise.
        scaled = max(-1.0, min(1.0, value * PEAK / sum(w for _h, w in HARMONICS)))
        out.append(int(round(scaled * 32767)))
    return out


def write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = samples()
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(CHANNELS)
        handle.setsampwidth(SAMPLE_WIDTH_BYTES)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(struct.pack(f"<{len(data)}h", *data))
    return path


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    written = write(target)
    print(f"wrote {written} ({written.stat().st_size} bytes, {TOTAL_SECONDS:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
