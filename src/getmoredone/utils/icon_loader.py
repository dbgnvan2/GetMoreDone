"""Icon loader utility for GetMoreDone application.

This module provides functions to load PNG icons and convert them to CustomTkinter-compatible images.
"""

import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from ..paths import resource_root

if TYPE_CHECKING:
    import customtkinter as ctk

try:
    from PIL import Image
    import customtkinter as ctk
    PNG_SUPPORT = True
except ImportError:
    PNG_SUPPORT = False
    ctk = None


# Resource root directory (repo root when running from source, PyInstaller bundle root when frozen)
ICONS_DIR = resource_root() / "assets" / "icons"


class IconLoader:
    """Utility class for loading and caching icons."""

    _cache = {}

    @classmethod
    def load_png_icon(cls, icon_name: str, size: int = 24) -> Optional["ctk.CTkImage"]:
        """Load a PNG icon and return a CTkImage object.

        Args:
            icon_name: Name of the icon file (without .png extension)
            size: Size in pixels for both width and height

        Returns:
            CTkImage object or None if loading fails
        """
        if not PNG_SUPPORT:
            print("Warning: PNG support not available. Install Pillow.")
            return None

        # Create cache key
        cache_key = f"{icon_name}_{size}"

        # Return cached version if available
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        # Build icon path
        icon_path = ICONS_DIR / f"{icon_name}.png"

        if not icon_path.exists():
            print(f"Warning: Icon file not found: {icon_path}")
            return None

        try:
            image = Image.open(icon_path).convert("RGBA")
            if image.size != (size, size):
                image = image.resize((size, size))

            # Create CTkImage (CustomTkinter's image wrapper)
            ctk_image = ctk.CTkImage(
                light_image=image,
                dark_image=image,
                size=(size, size)
            )

            # Cache the image
            cls._cache[cache_key] = ctk_image

            return ctk_image

        except Exception as e:
            print(f"Error loading icon {icon_name}: {e}")
            return None

    @classmethod
    def clear_cache(cls):
        """Clear the icon cache."""
        cls._cache.clear()


# Convenience functions for common icons
def load_play_icon(size: int = 24) -> Optional["ctk.CTkImage"]:
    """Load the play icon."""
    return IconLoader.load_png_icon("play", size)


def load_pause_icon(size: int = 24) -> Optional["ctk.CTkImage"]:
    """Load the pause icon."""
    return IconLoader.load_png_icon("pause", size)


def load_stop_icon(size: int = 24) -> Optional["ctk.CTkImage"]:
    """Load the stop icon."""
    return IconLoader.load_png_icon("stop", size)


def load_volume_icon(size: int = 24) -> Optional["ctk.CTkImage"]:
    """Load the volume icon."""
    return IconLoader.load_png_icon("volume", size)


def load_music_note_icon(size: int = 24) -> Optional["ctk.CTkImage"]:
    """Load the music note icon."""
    return IconLoader.load_png_icon("music_note", size)
