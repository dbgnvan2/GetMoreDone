"""
Settings screen - application settings and database management.
"""

import customtkinter as ctk
import shutil
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING
from tkinter import filedialog

from ..app_settings import AppSettings
from ..obsidian_utils import validate_obsidian_setup

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

        # Create header
        self.create_header()

        # Create settings sections
        self.create_database_section()
        self.create_obsidian_section()
        self.create_appearance_section()

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

    def create_database_section(self):
        """Create database management section."""
        section = ctk.CTkFrame(self)
        section.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        section.grid_columnconfigure(1, weight=1)

        # Section title
        ctk.CTkLabel(
            section,
            text="Database Management",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 15))

        # Database path
        ctk.CTkLabel(section, text="Database Path:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        db_path_label = ctk.CTkLabel(section, text=self.db_manager.db.db_path, anchor="w")
        db_path_label.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        # Backup button
        btn_backup = ctk.CTkButton(
            section,
            text="Backup Database",
            command=self.backup_database
        )
        btn_backup.grid(row=2, column=0, sticky="w", padx=10, pady=10)

        # Status label
        self.db_status_label = ctk.CTkLabel(section, text="", text_color="green")
        self.db_status_label.grid(row=2, column=1, sticky="w", padx=10, pady=10)

        # Info
        info_text = ("Backups are saved in the data/ directory with timestamps.\n"
                    "Database file: getmoredone.db")
        ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=10, pady=5
        )

    def create_obsidian_section(self):
        """Create Obsidian integration section."""
        section = ctk.CTkFrame(self)
        section.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        section.grid_columnconfigure(1, weight=1)

        # Section title
        ctk.CTkLabel(
            section,
            text="Obsidian Integration",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 15))

        # Vault path
        ctk.CTkLabel(section, text="Vault Path:").grid(row=1, column=0, sticky="w", padx=10, pady=5)

        self.vault_path_var = ctk.StringVar(value=self.settings.obsidian_vault_path or "")
        vault_path_entry = ctk.CTkEntry(section, textvariable=self.vault_path_var, width=300)
        vault_path_entry.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        btn_browse = ctk.CTkButton(
            section,
            text="Browse",
            width=80,
            command=self.browse_vault_path
        )
        btn_browse.grid(row=1, column=2, padx=5, pady=5)

        # Notes subfolder
        ctk.CTkLabel(section, text="Notes Subfolder:").grid(row=2, column=0, sticky="w", padx=10, pady=5)

        self.subfolder_var = ctk.StringVar(value=self.settings.obsidian_notes_subfolder)
        subfolder_entry = ctk.CTkEntry(section, textvariable=self.subfolder_var, width=200)
        subfolder_entry.grid(row=2, column=1, sticky="w", padx=10, pady=5)

        # Save and test buttons
        btn_frame = ctk.CTkFrame(section, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=10)

        btn_save = ctk.CTkButton(
            btn_frame,
            text="Save Settings",
            command=self.save_obsidian_settings,
            fg_color="darkgreen",
            hover_color="green"
        )
        btn_save.pack(side="left", padx=5)

        btn_test = ctk.CTkButton(
            btn_frame,
            text="Test Connection",
            command=self.test_obsidian_connection
        )
        btn_test.pack(side="left", padx=5)

        # Status label
        self.obsidian_status_label = ctk.CTkLabel(section, text="", wraplength=500)
        self.obsidian_status_label.grid(row=3, column=2, sticky="w", padx=10, pady=10)

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

    def create_appearance_section(self):
        """Create appearance settings section."""
        section = ctk.CTkFrame(self)
        section.grid(row=3, column=0, sticky="ew", padx=10, pady=10)

        # Section title
        ctk.CTkLabel(
            section,
            text="Appearance",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 15))

        # Theme
        ctk.CTkLabel(section, text="Theme:").grid(row=1, column=0, sticky="w", padx=10, pady=5)

        theme_var = ctk.StringVar(value="dark")
        theme_combo = ctk.CTkComboBox(
            section,
            values=["dark", "light", "system"],
            variable=theme_var,
            width=150,
            command=lambda choice: ctk.set_appearance_mode(choice)
        )
        theme_combo.grid(row=1, column=1, sticky="w", padx=10, pady=5)

    def backup_database(self):
        """Backup the database file."""
        try:
            db_path = Path(self.db_manager.db.db_path)
            if not db_path.exists():
                self.db_status_label.configure(text="Database file not found", text_color="red")
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
