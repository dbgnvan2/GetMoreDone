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
        self.create_date_increment_section()
        self.create_organizational_factors_section()

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

    def create_date_increment_section(self):
        """Create date increment settings section."""
        section = ctk.CTkFrame(self)
        section.grid(row=4, column=0, sticky="ew", padx=10, pady=10)
        section.grid_columnconfigure(1, weight=1)

        # Section title
        ctk.CTkLabel(
            section,
            text="Date Increment Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 15))

        # Include Saturday checkbox
        self.include_saturday_var = ctk.BooleanVar(value=self.settings.include_saturday)
        saturday_checkbox = ctk.CTkCheckBox(
            section,
            text="Include Saturday in date calculations (push, +/- buttons)",
            variable=self.include_saturday_var
        )
        saturday_checkbox.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        # Include Sunday checkbox
        self.include_sunday_var = ctk.BooleanVar(value=self.settings.include_sunday)
        sunday_checkbox = ctk.CTkCheckBox(
            section,
            text="Include Sunday in date calculations (push, +/- buttons)",
            variable=self.include_sunday_var
        )
        sunday_checkbox.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        # Save button
        btn_save = ctk.CTkButton(
            section,
            text="Save Settings",
            command=self.save_date_increment_settings,
            fg_color="darkgreen",
            hover_color="green",
            width=150
        )
        btn_save.grid(row=3, column=0, sticky="w", padx=10, pady=10)

        # Status label
        self.date_increment_status_label = ctk.CTkLabel(section, text="", text_color="green")
        self.date_increment_status_label.grid(row=3, column=1, sticky="w", padx=10, pady=10)

        # Info
        info_text = ("These settings control how dates are incremented when using:\n"
                    "• Push button (move item to next day)\n"
                    "• +/- buttons in date fields\n"
                    "• Continue button (duplicate action for next day)\n\n"
                    "Note: Manual date entry is not affected by these settings.")
        ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=10, pady=5
        )

    def save_date_increment_settings(self):
        """Save date increment settings."""
        self.settings.include_saturday = self.include_saturday_var.get()
        self.settings.include_sunday = self.include_sunday_var.get()

        self.settings.save()

        self.date_increment_status_label.configure(
            text="✓ Settings saved",
            text_color="green"
        )

    def create_organizational_factors_section(self):
        """Create organizational factors management section."""
        section = ctk.CTkFrame(self)
        section.grid(row=5, column=0, sticky="ew", padx=10, pady=10)
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
                command=lambda v=value, ft=factor_type: self.edit_factor_value(v, ft)
            )
            btn_edit.grid(row=idx, column=1, padx=5, pady=5)

            # Delete button
            btn_delete = ctk.CTkButton(
                scroll,
                text="Delete",
                width=80,
                fg_color="darkred",
                hover_color="red",
                command=lambda v=value, ft=factor_type: self.delete_factor_value(v, ft)
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
                status_label.configure(text="Please enter a value", text_color="red")
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
                status_label.configure(text=f"Error: {str(e)}", text_color="red")

        ctk.CTkButton(btn_frame, text="Save", command=save).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)

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
            other_values = [v for v in self.db_manager.get_distinct_groups() if v != value]
        else:
            other_values = [v for v in self.db_manager.get_distinct_categories() if v != value]

        replacement_var = ctk.StringVar(value=other_values[0] if other_values else "")
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
                        status_label.configure(text="Please select a replacement value", text_color="red")
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
                status_label.configure(text=f"Error: {str(e)}", text_color="red")

        ctk.CTkButton(btn_frame, text="Delete", fg_color="darkred", hover_color="red", command=delete).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)

    def refresh_organizational_factors(self):
        """Refresh the organizational factors section."""
        # Destroy and recreate the section
        # Find the section frame
        for child in self.winfo_children():
            if isinstance(child, ctk.CTkFrame):
                # Check if it's the organizational factors section (row 5)
                info = child.grid_info()
                if info.get('row') == 5:
                    child.destroy()
                    break

        # Recreate the section
        self.create_organizational_factors_section()

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
