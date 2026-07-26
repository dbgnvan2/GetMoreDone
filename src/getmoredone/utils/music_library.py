"""Music-library helpers for the Action Timer's background music.

Purpose: single source of truth for which audio formats are playable and for
locating a track to play, with an explicit status so the UI can tell the user
*why* music did or did not start (rather than failing silently to the console).

Spec:    focus-timer background music (Settings > Timer & Audio)
Tests:   tests/test_music_library.py
"""

from __future__ import annotations

import random as _random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..paths import bundled_audio_dir

# Formats pygame's music streamer loads reliably. AIFF (.aif/.aiff) is included
# because SDL 2 loads it fine — earlier versions of this app omitted it, which
# made whole folders of AIFF tracks look "empty" to the finder.
PREFERRED_FORMATS = (".mp3", ".wav", ".ogg", ".aif", ".aiff")

# Container formats pygame *may* fail to stream depending on installed codecs.
# They are still offered (better to try than to ignore) but ranked below the
# preferred set and reported so the user can convert if playback is silent.
FALLBACK_FORMATS = (".flac", ".m4a", ".aac", ".wma")

# Everything the finder will consider. Kept as one tuple so tests, settings
# copy, and the timer window all agree on the list.
SUPPORTED_FORMATS = PREFERRED_FORMATS + FALLBACK_FORMATS


@dataclass
class MusicSelection:
    """Result of trying to pick a track. `track` is None on any non-'ok' status."""

    status: str  # 'ok' | 'fallback_only' | 'no_folder' | 'missing_folder' | 'no_files'
    message: str  # human-readable, safe to show in the timer window
    track: Optional[str] = None  # absolute path to the chosen file
    folder: Optional[Path] = None  # the folder that was searched


def resolve_music_folder(configured: Optional[str]) -> Optional[Path]:
    """Return the effective music folder.

    The user's configured folder wins; when unset, fall back to the bundled
    ``audio/`` folder so music works out of the box. Returns None only when
    neither is available.
    """
    value = (configured or "").strip()
    if value:
        return Path(value).expanduser()
    default = bundled_audio_dir()
    return default if default.exists() else None


def find_music_files(folder: Path) -> list[Path]:
    """All playable audio files directly inside ``folder`` (sorted, non-recursive)."""
    try:
        entries = sorted(folder.iterdir())
    except (OSError, ValueError):
        return []
    return [
        f for f in entries
        if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS
    ]


def select_track(configured_folder: Optional[str], rng=_random) -> MusicSelection:
    """Pick a random playable track, preferring well-supported formats.

    Returns a :class:`MusicSelection` whose ``status`` distinguishes "no folder
    configured", "folder missing", "folder has no playable files", and success —
    so callers can surface the real reason instead of dropping it silently.
    """
    folder = resolve_music_folder(configured_folder)
    if folder is None:
        return MusicSelection(
            status="no_folder",
            message="No music folder set — choose one in Settings → Timer & Audio.",
        )

    if not folder.exists() or not folder.is_dir():
        return MusicSelection(
            status="missing_folder",
            message=f"Music folder not found: {folder}",
            folder=folder,
        )

    files = find_music_files(folder)
    if not files:
        return MusicSelection(
            status="no_files",
            message=(
                f"No playable music in “{folder.name}”. "
                "Add MP3, WAV, OGG, or AIFF files."
            ),
            folder=folder,
        )

    preferred = [f for f in files if f.suffix.lower() in PREFERRED_FORMATS]
    pool = preferred or files
    choice = rng.choice(pool)
    status = "ok" if preferred else "fallback_only"
    return MusicSelection(
        status=status,
        message=f"Now playing: {choice.name}",
        track=str(choice),
        folder=folder,
    )
