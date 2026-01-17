"""
VPS entity editor dialogs for creating and editing strategic planning items.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Optional, TYPE_CHECKING

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
        self.start_year_entry = ctk.CTkEntry(main_frame, placeholder_text="2025")
        self.start_year_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # End Year
        ctk.CTkLabel(main_frame, text="End Year:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.end_year_entry = ctk.CTkEntry(main_frame, placeholder_text="2030")
        self.end_year_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Title
        ctk.CTkLabel(main_frame, text="Title:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.title_entry = ctk.CTkEntry(main_frame, placeholder_text="My 5-Year Vision")
        self.title_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Vision Statement
        ctk.CTkLabel(main_frame, text="Vision Statement:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.vision_statement_text = ctk.CTkTextbox(main_frame, height=150)
        self.vision_statement_text.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
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
        self.metrics_text.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        row += 1

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        btn_cancel = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=0, padx=5, pady=5)

        btn_save = ctk.CTkButton(button_frame, text="Save", command=self.save_vision)
        btn_save.grid(row=0, column=1, padx=5, pady=5)

    def load_vision_data(self):
        """Load existing vision data into form."""
        if not self.vision:
            return

        self.start_year_entry.insert(0, str(self.vision['start_year']))
        self.end_year_entry.insert(0, str(self.vision['end_year']))
        if self.vision['title']:
            self.title_entry.insert(0, self.vision['title'])
        if self.vision['vision_statement']:
            self.vision_statement_text.insert("1.0", self.vision['vision_statement'])
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
        # Get values
        try:
            start_year = int(self.start_year_entry.get().strip())
            end_year = int(self.end_year_entry.get().strip())
        except ValueError:
            ctk.CTkMessageBox(
                title="Validation Error",
                message="Start and End years must be valid integers",
                icon="cancel"
            )
            return

        if end_year <= start_year:
            ctk.CTkMessageBox(
                title="Validation Error",
                message="End year must be greater than start year",
                icon="cancel"
            )
            return

        title = self.title_entry.get().strip()
        vision_statement = self.vision_statement_text.get("1.0", "end-1c").strip()

        # Parse metrics (one per line)
        import json
        metrics_text = self.metrics_text.get("1.0", "end-1c").strip()
        metrics = [line.strip() for line in metrics_text.split("\n") if line.strip()]
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
            ctk.CTkMessageBox(
                title="Error",
                message=f"Failed to save vision: {str(e)}",
                icon="cancel"
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
        self.year_entry = ctk.CTkEntry(main_frame, placeholder_text=str(current_year))
        self.year_entry.insert(0, str(current_year))
        self.year_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Title
        ctk.CTkLabel(main_frame, text="Title:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.title_entry = ctk.CTkEntry(main_frame, placeholder_text="Initiative name")
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
            values=["not_started", "in_progress", "at_risk", "completed", "on_hold", "cancelled"],
            variable=self.status_var
        )
        self.status_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        btn_cancel = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=0, padx=5, pady=5)

        btn_save = ctk.CTkButton(button_frame, text="Save", command=self.save_initiative)
        btn_save.grid(row=0, column=1, padx=5, pady=5)

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
            self.outcome_text.insert("1.0", self.initiative['outcome_statement'])
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

        self.geometry("600x450")
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
        self.week_start_entry = ctk.CTkEntry(main_frame, placeholder_text="YYYY-MM-DD")
        self.week_start_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Week End Date
        ctk.CTkLabel(main_frame, text="Week End:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.week_end_entry = ctk.CTkEntry(main_frame, placeholder_text="YYYY-MM-DD")
        self.week_end_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Title
        ctk.CTkLabel(main_frame, text="Title:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.title_entry = ctk.CTkEntry(main_frame, placeholder_text="Week action title")
        self.title_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Description
        ctk.CTkLabel(main_frame, text="Description:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.description_text = ctk.CTkTextbox(main_frame, height=100)
        self.description_text.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Expected Outcome
        ctk.CTkLabel(main_frame, text="Expected Outcome:", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, sticky="nw", padx=10, pady=5
        )
        self.outcome_text = ctk.CTkTextbox(main_frame, height=100)
        self.outcome_text.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        btn_cancel = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy)
        btn_cancel.grid(row=0, column=0, padx=5, pady=5)

        btn_save = ctk.CTkButton(button_frame, text="Save", command=self.save_action)
        btn_save.grid(row=0, column=1, padx=5, pady=5)

    def load_action_data(self):
        """Load existing action data into form."""
        if not self.action:
            return

        if self.action['week_start_date']:
            self.week_start_entry.insert(0, self.action['week_start_date'])
        if self.action['week_end_date']:
            self.week_end_entry.insert(0, self.action['week_end_date'])
        if self.action['title']:
            self.title_entry.insert(0, self.action['title'])
        if self.action['description']:
            self.description_text.insert("1.0", self.action['description'])
        if self.action['outcome_expected']:
            self.outcome_text.insert("1.0", self.action['outcome_expected'])

    def save_action(self):
        """Validate and save the action."""
        # Get values
        week_start = self.week_start_entry.get().strip()
        week_end = self.week_end_entry.get().strip()
        title = self.title_entry.get().strip()

        if not (week_start and week_end and title):
            return

        description = self.description_text.get("1.0", "end-1c").strip()
        outcome = self.outcome_text.get("1.0", "end-1c").strip()

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
                    outcome_expected=outcome
                )
            else:
                # Create new
                self.vps_manager.create_week_action(
                    month_tactic_id=self.month_tactic_id,
                    segment_description_id=self.segment_id,
                    week_start_date=week_start,
                    week_end_date=week_end,
                    title=title,
                    description=description,
                    outcome_expected=outcome
                )

            # Close dialog
            self.destroy()

        except Exception as e:
            print(f"Error saving week action: {e}")
