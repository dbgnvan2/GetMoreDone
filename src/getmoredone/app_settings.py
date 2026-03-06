"""
Application settings management.
Stores user preferences like Obsidian vault path.
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict, fields

from .paths import default_settings_path


@dataclass
class AppSettings:
    """Application settings."""

    obsidian_vault_path: Optional[str] = None
    obsidian_notes_subfolder: str = "GetMoreDone"
    # Default green checkmark, can be customized to image path or emoji
    completion_icon: str = "✓"
    appearance_mode: str = "dark"  # system | dark | light
    theme_name: str = "apple_grey"
    list_row_font_size: int = 14

    # Timer settings
    default_time_block_minutes: int = 30
    default_break_minutes: int = 5
    timer_window_width: int = 450
    timer_window_height: int = 550
    timer_window_x: Optional[int] = None
    timer_window_y: Optional[int] = None
    timer_warning_minutes: int = 10  # When to show green warning

    # Next Action Window settings
    next_action_window_width: int = 500
    next_action_window_height: int = 400
    next_action_window_x: Optional[int] = None
    next_action_window_y: Optional[int] = None

    # Audio settings
    enable_break_sounds: bool = True
    break_start_sound: Optional[str] = None  # Path to WAV file for break start
    break_end_sound: Optional[str] = None    # Path to WAV file for break end
    # Path to folder containing music files for timer
    music_folder: Optional[str] = None
    music_volume: float = 0.7                # Music volume (0.0 to 1.0)

    # Date increment settings
    # Include Saturday in date calculations (push, +/-)
    include_saturday: bool = True
    # Include Sunday in date calculations (push, +/-)
    include_sunday: bool = True
    # First day of week for VPS week generation (0=Monday .. 6=Sunday)
    first_day_of_week: int = 0

    # List view settings
    # Default state for list views (Today, Upcoming, All Items)
    default_columns_expanded: bool = False
    # Drag Schedule date box text color (hex)
    drag_schedule_date_text_color: str = "#FFFFFF"
    # Drag Schedule date/future box height in pixels
    drag_schedule_box_height_px: int = 86

    # Future date options (Drag Schedule)
    mid_term_offset_days: int = 90
    long_term_offset_days: int = 180
    next_month_offset_days: int = 0
    next_quarter_offset_days: int = 0

    # Email → Action Items (Gmail importer)
    gmail_import_enabled: bool = True
    gmail_import_trigger_label: str = "GMD"
    gmail_import_moved_label: str = "GMD/moved"
    gmail_import_interval_seconds: int = 300
    calendar_import_days_ahead: int = 14

    @classmethod
    def get_settings_path(cls) -> Path:
        """Get the path to the settings file (user-writable)."""
        return default_settings_path()

    @classmethod
    def load(cls) -> 'AppSettings':
        """Load settings from file."""
        settings_path = cls.get_settings_path()

        if settings_path.exists():
            try:
                with open(settings_path, 'r') as f:
                    data = json.load(f)
                valid_keys = {f.name for f in fields(cls)}
                filtered = {k: v for k, v in data.items() if k in valid_keys}
                settings = cls(**filtered)
                settings.appearance_mode = cls._normalize_appearance_mode(
                    settings.appearance_mode)
                settings.theme_name = cls._normalize_theme_name(
                    settings.theme_name)
                settings.list_row_font_size = cls._normalize_list_row_font_size(
                    getattr(settings, "list_row_font_size", 14)
                )
                return settings
            except Exception as e:
                print(f"Error loading settings: {e}")
                return cls()

        return cls()

    def save(self):
        """Save settings to file."""
        settings_path = self.get_settings_path()
        self.appearance_mode = self._normalize_appearance_mode(
            self.appearance_mode)
        self.theme_name = self._normalize_theme_name(self.theme_name)
        self.list_row_font_size = self._normalize_list_row_font_size(
            self.list_row_font_size
        )

        # Ensure data directory exists
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(settings_path, 'w') as f:
                json.dump(asdict(self), f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    @staticmethod
    def _normalize_appearance_mode(value: Optional[str]) -> str:
        allowed = {"system", "dark", "light"}
        mode = (value or "").strip().lower()
        return mode if mode in allowed else "dark"

    @staticmethod
    def _normalize_theme_name(value: Optional[str]) -> str:
        allowed = {"green", "orange", "pink", "grey", "blue", "purple", "apple_grey", "black_white"}
        name = (value or "").strip().lower()
        return name if name in allowed else "apple_grey"

    @staticmethod
    def _normalize_list_row_font_size(value: Optional[int]) -> int:
        try:
            size = int(value)
        except (TypeError, ValueError):
            size = 14
        return max(10, min(24, size))

    def validate_vault_path(self) -> bool:
        """Check if vault path exists."""
        if not self.obsidian_vault_path:
            return False
        return Path(self.obsidian_vault_path).exists()

    def get_notes_folder(self) -> Optional[Path]:
        """Get the full path to the notes subfolder."""
        if not self.obsidian_vault_path:
            return None

        vault = Path(self.obsidian_vault_path)
        if not vault.exists():
            return None

        notes_folder = vault / self.obsidian_notes_subfolder
        return notes_folder
