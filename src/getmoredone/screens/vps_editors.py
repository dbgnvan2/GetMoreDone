"""
VPS entity editor dialogs for creating and editing strategic planning items.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from tkinter import messagebox

from ..widgets.date_picker import DatePickerButton

if TYPE_CHECKING:
    from ..vps_manager import VPSManager


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
        ctk.CTkLabel(main_frame, text="(one per line)", font=ctk.CTkFont(size=10), text_color="gray").grid(
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

    def __init__(self, parent, vps_manager: 'VPSManager', annual_plan_id: str,
                 segment_id: str, initiative_id: Optional[str] = None):
        super().__init__(parent)

        self.vps_manager = vps_manager
        self.annual_plan_id = annual_plan_id
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

        # Quarter
        ctk.CTkLabel(main_frame, text="Quarter:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.quarter_var = ctk.StringVar(value="1")
        self.quarter_combo = ctk.CTkComboBox(
            main_frame,
            values=["1", "2", "3", "4"],
            variable=self.quarter_var
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
            main_frame, placeholder_text="Initiative name")
        self.title_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
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

    def save_initiative(self):
        """Validate and save the initiative."""
        # Get values
        quarter = int(self.quarter_var.get())
        try:
            year = int(self.year_entry.get().strip())
        except ValueError:
            return

        title = self.title_entry.get().strip()
        if not title:
            return

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
                self.vps_manager.create_quarter_initiative(
                    annual_plan_id=self.annual_plan_id,
                    segment_description_id=self.segment_id,
                    quarter=quarter,
                    year=year,
                    title=title,
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
        ctk.CTkLabel(main_frame, text="(one per line)", font=ctk.CTkFont(size=10), text_color="gray").grid(
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
            variable=self.month_var
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

    def load_tactic_data(self):
        """Load existing tactic data into form."""
        if not self.tactic:
            return

        self.month_var.set(str(self.tactic['month']))
        self.year_entry.delete(0, "end")
        self.year_entry.insert(0, str(self.tactic['year']))
        if self.tactic['priority_focus']:
            self.focus_entry.insert(0, self.tactic['priority_focus'])
        if self.tactic['description']:
            self.description_text.insert("1.0", self.tactic['description'])

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
                    description=description
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

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

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

        btn_save = ctk.CTkButton(
            button_frame, text="Save", command=self.save_action)
        btn_save.grid(row=0, column=0, padx=5, pady=5)

        btn_cancel = ctk.CTkButton(
            button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=1, padx=5, pady=5)

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

    def save_action(self):
        """Validate and save the action."""
        # Get values
        week_start = self.week_start_picker.get_date()
        week_end = self.week_end_picker.get_date()
        title = self.title_entry.get().strip()

        if not (week_start and week_end and title):
            return

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
                # Auto-create Action Items from non-blank Steps (idempotent - won't create duplicates)
                self.vps_manager.auto_create_action_items_from_steps(
                    self.action_id)
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

                # Auto-create Action Items from non-blank Steps
                self.vps_manager.auto_create_action_items_from_steps(action_id)

            # Close dialog
            self.destroy()

        except Exception as e:
            print(f"Error saving week action: {e}")
