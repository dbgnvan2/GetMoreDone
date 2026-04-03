"""
VSP entity editor dialogs for creating and editing strategic planning items.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from tkinter import messagebox

from ..color_contrast import pick_text_color
from ..theme import status_text_color
from ..widgets.date_picker import DatePickerButton

if TYPE_CHECKING:
    from ..vps_manager import VPSManager


def _show_dialog_after_layout(dialog: ctk.CTkToplevel, parent) -> None:
    """Position and reveal a dialog after its widgets have been laid out."""
    dialog.transient(parent)
    dialog.grab_set()
    dialog.update_idletasks()

    width = dialog.winfo_reqwidth() or dialog.winfo_width() or 600
    height = dialog.winfo_reqheight() or dialog.winfo_height() or 500

    parent.update_idletasks()
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()

    x = max(0, parent_x + (parent_width - width) // 2)
    y = max(0, parent_y + (parent_height - height) // 2)
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    dialog.deiconify()
    dialog.after_idle(lambda: _finish_dialog_show(dialog))


def _finish_dialog_show(dialog: ctk.CTkToplevel) -> None:
    """Finish showing a dialog after it becomes visible."""
    dialog.lift()
    dialog.focus_force()
    dialog.update_idletasks()


class TLVisionEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing TL Visions (Top Level Visions)."""

    def __init__(self, parent, vps_manager: 'VPSManager', segment_id: str, vision_id: Optional[str] = None):
        super().__init__(parent)

        self.vps_manager = vps_manager
        self.segment_id = segment_id
        self.vision_id = vision_id
        self.vision = None

        # Load vision if editing
        if vision_id:
            self.vision = vps_manager.get_tl_vision(vision_id)
            self.title("Edit TL Vision")
        else:
            self.title("New TL Vision")

        self.geometry("600x500")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create form
        self.create_form()

        # Load data if editing
        if self.vision:
            self.load_vision_data()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form layout."""
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_columnconfigure(1, weight=1)

        row = 0

        # Segment display (read-only)
        segment = self.vps_manager.get_segment(self.segment_id)
        if segment:
            ctk.CTkLabel(main_frame, text="Life Segment:", font=ctk.CTkFont(weight="bold")).grid(
                row=row, column=0, sticky="w", padx=10, pady=5
            )
            ctk.CTkLabel(
                main_frame,
                text=segment['name'],
                fg_color=segment['color_hex'],
                text_color=pick_text_color(segment['color_hex']),
                corner_radius=5
            ).grid(row=row, column=1, sticky="w", padx=10, pady=5)
            row += 1

        # Start Year
        ctk.CTkLabel(main_frame, text="Start Year:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.start_year_entry = ctk.CTkEntry(
            main_frame, placeholder_text="2025")
        self.start_year_entry.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # End Year
        ctk.CTkLabel(main_frame, text="End Year:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.end_year_entry = ctk.CTkEntry(main_frame, placeholder_text="2030")
        self.end_year_entry.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Title
        ctk.CTkLabel(main_frame, text="Title:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.title_entry = ctk.CTkEntry(
            main_frame, placeholder_text="My 5-Year Vision")
        self.title_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Vision Statement
        ctk.CTkLabel(main_frame, text="Vision Statement:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.vision_statement_text = ctk.CTkTextbox(main_frame, height=150)
        self.vision_statement_text.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Success Metrics
        ctk.CTkLabel(main_frame, text="Success Metrics:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        ctk.CTkLabel(main_frame, text="(one per line)", font=ctk.CTkFont(size=10), text_color=status_text_color("muted")).grid(
            row=row, column=1, sticky="w", padx=10, pady=(0, 2)
        )
        row += 1
        self.metrics_text = ctk.CTkTextbox(main_frame, height=100)
        self.metrics_text.grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        row += 1

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2,
                          sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        btn_save = ctk.CTkButton(
            button_frame, text="Save", command=self.save_vision)
        btn_save.grid(row=0, column=0, padx=5, pady=5)

        btn_cancel = ctk.CTkButton(
            button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=1, padx=5, pady=5)

    def load_vision_data(self):
        """Load existing vision data into form."""
        if not self.vision:
            return

        self.start_year_entry.insert(0, str(self.vision['start_year']))
        self.end_year_entry.insert(0, str(self.vision['end_year']))
        if self.vision['title']:
            self.title_entry.insert(0, self.vision['title'])
        if self.vision['vision_statement']:
            self.vision_statement_text.insert(
                "1.0", self.vision['vision_statement'])
        if self.vision['success_metrics']:
            # Parse JSON array and display one per line
            import json
            try:
                metrics = json.loads(self.vision['success_metrics'])
                self.metrics_text.insert("1.0", "\n".join(metrics))
            except:
                pass

    def save_vision(self):
        """Validate and save the vision."""
        # Get values with defaults
        current_year = datetime.now().year
        start_year_str = self.start_year_entry.get().strip()
        end_year_str = self.end_year_entry.get().strip()

        # Provide defaults if empty
        if not start_year_str:
            start_year = current_year
        else:
            try:
                start_year = int(start_year_str)
            except ValueError:
                messagebox.showerror(
                    "Validation Error",
                    "Start year must be a valid integer"
                )
                return

        if not end_year_str:
            end_year = start_year + 10  # Default 10-year vision
        else:
            try:
                end_year = int(end_year_str)
            except ValueError:
                messagebox.showerror(
                    "Validation Error",
                    "End year must be a valid integer"
                )
                return

        if end_year <= start_year:
            messagebox.showerror(
                "Validation Error",
                "End year must be greater than start year"
            )
            return

        title = self.title_entry.get().strip()
        vision_statement = self.vision_statement_text.get(
            "1.0", "end-1c").strip()

        # Parse metrics (one per line)
        import json
        metrics_text = self.metrics_text.get("1.0", "end-1c").strip()
        metrics = [line.strip()
                   for line in metrics_text.split("\n") if line.strip()]
        metrics_json = json.dumps(metrics)

        # Save or update
        try:
            if self.vision_id:
                # Update existing
                self.vps_manager.update_tl_vision(
                    self.vision_id,
                    start_year=start_year,
                    end_year=end_year,
                    title=title,
                    vision_statement=vision_statement,
                    success_metrics=metrics_json
                )
            else:
                # Create new
                self.vps_manager.create_tl_vision(
                    segment_description_id=self.segment_id,
                    start_year=start_year,
                    end_year=end_year,
                    title=title,
                    vision_statement=vision_statement,
                    success_metrics=metrics_json
                )

            # Close dialog
            self.destroy()

        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Failed to save vision: {str(e)}"
            )


class QuarterInitiativeEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing Quarter Initiatives."""

    def __init__(self, parent, vps_manager: 'VPSManager', annual_initiative_id: str,
                 segment_id: str, initiative_id: Optional[str] = None):
        super().__init__(parent)

        self.vps_manager = vps_manager
        self.annual_initiative_id = annual_initiative_id
        self.segment_id = segment_id
        self.initiative_id = initiative_id
        self.initiative = None

        # Load initiative if editing
        if initiative_id:
            self.initiative = vps_manager.get_quarter_initiative(initiative_id)
            self.title("Edit Quarter Initiative")
        else:
            self.title("New Quarter Initiative")

        self.geometry("600x500")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create form
        self.create_form()

        # Load data if editing
        if self.initiative:
            self.load_initiative_data()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form layout."""
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_columnconfigure(1, weight=1)

        row = 0

        # Qtr Number
        ctk.CTkLabel(main_frame, text="Qtr Number:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.quarter_var = ctk.StringVar(value="1")
        self.quarter_combo = ctk.CTkComboBox(
            main_frame,
            values=["1", "2", "3", "4"],
            variable=self.quarter_var,
            command=lambda _val: self._refresh_auto_title()
        )
        self.quarter_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Year
        ctk.CTkLabel(main_frame, text="Year:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        current_year = datetime.now().year
        self.year_entry = ctk.CTkEntry(
            main_frame, placeholder_text=str(current_year))
        self.year_entry.insert(0, str(current_year))
        self.year_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Title
        ctk.CTkLabel(main_frame, text="Title:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.title_entry = ctk.CTkEntry(
            main_frame, placeholder_text="Auto-generated from Annual Initiative")
        self.title_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        self.title_entry.configure(state="readonly")
        row += 1

        # Outcome Statement
        ctk.CTkLabel(main_frame, text="Outcome Statement:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.outcome_text = ctk.CTkTextbox(main_frame, height=150)
        self.outcome_text.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Status
        ctk.CTkLabel(main_frame, text="Status:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.status_var = ctk.StringVar(value="not_started")
        self.status_combo = ctk.CTkComboBox(
            main_frame,
            values=["not_started", "in_progress", "at_risk",
                    "completed", "on_hold", "cancelled"],
            variable=self.status_var
        )
        self.status_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2,
                          sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)

        btn_save = ctk.CTkButton(
            button_frame, text="Save", command=self.save_initiative)
        btn_save.grid(row=0, column=0, padx=5, pady=5)

        btn_cancel = ctk.CTkButton(
            button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=1, padx=5, pady=5)

        # Pre-fill defaults for new records
        if not self.initiative_id:
            next_q = self.vps_manager.get_next_quarter_for_annual_initiative(
                self.annual_initiative_id
            )
            self.quarter_var.set(str(next_q["quarter"]))
            self.year_entry.delete(0, "end")
            self.year_entry.insert(0, str(next_q["year"]))
            self._refresh_auto_title()

    def load_initiative_data(self):
        """Load existing initiative data into form."""
        if not self.initiative:
            return

        self.quarter_var.set(str(self.initiative['quarter']))
        self.year_entry.delete(0, "end")
        self.year_entry.insert(0, str(self.initiative['year']))
        if self.initiative['title']:
            self.title_entry.insert(0, self.initiative['title'])
        if self.initiative['outcome_statement']:
            self.outcome_text.insert(
                "1.0", self.initiative['outcome_statement'])
        if self.initiative['status']:
            self.status_var.set(self.initiative['status'])

    def _refresh_auto_title(self):
        """Auto-generate title for new quarter initiatives."""
        if self.initiative_id:
            return

        annual_initiative = self.vps_manager.get_annual_initiative(
            self.annual_initiative_id)
        prefix = "Annual Initiative"
        if annual_initiative and annual_initiative.get("title"):
            prefix = annual_initiative["title"].strip() or prefix
        quarter = self.quarter_var.get().strip() or "1"
        auto_title = f"{prefix} Q{quarter}"

        self.title_entry.configure(state="normal")
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, auto_title)
        self.title_entry.configure(state="readonly")

    def save_initiative(self):
        """Validate and save the initiative."""
        # Get values
        quarter = int(self.quarter_var.get())
        try:
            year = int(self.year_entry.get().strip())
        except ValueError:
            return

        title = self.title_entry.get().strip()

        outcome_statement = self.outcome_text.get("1.0", "end-1c").strip()
        status = self.status_var.get()

        # Save or update
        try:
            if self.initiative_id:
                # Update existing
                self.vps_manager.update_quarter_initiative(
                    self.initiative_id,
                    quarter=quarter,
                    year=year,
                    title=title,
                    outcome_statement=outcome_statement,
                    status=status
                )
            else:
                # Create new
                annual_initiative = self.vps_manager.get_annual_initiative(
                    self.annual_initiative_id)
                if not annual_initiative:
                    messagebox.showerror(
                        "Error", "Annual Initiative not found.")
                    return
                self.vps_manager.create_quarter_initiative(
                    annual_initiative_id=self.annual_initiative_id,
                    segment_description_id=self.segment_id,
                    quarter=quarter,
                    year=year,
                    title=title,
                    auto_create_chain=True,
                    outcome_statement=outcome_statement
                )

            # Close dialog
            self.destroy()

        except Exception as e:
            print(f"Error saving initiative: {e}")


class AnnualVisionEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing Annual Visions."""

    def __init__(self, parent, vps_manager: 'VPSManager', tl_vision_id: str,
                 segment_id: str, vision_id: Optional[str] = None):
        super().__init__(parent)

        self.vps_manager = vps_manager
        self.tl_vision_id = tl_vision_id
        self.segment_id = segment_id
        self.vision_id = vision_id
        self.vision = None

        # Load vision if editing
        if vision_id:
            self.vision = vps_manager.get_annual_vision(vision_id)
            self.title("Edit Annual Vision")
        else:
            self.title("New Annual Vision")

        self.geometry("600x500")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create form
        self.create_form()

        # Load data if editing
        if self.vision:
            self.load_vision_data()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form layout."""
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_columnconfigure(1, weight=1)

        row = 0

        # Segment display (read-only)
        segment = self.vps_manager.get_segment(self.segment_id)
        if segment:
            ctk.CTkLabel(main_frame, text="Life Segment:", font=ctk.CTkFont(weight="bold")).grid(
                row=row, column=0, sticky="w", padx=10, pady=5
            )
            ctk.CTkLabel(
                main_frame,
                text=segment['name'],
                fg_color=segment['color_hex'],
                text_color=pick_text_color(segment['color_hex']),
                corner_radius=5
            ).grid(row=row, column=1, sticky="w", padx=10, pady=5)
            row += 1

        # Year
        ctk.CTkLabel(main_frame, text="Year:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        current_year = datetime.now().year
        self.year_entry = ctk.CTkEntry(
            main_frame, placeholder_text=str(current_year))
        self.year_entry.insert(0, str(current_year))
        self.year_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Title
        ctk.CTkLabel(main_frame, text="Title:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.title_entry = ctk.CTkEntry(
            main_frame, placeholder_text="My Annual Vision for 2026")
        self.title_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Vision Statement
        ctk.CTkLabel(main_frame, text="Vision Statement:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.vision_statement_text = ctk.CTkTextbox(main_frame, height=150)
        self.vision_statement_text.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Key Priorities
        ctk.CTkLabel(main_frame, text="Key Priorities:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        ctk.CTkLabel(main_frame, text="(one per line)", font=ctk.CTkFont(size=10), text_color=status_text_color("muted")).grid(
            row=row, column=1, sticky="w", padx=10, pady=(0, 2)
        )
        row += 1
        self.priorities_text = ctk.CTkTextbox(main_frame, height=100)
        self.priorities_text.grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        row += 1

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2,
                          sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        btn_save = ctk.CTkButton(
            button_frame, text="Save", command=self.save_vision)
        btn_save.grid(row=0, column=0, padx=5, pady=5)

        btn_cancel = ctk.CTkButton(
            button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=1, padx=5, pady=5)

    def load_vision_data(self):
        """Load existing vision data into form."""
        if not self.vision:
            return

        self.year_entry.delete(0, "end")
        self.year_entry.insert(0, str(self.vision['year']))
        if self.vision['title']:
            self.title_entry.insert(0, self.vision['title'])
        if self.vision['vision_statement']:
            self.vision_statement_text.insert(
                "1.0", self.vision['vision_statement'])
        if self.vision['key_priorities']:
            # Parse JSON array and display one per line
            import json
            try:
                priorities = json.loads(self.vision['key_priorities'])
                self.priorities_text.insert("1.0", "\n".join(priorities))
            except:
                pass

    def save_vision(self):
        """Validate and save the vision."""
        # Get values
        try:
            year = int(self.year_entry.get().strip())
        except ValueError:
            return

        title = self.title_entry.get().strip()
        if not title:
            return

        vision_statement = self.vision_statement_text.get(
            "1.0", "end-1c").strip()

        # Parse priorities (one per line)
        import json
        priorities_text = self.priorities_text.get("1.0", "end-1c").strip()
        priorities = [line.strip()
                      for line in priorities_text.split("\n") if line.strip()]
        priorities_json = json.dumps(priorities)

        # Save or update
        try:
            if self.vision_id:
                # Update existing
                self.vps_manager.update_annual_vision(
                    self.vision_id,
                    year=year,
                    title=title,
                    vision_statement=vision_statement,
                    key_priorities=priorities_json
                )
            else:
                # Create new
                self.vps_manager.create_annual_vision(
                    tl_vision_id=self.tl_vision_id,
                    segment_description_id=self.segment_id,
                    year=year,
                    title=title,
                    vision_statement=vision_statement,
                    key_priorities=priorities_json
                )

            # Close dialog
            self.destroy()

        except Exception as e:
            print(f"Error saving annual vision: {e}")


class AnnualPlanEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing Annual Plans."""

    def __init__(self, parent, vps_manager: 'VPSManager', annual_vision_id: str,
                 segment_id: str, plan_id: Optional[str] = None):
        super().__init__(parent)

        self.vps_manager = vps_manager
        self.annual_vision_id = annual_vision_id
        self.segment_id = segment_id
        self.plan_id = plan_id
        self.plan = None

        # Load plan if editing
        if plan_id:
            self.plan = vps_manager.get_annual_plan(plan_id)
            self.title("Edit Annual Plan")
        else:
            self.title("New Annual Plan")

        self.geometry("600x500")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create form
        self.create_form()

        # Load data if editing
        if self.plan:
            self.load_plan_data()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form layout."""
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_columnconfigure(1, weight=1)

        row = 0

        # Segment display (read-only)
        segment = self.vps_manager.get_segment(self.segment_id)
        if segment:
            ctk.CTkLabel(main_frame, text="Life Segment:", font=ctk.CTkFont(weight="bold")).grid(
                row=row, column=0, sticky="w", padx=10, pady=5
            )
            ctk.CTkLabel(
                main_frame,
                text=segment['name'],
                fg_color=segment['color_hex'],
                text_color=pick_text_color(segment['color_hex']),
                corner_radius=5
            ).grid(row=row, column=1, sticky="w", padx=10, pady=5)
            row += 1

        # Year
        ctk.CTkLabel(main_frame, text="Year:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        current_year = datetime.now().year
        self.year_entry = ctk.CTkEntry(
            main_frame, placeholder_text=str(current_year))
        self.year_entry.insert(0, str(current_year))
        self.year_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Theme
        ctk.CTkLabel(main_frame, text="Theme:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.theme_entry = ctk.CTkEntry(
            main_frame, placeholder_text="Year's guiding theme")
        self.theme_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Objective
        ctk.CTkLabel(main_frame, text="Objective:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.objective_text = ctk.CTkTextbox(main_frame, height=120)
        self.objective_text.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Full Description
        ctk.CTkLabel(main_frame, text="Description:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.description_text = ctk.CTkTextbox(main_frame, height=120)
        self.description_text.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2,
                          sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        btn_save = ctk.CTkButton(
            button_frame, text="Save", command=self.save_plan)
        btn_save.grid(row=0, column=0, padx=5, pady=5)

        btn_cancel = ctk.CTkButton(
            button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=1, padx=5, pady=5)

    def load_plan_data(self):
        """Load existing plan data into form."""
        if not self.plan:
            return

        self.year_entry.delete(0, "end")
        self.year_entry.insert(0, str(self.plan['year']))
        if self.plan['theme']:
            self.theme_entry.insert(0, self.plan['theme'])
        if self.plan['objective']:
            self.objective_text.insert("1.0", self.plan['objective'])
        if self.plan.get('description'):
            self.description_text.insert("1.0", self.plan['description'])

    def save_plan(self):
        """Validate and save the plan."""
        # Get values with defaults
        year_str = self.year_entry.get().strip()
        if not year_str:
            year = datetime.now().year
        else:
            try:
                year = int(year_str)
            except ValueError:
                messagebox.showerror(
                    "Validation Error",
                    "Year must be a valid integer"
                )
                return

        theme = self.theme_entry.get().strip()
        if not theme:
            messagebox.showerror(
                "Validation Error",
                "Theme is required"
            )
            return

        objective = self.objective_text.get("1.0", "end-1c").strip()
        description = self.description_text.get("1.0", "end-1c").strip()

        # Save or update
        try:
            if self.plan_id:
                # Update existing
                self.vps_manager.update_annual_plan(
                    self.plan_id,
                    year=year,
                    theme=theme,
                    objective=objective,
                    description=description
                )
            else:
                # Create new
                self.vps_manager.create_annual_plan(
                    annual_vision_id=self.annual_vision_id,
                    segment_description_id=self.segment_id,
                    year=year,
                    theme=theme,
                    objective=objective,
                    description=description
                )

            # Close dialog
            self.destroy()

        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Error saving annual plan: {e}"
            )


class AnnualInitiativeEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing Annual Initiatives."""

    def __init__(self, parent, vps_manager: 'VPSManager', annual_plan_id: str,
                 segment_id: str, initiative_id: Optional[str] = None):
        super().__init__(parent)

        self.vps_manager = vps_manager
        self.annual_plan_id = annual_plan_id
        self.segment_id = segment_id
        self.initiative_id = initiative_id
        self.initiative = None

        if initiative_id:
            self.initiative = vps_manager.get_annual_initiative(initiative_id)
            self.title("Edit Annual Initiative")
        else:
            self.title("New Annual Initiative")

        self.geometry("600x500")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_form()

        if self.initiative:
            self.load_initiative_data()

        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form layout."""
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_columnconfigure(1, weight=1)

        row = 0

        ctk.CTkLabel(main_frame, text="Year:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        current_year = datetime.now().year
        self.year_entry = ctk.CTkEntry(
            main_frame, placeholder_text=str(current_year))
        self.year_entry.insert(0, str(current_year))
        self.year_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        ctk.CTkLabel(main_frame, text="Title:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.title_entry = ctk.CTkEntry(
            main_frame, placeholder_text="Annual initiative title")
        self.title_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        ctk.CTkLabel(main_frame, text="Outcome Statement:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.outcome_text = ctk.CTkTextbox(main_frame, height=120)
        self.outcome_text.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        ctk.CTkLabel(main_frame, text="Description:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.description_text = ctk.CTkTextbox(main_frame, height=120)
        self.description_text.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        ctk.CTkLabel(main_frame, text="Status:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.status_var = ctk.StringVar(value="not_started")
        self.status_combo = ctk.CTkComboBox(
            main_frame,
            values=["not_started", "in_progress", "at_risk",
                    "completed", "on_hold", "cancelled"],
            variable=self.status_var
        )
        self.status_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2,
                          sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        btn_save = ctk.CTkButton(
            button_frame, text="Save", command=self.save_initiative)
        btn_save.grid(row=0, column=0, padx=5, pady=5)

        btn_cancel = ctk.CTkButton(
            button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=1, padx=5, pady=5)

    def load_initiative_data(self):
        """Load existing initiative data into form."""
        if not self.initiative:
            return

        self.year_entry.delete(0, "end")
        self.year_entry.insert(0, str(self.initiative['year']))
        if self.initiative.get('title'):
            self.title_entry.insert(0, self.initiative['title'])
        if self.initiative.get('outcome_statement'):
            self.outcome_text.insert("1.0", self.initiative['outcome_statement'])
        if self.initiative.get('description'):
            self.description_text.insert("1.0", self.initiative['description'])
        if self.initiative.get('status'):
            self.status_var.set(self.initiative['status'])

    def save_initiative(self):
        """Validate and save the annual initiative."""
        try:
            year = int(self.year_entry.get().strip())
        except ValueError:
            messagebox.showerror("Validation Error", "Year must be a valid integer")
            return

        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("Validation Error", "Title is required")
            return

        outcome_statement = self.outcome_text.get("1.0", "end-1c").strip()
        description = self.description_text.get("1.0", "end-1c").strip()
        status = self.status_var.get()

        try:
            if self.initiative_id:
                self.vps_manager.update_annual_initiative(
                    self.initiative_id,
                    year=year,
                    title=title,
                    outcome_statement=outcome_statement,
                    description=description,
                    status=status
                )
            else:
                self.vps_manager.create_annual_initiative(
                    annual_plan_id=self.annual_plan_id,
                    segment_description_id=self.segment_id,
                    year=year,
                    title=title,
                    description=description,
                    outcome_statement=outcome_statement
                )

            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save annual initiative: {e}")


class MonthTacticEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing Month Tactics."""

    def __init__(self, parent, vps_manager: 'VPSManager', quarter_initiative_id: str,
                 segment_id: str, tactic_id: Optional[str] = None):
        super().__init__(parent)

        self.vps_manager = vps_manager
        self.quarter_initiative_id = quarter_initiative_id
        self.segment_id = segment_id
        self.tactic_id = tactic_id
        self.tactic = None

        # Load tactic if editing
        if tactic_id:
            self.tactic = vps_manager.get_month_tactic(tactic_id)
            self.title("Edit Month Tactic")
        else:
            self.title("New Month Tactic")

        self.geometry("600x450")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create form
        self.create_form()

        # Load data if editing
        if self.tactic:
            self.load_tactic_data()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form layout."""
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_columnconfigure(1, weight=1)

        row = 0

        # Month
        ctk.CTkLabel(main_frame, text="Month:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.month_var = ctk.StringVar(value=str(datetime.now().month))
        self.month_combo = ctk.CTkComboBox(
            main_frame,
            values=["1", "2", "3", "4", "5", "6",
                    "7", "8", "9", "10", "11", "12"],
            variable=self.month_var,
            command=lambda _val: self._refresh_auto_focus()
        )
        self.month_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Year
        ctk.CTkLabel(main_frame, text="Year:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        current_year = datetime.now().year
        self.year_entry = ctk.CTkEntry(
            main_frame, placeholder_text=str(current_year))
        self.year_entry.insert(0, str(current_year))
        self.year_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Priority Focus
        ctk.CTkLabel(main_frame, text="Priority Focus:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.focus_entry = ctk.CTkEntry(
            main_frame, placeholder_text="Main focus for the month")
        self.focus_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        self.focus_entry.configure(state="readonly")
        row += 1

        # Detailed Description
        ctk.CTkLabel(main_frame, text="Description:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.description_text = ctk.CTkTextbox(main_frame, height=200)
        self.description_text.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2,
                          sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        btn_save = ctk.CTkButton(
            button_frame, text="Save", command=self.save_tactic)
        btn_save.grid(row=0, column=0, padx=5, pady=5)

        btn_cancel = ctk.CTkButton(
            button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=1, padx=5, pady=5)

        if not self.tactic_id:
            next_month = self.vps_manager.get_next_month_for_quarter_initiative(
                self.quarter_initiative_id
            )
            self.month_var.set(str(next_month["month"]))
            self.year_entry.delete(0, "end")
            self.year_entry.insert(0, str(next_month["year"]))
            self._refresh_auto_focus()

    def load_tactic_data(self):
        """Load existing tactic data into form."""
        if not self.tactic:
            return

        self.month_var.set(str(self.tactic['month']))
        self.year_entry.delete(0, "end")
        self.year_entry.insert(0, str(self.tactic['year']))
        if self.tactic['priority_focus']:
            self.focus_entry.configure(state="normal")
            self.focus_entry.insert(0, self.tactic['priority_focus'])
            self.focus_entry.configure(state="readonly")
        if self.tactic['description']:
            self.description_text.insert("1.0", self.tactic['description'])

    def _refresh_auto_focus(self):
        """Auto-generate month focus for new records."""
        if self.tactic_id:
            return

        quarter_initiative = self.vps_manager.get_quarter_initiative(
            self.quarter_initiative_id
        )
        prefix = "Quarter"
        if quarter_initiative and quarter_initiative.get("title"):
            prefix = quarter_initiative["title"].strip() or prefix

        month = self.month_var.get().strip() or "1"
        auto_focus = f"{prefix} M{month}"
        self.focus_entry.configure(state="normal")
        self.focus_entry.delete(0, "end")
        self.focus_entry.insert(0, auto_focus)
        self.focus_entry.configure(state="readonly")

    def save_tactic(self):
        """Validate and save the tactic."""
        # Get values
        month = int(self.month_var.get())
        try:
            year = int(self.year_entry.get().strip())
        except ValueError:
            return

        priority_focus = self.focus_entry.get().strip()
        if not priority_focus:
            return

        description = self.description_text.get("1.0", "end-1c").strip()

        # Save or update
        try:
            if self.tactic_id:
                # Update existing
                self.vps_manager.update_month_tactic(
                    self.tactic_id,
                    month=month,
                    year=year,
                    priority_focus=priority_focus,
                    description=description
                )
            else:
                # Create new
                self.vps_manager.create_month_tactic(
                    quarter_initiative_id=self.quarter_initiative_id,
                    segment_description_id=self.segment_id,
                    month=month,
                    year=year,
                    priority_focus=priority_focus,
                    description=description,
                    auto_create_weeks=True
                )

            # Close dialog
            self.destroy()

        except Exception as e:
            print(f"Error saving month tactic: {e}")


class WeekActionEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing Week Actions."""

    def __init__(self, parent, vps_manager: 'VPSManager', month_tactic_id: str,
                 segment_id: str, action_id: Optional[str] = None):
        super().__init__(parent)
        self.withdraw()

        self.vps_manager = vps_manager
        self.month_tactic_id = month_tactic_id
        self.segment_id = segment_id
        self.action_id = action_id
        self.action = None

        # Load action if editing
        if action_id:
            self.action = vps_manager.get_week_action(action_id)
            self.title("Edit Week Action")
        else:
            self.title("New Week Action")

        self.geometry("700x900")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create form
        self.create_form()

        # Load data if editing
        if self.action:
            self.load_action_data()

        _show_dialog_after_layout(self, parent)

    def create_form(self):
        """Create the form layout."""
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_columnconfigure(1, weight=1)

        row = 0

        # Week Start Date
        ctk.CTkLabel(main_frame, text="Week Start:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.week_start_picker = DatePickerButton(main_frame)
        self.week_start_picker.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Week End Date
        ctk.CTkLabel(main_frame, text="Week End:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.week_end_picker = DatePickerButton(main_frame)
        self.week_end_picker.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Title
        ctk.CTkLabel(main_frame, text="Title:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.title_entry = ctk.CTkEntry(
            main_frame, placeholder_text="Week action title")
        self.title_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Description
        ctk.CTkLabel(main_frame, text="Description:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.description_text = ctk.CTkTextbox(main_frame, height=100)
        self.description_text.grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Expected Outcome
        ctk.CTkLabel(main_frame, text="Expected Outcome:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.outcome_text = ctk.CTkTextbox(main_frame, height=100)
        self.outcome_text.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Add separator
        separator = ctk.CTkFrame(main_frame, height=2, fg_color="gray")
        separator.grid(row=row, column=0, columnspan=2,
                       sticky="ew", padx=10, pady=10)
        row += 1

        # Step and Key Result fields
        self.step_entries = []
        self.key_result_entries = []

        for i in range(1, 6):
            # Step field
            ctk.CTkLabel(main_frame, text=f"Step {i}:", font=ctk.CTkFont(weight="bold")).grid(
                row=row, column=0, sticky="w", padx=10, pady=5
            )
            step_entry = ctk.CTkEntry(
                main_frame, placeholder_text=f"Step {i} (50 chars max)")
            step_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
            self.step_entries.append(step_entry)
            row += 1

            # Key Result field
            ctk.CTkLabel(main_frame, text=f"Key Result {i}:", font=ctk.CTkFont(weight="bold")).grid(
                row=row, column=0, sticky="w", padx=10, pady=5
            )
            key_result_entry = ctk.CTkEntry(
                main_frame, placeholder_text=f"Key Result {i} (50 chars max)")
            key_result_entry.grid(
                row=row, column=1, sticky="ew", padx=10, pady=5)
            self.key_result_entries.append(key_result_entry)
            row += 1

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2,
                          sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)

        btn_save = ctk.CTkButton(
            button_frame, text="Save", command=self.save_action)
        btn_save.grid(row=0, column=0, padx=5, pady=5)

        btn_create_next_actions = ctk.CTkButton(
            button_frame, text="Create Next Actions", command=self.create_next_actions)
        btn_create_next_actions.grid(row=0, column=1, padx=5, pady=5)

        btn_cancel = ctk.CTkButton(
            button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=2, padx=5, pady=5)

    def load_action_data(self):
        """Load existing action data into form."""
        if not self.action:
            return

        if self.action['week_start_date']:
            self.week_start_picker.set_date(self.action['week_start_date'])
        if self.action['week_end_date']:
            self.week_end_picker.set_date(self.action['week_end_date'])
        if self.action['title']:
            self.title_entry.insert(0, self.action['title'])
        if self.action['description']:
            self.description_text.insert("1.0", self.action['description'])
        if self.action['outcome_expected']:
            self.outcome_text.insert("1.0", self.action['outcome_expected'])

        # Load Step and Key Result fields
        for i in range(1, 6):
            step_value = self.action.get(f'step_{i}', '')
            if step_value:
                self.step_entries[i-1].insert(0, step_value)

            key_result_value = self.action.get(f'key_result_{i}', '')
            if key_result_value:
                self.key_result_entries[i-1].insert(0, key_result_value)

    def _save_action(self, close_on_success: bool = True) -> Optional[str]:
        """Validate and save the week action and optionally close."""
        # Get values
        week_start = self.week_start_picker.get_date()
        week_end = self.week_end_picker.get_date()
        title = self.title_entry.get().strip()

        if not (week_start and week_end and title):
            messagebox.showerror(
                "Validation Error", "Week start, week end, and title are required.")
            return None

        description = self.description_text.get("1.0", "end-1c").strip()
        outcome = self.outcome_text.get("1.0", "end-1c").strip()

        # Get Step and Key Result values (limit to 50 chars each)
        steps = {}
        key_results = {}
        for i in range(1, 6):
            step_value = self.step_entries[i-1].get().strip()[:50]
            key_result_value = self.key_result_entries[i-1].get().strip()[:50]
            steps[f'step_{i}'] = step_value
            key_results[f'key_result_{i}'] = key_result_value

        # Save or update
        try:
            if self.action_id:
                # Update existing
                self.vps_manager.update_week_action(
                    self.action_id,
                    week_start_date=week_start,
                    week_end_date=week_end,
                    title=title,
                    description=description,
                    outcome_expected=outcome,
                    **steps,
                    **key_results
                )
                saved_id = self.action_id
            else:
                # Create new
                action_id = self.vps_manager.create_week_action(
                    month_tactic_id=self.month_tactic_id,
                    segment_description_id=self.segment_id,
                    week_start_date=week_start,
                    week_end_date=week_end,
                    title=title,
                    description=description,
                    outcome_expected=outcome,
                    **steps,
                    **key_results
                )
                self.action_id = action_id
                saved_id = action_id

            if close_on_success:
                self.destroy()
            return saved_id

        except Exception as e:
            messagebox.showerror("Error", f"Error saving week action: {e}")
            return None

    def save_action(self):
        """Save and close."""
        self._save_action(close_on_success=True)

    def create_next_actions(self):
        """Create 1-5 linked Action Items from this weekly tactic."""
        action_id = self._save_action(close_on_success=False)
        if not action_id:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Create Next Actions")
        dialog.geometry("500x380")
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text="Enter up to 5 action titles (one per line):",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        txt_actions = ctk.CTkTextbox(dialog, height=220)
        txt_actions.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)

        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=10)
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        def on_create():
            raw = txt_actions.get("1.0", "end-1c")
            titles = [line.strip() for line in raw.splitlines() if line.strip()][:5]
            if not titles:
                messagebox.showerror(
                    "Validation Error", "Please enter at least one action title.")
                return

            created = self.vps_manager.create_action_items_for_week_action(
                action_id, titles)
            messagebox.showinfo(
                "Next Actions Created",
                f"Created {len(created)} action item(s)."
            )
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="Create", command=on_create).grid(
            row=0, column=0, padx=5, pady=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=dialog.destroy).grid(
            row=0, column=1, padx=5, pady=5)
