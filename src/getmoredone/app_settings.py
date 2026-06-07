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
    # M7.A.1 — Separate subfolder for Project Notes so they don't mingle with
    # action-item notes. Blank value falls back to obsidian_notes_subfolder.
    # Spec: docs/implementation_plan_2026-06-06_project_notes.md#M7.A.1
    project_notes_subfolder: str = "GetMoreDone/Projects"
    # Default green checkmark, can be customized to image path or emoji
    completion_icon: str = "✓"
    completion_badge_path: Optional[str] = None
    completion_confetti_threshold: int = 0
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
    # First day of week for VSP week generation (0=Monday .. 6=Sunday)
    first_day_of_week: int = 0

    # List view settings
    # Default state for list views (Today, Upcoming, All Items)
    default_columns_expanded: bool = False
    # First day of business year in MM-DD format
    business_year_start_mmdd: str = "01-01"
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
                settings.completion_confetti_threshold = cls._normalize_completion_confetti_threshold(
                    getattr(settings, "completion_confetti_threshold", 0)
                )
                settings.business_year_start_mmdd = cls._normalize_business_year_start_mmdd(
                    getattr(settings, "business_year_start_mmdd", "01-01")
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
        self.completion_confetti_threshold = self._normalize_completion_confetti_threshold(
            self.completion_confetti_threshold
        )
        self.business_year_start_mmdd = self._normalize_business_year_start_mmdd(
            self.business_year_start_mmdd
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

    @staticmethod
    def _normalize_business_year_start_mmdd(value: Optional[str]) -> str:
        text = (value or "").strip()
        if len(text) != 5 or text[2] != "-":
            return "01-01"
        month_text, day_text = text.split("-", 1)
        try:
            month = int(month_text)
            day = int(day_text)
        except ValueError:
            return "01-01"
        if month < 1 or month > 12:
            return "01-01"
        max_days = {
            1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
            7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
        }[month]
        if day < 1 or day > max_days:
            return "01-01"
        return f"{month:02d}-{day:02d}"

    @staticmethod
    def _normalize_completion_confetti_threshold(value: Optional[int]) -> int:
        try:
            threshold = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, threshold)

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

    def get_project_notes_folder(self) -> Optional[Path]:
        """Full path to the Project Notes subfolder, falling back when blank.

        Purpose: Resolve the Obsidian folder where Project Notes (.md) live.
                 If project_notes_subfolder is blank, falls back to the
                 generic obsidian_notes_subfolder so users who haven't
                 configured the new setting still get sane behavior.
        Spec:    docs/implementation_plan_2026-06-06_project_notes.md#M7.A.2
        Tests:   tests/test_project_notes.py::TestM7Settings::test_get_project_notes_folder_returns_path
                 tests/test_project_notes.py::TestM7Settings::test_blank_project_subfolder_falls_back
        """
        if not self.obsidian_vault_path:
            return None
        vault = Path(self.obsidian_vault_path)
        if not vault.exists():
            return None
        subfolder = (self.project_notes_subfolder or "").strip() or self.obsidian_notes_subfolder
        return vault / subfolder

    def get_project_notes_subfolder_or_default(self) -> str:
        """Return the subfolder string to pass to create_obsidian_note.

        Purpose: Resolves to the project subfolder, or to the generic
                 obsidian_notes_subfolder if the project setting is blank.
                 Separate from get_project_notes_folder() because
                 create_obsidian_note takes the subfolder *string*, not a Path.
        Spec:    docs/implementation_plan_2026-06-06_project_notes.md#M7.A.5
        Tests:   tests/test_project_notes.py::TestM7Settings::test_blank_project_subfolder_falls_back
        """
        return (self.project_notes_subfolder or "").strip() or self.obsidian_notes_subfolder
