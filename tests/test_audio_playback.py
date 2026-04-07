"""Tests for lightweight audio playback helpers."""

from src.getmoredone.utils import audio_playback


def test_play_audio_file_async_uses_afplay_on_macos(monkeypatch):
    calls = []

    monkeypatch.setattr(audio_playback, "_command_path", lambda name: f"/usr/bin/{name}" if name == "afplay" else None)
    monkeypatch.setattr(audio_playback, "_launch_process", lambda command: calls.append(command) or True)

    assert audio_playback.play_audio_file_async("/tmp/test.wav", platform_name="darwin")
    assert calls == [["/usr/bin/afplay", "/tmp/test.wav"]]


def test_play_system_beep_uses_linux_candidates(monkeypatch):
    calls = []

    monkeypatch.setattr(
        audio_playback,
        "_system_sound_candidates",
        lambda: [["/usr/bin/paplay", "/tmp/sound.oga"], ["/usr/bin/beep", "-f", "800", "-l", "500"]],
    )
    monkeypatch.setattr(audio_playback, "_launch_process", lambda command: calls.append(command) or (command[0] == "/usr/bin/beep"))

    assert audio_playback.play_system_beep(platform_name="linux")
    assert calls == [
        ["/usr/bin/paplay", "/tmp/sound.oga"],
        ["/usr/bin/beep", "-f", "800", "-l", "500"],
    ]


def test_play_system_beep_falls_back_to_terminal_bell(monkeypatch):
    monkeypatch.setattr(audio_playback, "_system_sound_candidates", lambda: [])
    monkeypatch.setattr(audio_playback, "terminal_bell", lambda: True)

    assert audio_playback.play_system_beep(platform_name="linux")
