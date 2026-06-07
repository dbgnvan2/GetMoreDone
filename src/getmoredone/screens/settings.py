"""
Settings screen - application settings and database management.
"""

import customtkinter as ctk
import shutil
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING
from tkinter import filedialog, colorchooser, messagebox

from ..app_settings import AppSettings
from ..obsidian_utils import validate_obsidian_setup
from ..theme import APPEARANCE_MODES, THEME_NAMES, button_style, combo_box_style, status_text_color
from .settings_integrations import SettingsIntegrationsMixin
from .settings_vsp_segments import SettingsVSPSegmentsMixin
from ..utils.icon_loader import load_volume_icon

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class SettingsScreen(SettingsIntegrationsMixin, SettingsVSPSegmentsMixin, ctk.CTkFrame):
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

        # VSP segment management moved into VSP Plan -> Vision Elements.

    def _status_label(self, parent, text: str = "", level: str = "success", **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=status_text_color(level), **kwargs)

    def _info_label(self, parent, text: str, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=status_text_color("muted"), **kwargs)

    def _set_status(self, label: ctk.CTkLabel, text: str, level: str = "success"):
        label.configure(text=text, text_color=status_text_color(level))

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

        ctk.CTkLabel(section, text="Business year starts (MM-DD):").grid(
            row=3, column=0, sticky="w", padx=10, pady=5
        )
        self.business_year_start_var = ctk.StringVar(
            value=getattr(self.settings, "business_year_start_mmdd", "01-01")
        )
        self.business_year_start_entry = ctk.CTkEntry(
            section,
            textvariable=self.business_year_start_var,
            width=120,
        )
        self.business_year_start_entry.grid(row=3, column=1, sticky="w", padx=10, pady=5)

        self.db_save_btn = ctk.CTkButton(
            section,
            text="Save Database Settings",
            command=self.save_database_settings,
            width=180,
            **button_style("secondary"),
        )
        self.db_save_btn.grid(row=4, column=0, sticky="w", padx=10, pady=10)

        # Status label
        self.db_status_label = self._status_label(section, text="", level="success")
        self.db_status_label.grid(
            row=4, column=1, sticky="w", padx=10, pady=10)

        # Info
        info_text = (
            "Backups are saved in the data/ directory with timestamps.\n"
            "Database file: getmoredone.db\n"
            "Business year start uses recurring MM-DD format.\n\n"
            "Demo Data: adds a small set of sample items to the CURRENT database (no deletion)."
        )
        self._info_label(section, text=info_text, justify="left").grid(
            row=5, column=0, columnspan=2, sticky="w", padx=10, pady=5
        )

    def save_database_settings(self):
        """Save database-related preferences."""
        self.settings.business_year_start_mmdd = self.business_year_start_var.get().strip()
        self.settings.save()
        self.business_year_start_var.set(self.settings.business_year_start_mmdd)
        self._set_status(self.db_status_label, "✓ Database settings saved", "success")

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

        # M7.A.4 — Project Notes Folder (separate folder for Project Notes;
        # blank falls back to Notes Subfolder above).
        # Spec: docs/implementation_plan_2026-06-06_project_notes.md#M7.A.4
        ctk.CTkLabel(section, text="Project Notes Folder:").grid(
            row=3, column=0, sticky="w", padx=10, pady=5)
        self.project_notes_folder_var = ctk.StringVar(
            value=self.settings.project_notes_subfolder)
        project_notes_entry = ctk.CTkEntry(
            section, textvariable=self.project_notes_folder_var, width=200,
            placeholder_text="GetMoreDone/Projects")
        project_notes_entry.grid(row=3, column=1, sticky="w", padx=10, pady=5)

        # Save and test buttons
        btn_frame = ctk.CTkFrame(section, fg_color="transparent")
        btn_frame.grid(row=4, column=0, columnspan=2,
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
        self._info_label(section, text=info_text, justify="left", wraplength=600).grid(
            row=4, column=0, columnspan=3, sticky="w", padx=10, pady=5
        )

    def browse_vault_path(self):
        """Open folder browser for vault path."""
        path = filedialog.askdirectory(title="Select Obsidian Vault Folder")
        if path:
            self.vault_path_var.set(path)

    def save_obsidian_settings(self):
        """Save Obsidian settings.

        Spec: docs/implementation_plan_2026-06-06_project_notes.md#M7.A.4
        Tests: tests/test_project_notes.py::TestM7Settings::test_settings_roundtrip_project_subfolder
        """
        self.settings.obsidian_vault_path = self.vault_path_var.get().strip() or None
        self.settings.obsidian_notes_subfolder = self.subfolder_var.get().strip() or "GetMoreDone"
        # M7.A.4 — Project Notes Folder; blank is allowed and falls back to
        # obsidian_notes_subfolder at use-time (see get_project_notes_subfolder_or_default).
        self.settings.project_notes_subfolder = self.project_notes_folder_var.get().strip()

        self.settings.save()

        self._set_status(self.obsidian_status_label, "✓ Settings saved", "success")

    def test_obsidian_connection(self):
        """Test Obsidian vault connection."""
        vault_path = self.vault_path_var.get().strip()
        subfolder = self.subfolder_var.get().strip() or "GetMoreDone"

        if not vault_path:
            self._set_status(self.obsidian_status_label, "❌ Please enter a vault path", "error")
            return

        is_valid, message = validate_obsidian_setup(vault_path, subfolder)

        if is_valid:
            self._set_status(self.obsidian_status_label, f"✓ {message}", "success")
        else:
            self._set_status(self.obsidian_status_label, f"❌ {message}", "error")

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
            **combo_box_style(),
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
            **combo_box_style(),
            command=self.on_theme_preference_changed
        )
        self.theme_name_combo.grid(row=2, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(section, text="Row Text Size:").grid(
            row=3, column=0, sticky="w", padx=10, pady=5)
        current_font_size = int(getattr(self.settings, "list_row_font_size", 14))
        self.list_row_font_size_var = ctk.StringVar(value=str(current_font_size))
        self.list_row_font_size_combo = ctk.CTkComboBox(
            section,
            values=[str(size) for size in range(10, 25)],
            variable=self.list_row_font_size_var,
            width=180,
            **combo_box_style(),
            command=self.on_theme_preference_changed
        )
        self.list_row_font_size_combo.grid(row=3, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(section, text="Completion Badge:").grid(
            row=4, column=0, sticky="w", padx=10, pady=5)
        self.completion_badge_path_var = ctk.StringVar(
            value=getattr(self.settings, "completion_badge_path", "") or ""
        )
        self.completion_badge_path_entry = ctk.CTkEntry(
            section,
            textvariable=self.completion_badge_path_var,
            width=260,
        )
        self.completion_badge_path_entry.grid(row=4, column=1, sticky="w", padx=10, pady=5)
        self.completion_badge_browse_btn = ctk.CTkButton(
            section,
            text="Browse",
            width=90,
            command=self.browse_completion_badge,
            **button_style("secondary"),
        )
        self.completion_badge_browse_btn.grid(row=4, column=2, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(section, text="Confetti Every N Completions:").grid(
            row=5, column=0, sticky="w", padx=10, pady=5)
        self.completion_confetti_threshold_var = ctk.StringVar(
            value=str(getattr(self.settings, "completion_confetti_threshold", 0))
        )
        self.completion_confetti_threshold_entry = ctk.CTkEntry(
            section,
            textvariable=self.completion_confetti_threshold_var,
            width=180,
        )
        self.completion_confetti_threshold_entry.grid(row=5, column=1, sticky="w", padx=10, pady=5)

        self.theme_apply_btn = ctk.CTkButton(
            section,
            text="Apply / Save",
            command=self.apply_theme_preferences,
            width=120
        )
        self.theme_apply_btn.grid(row=1, column=3, rowspan=5, sticky="w", padx=10, pady=5)

        self.appearance_status_label = self._status_label(section, text="", level="success")
        self.appearance_status_label.grid(row=6, column=0, columnspan=4, sticky="w", padx=10, pady=(8, 4))

        info_text = (
            "Appearance mode controls system/dark/light rendering.\n"
            "Color theme switches between bundled CustomTkinter palettes.\n"
            "Row Text Size controls font size in item listing rows.\n"
            "Completion Badge can be an uploaded image shown on Today completed items.\n"
            "Set Confetti Every N Completions to 0 to disable confetti."
        )
        self._info_label(section, text=info_text, justify="left", wraplength=600).grid(
            row=7, column=0, columnspan=4, sticky="w", padx=10, pady=5
        )

    def on_theme_preference_changed(self, _choice=None):
        """Apply and persist theme choices immediately."""
        self.apply_theme_preferences()

    def apply_theme_preferences(self):
        """Save selected appearance and theme, then apply app-wide."""
        self.settings.appearance_mode = self.appearance_mode_var.get().strip().lower()
        self.settings.theme_name = self.theme_name_var.get().strip().lower()
        try:
            self.settings.list_row_font_size = int(self.list_row_font_size_var.get().strip())
        except ValueError:
            self.settings.list_row_font_size = 14
        self.settings.completion_badge_path = self.completion_badge_path_var.get().strip() or None
        self.settings.completion_confetti_threshold = self._parse_positive_or_zero_int(
            self.completion_confetti_threshold_var.get(),
            default=getattr(self.settings, "completion_confetti_threshold", 0),
        )
        self.settings.save()

        self.app.settings = self.settings
        self.app.apply_theme_preferences()
        self._set_status(self.appearance_status_label, "✓ Saved appearance and completion badge settings", "success")

    def browse_completion_badge(self):
        """Pick an image file for the completion badge."""
        path = filedialog.askopenfilename(
            title="Select Completion Badge",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif *.webp"), ("All Files", "*.*")],
        )
        if path:
            self.completion_badge_path_var.set(path)

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

        # First day of week selector (used by VSP week generation)
        ctk.CTkLabel(section, text="First day of week (VSP):").grid(
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
            width=180,
            **combo_box_style(),
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
        self.date_increment_status_label = self._status_label(section, text="", level="success")
        self.date_increment_status_label.grid(
            row=7, column=1, sticky="w", padx=10, pady=10)

        # Info
        info_text = ("These settings control how dates are incremented when using:\n"
                     "• Push button (move item to next day)\n"
                     "• +/- buttons in date fields\n"
                     "• Continue button (duplicate action for next day)\n\n"
                     "Note: Manual date entry is not affected by these settings.")
        self._info_label(section, text=info_text, justify="left", wraplength=600).grid(
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

        self._set_status(self.date_increment_status_label, "✓ Settings saved", "success")

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

    def _parse_positive_or_zero_int(self, value: str, default: int) -> int:
        try:
            parsed = int(str(value).strip())
            return parsed if parsed >= 0 else default
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

        self._set_status(self.future_date_status_label, "✓ Future date options saved", "success")

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
        self.timer_audio_status_label = self._status_label(section, text="", level="success")
        self.timer_audio_status_label.grid(
            row=3, column=1, sticky="w", padx=10, pady=10)

        # Info
        info_text = ("Select a folder containing music files (MP3, WAV, OGG, FLAC, M4A).\n"
                     "When you start a timer, a random music file from this folder will play.\n"
                     "Adjust volume to control music playback loudness (70% recommended).")
        self._info_label(section, text=info_text, justify="left", wraplength=600).grid(
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

        self._set_status(
            self.timer_audio_status_label,
            f"✓ Settings saved (Volume: {int(self.settings.music_volume * 100)}%)",
            "success",
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
        self._info_label(section, text=info_text, justify="left", wraplength=600).grid(
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
                self._set_status(status_label, "Please enter a value", "error")
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
                        text_color=status_text_color("success")
                    )
                else:
                    status_label.configure(
                        text="Value not replaced (option unchecked)",
                        text_color=status_text_color("warning")
                    )

                # Close dialog after a brief delay
                dialog.after(1000, dialog.destroy)
                # Refresh the organizational factors section
                self.refresh_organizational_factors()

            except Exception as e:
                self._set_status(status_label, f"Error: {str(e)}", "error")

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
            width=200,
            **combo_box_style(),
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
                        text_color=status_text_color("success")
                    )
                else:
                    # Replace with another value
                    replacement = replacement_var.get().strip()
                    if not replacement:
                        self._set_status(status_label, "Please select a replacement value", "error")
                        return

                    self.db_manager.delete_organizational_factor(
                        factor_type, value, replacement
                    )
                    status_label.configure(
                        text=f"✓ Deleted (replaced with '{replacement}')",
                        text_color=status_text_color("success")
                    )

                # Close dialog after a brief delay
                dialog.after(1000, dialog.destroy)
                # Refresh the organizational factors section
                self.refresh_organizational_factors()

            except Exception as e:
                self._set_status(status_label, f"Error: {str(e)}", "error")

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
                self._set_status(self.db_status_label, "Database file not found", "error")
                return

            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = db_path.parent / f"getmoredone_backup_{timestamp}.db"

            # Copy database file
            shutil.copy2(db_path, backup_path)

            self._set_status(self.db_status_label, f"Backup created: {backup_path.name}", "success")

        except Exception as e:
            self._set_status(self.db_status_label, f"Backup failed: {str(e)}", "error")

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

            self._set_status(self.db_status_label, f"Demo data added ({created} items)", "success")

        except Exception as e:
            self._set_status(self.db_status_label, f"Demo data failed: {str(e)}", "error")
