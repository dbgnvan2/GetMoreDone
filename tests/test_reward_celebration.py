"""The celebration overlay, the bundled chime, and the two dialogs' copy.

Purpose: RP-4.2a / RP-4.5e / RP-4.5f / RP-7 — the copy is the feature, the
         animation must never outlive its window, and the committed binary must
         be provably the generator's output.
Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#45-reward-sequence-on-done
Tests:   this file
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import customtkinter as ctk
import pytest

from src.getmoredone.screens import timer_window_celebration as celebration
from src.getmoredone.screens.timer_window_celebration import (
    CELEBRATION_MS,
    TimerCelebrationMixin,
    celebration_audio_path,
)
from src.getmoredone.screens.timer_window_dialogs import DeliverableDialog, SavorDialog

REPO = Path(__file__).resolve().parents[1]

# Written out, not imported from the module under test. Copy asserted against
# its own constant agrees with whatever the constant now says, which is how a
# rewritten sentence sails through a test that claims to pin it.
EXPECTED_SAVOR_TITLE = "Deliverable complete"
EXPECTED_SAVOR_WHAT = "You set out to: {deliverable}. It's done."
EXPECTED_SAVOR_HOW = (
    "Pause 5 seconds. Look at what you just made. Notice the physical sense of "
    "'closed.' You did something hard and leaned in — feel the effort, not just "
    "the finish."
)
EXPECTED_SAVOR_BUTTON = "Finished"
EXPECTED_DELIVERABLE_HINT = "What does 'done' look like? A checkable artifact, not time spent."

# Words the savor step must never use. The copy points at the artifact and at
# the felt sense of having closed something; a verbal pat is the cheap reward
# this protocol exists to stop training.
FORBIDDEN_IN_SAVOR = ("good job", "well done", "congratulations", "great work", "nice work")


@pytest.fixture
def root():
    win = ctk.CTk()
    win.withdraw()
    yield win
    win.destroy()


class _Host(TimerCelebrationMixin, ctk.CTkToplevel):
    """The smallest thing the celebration mixin can be attached to."""


@pytest.fixture
def host(root):
    window = _Host(root)
    window.geometry("380x520")
    yield window
    try:
        window.destroy()
    except Exception:
        pass


# --- RP-4.5e : the savor copy -----------------------------------------------

def test_rp45e_savor_dialog_copy_is_verbatim(root):
    """RP-4.5e — title, WHAT, HOW and button exactly as the spec writes them."""
    dialog = SavorDialog(root, "Draft section 2's opening paragraph")
    try:
        assert dialog.title() == EXPECTED_SAVOR_TITLE
        assert dialog.what_label.cget("text") == (
            "You set out to: Draft section 2's opening paragraph. It's done."
        )
        assert dialog.how_label.cget("text") == EXPECTED_SAVOR_HOW
        assert SavorDialog.WHAT == EXPECTED_SAVOR_WHAT
        assert SavorDialog.BUTTON == EXPECTED_SAVOR_BUTTON
    finally:
        dialog.destroy()


def test_rp45e_savor_copy_contains_no_verbal_pat(root):
    """The copy directs attention at the artifact, never at the person."""
    dialog = SavorDialog(root, "Anything")
    try:
        text = (dialog.what_label.cget("text") + " " + dialog.how_label.cget("text")).lower()
        found = [phrase for phrase in FORBIDDEN_IN_SAVOR if phrase in text]
        assert not found, f"the savor copy has turned into a verbal pat: {found}"
    finally:
        dialog.destroy()


def test_rp45e_acknowledging_records_it_and_closing_does_not(root):
    """The two ways out of the dialog stay distinguishable."""
    dialog = SavorDialog(root, "Anything")
    assert dialog.acknowledged is False
    dialog.acknowledge()
    assert dialog.acknowledged is True

    other = SavorDialog(root, "Anything")
    other.close_unacknowledged()
    assert other.acknowledged is False


# --- RP-4.2a : the deliverable dialog ---------------------------------------

def test_rp42a_deliverable_dialog_refuses_blank_and_shows_the_hint(root):
    """RP-4.2a — a blank deliverable does not close the dialog."""
    dialog = DeliverableDialog(root, "A task")
    try:
        assert EXPECTED_DELIVERABLE_HINT == DeliverableDialog.HINT

        dialog.entry.delete(0, "end")
        dialog.entry.insert(0, "   ")
        dialog.confirm()

        assert dialog.winfo_exists(), "a blank deliverable closed the dialog anyway"
        assert dialog.result is None
        assert dialog.error_label.cget("text") == DeliverableDialog.BLANK_ERROR

        dialog.entry.delete(0, "end")
        dialog.entry.insert(0, "  Draft section 2  ")
        dialog.confirm()
        assert dialog.result == "Draft section 2", "the confirmed text was not trimmed"
    finally:
        if dialog.winfo_exists():
            dialog.destroy()


def test_rp42a_cancel_returns_no_deliverable(root):
    dialog = DeliverableDialog(root, "A task", deliverable="Prefilled")
    assert dialog.entry.get() == "Prefilled"
    dialog.cancel()
    assert dialog.result is None


# --- RP-4.5f : the celebration is non-blocking and cleans up ----------------

@pytest.mark.parametrize("kind", ["confetti", "balloon", "tada"])
def test_rp45f_every_celebration_type_draws_and_schedules(host, monkeypatch, kind):
    """Each declared type actually does something, and nothing blocks."""
    monkeypatch.setattr(celebration, "play_audio_file_async", lambda path: True)

    assert host.fire_celebration(kind) is True
    assert host._celebration_canvas is not None
    assert host._celebration_canvas.find_all(), f"{kind} drew nothing"
    assert host._celebration_after_ids, f"{kind} scheduled no frames"


def test_rp45f_no_celebration_when_the_protocol_did_not_pick_one(host):
    """The ordinary case: 80% of completions have nothing to fire."""
    assert host.fire_celebration(None) is False
    assert host._celebration_canvas is None
    assert not host._celebration_after_ids


def test_rp45f_an_unknown_type_leaves_nothing_running(host):
    """A bad value is refused and does not leave a canvas or a timer behind."""
    assert host.fire_celebration("fireworks") is False
    assert host._celebration_canvas is None
    assert not host._celebration_after_ids


def test_rp45f_celebration_cleans_up_on_window_close(host, monkeypatch):
    """RP-4.5f — the completion flow destroys the window seconds later.

    Every frame is scheduled through the window's own after(), so one still
    pending when the window goes away raises "invalid command name" — at the
    exact moment the user has just finished something.
    """
    monkeypatch.setattr(celebration, "play_audio_file_async", lambda path: True)
    host.fire_celebration("confetti")
    assert host._celebration_after_ids

    host.cancel_celebration()

    assert host._celebration_after_ids == set()
    assert host._celebration_canvas is None
    host.cancel_celebration()   # twice in a row must be harmless


def test_rp45f_a_second_celebration_does_not_stack_on_the_first(host, monkeypatch):
    """Two Dones in quick succession leave one canvas, not two."""
    monkeypatch.setattr(celebration, "play_audio_file_async", lambda path: True)
    host.fire_celebration("confetti")
    first = host._celebration_canvas
    host.fire_celebration("balloon")

    assert host._celebration_canvas is not first
    assert not first.winfo_exists(), "the first celebration's canvas was left behind"


def test_rp45f_the_frame_step_stops_once_the_canvas_is_gone(host, monkeypatch):
    """A frame that runs after teardown must return, not raise."""
    monkeypatch.setattr(celebration, "play_audio_file_async", lambda path: True)
    host.fire_celebration("confetti")
    canvas = host._celebration_canvas
    host.cancel_celebration()

    assert host._still_running(canvas) is False


def test_rp45f_celebration_length_is_short(host, monkeypatch):
    """"Lightweight overlay, ~1-2s" — long enough to see, short enough to ignore."""
    monkeypatch.setattr(celebration, "play_audio_file_async", lambda path: True)
    assert 1000 <= CELEBRATION_MS <= 2000


# --- the audio channel ------------------------------------------------------

def test_rp45_tada_plays_the_bundled_chime(host, monkeypatch):
    played = []
    monkeypatch.setattr(celebration, "play_audio_file_async",
                        lambda path: played.append(path) or True)
    host.fire_celebration("tada")
    assert played == [str(celebration_audio_path())]


def test_rp45_tada_falls_back_to_the_system_sound_when_no_player_opens_it(host, monkeypatch, caplog):
    """A missing player is surfaced, not silently swallowed."""
    beeped = []
    monkeypatch.setattr(celebration, "play_audio_file_async", lambda path: False)
    monkeypatch.setattr(celebration, "play_system_beep", lambda: beeped.append(True) or True)

    with caplog.at_level("WARNING"):
        host.fire_celebration("tada")

    assert beeped == [True]
    assert any("system sound" in record.message for record in caplog.records), (
        "the fallback happened without saying why"
    )


def test_rp45_tada_falls_back_when_the_asset_is_missing(host, monkeypatch, tmp_path, caplog):
    beeped = []
    monkeypatch.setattr(celebration, "celebration_audio_path", lambda: tmp_path / "absent.wav")
    monkeypatch.setattr(celebration, "play_system_beep", lambda: beeped.append(True) or True)

    with caplog.at_level("WARNING"):
        host.fire_celebration("tada")

    assert beeped == [True]
    assert any("missing" in record.message for record in caplog.records)


# --- RP-7 : the committed chime ---------------------------------------------

def _read_wav(path):
    with wave.open(str(path)) as handle:
        params = handle.getparams()
        frames = handle.readframes(handle.getnframes())
    return params, struct.unpack(f"<{len(frames) // 2}h", frames)


def test_rp7_the_chime_is_bundled_where_the_app_looks_for_it():
    path = celebration_audio_path()
    assert path.exists(), f"the celebration chime is not at {path}"
    assert path.is_relative_to(REPO / "assets"), (
        "the chime must live under assets/, which is what daVIPA.spec bundles"
    )


def test_rp7_the_chime_is_short_small_and_playable():
    """Short and local, as the spec requires — no network, no large binary."""
    path = celebration_audio_path()
    params, samples = _read_wav(path)

    assert params.nchannels == 1
    assert params.sampwidth == 2
    seconds = params.nframes / params.framerate
    assert 0.3 <= seconds <= 2.0, f"the chime is {seconds:.2f}s long"
    assert path.stat().st_size < 100_000, "the chime is larger than a short chime should be"
    assert max(abs(s) for s in samples) > 3000, "the chime is silent"
    assert max(abs(s) for s in samples) < 32767, "the chime clips"


def test_rp7_committed_tada_wav_is_this_scripts_output(tmp_path):
    """The committed binary is provably what tools/generate_tada_wav.py makes.

    Samples are compared with a one-LSB tolerance rather than the file hashed.
    The waveform goes through math.sin, which is the platform libm, so the last
    bit of a sample can differ between the machine that committed the file and
    the machine running this. Any real drift — an edited note, envelope or
    amplitude — moves samples by hundreds, not by one.
    """
    import tools.generate_tada_wav as generator

    regenerated = generator.write(tmp_path / "tada.wav")
    committed_params, committed = _read_wav(celebration_audio_path())
    fresh_params, fresh = _read_wav(regenerated)

    assert committed_params == fresh_params, (
        "the committed chime's format does not match the generator's output"
    )
    assert len(committed) == len(fresh)
    worst = max(abs(a - b) for a, b in zip(committed, fresh))
    assert worst <= 1, (
        f"the committed chime differs from the generator's output by up to {worst} "
        "— it was not produced by this script, or the script has changed since"
    )
