"""
Automated guard rails for the optional audio/timer configuration.

Rather than trying to play music for five seconds (which breaks headless
test runs), we verify that pygame can initialize *and* that the configured
music folder at least contains a playable file. If the user hasn't configured
audio yet, the test is skipped with a clear message so CI remains green.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import json
import os

import pytest
from platformdirs import user_data_dir

from src.getmoredone.paths import APP_AUTHOR, APP_NAME

try:
    import pygame
except Exception:  # pragma: no cover - pygame missing in some environments
    pygame = None  # type: ignore

from src.getmoredone.app_settings import AppSettings
# Single source of truth for playable formats — keep the timer window, settings
# copy, and this guard rail in agreement.
from src.getmoredone.utils.music_library import SUPPORTED_FORMATS as SUPPORTED_EXTENSIONS


def _iter_audio_files(folder: Path) -> Iterable[Path]:
    for entry in folder.iterdir():
        if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield entry


@pytest.mark.audio
def test_audio_configuration_allows_playback(tmp_path):
    """Ensure pygame can load at least one configured audio file."""
    if pygame is None:
        pytest.skip("pygame not installed; audio features unavailable")

    # Read the *real* settings deliberately. The suite redirects
    # AppSettings.get_settings_path to a temporary file (conftest.py), so
    # `AppSettings.load()` here would always see an empty music folder and this
    # test could never run on any machine — while its skip reason went on
    # telling the reader to configure it in Settings, advice that could not
    # have had any effect.
    #
    # GETMOREDONE_MUSIC_FOLDER takes precedence, so CI and a headless run can
    # point this at a fixture without touching user settings at all.
    music_folder = (os.environ.get("GETMOREDONE_MUSIC_FOLDER") or "").strip()
    if not music_folder:
        real_settings = Path(user_data_dir(APP_NAME, APP_AUTHOR)) / "settings.json"
        if real_settings.exists():
            try:
                music_folder = (
                    json.loads(real_settings.read_text()).get("music_folder") or "").strip()
            except (OSError, ValueError):
                music_folder = ""
    if not music_folder:
        pytest.skip(
            "no music folder: set GETMOREDONE_MUSIC_FOLDER, or configure one in "
            "Settings > Timer & Audio (this test reads the real settings file on "
            "purpose — the suite's settings are redirected to a temp file)")

    folder_path = Path(music_folder).expanduser()
    if not folder_path.exists():
        pytest.skip(f"configured music folder does not exist: {folder_path}")

    tracks = list(_iter_audio_files(folder_path))
    if not tracks:
        pytest.skip(f"no playable audio files found in {folder_path}")

    # Initialize pygame mixer. If the system audio stack is unavailable
    # (e.g., headless CI), skip rather than fail.
    try:
        pygame.mixer.init(44100, -16, 2, 512)
    except Exception as exc:  # pragma: no cover - depends on OS audio devices
        pytest.skip(f"pygame mixer unavailable: {exc}")

    try:
        pygame.mixer.music.load(str(tracks[0]))
        pygame.mixer.music.set_volume(getattr(settings, "music_volume", 1.0) or 1.0)
    finally:
        pygame.mixer.quit()
