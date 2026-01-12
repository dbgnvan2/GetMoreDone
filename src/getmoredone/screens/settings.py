"""
Settings screen - application settings and database management.
"""

import customtkinter as ctk
import shutil
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class SettingsScreen(ctk.CTkFrame):
    """Screen for application settings."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app

        self.grid_columnconfigure(0, weight=1)

        # Create header
        self.create_header()

        # Create settings sections
        self.create_database_section()
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

    def create_appearance_section(self):
        """Create appearance settings section."""
        section = ctk.CTkFrame(self)
        section.grid(row=2, column=0, sticky="ew", padx=10, pady=10)

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
