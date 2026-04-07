"""Lightweight audio playback helpers for alerts and short sounds."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _launch_process(command: list[str]) -> bool:
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _play_windows_wav(file_path: str) -> bool:
    try:
        import winsound

        winsound.PlaySound(file_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return True
    except Exception:
        return False


def _play_windows_beep() -> bool:
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        return True
    except Exception:
        return False


def _command_path(name: str) -> str | None:
    return shutil.which(name)


def _system_sound_candidates() -> list[list[str]]:
    paplay = _command_path("paplay")
    aplay = _command_path("aplay")
    beep = _command_path("beep")
    candidates: list[list[str]] = []
    if paplay:
        candidates.append([paplay, "/usr/share/sounds/freedesktop/stereo/complete.oga"])
    if aplay:
        candidates.append([aplay, "/usr/share/sounds/alsa/Front_Center.wav"])
    if beep:
        candidates.append([beep, "-f", "800", "-l", "500"])
    return candidates


def terminal_bell() -> bool:
    try:
        print("\a", end="", flush=True)
        return True
    except Exception:
        return False


def play_audio_file_async(file_path: str, platform_name: str | None = None) -> bool:
    """Play a local audio file asynchronously when a supported player exists."""
    target = str(Path(file_path))
    platform_name = platform_name or sys.platform

    if platform_name == "win32":
        return _play_windows_wav(target)

    if platform_name == "darwin":
        afplay = _command_path("afplay")
        return _launch_process([afplay, target]) if afplay else False

    aplay = _command_path("aplay")
    return _launch_process([aplay, target]) if aplay else False


def play_system_beep(platform_name: str | None = None) -> bool:
    """Play a short system notification sound, falling back to terminal bell."""
    platform_name = platform_name or sys.platform

    if platform_name == "win32":
        return _play_windows_beep() or terminal_bell()

    if platform_name == "darwin":
        afplay = _command_path("afplay")
        if afplay and _launch_process([afplay, "/System/Library/Sounds/Glass.aiff"]):
            return True
        return terminal_bell()

    for command in _system_sound_candidates():
        if _launch_process(command):
            return True

    return terminal_bell()
