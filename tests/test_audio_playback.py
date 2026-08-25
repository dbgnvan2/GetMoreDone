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


def test_release_audio_device_closes_the_mixer(monkeypatch):
    """pygame.mixer.init() took the sound card and nothing ever gave it back.

    Held for the whole life of the process — a finite OS resource acquired and
    never returned (P30), invisible because nothing about it is on screen.

    Unload before quit: quit() alone leaves the loaded track's file handle held
    until the interpreter exits.
    """
    import sys
    import types

    calls = []
    music = types.SimpleNamespace(
        stop=lambda: calls.append("stop"),
        unload=lambda: calls.append("unload"),
    )
    mixer = types.SimpleNamespace(
        get_init=lambda: (44100, -16, 2),
        quit=lambda: calls.append("quit"),
        music=music,
    )
    monkeypatch.setitem(sys.modules, "pygame", types.SimpleNamespace(mixer=mixer))

    assert audio_playback.release_audio_device() is True
    assert calls == ["stop", "unload", "quit"], (
        f"the device was not released cleanly: {calls}"
    )


def test_release_audio_device_is_a_no_op_when_the_mixer_never_started(monkeypatch):
    """Shutdown must not care whether music was ever played."""
    import sys
    import types

    calls = []
    mixer = types.SimpleNamespace(
        get_init=lambda: None,
        quit=lambda: calls.append("quit"),
        music=types.SimpleNamespace(stop=lambda: None, unload=lambda: None),
    )
    monkeypatch.setitem(sys.modules, "pygame", types.SimpleNamespace(mixer=mixer))

    assert audio_playback.release_audio_device() is False
    assert calls == [], "quit() was called on a mixer that was never started"


def test_the_app_releases_the_audio_device_on_shutdown():
    """WL — wired, not merely written (P21).

    A release function nothing calls is the same leak with more code. Parsed
    rather than grepped: the name appears in this file and in comments.
    """
    import ast
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1]
           / "src" / "getmoredone" / "app.py").read_text()
    tree = ast.parse(src)
    closing = [n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "on_closing"]
    assert closing, "app.py has no on_closing"

    called = {
        node.func.id
        for fn in closing for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "release_audio_device" in called, (
        "on_closing does not release the audio device, so the sound card stays "
        "held for the life of the process"
    )
