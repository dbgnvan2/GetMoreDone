"""Tests for the timer's music-library helpers.

Covers the two bugs behind "the music function has a hard time finding music":
  1. .aif/.aiff were excluded from the format allowlist, so a folder full of
     playable AIFF tracks looked empty.
  2. With no folder configured, nothing played and nothing said why.

Tests: src/getmoredone/utils/music_library.py
"""

import random

import pytest

from src.getmoredone.utils import music_library
from src.getmoredone.utils.music_library import (
    PREFERRED_FORMATS,
    SUPPORTED_FORMATS,
    find_music_files,
    resolve_music_folder,
    select_track,
)


def _touch(folder, *names):
    """Create empty files with the given names inside folder; return their paths."""
    made = []
    for name in names:
        p = folder / name
        p.write_bytes(b"")
        made.append(p)
    return made


# --- Format allowlist (the core regression) --------------------------------

def test_aiff_is_a_supported_and_preferred_format():
    """Regression: .aif/.aiff must be recognized (SDL/pygame plays them)."""
    for ext in (".aif", ".aiff"):
        assert ext in SUPPORTED_FORMATS
        assert ext in PREFERRED_FORMATS


def test_select_track_finds_aiff_only_folder(tmp_path):
    """A folder of only AIFF files used to look empty; now it yields a track."""
    _touch(tmp_path, "01 Reel.aif", "02 Jig.aiff")

    sel = select_track(str(tmp_path))

    assert sel.status == "ok"
    assert sel.track is not None
    assert sel.track.lower().endswith((".aif", ".aiff"))


def test_find_music_files_ignores_unsupported(tmp_path):
    """Non-audio files are excluded; audio files are kept."""
    _touch(tmp_path, "song.mp3", "notes.txt", "cover.jpg", "tune.aif")
    found = {p.name for p in find_music_files(tmp_path)}
    assert found == {"song.mp3", "tune.aif"}


# --- Preference ranking -----------------------------------------------------

def test_select_track_prefers_supported_over_fallback(tmp_path):
    """When both are present, a preferred format is chosen over a fallback one."""
    _touch(tmp_path, "reliable.mp3", "iffy.m4a")
    sel = select_track(str(tmp_path), rng=random.Random(0))
    assert sel.status == "ok"
    assert sel.track.endswith("reliable.mp3")


def test_select_track_fallback_only_reports_status(tmp_path):
    """A folder of only fallback formats still plays, but flags the risk."""
    _touch(tmp_path, "only.m4a")
    sel = select_track(str(tmp_path))
    assert sel.status == "fallback_only"
    assert sel.track.endswith("only.m4a")


# --- Empty / missing / unset situations, each with a distinct status --------

def test_select_track_no_playable_files(tmp_path):
    _touch(tmp_path, "readme.txt")
    sel = select_track(str(tmp_path))
    assert sel.status == "no_files"
    assert sel.track is None
    assert "No playable music" in sel.message


def test_select_track_missing_folder(tmp_path):
    missing = tmp_path / "does-not-exist"
    sel = select_track(str(missing))
    assert sel.status == "missing_folder"
    assert sel.track is None


def test_select_track_no_folder_when_default_absent(tmp_path, monkeypatch):
    """With nothing configured and no bundled folder, report 'no_folder' clearly."""
    monkeypatch.setattr(
        music_library, "bundled_audio_dir", lambda: tmp_path / "nope")
    sel = select_track(None)
    assert sel.status == "no_folder"
    assert sel.track is None
    assert "Settings" in sel.message


# --- Default-folder fallback ------------------------------------------------

def test_resolve_music_folder_prefers_configured(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    configured = tmp_path / "mine"
    configured.mkdir()
    monkeypatch.setattr(music_library, "bundled_audio_dir", lambda: bundled)
    assert resolve_music_folder(str(configured)) == configured


def test_resolve_music_folder_falls_back_to_bundled(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    monkeypatch.setattr(music_library, "bundled_audio_dir", lambda: bundled)
    assert resolve_music_folder(None) == bundled
    assert resolve_music_folder("   ") == bundled  # blank counts as unset


def test_select_track_uses_bundled_default(tmp_path, monkeypatch):
    """Unset folder + a bundled folder with tracks => music just works."""
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    _touch(bundled, "builtin.ogg")
    monkeypatch.setattr(music_library, "bundled_audio_dir", lambda: bundled)
    sel = select_track(None)
    assert sel.status == "ok"
    assert sel.track.endswith("builtin.ogg")


def test_bundled_audio_dir_points_at_audio():
    from src.getmoredone.paths import bundled_audio_dir
    assert bundled_audio_dir().name == "audio"
