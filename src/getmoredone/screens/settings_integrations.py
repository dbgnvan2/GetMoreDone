"""Email, calendar, and future-date support for the Settings screen."""

from __future__ import annotations

import customtkinter as ctk
import subprocess
import threading
from pathlib import Path
from tkinter import messagebox

from ..theme import button_style, status_text_color


class SettingsIntegrationsMixin:
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
        self._info_label(section, text=info, justify="left", wraplength=700).grid(
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

        self.future_date_status_label = self._status_label(section, text="", level="success")
        self.future_date_status_label.grid(row=5, column=1, sticky="w", padx=10, pady=10)

        info_text = (
            "Near/Long term are offsets from today.\n"
            "Next Month/Quarter offsets are applied to the 1st of next month/quarter."
        )
        self._info_label(section, text=info_text, justify="left", wraplength=600).grid(
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

            self._set_status(self.gmail_status_label, "Saved (launchd updated).", "success")
        except Exception as e:
            self._set_status(self.gmail_status_label, f"Save failed: {e}", "error")

    def run_email_import_now(self):
        """Run the Gmail importer immediately (in a background thread)."""
        # Save current UI values first
        self.save_email_import_settings()

        if not bool(self.gmail_enabled_var.get()):
            self._set_status(self.gmail_status_label, "Importer is disabled (enable it first).", "muted")
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
                self.gmail_status_label.after(
                    0,
                    lambda: self._set_status(
                        self.gmail_status_label,
                        f"Imported {n} email(s) from {cfg.trigger_label_name}.",
                        "success" if n else "muted",
                    ),
                )
            except Exception as e:
                self.gmail_status_label.after(
                    0,
                    lambda: self._set_status(self.gmail_status_label, f"Import failed: {e}", "error"),
                )

        self._set_status(self.gmail_status_label, "Running import…", "muted")
        threading.Thread(target=work, daemon=True).start()

    def open_email_import_logs(self):
        """Open the launchd log files for the importer (best-effort)."""
        # These are the log paths used by our launchd plists.
        out_log = "/tmp/getmoredone-gmailimport-com.getmoredone.gmailimport.prod.out.log"
        err_log = "/tmp/getmoredone-gmailimport-com.getmoredone.gmailimport.prod.err.log"
        try:
            subprocess.run(["open", out_log], check=False)
            subprocess.run(["open", err_log], check=False)
            self._set_status(self.gmail_status_label, "Opened logs.", "muted")
        except Exception as e:
            self._set_status(self.gmail_status_label, f"Could not open logs: {e}", "error")

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
                level = "success" if (stats["created"] > 0 or stats.get("updated_existing", 0) > 0) else "muted"
                self.calendar_status_label.after(
                    0, lambda: self._set_status(self.calendar_status_label, msg, level)
                )
            except Exception as e:
                self.calendar_status_label.after(
                    0,
                    lambda: self._set_status(self.calendar_status_label, f"Calendar import failed: {e}", "error"),
                )

        self._set_status(self.calendar_status_label, "Running calendar import…", "muted")
        threading.Thread(target=work, daemon=True).start()
