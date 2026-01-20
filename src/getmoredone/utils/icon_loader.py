"""Icon loader utility for GetMoreDone application.

This module provides functions to load SVG icons and convert them to CustomTkinter-compatible images.
"""

import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import io

if TYPE_CHECKING:
    import customtkinter as ctk

try:
    import cairosvg
    from PIL import Image
    import customtkinter as ctk
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False
    ctk = None


# Get the project root directory (where assets folder is located)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ICONS_DIR = PROJECT_ROOT / "assets" / "icons"


class IconLoader:
    """Utility class for loading and caching icons."""

    _cache = {}

    @classmethod
    def load_svg_icon(cls, icon_name: str, size: int = 24, color: str = "white") -> Optional["ctk.CTkImage"]:
        """Load an SVG icon and return a CTkImage object.

        Args:
            icon_name: Name of the icon file (without .svg extension)
            size: Size in pixels for both width and height
            color: Color to render the icon (default: white)

        Returns:
            CTkImage object or None if loading fails
        """
        if not SVG_SUPPORT:
            print("Warning: SVG support not available. Install Pillow and cairosvg.")
            return None

        # Create cache key
        cache_key = f"{icon_name}_{size}_{color}"

        # Return cached version if available
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        # Build icon path
        icon_path = ICONS_DIR / f"{icon_name}.svg"

        if not icon_path.exists():
            print(f"Warning: Icon file not found: {icon_path}")
            return None

        try:
            # Read SVG file
            with open(icon_path, 'r') as f:
                svg_data = f.read()

            # Replace fill color if needed (simple approach)
            if color != "white":
                svg_data = svg_data.replace('fill="white"', f'fill="{color}"')

            # Convert SVG to PNG in memory
            png_data = cairosvg.svg2png(
                bytestring=svg_data.encode('utf-8'),
                output_width=size,
                output_height=size
            )

            # Load PNG data into PIL Image
            image = Image.open(io.BytesIO(png_data))

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
    return IconLoader.load_svg_icon("play", size)


def load_pause_icon(size: int = 24) -> Optional["ctk.CTkImage"]:
    """Load the pause icon."""
    return IconLoader.load_svg_icon("pause", size)


def load_stop_icon(size: int = 24) -> Optional["ctk.CTkImage"]:
    """Load the stop icon."""
    return IconLoader.load_svg_icon("stop", size)


def load_volume_icon(size: int = 24) -> Optional["ctk.CTkImage"]:
    """Load the volume icon."""
    return IconLoader.load_svg_icon("volume", size)


def load_music_note_icon(size: int = 24) -> Optional["ctk.CTkImage"]:
    """Load the music note icon."""
    return IconLoader.load_svg_icon("music_note", size)
