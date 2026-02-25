"""
Settings screen - application settings and database management.
"""

import customtkinter as ctk
import shutil
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING
from tkinter import filedialog, colorchooser, messagebox

from ..app_settings import AppSettings
from ..obsidian_utils import validate_obsidian_setup
from ..theme import APPEARANCE_MODES, THEME_NAMES, button_style
from ..utils.icon_loader import load_volume_icon

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class SettingsScreen(ctk.CTkFrame):
    """Screen for application settings."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app

        # Load app settings
        self.settings = AppSettings.load()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Create tabbed interface
        self.create_tabs()

    def create_header(self):
        """Create header."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        title = ctk.CTkLabel(
            header,
            text="Settings",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(side="left", padx=10, pady=10)

    def create_tabs(self):
        """Create tabbed interface for settings."""
        # Create tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Tab 1: Database Management (Database + Obsidian)
        db_tab = self.tabview.add("Database Management")
        db_tab.grid_columnconfigure(0, weight=1)
        self.create_database_section(db_tab)
        self.create_obsidian_section(db_tab)

        # Tab 2: Appearance (Appearance + Date Settings)
        appearance_tab = self.tabview.add("Appearance")
        appearance_tab.grid_columnconfigure(0, weight=1)
        self.create_appearance_section(appearance_tab)
        self.create_date_increment_section(appearance_tab)

        # Tab 3: Future Dates
        future_tab = self.tabview.add("Future Dates")
        future_tab.grid_columnconfigure(0, weight=1)
        self.create_future_date_options_section(future_tab)

        # Tab 4: Timer & Audio
        timer_tab = self.tabview.add("Timer & Audio")
        timer_tab.grid_columnconfigure(0, weight=1)
        self.create_timer_audio_section(timer_tab)

        # Tab 5: Organizational Factors
        org_tab = self.tabview.add("Organizational Factors")
        org_tab.grid_columnconfigure(0, weight=1)
        self.create_organizational_factors_section(org_tab)

        # Tab 6: Email Import
        email_tab = self.tabview.add("Email Import")
        email_tab.grid_columnconfigure(0, weight=1)
        self.create_email_import_section(email_tab)

        # Tab 7: VPS Life Segments
        vps_tab = self.tabview.add("VPS Life Segments")
        vps_tab.grid_columnconfigure(0, weight=1)
        self.create_vps_segments_section(vps_tab)

    def create_database_section(self, parent=None):
        """Create database management section."""
        if parent is None:
            parent = self
        section = ctk.CTkFrame(parent)
        section.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        section.grid_columnconfigure(1, weight=1)

        # Section title
        ctk.CTkLabel(
            section,
            text="Database Management",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 15))

        # Database path
        ctk.CTkLabel(section, text="Database Path:").grid(
            row=1, column=0, sticky="w", padx=10, pady=5)
        db_path_label = ctk.CTkLabel(
            section, text=self.db_manager.db.db_path, anchor="w")
        db_path_label.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        # Backup button
        btn_backup = ctk.CTkButton(
            section,
            text="Backup Database",
            command=self.backup_database
        )
        btn_backup.grid(row=2, column=0, sticky="w", padx=10, pady=10)

        # Load demo data button
        btn_demo = ctk.CTkButton(
            section,
            text="Load Demo Data",
            command=self.load_demo_data,
            **button_style("secondary"),
        )
        btn_demo.grid(row=2, column=1, sticky="w", padx=10, pady=10)

        # Status label
        self.db_status_label = ctk.CTkLabel(
            section, text="", text_color="green")
        self.db_status_label.grid(
            row=3, column=1, sticky="w", padx=10, pady=10)

        # Info
        info_text = (
            "Backups are saved in the data/ directory with timestamps.\n"
            "Database file: getmoredone.db\n\n"
            "Demo Data: adds a small set of sample items to the CURRENT database (no deletion)."
        )
        ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray").grid(
            row=4, column=0, columnspan=2, sticky="w", padx=10, pady=5
        )

    def create_obsidian_section(self, parent=None):
        """Create Obsidian integration section."""
        if parent is None:
            parent = self
        section = ctk.CTkFrame(parent)
        section.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        section.grid_columnconfigure(1, weight=1)

        # Section title
        ctk.CTkLabel(
            section,
            text="Obsidian Integration",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 15))

        # Vault path
        ctk.CTkLabel(section, text="Vault Path:").grid(
            row=1, column=0, sticky="w", padx=10, pady=5)

        self.vault_path_var = ctk.StringVar(
            value=self.settings.obsidian_vault_path or "")
        vault_path_entry = ctk.CTkEntry(
            section, textvariable=self.vault_path_var, width=300)
        vault_path_entry.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        btn_browse = ctk.CTkButton(
            section,
            text="Browse",
            width=80,
            command=self.browse_vault_path
        )
        btn_browse.grid(row=1, column=2, padx=5, pady=5)

        # Notes subfolder
        ctk.CTkLabel(section, text="Notes Subfolder:").grid(
            row=2, column=0, sticky="w", padx=10, pady=5)

        self.subfolder_var = ctk.StringVar(
            value=self.settings.obsidian_notes_subfolder)
        subfolder_entry = ctk.CTkEntry(
            section, textvariable=self.subfolder_var, width=200)
        subfolder_entry.grid(row=2, column=1, sticky="w", padx=10, pady=5)

        # Save and test buttons
        btn_frame = ctk.CTkFrame(section, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2,
                       sticky="w", padx=10, pady=10)

        btn_save = ctk.CTkButton(
            btn_frame,
            text="Save Settings",
            command=self.save_obsidian_settings,
            **button_style("primary"),
        )
        btn_save.pack(side="left", padx=5)

        btn_test = ctk.CTkButton(
            btn_frame,
            text="Test Connection",
            command=self.test_obsidian_connection
        )
        btn_test.pack(side="left", padx=5)

        # Status label
        self.obsidian_status_label = ctk.CTkLabel(
            section, text="", wraplength=500)
        self.obsidian_status_label.grid(
            row=3, column=2, sticky="w", padx=10, pady=10)

        # Info
        info_text = ("Configure your Obsidian vault to link notes to Action Items and Contacts.\n"
                     "Notes will be saved to: {vault_path}/{subfolder}/\n"
                     "The vault must have a .obsidian folder (be a valid Obsidian vault).")
        ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(
            row=4, column=0, columnspan=3, sticky="w", padx=10, pady=5
        )

    def browse_vault_path(self):
        """Open folder browser for vault path."""
        path = filedialog.askdirectory(title="Select Obsidian Vault Folder")
        if path:
            self.vault_path_var.set(path)

    def save_obsidian_settings(self):
        """Save Obsidian settings."""
        self.settings.obsidian_vault_path = self.vault_path_var.get().strip() or None
        self.settings.obsidian_notes_subfolder = self.subfolder_var.get().strip() or "GetMoreDone"

        self.settings.save()

        self.obsidian_status_label.configure(
            text="✓ Settings saved",
            text_color="green"
        )

    def test_obsidian_connection(self):
        """Test Obsidian vault connection."""
        vault_path = self.vault_path_var.get().strip()
        subfolder = self.subfolder_var.get().strip() or "GetMoreDone"

        if not vault_path:
            self.obsidian_status_label.configure(
                text="❌ Please enter a vault path",
                text_color="red"
            )
            return

        is_valid, message = validate_obsidian_setup(vault_path, subfolder)

        if is_valid:
            self.obsidian_status_label.configure(
                text=f"✓ {message}",
                text_color="green"
            )
        else:
            self.obsidian_status_label.configure(
                text=f"❌ {message}",
                text_color="red"
            )

    def create_appearance_section(self, parent=None):
        """Create appearance settings section."""
        if parent is None:
            parent = self
        section = ctk.CTkFrame(parent)
        section.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        section.grid_columnconfigure(1, weight=1)

        # Section title
        ctk.CTkLabel(
            section,
            text="Appearance",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 15))

        ctk.CTkLabel(section, text="Appearance Mode:").grid(
            row=1, column=0, sticky="w", padx=10, pady=5)
        self.appearance_mode_var = ctk.StringVar(
            value=getattr(self.settings, "appearance_mode", "dark")
        )
        self.appearance_mode_combo = ctk.CTkComboBox(
            section,
            values=list(APPEARANCE_MODES),
            variable=self.appearance_mode_var,
            width=180,
            command=self.on_theme_preference_changed
        )
        self.appearance_mode_combo.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(section, text="Color Theme:").grid(
            row=2, column=0, sticky="w", padx=10, pady=5)
        self.theme_name_var = ctk.StringVar(
            value=getattr(self.settings, "theme_name", "apple_grey")
        )
        self.theme_name_combo = ctk.CTkComboBox(
            section,
            values=list(THEME_NAMES),
            variable=self.theme_name_var,
            width=180,
            command=self.on_theme_preference_changed
        )
        self.theme_name_combo.grid(row=2, column=1, sticky="w", padx=10, pady=5)

        self.theme_apply_btn = ctk.CTkButton(
            section,
            text="Apply Theme",
            command=self.apply_theme_preferences,
            width=120
        )
        self.theme_apply_btn.grid(row=1, column=2, rowspan=2, sticky="w", padx=10, pady=5)

        self.appearance_status_label = ctk.CTkLabel(section, text="", text_color="green")
        self.appearance_status_label.grid(row=3, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 4))

        info_text = (
            "Appearance mode controls system/dark/light rendering.\n"
            "Color theme switches between bundled CustomTkinter palettes."
        )
        ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(
            row=4, column=0, columnspan=3, sticky="w", padx=10, pady=5
        )

    def on_theme_preference_changed(self, _choice=None):
        """Apply and persist theme choices immediately."""
        self.apply_theme_preferences()

    def apply_theme_preferences(self):
        """Save selected appearance and theme, then apply app-wide."""
        self.settings.appearance_mode = self.appearance_mode_var.get().strip().lower()
        self.settings.theme_name = self.theme_name_var.get().strip().lower()
        self.settings.save()

        self.app.settings = self.settings
        self.app.apply_theme_preferences()
        self.appearance_status_label.configure(
            text=f"✓ Applied {self.settings.appearance_mode}/{self.settings.theme_name}",
            text_color="green",
        )

    def create_date_increment_section(self, parent=None):
        """Create date increment settings section."""
        if parent is None:
            parent = self
        section = ctk.CTkFrame(parent)
        section.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        section.grid_columnconfigure(1, weight=1)

        # Section title
        ctk.CTkLabel(
            section,
            text="Date Increment Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 15))

        # Include Saturday checkbox
        self.include_saturday_var = ctk.BooleanVar(
            value=self.settings.include_saturday)
        saturday_checkbox = ctk.CTkCheckBox(
            section,
            text="Include Saturday in date calculations (push, +/- buttons)",
            variable=self.include_saturday_var
        )
        saturday_checkbox.grid(
            row=1, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        # Include Sunday checkbox
        self.include_sunday_var = ctk.BooleanVar(
            value=self.settings.include_sunday)
        sunday_checkbox = ctk.CTkCheckBox(
            section,
            text="Include Sunday in date calculations (push, +/- buttons)",
            variable=self.include_sunday_var
        )
        sunday_checkbox.grid(row=2, column=0, columnspan=2,
                             sticky="w", padx=10, pady=5)

        # Default list view expansion checkbox
        self.default_columns_expanded_var = ctk.BooleanVar(
            value=self.settings.default_columns_expanded)
        columns_expanded_checkbox = ctk.CTkCheckBox(
            section,
            text="Start list views expanded (Today, Upcoming, All Items)",
            variable=self.default_columns_expanded_var
        )
        columns_expanded_checkbox.grid(row=3, column=0, columnspan=2,
                                       sticky="w", padx=10, pady=5)

        # First day of week selector (used by VPS week generation)
        ctk.CTkLabel(section, text="First day of week (VPS):").grid(
            row=4, column=0, sticky="w", padx=10, pady=5
        )
        first_day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        first_day_idx = int(getattr(self.settings, "first_day_of_week", 0))
        if first_day_idx < 0 or first_day_idx > 6:
            first_day_idx = 0
        self.first_day_of_week_var = ctk.StringVar(value=first_day_names[first_day_idx])
        self.first_day_of_week_combo = ctk.CTkComboBox(
            section,
            values=first_day_names,
            variable=self.first_day_of_week_var,
            width=180
        )
        self.first_day_of_week_combo.grid(row=4, column=1, sticky="w", padx=10, pady=5)

        # Drag Schedule date text color setting
        ctk.CTkLabel(section, text="Drag Schedule date text color:").grid(
            row=5, column=0, sticky="w", padx=10, pady=5
        )
        self.drag_schedule_text_color_var = ctk.StringVar(
            value=getattr(self.settings, "drag_schedule_date_text_color", "#FFFFFF")
        )
        self.drag_schedule_text_color_entry = ctk.CTkEntry(
            section,
            textvariable=self.drag_schedule_text_color_var,
            width=180
        )
        self.drag_schedule_text_color_entry.grid(row=5, column=1, sticky="w", padx=10, pady=5)

        self.drag_schedule_text_color_pick_btn = ctk.CTkButton(
            section,
            text="Pick Color",
            width=100,
            command=self.pick_drag_schedule_text_color
        )
        self.drag_schedule_text_color_pick_btn.grid(row=5, column=2, sticky="w", padx=6, pady=5)

        # Drag Schedule date box height setting
        ctk.CTkLabel(section, text="Drag Schedule box height (px):").grid(
            row=6, column=0, sticky="w", padx=10, pady=5
        )
        self.drag_schedule_box_height_var = ctk.StringVar(
            value=str(getattr(self.settings, "drag_schedule_box_height_px", 86))
        )
        self.drag_schedule_box_height_entry = ctk.CTkEntry(
            section,
            textvariable=self.drag_schedule_box_height_var,
            width=180
        )
        self.drag_schedule_box_height_entry.grid(row=6, column=1, sticky="w", padx=10, pady=5)

        # Save button
        btn_save = ctk.CTkButton(
            section,
            text="Save Settings",
            command=self.save_date_increment_settings,
            **button_style("primary"),
            width=150
        )
        btn_save.grid(row=7, column=0, sticky="w", padx=10, pady=10)

        # Status label
        self.date_increment_status_label = ctk.CTkLabel(
            section, text="", text_color="green")
        self.date_increment_status_label.grid(
            row=7, column=1, sticky="w", padx=10, pady=10)

        # Info
        info_text = ("These settings control how dates are incremented when using:\n"
                     "• Push button (move item to next day)\n"
                     "• +/- buttons in date fields\n"
                     "• Continue button (duplicate action for next day)\n\n"
                     "Note: Manual date entry is not affected by these settings.")
        ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(
            row=8, column=0, columnspan=2, sticky="w", padx=10, pady=5
        )

    def save_date_increment_settings(self):
        """Save date increment settings."""
        self.settings.include_saturday = self.include_saturday_var.get()
        self.settings.include_sunday = self.include_sunday_var.get()
        self.settings.default_columns_expanded = self.default_columns_expanded_var.get()
        first_day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        selected = self.first_day_of_week_var.get().strip()
        try:
            self.settings.first_day_of_week = first_day_names.index(selected)
        except ValueError:
            self.settings.first_day_of_week = 0

        color_value = self.drag_schedule_text_color_var.get().strip() or "#FFFFFF"
        if not color_value.startswith("#"):
            color_value = f"#{color_value}"
        if len(color_value) != 7:
            color_value = "#FFFFFF"
        self.settings.drag_schedule_date_text_color = color_value
        self.settings.drag_schedule_box_height_px = self._parse_positive_int(
            self.drag_schedule_box_height_var.get(),
            default=getattr(self.settings, "drag_schedule_box_height_px", 86)
        )
        self.settings.save()

        self.date_increment_status_label.configure(
            text="✓ Settings saved",
            text_color="green"
        )

    def pick_drag_schedule_text_color(self):
        """Pick Drag Schedule date text color using color chooser."""
        initial = self.drag_schedule_text_color_var.get().strip() or "#FFFFFF"
        picked = colorchooser.askcolor(color=initial, title="Pick Drag Schedule Date Text Color")
        if picked and picked[1]:
            self.drag_schedule_text_color_var.set(picked[1].upper())

    def _parse_positive_int(self, value: str, default: int) -> int:
        try:
            parsed = int(str(value).strip())
            return parsed if parsed > 0 else default
        except Exception:
            return default

    def _parse_int(self, value: str, default: int) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return default

    def save_future_date_options(self):
        """Save Future Date Options settings."""
        self.settings.mid_term_offset_days = self._parse_positive_int(
            self.future_near_var.get(), default=self.settings.mid_term_offset_days)
        self.settings.long_term_offset_days = self._parse_positive_int(
            self.future_long_var.get(), default=self.settings.long_term_offset_days)
        self.settings.next_month_offset_days = self._parse_int(
            self.future_next_month_var.get(), default=self.settings.next_month_offset_days)
        self.settings.next_quarter_offset_days = self._parse_int(
            self.future_next_quarter_var.get(), default=self.settings.next_quarter_offset_days)

        self.settings.save()

        self.future_date_status_label.configure(
            text="✓ Future date options saved",
            text_color="green"
        )

    def create_timer_audio_section(self, parent=None):
        """Create timer and audio settings section."""
        if parent is None:
            parent = self
        section = ctk.CTkFrame(parent)
        section.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        section.grid_columnconfigure(1, weight=1)

        # Section title
        ctk.CTkLabel(
            section,
            text="Timer Music",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 15))

        # Music folder path
        ctk.CTkLabel(section, text="Music Folder:").grid(
            row=1, column=0, sticky="w", padx=10, pady=5)

        self.music_folder_var = ctk.StringVar(
            value=self.settings.music_folder or "")
        music_folder_entry = ctk.CTkEntry(
            section, textvariable=self.music_folder_var, width=300)
        music_folder_entry.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        btn_browse = ctk.CTkButton(
            section,
            text="Browse",
            width=80,
            command=self.browse_music_folder
        )
        btn_browse.grid(row=1, column=2, padx=5, pady=5)

        # Music volume slider
        volume_label_frame = ctk.CTkFrame(section, fg_color="transparent")
        volume_label_frame.grid(row=2, column=0, sticky="w", padx=10, pady=5)

        # Load and display volume icon
        volume_icon = load_volume_icon(size=18)
        if volume_icon:
            icon_label = ctk.CTkLabel(
                volume_label_frame, text="", image=volume_icon)
            icon_label.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(volume_label_frame,
                     text="Music Volume:").pack(side="left")

        volume_frame = ctk.CTkFrame(section, fg_color="transparent")
        volume_frame.grid(row=2, column=1, columnspan=2,
                          sticky="ew", padx=10, pady=5)

        self.music_volume_var = ctk.DoubleVar(value=self.settings.music_volume)
        self.music_volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0.0,
            to=1.0,
            variable=self.music_volume_var,
            width=200,
            command=self.update_volume_label
        )
        self.music_volume_slider.pack(side="left", padx=(0, 10))

        self.volume_label = ctk.CTkLabel(
            volume_frame, text=f"{int(self.settings.music_volume * 100)}%", width=40)
        self.volume_label.pack(side="left")

        # Save button
        btn_save = ctk.CTkButton(
            section,
            text="Save Settings",
            command=self.save_timer_audio_settings,
            **button_style("primary"),
            width=150
        )
        btn_save.grid(row=3, column=0, sticky="w", padx=10, pady=10)

        # Status label
        self.timer_audio_status_label = ctk.CTkLabel(
            section, text="", text_color="green")
        self.timer_audio_status_label.grid(
            row=3, column=1, sticky="w", padx=10, pady=10)

        # Info
        info_text = ("Select a folder containing music files (MP3, WAV, OGG, FLAC, M4A).\n"
                     "When you start a timer, a random music file from this folder will play.\n"
                     "Adjust volume to control music playback loudness (70% recommended).")
        ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(
            row=4, column=0, columnspan=3, sticky="w", padx=10, pady=5
        )

    def browse_music_folder(self):
        """Open folder browser for music folder."""
        path = filedialog.askdirectory(title="Select Music Folder")
        if path:
            self.music_folder_var.set(path)

    def update_volume_label(self, value):
        """Update volume label when slider changes."""
        percentage = int(float(value) * 100)
        self.volume_label.configure(text=f"{percentage}%")

    def save_timer_audio_settings(self):
        """Save timer and audio settings."""
        self.settings.music_folder = self.music_folder_var.get().strip() or None
        self.settings.music_volume = self.music_volume_var.get()
        self.settings.save()

        self.timer_audio_status_label.configure(
            text=f"✓ Settings saved (Volume: {int(self.settings.music_volume * 100)}%)",
            text_color="green"
        )

    def create_organizational_factors_section(self, parent=None):
        """Create organizational factors management section."""
        if parent is None:
            parent = self
        section = ctk.CTkFrame(parent)
        section.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        section.grid_columnconfigure(0, weight=1)

        # Section title
        ctk.CTkLabel(
            section,
            text="Organizational Factors",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 15))

        # Info
        info_text = ("Manage the values for Group and Category fields.\n"
                     "Edit values to rename them across all items, or delete values with replacement.")
        ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(
            row=1, column=0, sticky="w", padx=10, pady=5
        )

        # Create tabs for Groups and Categories
        tabview = ctk.CTkTabview(section)
        tabview.grid(row=2, column=0, sticky="ew", padx=10, pady=10)

        # Groups tab
        groups_tab = tabview.add("Groups")
        self.create_factor_editor(groups_tab, "group")

        # Categories tab
        categories_tab = tabview.add("Categories")
        self.create_factor_editor(categories_tab, "category")

    def create_factor_editor(self, parent, factor_type: str):
        """Create editor for a specific organizational factor."""
        parent.grid_columnconfigure(0, weight=1)

        # Scrollable frame for list
        scroll = ctk.CTkScrollableFrame(parent, height=300)
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(1, weight=1)

        # Get current values
        if factor_type == "group":
            values = self.db_manager.get_distinct_groups()
        else:
            values = self.db_manager.get_distinct_categories()

        # Display each value with edit/delete buttons
        for idx, value in enumerate(values):
            # Value label
            value_label = ctk.CTkLabel(scroll, text=value, anchor="w")
            value_label.grid(row=idx, column=0, sticky="w", padx=10, pady=5)

            # Edit button
            btn_edit = ctk.CTkButton(
                scroll,
                text="Rename",
                width=80,
                command=lambda v=value, ft=factor_type: self.edit_factor_value(
                    v, ft)
            )
            btn_edit.grid(row=idx, column=1, padx=5, pady=5)

            # Delete button
            btn_delete = ctk.CTkButton(
                scroll,
                text="Delete",
                width=80,
                **button_style("danger"),
                command=lambda v=value, ft=factor_type: self.delete_factor_value(
                    v, ft)
            )
            btn_delete.grid(row=idx, column=2, padx=5, pady=5)

        # Add refresh button
        btn_refresh = ctk.CTkButton(
            parent,
            text="Refresh List",
            command=lambda: self.refresh_organizational_factors()
        )
        btn_refresh.grid(row=1, column=0, padx=10, pady=5)

    def edit_factor_value(self, old_value: str, factor_type: str):
        """Edit (rename) an organizational factor value."""
        # Create dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Rename {factor_type.capitalize()}")
        dialog.geometry("500x250")
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Content
        ctk.CTkLabel(
            dialog,
            text=f"Rename {factor_type.capitalize()}: {old_value}",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(padx=20, pady=(20, 10))

        ctk.CTkLabel(dialog, text="New value:").pack(padx=20, pady=5)
        new_value_var = ctk.StringVar(value=old_value)
        entry = ctk.CTkEntry(dialog, textvariable=new_value_var, width=300)
        entry.pack(padx=20, pady=5)

        # Global replace option
        replace_var = ctk.BooleanVar(value=True)
        checkbox = ctk.CTkCheckBox(
            dialog,
            text="Replace this value in all existing items",
            variable=replace_var
        )
        checkbox.pack(padx=20, pady=10)

        # Status label
        status_label = ctk.CTkLabel(dialog, text="")
        status_label.pack(padx=20, pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(padx=20, pady=10)

        def save():
            new_value = new_value_var.get().strip()
            if not new_value:
                status_label.configure(
                    text="Please enter a value", text_color="red")
                return

            if new_value == old_value:
                dialog.destroy()
                return

            try:
                if replace_var.get():
                    # Global replace
                    self.db_manager.update_organizational_factor(
                        factor_type, old_value, new_value
                    )
                    status_label.configure(
                        text=f"✓ Replaced in all items",
                        text_color="green"
                    )
                else:
                    status_label.configure(
                        text="Value not replaced (option unchecked)",
                        text_color="orange"
                    )

                # Close dialog after a brief delay
                dialog.after(1000, dialog.destroy)
                # Refresh the organizational factors section
                self.refresh_organizational_factors()

            except Exception as e:
                status_label.configure(
                    text=f"Error: {str(e)}", text_color="red")

        ctk.CTkButton(btn_frame, text="Save", command=save).pack(
            side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel",
                      command=dialog.destroy).pack(side="left", padx=5)

    def delete_factor_value(self, value: str, factor_type: str):
        """Delete an organizational factor value."""
        # Create dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Delete {factor_type.capitalize()}")
        dialog.geometry("500x300")
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Content
        ctk.CTkLabel(
            dialog,
            text=f"Delete {factor_type.capitalize()}: {value}",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(padx=20, pady=(20, 10))

        ctk.CTkLabel(
            dialog,
            text="What should happen to items with this value?",
            wraplength=450
        ).pack(padx=20, pady=5)

        # Replacement options
        action_var = ctk.StringVar(value="clear")

        ctk.CTkRadioButton(
            dialog,
            text="Clear the value (set to empty)",
            variable=action_var,
            value="clear"
        ).pack(padx=20, pady=5)

        replace_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        replace_frame.pack(padx=20, pady=5)

        ctk.CTkRadioButton(
            replace_frame,
            text="Replace with:",
            variable=action_var,
            value="replace"
        ).pack(side="left", padx=5)

        # Get other values for replacement
        if factor_type == "group":
            other_values = [
                v for v in self.db_manager.get_distinct_groups() if v != value]
        else:
            other_values = [
                v for v in self.db_manager.get_distinct_categories() if v != value]

        replacement_var = ctk.StringVar(
            value=other_values[0] if other_values else "")
        replacement_combo = ctk.CTkComboBox(
            replace_frame,
            values=other_values if other_values else [""],
            variable=replacement_var,
            width=200
        )
        replacement_combo.pack(side="left", padx=5)

        # Status label
        status_label = ctk.CTkLabel(dialog, text="")
        status_label.pack(padx=20, pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(padx=20, pady=10)

        def delete():
            try:
                if action_var.get() == "clear":
                    # Remove the value (set to NULL)
                    self.db_manager.delete_organizational_factor(
                        factor_type, value, None
                    )
                    status_label.configure(
                        text=f"✓ Deleted (cleared in all items)",
                        text_color="green"
                    )
                else:
                    # Replace with another value
                    replacement = replacement_var.get().strip()
                    if not replacement:
                        status_label.configure(
                            text="Please select a replacement value", text_color="red")
                        return

                    self.db_manager.delete_organizational_factor(
                        factor_type, value, replacement
                    )
                    status_label.configure(
                        text=f"✓ Deleted (replaced with '{replacement}')",
                        text_color="green"
                    )

                # Close dialog after a brief delay
                dialog.after(1000, dialog.destroy)
                # Refresh the organizational factors section
                self.refresh_organizational_factors()

            except Exception as e:
                status_label.configure(
                    text=f"Error: {str(e)}", text_color="red")

        ctk.CTkButton(btn_frame, text="Delete", **button_style("danger"), command=delete).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel",
                      command=dialog.destroy).pack(side="left", padx=5)

    def refresh_organizational_factors(self):
        """Refresh the organizational factors section."""
        # Get the Organizational Factors tab
        org_tab = self.tabview.tab("Organizational Factors")

        # Destroy all children in the tab
        for child in org_tab.winfo_children():
            child.destroy()

        # Recreate the section
        self.create_organizational_factors_section(org_tab)

    def backup_database(self):
        """Backup the database file."""
        try:
            db_path = Path(self.db_manager.db.db_path)
            if not db_path.exists():
                self.db_status_label.configure(
                    text="Database file not found", text_color="red")
                return

            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = db_path.parent / f"getmoredone_backup_{timestamp}.db"

            # Copy database file
            shutil.copy2(db_path, backup_path)

            self.db_status_label.configure(
                text=f"Backup created: {backup_path.name}",
                text_color="green"
            )

        except Exception as e:
            self.db_status_label.configure(
                text=f"Backup failed: {str(e)}",
                text_color="red"
            )

    def load_demo_data(self):
        """Insert demo data into the CURRENT database (safe additive)."""
        from tkinter import messagebox
        try:
            response = messagebox.askyesno(
                "Load Demo Data",
                "This will ADD a small set of sample Action Items to your current database.\n\n"
                "It will NOT delete any existing items.\n\n"
                "Continue?",
                icon='warning'
            )
            if not response:
                return

            from ..demo_data import load_demo_data
            created = load_demo_data(db_path=self.db_manager.db.db_path)

            self.db_status_label.configure(
                text=f"Demo data added ({created} items)",
                text_color="green",
            )

        except Exception as e:
            self.db_status_label.configure(
                text=f"Demo data failed: {str(e)}",
                text_color="red",
            )

    def create_email_import_section(self, parent=None):
        """Create Email Import settings section (Gmail label → Action Items)."""
        if parent is None:
            parent = self

        section = ctk.CTkFrame(parent)
        section.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        section.grid_columnconfigure(1, weight=1)

        # Title
        ctk.CTkLabel(
            section,
            text="Email Import (Gmail)",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 5))

        info = (
            "Move/label an email into the Trigger Label (e.g. GMD) and GetMoreDone will create an Action Item.\n"
            "After import, the email is moved by removing the trigger label and applying the Processed Label (e.g. GMD/moved).\n\n"
            "This uses the Gmail account you authorized on this computer (OAuth token in ~/.getmoredone/)."
        )
        ctk.CTkLabel(section, text=info, justify="left", text_color="gray", wraplength=700).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10)
        )

        # Enabled toggle
        self.gmail_enabled_var = ctk.BooleanVar(value=bool(getattr(self.settings, "gmail_import_enabled", True)))
        ctk.CTkCheckBox(
            section,
            text="Enable Gmail import",
            variable=self.gmail_enabled_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))

        # Trigger label
        ctk.CTkLabel(section, text="Trigger Label:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        self.gmail_trigger_var = ctk.StringVar(value=getattr(self.settings, "gmail_import_trigger_label", "GMD"))
        ctk.CTkEntry(section, textvariable=self.gmail_trigger_var, width=260).grid(row=3, column=1, sticky="w", padx=10, pady=5)

        # Processed label
        ctk.CTkLabel(section, text="Processed Label:").grid(row=4, column=0, sticky="w", padx=10, pady=5)
        self.gmail_moved_var = ctk.StringVar(value=getattr(self.settings, "gmail_import_moved_label", "GMD/moved"))
        ctk.CTkEntry(section, textvariable=self.gmail_moved_var, width=260).grid(row=4, column=1, sticky="w", padx=10, pady=5)

        # Interval
        ctk.CTkLabel(section, text="Poll Interval (sec):").grid(row=5, column=0, sticky="w", padx=10, pady=5)
        self.gmail_interval_var = ctk.StringVar(value=str(getattr(self.settings, "gmail_import_interval_seconds", 60)))
        ctk.CTkEntry(section, textvariable=self.gmail_interval_var, width=120).grid(row=5, column=1, sticky="w", padx=10, pady=5)

        # Calendar import lookahead
        ctk.CTkLabel(section, text="Calendar Days to check:").grid(row=6, column=0, sticky="w", padx=10, pady=5)
        self.calendar_days_var = ctk.StringVar(value=str(getattr(self.settings, "calendar_import_days_ahead", 14)))
        ctk.CTkEntry(section, textvariable=self.calendar_days_var, width=120).grid(row=6, column=1, sticky="w", padx=10, pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(section, fg_color="transparent")
        btn_frame.grid(row=7, column=0, columnspan=2, sticky="w", padx=10, pady=10)

        ctk.CTkButton(
            btn_frame,
            text="Save Email Import Settings",
            command=self.save_email_import_settings,
            **button_style("primary"),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Run Import Now",
            command=self.run_email_import_now,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Run Calendar Import Now",
            command=self.run_calendar_import_now,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Open Logs",
            command=self.open_email_import_logs,
            **button_style("secondary"),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Email Import Help",
            command=self.show_email_import_help,
            **button_style("secondary"),
        ).pack(side="left", padx=5)

        # Status label
        self.gmail_status_label = ctk.CTkLabel(section, text="", wraplength=700)
        self.gmail_status_label.grid(row=8, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))

        self.calendar_status_label = ctk.CTkLabel(section, text="", wraplength=700)
        self.calendar_status_label.grid(row=9, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))

    def create_future_date_options_section(self, parent=None):
        """Create Future Date Options section (Drag Schedule)."""
        if parent is None:
            parent = self

        section = ctk.CTkFrame(parent)
        section.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        section.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            section,
            text="Future Date Options (Drag Schedule)",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 10))

        ctk.CTkLabel(section, text="Near Term (days from today):").grid(
            row=1, column=0, sticky="w", padx=10, pady=5)
        self.future_near_var = ctk.StringVar(value=str(self.settings.mid_term_offset_days))
        ctk.CTkEntry(section, textvariable=self.future_near_var, width=120).grid(
            row=1, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(section, text="Long Term (days from today):").grid(
            row=2, column=0, sticky="w", padx=10, pady=5)
        self.future_long_var = ctk.StringVar(value=str(self.settings.long_term_offset_days))
        ctk.CTkEntry(section, textvariable=self.future_long_var, width=120).grid(
            row=2, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(section, text="1st Next Month Offset (days from 1st):").grid(
            row=3, column=0, sticky="w", padx=10, pady=5)
        self.future_next_month_var = ctk.StringVar(value=str(getattr(self.settings, "next_month_offset_days", 0)))
        ctk.CTkEntry(section, textvariable=self.future_next_month_var, width=120).grid(
            row=3, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(section, text="1st Next Quarter Offset (days from 1st):").grid(
            row=4, column=0, sticky="w", padx=10, pady=5)
        self.future_next_quarter_var = ctk.StringVar(value=str(getattr(self.settings, "next_quarter_offset_days", 0)))
        ctk.CTkEntry(section, textvariable=self.future_next_quarter_var, width=120).grid(
            row=4, column=1, sticky="w", padx=10, pady=5)

        btn_save = ctk.CTkButton(
            section,
            text="Save Future Date Options",
            command=self.save_future_date_options,
            **button_style("primary"),
            width=220
        )
        btn_save.grid(row=5, column=0, sticky="w", padx=10, pady=10)

        self.future_date_status_label = ctk.CTkLabel(section, text="", text_color="green")
        self.future_date_status_label.grid(row=5, column=1, sticky="w", padx=10, pady=10)

        info_text = (
            "Near/Long term are offsets from today.\n"
            "Next Month/Quarter offsets are applied to the 1st of next month/quarter."
        )
        ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(
            row=6, column=0, columnspan=2, sticky="w", padx=10, pady=5
        )

    def save_email_import_settings(self):
        """Save Email Import settings into settings.json."""
        try:
            self.settings.gmail_import_enabled = bool(self.gmail_enabled_var.get())
            self.settings.gmail_import_trigger_label = self.gmail_trigger_var.get().strip() or "GMD"
            self.settings.gmail_import_moved_label = self.gmail_moved_var.get().strip() or "GMD/moved"

            try:
                interval = int(self.gmail_interval_var.get().strip() or "60")
            except Exception:
                interval = 60
            if interval < 15:
                interval = 15
            self.settings.gmail_import_interval_seconds = interval

            try:
                calendar_days = int(self.calendar_days_var.get().strip() or "14")
            except Exception:
                calendar_days = 14
            if calendar_days < 1:
                calendar_days = 1
            if calendar_days > 365:
                calendar_days = 365
            self.settings.calendar_import_days_ahead = calendar_days

            self.settings.save()

            # Apply to launchd (prod) so interval changes take effect automatically
            try:
                repo_root = Path(__file__).resolve().parents[3]
                updater = repo_root / "tools" / "update_launchd_importer.py"
                python_exe = repo_root / "venv" / "bin" / "python"
                if updater.exists() and python_exe.exists():
                    subprocess.run([str(python_exe), str(updater), "--reload", "prod"], check=False)
            except Exception:
                pass

            self.gmail_status_label.configure(text="Saved (launchd updated).", text_color="green")
        except Exception as e:
            self.gmail_status_label.configure(text=f"Save failed: {e}", text_color="red")

    def run_email_import_now(self):
        """Run the Gmail importer immediately (in a background thread)."""
        # Save current UI values first
        self.save_email_import_settings()

        if not bool(self.gmail_enabled_var.get()):
            self.gmail_status_label.configure(text="Importer is disabled (enable it first).", text_color="gray")
            return

        def work():
            try:
                from ..gmail_importer import GmailImportConfig, import_labeled_emails

                cfg = GmailImportConfig(
                    trigger_label_name=self.settings.gmail_import_trigger_label,
                    moved_label_name=self.settings.gmail_import_moved_label,
                    who_value="Email",
                    group_value="EMAIL",
                    start_offset_days=0,
                    due_offset_days=1,
                )
                n = import_labeled_emails(db_path=self.db_manager.db.db_path, cfg=cfg, dry_run=False)
                self.gmail_status_label.after(0, lambda: self.gmail_status_label.configure(
                    text=f"Imported {n} email(s) from {cfg.trigger_label_name}.",
                    text_color=("green" if n else "gray"),
                ))
            except Exception as e:
                self.gmail_status_label.after(0, lambda: self.gmail_status_label.configure(
                    text=f"Import failed: {e}",
                    text_color="red",
                ))

        self.gmail_status_label.configure(text="Running import…", text_color="gray")
        threading.Thread(target=work, daemon=True).start()

    def open_email_import_logs(self):
        """Open the launchd log files for the importer (best-effort)."""
        # These are the log paths used by our launchd plists.
        out_log = "/tmp/getmoredone-gmailimport-com.getmoredone.gmailimport.prod.out.log"
        err_log = "/tmp/getmoredone-gmailimport-com.getmoredone.gmailimport.prod.err.log"
        try:
            subprocess.run(["open", out_log], check=False)
            subprocess.run(["open", err_log], check=False)
            self.gmail_status_label.configure(text="Opened logs.", text_color="gray")
        except Exception as e:
            self.gmail_status_label.configure(text=f"Could not open logs: {e}", text_color="red")

    def show_email_import_help(self):
        """Show a help dialog with Gmail importer recovery steps."""
        help_path = Path(__file__).resolve().parents[3] / "docs" / "EMAIL_IMPORT_HELP.md"
        try:
            content = help_path.read_text(encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Email Import Help", f"Could not load help file:\n{e}")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Gmail Import Help")
        dialog.geometry("720x520")
        dialog.transient(self)
        dialog.grab_set()

        textbox = ctk.CTkTextbox(dialog, wrap="word")
        textbox.pack(fill="both", expand=True, padx=15, pady=(15, 5))
        textbox.insert("1.0", content)
        textbox.configure(state="disabled")

        ctk.CTkButton(dialog, text="Close", command=dialog.destroy).pack(pady=(0, 15))

    def run_calendar_import_now(self):
        """Run Google Calendar importer immediately (in a background thread)."""
        # Save current UI values first (including calendar lookahead days)
        self.save_email_import_settings()

        def work():
            try:
                from ..calendar_importer import CalendarImportConfig, import_upcoming_calendar_events

                cfg = CalendarImportConfig(
                    calendar_id="primary",
                    days_ahead=max(1, int(getattr(self.settings, "calendar_import_days_ahead", 14))),
                    who_value="Calendar",
                    group_value="CALENDAR",
                    include_all_day=True,
                )
                stats = import_upcoming_calendar_events(
                    db_path=self.db_manager.db.db_path,
                    cfg=cfg,
                    dry_run=False,
                )

                msg = (
                    f"Calendar import complete: seen={stats['events_seen']}, "
                    f"created={stats['created']}, "
                    f"updated_existing={stats.get('updated_existing', 0)}, "
                    f"skipped_existing={stats['skipped_existing']}, "
                    f"skipped_all_day={stats['skipped_all_day']}"
                )
                color = "green" if (stats["created"] > 0 or stats.get("updated_existing", 0) > 0) else "gray"
                self.calendar_status_label.after(
                    0, lambda: self.calendar_status_label.configure(text=msg, text_color=color)
                )
            except Exception as e:
                self.calendar_status_label.after(
                    0,
                    lambda: self.calendar_status_label.configure(
                        text=f"Calendar import failed: {e}",
                        text_color="red",
                    ),
                )

        self.calendar_status_label.configure(text="Running calendar import…", text_color="gray")
        threading.Thread(target=work, daemon=True).start()

    def create_vps_segments_section(self, parent=None):
        """Create VPS Life Segments management section."""
        if parent is None:
            parent = self

        section = ctk.CTkFrame(parent)
        section.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(2, weight=1)

        # Section title
        title_frame = ctk.CTkFrame(section)
        title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        title_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            title_frame,
            text="VPS Life Segments",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=10)

        ctk.CTkLabel(
            title_frame,
            text="Manage your life segments for Visionary Planning System",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(side="left", padx=10)

        # Buttons frame
        buttons_frame = ctk.CTkFrame(section)
        buttons_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        ctk.CTkButton(
            buttons_frame,
            text="+ New Segment",
            command=self.create_new_segment,
            width=150,
            **button_style("primary"),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            buttons_frame,
            text="↻ Refresh",
            command=self.refresh_segments_list,
            width=100
        ).pack(side="left", padx=5)

        # Segments list (scrollable)
        self.segments_scroll_frame = ctk.CTkScrollableFrame(
            section, label_text="")
        self.segments_scroll_frame.grid(
            row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.segments_scroll_frame.grid_columnconfigure(0, weight=1)

        # Load segments
        self.refresh_segments_list()

    def refresh_segments_list(self):
        """Refresh the segments list display."""
        # Clear current widgets
        for widget in self.segments_scroll_frame.winfo_children():
            widget.destroy()

        # Get all segments (including inactive)
        segments = self.app.vps_manager.get_all_segments(active_only=False)

        if not segments:
            label = ctk.CTkLabel(
                self.segments_scroll_frame,
                text="No life segments defined. Click '+ New Segment' to create one.",
                font=ctk.CTkFont(size=12),
                text_color="gray"
            )
            label.grid(row=0, column=0, pady=20)
            return

        # Display each segment
        for idx, segment in enumerate(segments):
            self.create_segment_row(segment, idx)

    def create_segment_row(self, segment: dict, row: int):
        """Create a row displaying a segment with edit/delete buttons."""
        frame = ctk.CTkFrame(self.segments_scroll_frame)
        frame.grid(row=row, column=0, sticky="ew", pady=5, padx=5)
        frame.grid_columnconfigure(2, weight=1)

        # Color indicator
        color_frame = ctk.CTkFrame(
            frame, width=40, height=40, fg_color=segment['color_hex'])
        color_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=5)
        color_frame.grid_propagate(False)

        # Segment name
        name_label = ctk.CTkLabel(
            frame,
            text=f"🎯 {segment['name']}",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        name_label.grid(row=0, column=1, columnspan=2,
                        sticky="w", padx=10, pady=(5, 0))

        # Segment description
        desc_label = ctk.CTkLabel(
            frame,
            text=segment['description'] or "No description",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w"
        )
        desc_label.grid(row=1, column=1, columnspan=2,
                        sticky="w", padx=10, pady=(0, 5))

        # Status badge
        status_text = "✓ Active" if segment['is_active'] else "○ Inactive"
        status_color = "green" if segment['is_active'] else "gray"
        status_label = ctk.CTkLabel(
            frame,
            text=status_text,
            font=ctk.CTkFont(size=10),
            text_color=status_color
        )
        status_label.grid(row=0, column=3, padx=5, pady=5)

        # Edit button
        edit_btn = ctk.CTkButton(
            frame,
            text="✎ Edit",
            command=lambda s=segment: self.edit_segment(s),
            width=80
        )
        edit_btn.grid(row=0, column=4, rowspan=2, padx=5, pady=5)

        # Delete button
        delete_btn = ctk.CTkButton(
            frame,
            text="🗑 Delete",
            command=lambda s=segment: self.delete_segment(s),
            **button_style("danger"),
            width=80
        )
        delete_btn.grid(row=0, column=5, rowspan=2, padx=5, pady=5)

    def create_new_segment(self):
        """Open dialog to create a new segment."""
        from .vps_segment_editor import VPSSegmentEditorDialog
        dialog = VPSSegmentEditorDialog(self, self.app.vps_manager)
        self.wait_window(dialog)
        self.refresh_segments_list()

    def edit_segment(self, segment: dict):
        """Open dialog to edit a segment."""
        from .vps_segment_editor import VPSSegmentEditorDialog
        dialog = VPSSegmentEditorDialog(self, self.app.vps_manager, segment)
        self.wait_window(dialog)
        self.refresh_segments_list()

    def delete_segment(self, segment: dict):
        """Delete a segment after comprehensive check and typed confirmation."""
        from tkinter import messagebox
        import customtkinter as ctk

        # First check: Get comprehensive count of all related records
        success, counts = self.app.vps_manager.delete_segment(segment['id'])

        if not success:
            # Has child records - show detailed breakdown and require typed confirmation
            total = sum(counts.values())

            # Build detailed message
            breakdown = "\n".join(
                [f"  • {label}: {count}" for label, count in counts.items()])

            warning_msg = (
                f"⚠️  CASCADE DELETE WARNING  ⚠️\n\n"
                f"Segment '{segment['name']}' has {total} linked records:\n\n"
                f"{breakdown}\n\n"
                f"If you proceed, ALL {total} records will be PERMANENTLY DELETED.\n\n"
                f"This includes all child records in the hierarchy:\n"
                f"Visions → Plans → Initiatives → Tactics → Actions\n\n"
                f"⚠️  THIS CANNOT BE UNDONE  ⚠️\n\n"
                f"To proceed with deletion, type exactly:\n"
                f"yes proceed"
            )

            # Create custom dialog for typed confirmation
            dialog = ctk.CTkToplevel(self)
            dialog.title("Confirm Cascade Deletion")
            dialog.geometry("600x500")
            dialog.transient(self)
            dialog.grab_set()

            # Warning message
            warning_frame = ctk.CTkFrame(dialog, fg_color="#8B0000")
            warning_frame.pack(fill="x", padx=20, pady=(20, 10))

            ctk.CTkLabel(
                warning_frame,
                text=warning_msg,
                justify="left",
                text_color="white",
                font=("Arial", 12)
            ).pack(padx=20, pady=20)

            # Typed confirmation entry
            entry_frame = ctk.CTkFrame(dialog)
            entry_frame.pack(fill="x", padx=20, pady=10)

            ctk.CTkLabel(
                entry_frame,
                text="Type 'yes proceed' to confirm:",
                font=("Arial", 12, "bold")
            ).pack(anchor="w", padx=10, pady=(10, 5))

            confirmation_var = ctk.StringVar()
            entry = ctk.CTkEntry(
                entry_frame,
                textvariable=confirmation_var,
                width=400,
                height=35,
                font=("Arial", 12)
            )
            entry.pack(padx=10, pady=(0, 10))
            entry.focus()

            # Status label
            status_label = ctk.CTkLabel(
                dialog,
                text="",
                text_color="red",
                font=("Arial", 11)
            )
            status_label.pack(pady=5)

            # Button frame
            btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_frame.pack(pady=20)

            def proceed_deletion():
                typed_text = confirmation_var.get().strip()
                if typed_text == "yes proceed":
                    dialog.destroy()
                    # Actually delete by clearing all records first
                    try:
                        # Since we can't delete with children, we need to tell user
                        # to remove records manually
                        messagebox.showwarning(
                            "Manual Deletion Required",
                            f"To delete segment '{segment['name']}':\n\n"
                            f"1. Go to VPS Planning screen\n"
                            f"2. Delete all {total} records in this segment\n"
                            f"   (Start with Week Actions, work up to TL Visions)\n"
                            f"3. Return here to delete the empty segment\n\n"
                            f"This manual process prevents accidental data loss."
                        )
                    except Exception as e:
                        messagebox.showerror(
                            "Error", f"Deletion failed: {str(e)}")
                else:
                    status_label.configure(
                        text="❌ Incorrect confirmation text. Type exactly: yes proceed"
                    )

            def cancel_deletion():
                dialog.destroy()

            # Buttons
            ctk.CTkButton(
                btn_frame,
                text="Cancel",
                command=cancel_deletion,
                width=120,
                **button_style("secondary"),
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                btn_frame,
                text="Proceed with Deletion",
                command=proceed_deletion,
                width=180,
                **button_style("danger"),
            ).pack(side="left", padx=5)

            # Bind Enter key
            entry.bind('<Return>', lambda e: proceed_deletion())
            entry.bind('<Escape>', lambda e: cancel_deletion())

        else:
            # No child records - safe to delete with simple confirmation
            response = messagebox.askyesno(
                "Confirm Deletion",
                f"Delete segment '{segment['name']}'?\n\n"
                f"This segment has no linked records.",
                icon='warning'
            )

            if response:
                messagebox.showinfo(
                    "Success",
                    f"Segment '{segment['name']}' has been deleted."
                )
                self.refresh_segments_list()
