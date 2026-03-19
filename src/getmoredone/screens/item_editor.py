"""
Item editor dialog for creating and editing action items.
"""

import calendar
import logging
import re
import customtkinter as ctk
from datetime import datetime, timedelta, date
from typing import Optional, TYPE_CHECKING, Dict, Any, Tuple, List

from ..models import ActionItem, PriorityFactors, ItemLink
from ..validation import Validator
from ..app_settings import AppSettings
from ..color_contrast import pick_text_color
from ..date_utils import increment_date
from ..paths import app_data_dir_path
from ..theme import button_style, semantic_colors
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors
from .title_format import split_action_item_title, build_action_item_title

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..vps_manager import VPSManager


def _get_weekly_debug_logger() -> logging.Logger:
    logger = logging.getLogger("getmoredone.weekly_tactic")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_path = app_data_dir_path() / "weekly_tactic_debug.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class ItemEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing action items."""

    def __init__(self, parent, db_manager: 'DatabaseManager', item_id: Optional[str] = None,
                 week_action_id: Optional[str] = None, segment_description_id: Optional[str] = None,
                 vps_manager: Optional['VPSManager'] = None, on_close_callback=None,
                 focus_tab: Optional[str] = None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.vps_manager = vps_manager
        self.logger = _get_weekly_debug_logger()
        self.item_id = item_id
        self.item: Optional[ActionItem] = None
        self.week_action_id = week_action_id
        self.segment_description_id = segment_description_id
        self.focus_tab = focus_tab
        self.week_action_options = {}  # Map display string to week_action_id
        self.week_action_display_values = ["(None)"]
        self.app_settings = AppSettings.load()
        self.first_day_of_week = int(getattr(self.app_settings, "first_day_of_week", 0))
        # Callback to refresh parent when dialog closes
        self.on_close_callback = on_close_callback

        self.segment_name_map = {}
        if self.vps_manager:
            try:
                segments = self.vps_manager.get_all_segments()
                self.segment_name_map = {
                    seg["id"]: seg["name"] for seg in segments if seg.get("id")
                }
            except Exception:
                self.segment_name_map = {}

        # Load item if editing
        if item_id:
            self.item = db_manager.get_action_item(item_id)
            if self.item and self.item.item_type == "week":
                self.title("Edit Weekly Tactic")
            else:
                self.title("Edit Action Item")
        else:
            self.title("New Action Item")

        self.geometry("920x550")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Bind resize event
        self.bind("<Configure>", self.on_resize)
        self.last_width = 920  # Track width for responsive layout

        # Create form
        self.create_form()
        self._apply_record_type_ui()

        # Load item data if editing, or apply defaults if new
        if self.item:
            self.load_item_data()
        else:
            # Apply defaults for new items
            self.apply_defaults_to_form()

        if self.focus_tab:
            try:
                self.tabview.set(self.focus_tab)
            except Exception:
                pass

        # Make dialog appear on top of parent (but not modal - allows multiple editors)
        self.transient(parent)

        # Bind cleanup callback when dialog is closed
        self.protocol("WM_DELETE_WINDOW", self.on_dialog_close)

        # Center on parent window
        self.center_on_parent()

    def create_form(self):
        """Create the form layout with responsive two-column design."""
        # Main container frame
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_columnconfigure(0, weight=1)  # Left column
        main_frame.grid_columnconfigure(
            1, weight=0)  # Right column - fixed width
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_rowconfigure(2, weight=1)

        # Left column
        left_col = ctk.CTkFrame(main_frame)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_col.grid_columnconfigure(1, weight=1)

        # Right column
        right_col = ctk.CTkFrame(main_frame)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right_col.grid_columnconfigure(1, weight=1)
        right_col.grid_rowconfigure(0, weight=1)

        # Resizable separator between panel 1 (top form) and panel 2 (tabs)
        self.separator_frame = ctk.CTkFrame(
            main_frame, height=5, fg_color="gray40", cursor="sb_v_double_arrow")
        self.separator_frame.bind("<Button-1>", self.start_resize)
        self.separator_frame.bind("<B1-Motion>", self.do_resize)
        self.resizing = False
        self.resize_start_y = 0
        self.is_single_column = False

        # === LEFT COLUMN ===
        row_l = 0

        # Parent Item Info (if this is a sub-item)
        if self.item and self.item.parent_id:
            parent_item = self.db_manager.get_action_item(self.item.parent_id)
            if parent_item:
                parent_frame = ctk.CTkFrame(
                    left_col, fg_color="gray25", corner_radius=8)
                parent_frame.grid(row=row_l, column=0, columnspan=2,
                                  sticky="ew", padx=10, pady=(5, 10))

                ctk.CTkLabel(
                    parent_frame,
                    text=f"Sub-item of: {parent_item.title}",
                    font=ctk.CTkFont(size=12),
                    text_color="lightblue"
                ).pack(side="left", padx=10, pady=5)

                btn_view_parent = ctk.CTkButton(
                    parent_frame,
                    text="View Parent",
                    width=80,
                    height=24,
                    command=lambda: self.view_parent_item(parent_item.id)
                )
                btn_view_parent.pack(side="right", padx=10, pady=5)

                row_l += 1

        # Basic Info Section
        ctk.CTkLabel(
            left_col,
            text="Basic Information",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row_l, column=0, sticky="w", padx=10, pady=(5, 10))
        self.record_type_badge = ctk.CTkLabel(
            left_col,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8,
        )
        self.record_type_badge.grid(row=row_l, column=1, sticky="e", padx=10, pady=(5, 10))
        row_l += 1

        # Who (with contact lookup)
        who_label_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        who_label_frame.grid(row=row_l, column=0, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(who_label_frame, text="* Who:").pack(side="left")

        # Add contact button
        btn_add_contact = ctk.CTkButton(
            who_label_frame,
            text="+",
            width=30,
            height=24,
            command=self.add_new_contact
        )
        btn_add_contact.pack(side="left", padx=(5, 0))

        # Who entry with autocomplete
        who_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        who_frame.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)

        self.who_var = ctk.StringVar()
        self.who_entry = ctk.CTkEntry(
            who_frame, textvariable=self.who_var, width=320)
        self.who_entry.pack()
        self.who_entry.bind('<KeyRelease>', self.on_who_search)
        self.who_entry.bind('<Button-1>', self.on_who_click)  # Show on click
        self.who_entry.bind('<Tab>', lambda e: self.hide_contact_suggestions())
        self.who_entry.bind(
            '<Escape>', lambda e: self.hide_contact_suggestions())
        # Apply defaults when focus leaves WHO field
        self.who_entry.bind('<FocusOut>', lambda e: self.on_who_changed())

        # Dropdown for contact suggestions
        self.contact_suggestions_frame = None
        self.selected_contact_id = None
        self.suggestions_hide_job = None  # Track scheduled hide job

        # Try to auto-select contact if who name matches a contact
        if not self.item_id:
            # Set default who value - check system defaults first
            system_defaults = self.db_manager.get_defaults("system")
            if system_defaults and system_defaults.who:
                self.who_var.set(system_defaults.who)
                # Try to match with a contact
                contacts = self.db_manager.get_all_contacts(active_only=True)
                for contact in contacts:
                    if contact.name == system_defaults.who:
                        self.selected_contact_id = contact.id
                        break
            else:
                # Fall back to first active contact or "Self"
                contacts = self.db_manager.get_all_contacts(active_only=True)
                if contacts:
                    self.who_var.set(contacts[0].name)
                    self.selected_contact_id = contacts[0].id
                else:
                    self.who_var.set("Self")

        row_l += 1

        # Context + Title
        self.context_label = ctk.CTkLabel(left_col, text="Context:")
        self.context_label.grid(row=row_l, column=0, sticky="w", padx=10, pady=5)
        self.title_context_entry = ctk.CTkEntry(
            left_col, width=320, placeholder_text="PW|LS|Blog - W8")
        self.title_context_entry.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)
        row_l += 1

        ctk.CTkLabel(left_col, text="* Immediate Step:").grid(row=row_l,
                                                     column=0, sticky="w", padx=10, pady=5)
        self.title_entry = ctk.CTkEntry(left_col, width=320, placeholder_text="write blog 3")
        self.title_entry.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)
        row_l += 1

        # Description
        ctk.CTkLabel(left_col, text="Description:").grid(
            row=row_l, column=0, sticky="nw", padx=10, pady=5)
        self.description_text = ctk.CTkTextbox(left_col, height=100, width=320)
        self.description_text.grid(
            row=row_l, column=1, sticky="nsew", padx=10, pady=5)
        left_col.grid_rowconfigure(row_l, weight=1)  # Allow vertical resizing
        row_l += 1

        # Planned Minutes (keep in left column for now)
        ctk.CTkLabel(left_col, text="Planned Minutes:").grid(
            row=row_l, column=0, sticky="w", padx=10, pady=5)
        self.planned_minutes_entry = ctk.CTkEntry(
            left_col, placeholder_text="0", width=320)
        self.planned_minutes_entry.grid(
            row=row_l, column=1, sticky="w", padx=10, pady=5)
        row_l += 1

        # Next Action
        ctk.CTkLabel(left_col, text="Next Action:").grid(
            row=row_l, column=0, sticky="nw", padx=10, pady=5)
        self.next_action_text = ctk.CTkTextbox(left_col, height=120, width=320)
        self.next_action_text.grid(
            row=row_l, column=1, sticky="nsew", padx=10, pady=5)
        left_col.grid_rowconfigure(row_l, weight=1)  # Bottom section grows with window
        row_l += 1

        # === RIGHT COLUMN with TABS ===
        row_r = 0

        # Create tabview for right column with fixed height
        self.tabview = ctk.CTkTabview(right_col, width=380, height=400)
        self.tabview.grid(row=row_r, column=0, columnspan=2,
                          sticky="nsew", padx=10, pady=10)
        row_r += 1

        # Create tabs (Dates tab first as default)
        self.tab_dates = self.tabview.add("Dates")
        self.tab_priority = self.tabview.add("Priority")
        self.tab_organization = self.tabview.add("Organization")
        self.tab_notes = self.tabview.add("Notes")

        # Configure tab grids - items stick to top, don't expand vertically
        self.tab_dates.grid_columnconfigure(1, weight=1)
        self.tab_priority.grid_columnconfigure(1, weight=1)
        self.tab_organization.grid_columnconfigure(1, weight=1)
        self.tab_notes.grid_columnconfigure(0, weight=1)

        # Don't let rows expand - this keeps items at the top
        # Empty row at bottom absorbs space
        self.tab_dates.grid_rowconfigure(99, weight=1)
        self.tab_priority.grid_rowconfigure(99, weight=1)
        self.tab_organization.grid_rowconfigure(99, weight=1)
        self.tab_notes.grid_rowconfigure(99, weight=1)

        # === TAB 0: DATES ===
        tab0_row = 0

        # Start Date
        ctk.CTkLabel(self.tab_dates, text="Start Date:").grid(
            row=tab0_row, column=0, sticky="w", padx=10, pady=5)

        start_date_frame = ctk.CTkFrame(self.tab_dates, fg_color="transparent")
        start_date_frame.grid(row=tab0_row, column=1,
                              sticky="w", padx=10, pady=5)

        self.start_date_entry = ctk.CTkEntry(
            start_date_frame, placeholder_text="YYYY-MM-DD", width=150)
        self.start_date_entry.pack(side="left", padx=(0, 5))
        # Bind to validate due date when start date is manually edited
        self.start_date_entry.bind(
            "<FocusOut>", lambda e: self.validate_and_adjust_due_date())

        btn_start_today = ctk.CTkButton(start_date_frame, text="Today", width=50,
                                        command=lambda: self.set_date(self.start_date_entry, 0))
        btn_start_today.pack(side="left", padx=2)

        btn_start_minus = ctk.CTkButton(start_date_frame, text="-1", width=40,
                                        command=lambda: self.adjust_date(self.start_date_entry, -1))
        btn_start_minus.pack(side="left", padx=2)

        btn_start_plus = ctk.CTkButton(start_date_frame, text="+1", width=40,
                                       command=lambda: self.adjust_date(self.start_date_entry, 1))
        btn_start_plus.pack(side="left", padx=2)

        btn_start_clear = ctk.CTkButton(start_date_frame, text="Clear", width=50,
                                        command=lambda: self.start_date_entry.delete(0, "end"))
        btn_start_clear.pack(side="left", padx=2)
        tab0_row += 1

        # Due Date
        ctk.CTkLabel(self.tab_dates, text="Due Date:").grid(
            row=tab0_row, column=0, sticky="w", padx=10, pady=5)

        due_date_frame = ctk.CTkFrame(self.tab_dates, fg_color="transparent")
        due_date_frame.grid(row=tab0_row, column=1,
                            sticky="w", padx=10, pady=5)

        self.due_date_entry = ctk.CTkEntry(
            due_date_frame, placeholder_text="YYYY-MM-DD", width=150)
        self.due_date_entry.pack(side="left", padx=(0, 5))
        # Bind to validate due date when manually edited
        self.due_date_entry.bind(
            "<FocusOut>", lambda e: self.validate_due_date_on_edit())

        btn_due_today = ctk.CTkButton(due_date_frame, text="Today", width=50,
                                      command=lambda: self.set_date(self.due_date_entry, 0))
        btn_due_today.pack(side="left", padx=2)

        btn_due_minus = ctk.CTkButton(due_date_frame, text="-1", width=40,
                                      command=lambda: self.adjust_date(self.due_date_entry, -1))
        btn_due_minus.pack(side="left", padx=2)

        btn_due_plus = ctk.CTkButton(due_date_frame, text="+1", width=40,
                                     command=lambda: self.adjust_date(self.due_date_entry, 1))
        btn_due_plus.pack(side="left", padx=2)

        btn_due_clear = ctk.CTkButton(due_date_frame, text="Clear", width=50,
                                      command=lambda: self.due_date_entry.delete(0, "end"))
        btn_due_clear.pack(side="left", padx=2)
        tab0_row += 1

        # Is Meeting + Calendar
        ctk.CTkLabel(self.tab_dates, text="Is Meeting:").grid(
            row=tab0_row, column=0, sticky="w", padx=10, pady=5)
        self.is_meeting_var = ctk.BooleanVar(value=False)
        meeting_frame = ctk.CTkFrame(self.tab_dates, fg_color="transparent")
        meeting_frame.grid(row=tab0_row, column=1, sticky="w", padx=10, pady=5)
        meeting_frame.grid_columnconfigure(0, minsize=150)

        self.is_meeting_checkbox = ctk.CTkCheckBox(
            meeting_frame,
            text="",
            variable=self.is_meeting_var,
            onvalue=True,
            offvalue=False
        )
        self.is_meeting_checkbox.grid(row=0, column=0, sticky="w")

        btn_calendar = ctk.CTkButton(
            meeting_frame,
            text="📅 Calendar",
            command=self.create_calendar_event,
            width=100,
            **button_style("secondary"),
        )
        btn_calendar.grid(row=0, column=1, sticky="w", padx=(5, 0))
        tab0_row += 1

        # Meeting Start Time (read-only, set when calendar event is created)
        ctk.CTkLabel(self.tab_dates, text="Meeting Time:").grid(
            row=tab0_row, column=0, sticky="w", padx=10, pady=5)
        self.meeting_time_label = ctk.CTkLabel(
            self.tab_dates, text="Not scheduled", anchor="w")
        self.meeting_time_label.grid(
            row=tab0_row, column=1, sticky="w", padx=10, pady=5)
        tab0_row += 1

        # === TAB 1: PRIORITY FACTORS ===
        tab1_row = 0

        # Importance
        ctk.CTkLabel(self.tab_priority, text="Importance:").grid(
            row=tab1_row, column=0, sticky="w", padx=10, pady=5)
        importance_values = [
            f"{k} ({v})" for k, v in PriorityFactors.IMPORTANCE.items()]
        self.importance_var = ctk.StringVar(value="")
        self.importance_combo = ctk.CTkComboBox(
            self.tab_priority, values=importance_values, variable=self.importance_var, width=180,
            command=lambda _: self.update_priority_display()
        )
        self.importance_combo.grid(
            row=tab1_row, column=1, sticky="w", padx=10, pady=5)
        tab1_row += 1

        # Urgency
        ctk.CTkLabel(self.tab_priority, text="Urgency:").grid(
            row=tab1_row, column=0, sticky="w", padx=10, pady=5)
        urgency_values = [
            f"{k} ({v})" for k, v in PriorityFactors.URGENCY.items()]
        self.urgency_var = ctk.StringVar(value="")
        self.urgency_combo = ctk.CTkComboBox(
            self.tab_priority, values=urgency_values, variable=self.urgency_var, width=180,
            command=lambda _: self.update_priority_display()
        )
        self.urgency_combo.grid(row=tab1_row, column=1,
                                sticky="w", padx=10, pady=5)
        tab1_row += 1

        # Effort-Cost (Size internally)
        ctk.CTkLabel(self.tab_priority, text="Effort-Cost:").grid(row=tab1_row,
                                                                  column=0, sticky="w", padx=10, pady=5)
        size_values = [f"{k} ({v})" for k, v in PriorityFactors.SIZE.items()]
        self.size_var = ctk.StringVar(value="")
        self.size_combo = ctk.CTkComboBox(
            self.tab_priority, values=size_values, variable=self.size_var, width=180,
            command=lambda _: self.update_priority_display()
        )
        self.size_combo.grid(row=tab1_row, column=1,
                             sticky="w", padx=10, pady=5)
        tab1_row += 1

        # Value
        ctk.CTkLabel(self.tab_priority, text="Value:").grid(
            row=tab1_row, column=0, sticky="w", padx=10, pady=5)
        value_values = [f"{k} ({v})" for k, v in PriorityFactors.VALUE.items()]
        self.value_var = ctk.StringVar(value="")
        self.value_combo = ctk.CTkComboBox(
            self.tab_priority, values=value_values, variable=self.value_var, width=180,
            command=lambda _: self.update_priority_display()
        )
        self.value_combo.grid(row=tab1_row, column=1,
                              sticky="w", padx=10, pady=5)
        tab1_row += 1

        # Priority Score Display (more compact)
        score_frame = ctk.CTkFrame(self.tab_priority, corner_radius=8)
        score_frame.grid(row=tab1_row, column=0, columnspan=2,
                         sticky="ew", padx=10, pady=(15, 5))
        score_frame.grid_columnconfigure(0, weight=1)
        score_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            score_frame,
            text="Priority Score:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=8)

        self.priority_label = ctk.CTkLabel(
            score_frame,
            text="0 (0×0×0×0)",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="e",
        )
        self.priority_label.grid(row=0, column=1, sticky="e", padx=10, pady=8)
        tab1_row += 1

        # === TAB 2: ORGANIZATION ===
        tab2_row = 0

        # Group
        ctk.CTkLabel(self.tab_organization, text="Group:").grid(
            row=tab2_row, column=0, sticky="w", padx=10, pady=5)
        groups = self.db_manager.get_distinct_groups()
        self.group_var = ctk.StringVar(value="")
        self.group_combo = ctk.CTkComboBox(self.tab_organization, values=groups if groups else [
                                           ""], variable=self.group_var, width=180)
        self.group_combo.grid(row=tab2_row, column=1,
                              sticky="w", padx=10, pady=5)
        tab2_row += 1

        # Category
        ctk.CTkLabel(self.tab_organization, text="Category:").grid(
            row=tab2_row, column=0, sticky="w", padx=10, pady=5)
        categories = self.db_manager.get_distinct_categories()
        self.category_var = ctk.StringVar(value="")
        self.category_combo = ctk.CTkComboBox(self.tab_organization, values=categories if categories else [
                                              ""], variable=self.category_var, width=180)
        self.category_combo.grid(
            row=tab2_row, column=1, sticky="w", padx=10, pady=5)
        tab2_row += 1

        # Weekly Tactic (VSP Integration)
        ctk.CTkLabel(self.tab_organization, text="Weekly Tactic:").grid(
            row=tab2_row, column=0, sticky="w", padx=10, pady=5)
        self.week_action_var = ctk.StringVar(value="")
        self.week_action_combo = ctk.CTkComboBox(self.tab_organization, values=[
                                                 ""], variable=self.week_action_var, width=250)
        self.week_action_combo.grid(
            row=tab2_row, column=1, sticky="w", padx=10, pady=5)
        tab2_row += 1

        # Load week actions if vps_manager is available
        self.load_week_actions()

        # Original Due Date (read-only display)
        ctk.CTkLabel(self.tab_organization, text="Original Due Date:").grid(
            row=tab2_row, column=0, sticky="w", padx=10, pady=5)
        self.original_due_date_label = ctk.CTkLabel(
            self.tab_organization,
            text="-",
            anchor="w",
            text_color="gray"
        )
        self.original_due_date_label.grid(
            row=tab2_row, column=1, sticky="w", padx=10, pady=5)
        tab2_row += 1

        # Completed Date (read-only display)
        ctk.CTkLabel(self.tab_organization, text="Completed Date:").grid(
            row=tab2_row, column=0, sticky="w", padx=10, pady=5)
        self.completed_at_label = ctk.CTkLabel(
            self.tab_organization,
            text="-",
            anchor="w",
            text_color="lightgreen"
        )
        self.completed_at_label.grid(
            row=tab2_row, column=1, sticky="w", padx=10, pady=5)
        tab2_row += 1

        # === TAB 3: OBSIDIAN NOTES ===
        tab3_row = 0

        # Notes list frame
        self.notes_frame = ctk.CTkScrollableFrame(self.tab_notes, height=180)
        self.notes_frame.grid(row=tab3_row, column=0,
                              sticky="new", padx=10, pady=5)
        self.notes_frame.grid_columnconfigure(0, weight=1)
        tab3_row += 1

        # Notes buttons
        notes_btn_frame = ctk.CTkFrame(self.tab_notes, fg_color="transparent")
        notes_btn_frame.grid(row=tab3_row, column=0,
                             sticky="w", padx=10, pady=5)

        btn_create_note = ctk.CTkButton(
            notes_btn_frame,
            text="+ Create Note",
            width=110,
            command=self.create_note
        )
        btn_create_note.pack(side="left", padx=2)

        btn_link_note = ctk.CTkButton(
            notes_btn_frame,
            text="+ Link Note",
            width=100,
            command=self.link_existing_note
        )
        btn_link_note.pack(side="left", padx=2)
        tab3_row += 1

        # Load notes (if item exists)
        if self.item_id:
            self.load_notes()
        else:
            # Show message for new items
            ctk.CTkLabel(
                self.notes_frame,
                text="Item will be saved when you create or link a note",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            ).grid(row=0, column=0, pady=10)

        # === BUTTONS ===
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        # Row 1: Primary actions
        top_row = ctk.CTkFrame(btn_frame, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 5))

        action_btn_width = 110

        btn_save = ctk.CTkButton(top_row, text="Save",
                                 command=self.save_item, width=action_btn_width)
        btn_save.pack(side="left", padx=2)

        btn_save_close = ctk.CTkButton(
            top_row, text="Save & Close", command=self.save_and_close, width=action_btn_width)
        btn_save_close.pack(side="left", padx=2)

        if not self.item_id:
            btn_save_new = ctk.CTkButton(
                top_row, text="Save + New", command=self.save_and_new, width=action_btn_width)
            btn_save_new.pack(side="left", padx=2)

        if self.item_id:
            btn_duplicate = ctk.CTkButton(
                top_row, text="Duplicate", command=self.duplicate_item, width=action_btn_width)
            btn_duplicate.pack(side="left", padx=2)

            btn_followup = ctk.CTkButton(
                top_row, text="Add Follow-up", command=self.create_followup, width=action_btn_width)
            btn_followup.pack(side="left", padx=2)

        # Error label
        self.error_label = ctk.CTkLabel(
            top_row, text="", text_color="red", wraplength=600)
        self.error_label.pack(side="left", expand=True, padx=10)

        # Row 2: Secondary actions (only for existing items)
        if self.item_id:
            bottom_row = ctk.CTkFrame(btn_frame, fg_color="transparent")
            bottom_row.pack(fill="x")

            btn_create_tasks = ctk.CTkButton(
                bottom_row, text="Add Tasks", command=self.create_sub_item, width=action_btn_width)
            btn_create_tasks.pack(side="left", padx=2)

            btn_show_related = ctk.CTkButton(
                bottom_row, text="Show Related", command=self.show_related, width=action_btn_width)
            btn_show_related.pack(side="left", padx=2)

            btn_set_parent = ctk.CTkButton(
                bottom_row, text="Set Parent", command=self.set_parent, width=action_btn_width)
            btn_set_parent.pack(side="left", padx=2)

            btn_set_weekly = ctk.CTkButton(
                bottom_row, text="Set Wk Tactic", command=self.set_weekly_tactic, width=action_btn_width)
            btn_set_weekly.pack(side="left", padx=2)

        # Row 3: Completion actions
        third_row = ctk.CTkFrame(btn_frame, fg_color="transparent")
        third_row.pack(fill="x", pady=(5, 0))

        if self.item_id:
            btn_complete = ctk.CTkButton(
                third_row,
                text="Complete",
                command=self.complete_item,
                width=action_btn_width,
                **button_style("danger"),
            )
            btn_complete.pack(side="left", padx=2)

        btn_cancel = ctk.CTkButton(
            third_row, text="Cancel", command=self.destroy, width=action_btn_width)
        btn_cancel.pack(side="left", padx=2)

        if self.item_id:
            btn_delete = ctk.CTkButton(
                third_row,
                text="Delete",
                command=self.delete_item,
                width=action_btn_width,
                **button_style("danger"),
            )
            btn_delete.pack(side="left", padx=2)

        # Store references for responsive layout
        self.left_col = left_col
        self.right_col = right_col
        self.main_frame = main_frame

    def load_week_actions(self):
        """Load week actions into the dropdown if the VSP manager is available."""
        if not self.vps_manager:
            self.week_action_combo.configure(
                values=["(VSP Manager not available)"], state="disabled")
            return

        try:
            range_start, range_end = self._get_week_window_range()
            db_path = getattr(getattr(self.db_manager, "db", None), "db_path", "(unknown)")
            self.logger.info(
                "[load_week_actions] item_id=%s db=%s range=%s..%s",
                self.item_id,
                db_path,
                range_start.isoformat(),
                range_end.isoformat(),
            )

            week_actions = self.vps_manager.get_week_actions_in_range(
                range_start.isoformat(), range_end.isoformat(), active_only=False
            )
            self.logger.info("[load_week_actions] in_range_count=%d", len(week_actions))

            if not week_actions:
                # Fallback to the entire weekly tactic catalog so the dropdown is never empty.
                week_actions = self.vps_manager.get_week_actions(active_only=False)
                self.logger.info("[load_week_actions] fallback_all_week_actions_count=%d", len(week_actions))

            if not week_actions:
                self.week_action_combo.configure(
                    values=["(No Week Actions available)"])
                self.logger.warning("[load_week_actions] no_week_actions_available")
                return

            # Create display strings: "Weekly Tactic YYYY-MM-DD: Title"
            self.week_action_options = {}
            self.week_action_display_values = ["(None)"]

            for wa in week_actions:
                display = self._format_week_action_display(wa)
                self.week_action_display_values.append(display)
                self.week_action_options[display] = wa['id']

            self.week_action_combo.configure(values=self.week_action_display_values)
            self.logger.info(
                "[load_week_actions] dropdown_values_count=%d",
                len(self.week_action_display_values),
            )

        except Exception as e:
            self.logger.exception("[load_week_actions] error=%s", e)
            self.week_action_combo.configure(
                values=["(Error loading week actions)"], state="disabled")

    def _get_week_window_range(self):
        anchor = self._get_anchor_date()
        start = anchor - timedelta(days=21)
        offset_start = (start.weekday() - self.first_day_of_week) % 7
        start -= timedelta(days=offset_start)

        end = anchor + timedelta(days=7)
        last_day_index = (self.first_day_of_week + 6) % 7
        offset_end = (last_day_index - end.weekday()) % 7
        end += timedelta(days=offset_end)

        return start, end

    def _get_anchor_date(self) -> date:
        """Determine the anchor date for week lookups."""
        date_strs = []
        if self.item:
            if self.item.start_date:
                date_strs.append(self.item.start_date)
            if self.item.due_date:
                date_strs.append(self.item.due_date)
        else:
            start_text = self.start_date_entry.get().strip()
            due_text = self.due_date_entry.get().strip()
            if start_text:
                date_strs.append(start_text)
            if due_text:
                date_strs.append(due_text)

        for text in date_strs:
            try:
                return date.fromisoformat(text)
            except ValueError:
                continue

        return date.today()

    def _format_week_action_display(self, week_action: Dict[str, Any]) -> str:
        seg_name = self.segment_name_map.get(week_action.get("segment_description_id"), "").strip()
        seg_suffix = f" [{seg_name}]" if seg_name else ""
        return f"Weekly Tactic {week_action['week_start_date']}: {week_action['title']}{seg_suffix}"

    def _is_weekly_tactic_record(self) -> bool:
        return bool(self.item and self.item.item_type == "week")

    def _canonical_weekly_tactic_title(self, raw_title: str, annual_plan_element_id: Optional[str], start_date: Optional[str]) -> str:
        title = (raw_title or "").strip()
        if not title:
            return title

        if self.vps_manager and annual_plan_element_id and start_date:
            try:
                ape = self.vps_manager.db.conn.execute(
                    "SELECT key_field FROM annual_plan_elements WHERE id = ?",
                    (annual_plan_element_id,),
                ).fetchone()
                if ape and (ape["key_field"] or "").strip():
                    ws = date.fromisoformat(start_date)
                    week_of_year = ws.isocalendar().week
                    prefix = self.vps_manager.normalize_week_token(
                        self.vps_manager.shorten_pipe_prefix(ape["key_field"])
                    )
                    if prefix:
                        return f"{prefix} - W{week_of_year}"
            except Exception:
                pass

        parsed = split_action_item_title(title)
        if parsed.context and parsed.title:
            if "|" in parsed.title and re.search(r"\bW\s*\d+\b", parsed.title, flags=re.IGNORECASE):
                return parsed.title
        return title

    def _apply_record_type_ui(self):
        palette = semantic_colors()
        if self._is_weekly_tactic_record():
            self.record_type_badge.configure(
                text="Weekly Tactic",
                fg_color=palette["success_strong"],
                text_color=palette["on_strong"],
            )
            self.context_label.configure(text="Context (unused for Weekly Tactic):")
            self.title_context_entry.configure(state="normal")
            self.title_context_entry.delete(0, "end")
            self.title_context_entry.configure(state="disabled")
            return

        self.record_type_badge.configure(
            text="Action Item",
            fg_color=palette["surface_subtle"],
            text_color=palette["body_text"],
        )
        self.context_label.configure(text="Context:")
        self.title_context_entry.configure(state="normal")

    def load_item_data(self):
        """Load item data into form fields."""
        if not self.item:
            return

        self.who_var.set(self.item.who)
        self.selected_contact_id = self.item.contact_id
        self._apply_record_type_ui()
        parsed = split_action_item_title(self.item.title)
        if self._is_weekly_tactic_record():
            canonical_title = self._canonical_weekly_tactic_title(
                self.item.title,
                self.item.annual_plan_element_id,
                self.item.start_date,
            )
            if canonical_title and canonical_title != (self.item.title or "").strip():
                self.item.title = canonical_title
                self.db_manager.update_action_item(self.item, normalize_week_dates=False)
            self.title_entry.insert(0, canonical_title)
        else:
            if parsed.context:
                self.title_context_entry.insert(0, parsed.context)
            self.title_entry.insert(0, parsed.title or self.item.title)

        if self.item.description:
            self.description_text.insert("1.0", self.item.description)

        if self.item.next_action:
            self.next_action_text.insert("1.0", self.item.next_action)

        if self.item.start_date:
            self.start_date_entry.insert(0, self.item.start_date)

        if self.item.due_date:
            self.due_date_entry.insert(0, self.item.due_date)

        # Is Meeting
        self.is_meeting_var.set(self.item.is_meeting)

        # Meeting Start Time (read-only display)
        if self.item.meeting_start_time:
            # Format: show date and time (YYYY-MM-DD HH:MM)
            meeting_display = self.item.meeting_start_time[:16].replace(
                'T', ' ')
            self.meeting_time_label.configure(text=meeting_display)
        else:
            self.meeting_time_label.configure(text="Not scheduled")

        # Original Due Date (read-only display)
        if self.item.original_due_date:
            self.original_due_date_label.configure(
                text=self.item.original_due_date)
        else:
            self.original_due_date_label.configure(text="-")

        # Completed Date (read-only display)
        if self.item.completed_at:
            # Format: show date and time
            completed_display = self.item.completed_at[:19].replace('T', ' ')
            self.completed_at_label.configure(text=completed_display)
        else:
            self.completed_at_label.configure(text="-")

        # Priority factors
        if self.item.importance is not None:
            for k, v in PriorityFactors.IMPORTANCE.items():
                if v == self.item.importance:
                    self.importance_var.set(f"{k} ({v})")
                    break

        if self.item.urgency is not None:
            for k, v in PriorityFactors.URGENCY.items():
                if v == self.item.urgency:
                    self.urgency_var.set(f"{k} ({v})")
                    break

        if self.item.size is not None:
            for k, v in PriorityFactors.SIZE.items():
                if v == self.item.size:
                    self.size_var.set(f"{k} ({v})")
                    break

        if self.item.value is not None:
            for k, v in PriorityFactors.VALUE.items():
                if v == self.item.value:
                    self.value_var.set(f"{k} ({v})")
                    break

        if self.item.group:
            self.group_var.set(self.item.group)

        if self.item.category:
            self.category_var.set(self.item.category)

        if self.item.planned_minutes is not None:
            self.planned_minutes_entry.insert(
                0, str(self.item.planned_minutes))

        # Week Action
        if self.item.week_action_id and self.vps_manager:
            # Find the matching week action and set the display value
            for display, wa_id in self.week_action_options.items():
                if wa_id == self.item.week_action_id:
                    self.week_action_var.set(display)
                    break

        self.update_priority_display()

    def validate_due_date_on_edit(self):
        """
        Validate due date when manually edited.
        Shows error if due < start but doesn't auto-correct.
        """
        from datetime import datetime

        # Clear any previous error messages
        self.error_label.configure(text="")

        start_text = self.start_date_entry.get().strip()
        due_text = self.due_date_entry.get().strip()

        # Only validate if both dates have values
        if not start_text or not due_text:
            return

        try:
            start_date = datetime.strptime(start_text, "%Y-%m-%d").date()
            due_date = datetime.strptime(due_text, "%Y-%m-%d").date()

            if due_date < start_date:
                # Show error - user must fix it manually
                self.error_label.configure(text="Due must be >= Start")
        except ValueError:
            # Invalid date format - ignore for now
            pass

    def validate_and_adjust_due_date(self):
        """
        Validate and adjust due date based on start date.
        Rules:
        - If due date is blank → set to start date
        - If due date < start date → set to start date
        - If due date >= start date → no change
        """
        from datetime import datetime

        start_text = self.start_date_entry.get().strip()
        due_text = self.due_date_entry.get().strip()

        # Only validate if start date has a value
        if not start_text:
            return

        try:
            start_date = datetime.strptime(start_text, "%Y-%m-%d").date()
        except ValueError:
            # Invalid start date format, skip validation
            return

        # If due date is blank, set it to start date
        if not due_text:
            self.due_date_entry.delete(0, "end")
            self.due_date_entry.insert(0, start_text)
            return

        # If due date is present, check if it's less than start
        try:
            due_date = datetime.strptime(due_text, "%Y-%m-%d").date()
            if due_date < start_date:
                # Due date is less than start, set it to start
                self.due_date_entry.delete(0, "end")
                self.due_date_entry.insert(0, start_text)
        except ValueError:
            # Invalid due date format, set it to start date
            self.due_date_entry.delete(0, "end")
            self.due_date_entry.insert(0, start_text)

    def set_date(self, entry_widget, offset_days: int):
        """Set date field to today + offset_days."""
        from datetime import date, timedelta, datetime

        # Clear any previous error messages
        self.error_label.configure(text="")

        target_date = date.today() + timedelta(days=offset_days)

        # If setting due date, validate it won't be before start date
        if entry_widget == self.due_date_entry:
            start_text = self.start_date_entry.get().strip()
            if start_text:
                try:
                    start_date = datetime.strptime(
                        start_text, "%Y-%m-%d").date()
                    if target_date < start_date:
                        # Show error and don't change the date
                        self.error_label.configure(text="Due must be >= Start")
                        return
                except ValueError:
                    # Invalid start date format, allow the change
                    pass

        entry_widget.delete(0, "end")
        entry_widget.insert(0, target_date.strftime("%Y-%m-%d"))

        # If we just set the start date, validate and adjust due date
        if entry_widget == self.start_date_entry:
            self.validate_and_adjust_due_date()

    def adjust_date(self, entry_widget, days_delta: int):
        """Add or subtract days from the current date in the field, using weekend-aware logic."""
        from datetime import datetime

        # Clear any previous error messages
        self.error_label.configure(text="")

        # Load settings for weekend handling
        settings = AppSettings.load()

        current_text = entry_widget.get().strip()
        if not current_text:
            # If field is empty, use today as base
            base_date = datetime.now().date()
        else:
            # Parse the current date
            try:
                base_date = datetime.strptime(current_text, "%Y-%m-%d").date()
            except ValueError:
                # If invalid format, use today
                base_date = datetime.now().date()

        # Use weekend-aware date increment
        new_date = increment_date(
            base_date, days_delta, settings.include_saturday, settings.include_sunday)

        # If adjusting due date, validate it won't go below start date
        if entry_widget == self.due_date_entry:
            start_text = self.start_date_entry.get().strip()
            if start_text:
                try:
                    start_date = datetime.strptime(
                        start_text, "%Y-%m-%d").date()
                    if new_date < start_date:
                        # Show error and don't change the date
                        self.error_label.configure(text="Due must be >= Start")
                        return
                except ValueError:
                    # Invalid start date format, allow the change
                    pass

        # Apply the date change
        entry_widget.delete(0, "end")
        entry_widget.insert(0, new_date.strftime("%Y-%m-%d"))

        # If adjusting start date, handle due date based on current state
        if entry_widget == self.start_date_entry:
            due_text = self.due_date_entry.get().strip()

            # If due date exists and is valid, check if we should maintain the gap
            if due_text:
                try:
                    due_base = datetime.strptime(due_text, "%Y-%m-%d").date()
                    # If due was >= old start, maintain the gap by incrementing
                    if due_base >= base_date:
                        new_due = increment_date(
                            due_base, days_delta, settings.include_saturday, settings.include_sunday)
                        self.due_date_entry.delete(0, "end")
                        self.due_date_entry.insert(
                            0, new_due.strftime("%Y-%m-%d"))
                    else:
                        # Due was < start, so adjust it using validation
                        self.validate_and_adjust_due_date()
                except ValueError:
                    # Invalid due date format, adjust using validation
                    self.validate_and_adjust_due_date()
            else:
                # Due date is blank, adjust using validation
                self.validate_and_adjust_due_date()

    def apply_defaults_to_form(self):
        """Apply system and who-specific defaults to form fields for new items."""
        # First, get system defaults to check WHO field
        system_defaults = self.db_manager.get_defaults("system")

        # Apply WHO from system defaults if set and current WHO is empty or default
        if system_defaults and system_defaults.who:
            current_who = self.who_var.get()
            # Only set if WHO is empty or is the auto-filled first contact
            # This ensures system default WHO takes precedence
            if not current_who:
                self.who_var.set(system_defaults.who)
                # Try to match with a contact
                contacts = self.db_manager.get_all_contacts(active_only=True)
                for contact in contacts:
                    if contact.name == system_defaults.who:
                        self.selected_contact_id = contact.id
                        break

        # Now get the current WHO value (which may have been updated)
        who = self.who_var.get()
        who_defaults = self.db_manager.get_defaults("who", who)

        # Helper to get default value with precedence
        def get_default(field_name):
            if who_defaults:
                val = getattr(who_defaults, field_name, None)
                if val is not None:
                    return val
            if system_defaults:
                val = getattr(system_defaults, field_name, None)
                if val is not None:
                    return val
            return None

        # Apply priority factor defaults
        importance = get_default("importance")
        if importance is not None:
            for k, v in PriorityFactors.IMPORTANCE.items():
                if v == importance:
                    self.importance_var.set(f"{k} ({v})")
                    break

        urgency = get_default("urgency")
        if urgency is not None:
            for k, v in PriorityFactors.URGENCY.items():
                if v == urgency:
                    self.urgency_var.set(f"{k} ({v})")
                    break

        size = get_default("size")
        if size is not None:
            for k, v in PriorityFactors.SIZE.items():
                if v == size:
                    self.size_var.set(f"{k} ({v})")
                    break

        value = get_default("value")
        if value is not None:
            for k, v in PriorityFactors.VALUE.items():
                if v == value:
                    self.value_var.set(f"{k} ({v})")
                    break

        # Apply organization defaults
        group = get_default("group")
        if group:
            self.group_var.set(group)

        category = get_default("category")
        if category:
            self.category_var.set(category)

        planned_minutes = get_default("planned_minutes")
        if planned_minutes is not None:
            self.planned_minutes_entry.delete(0, "end")
            self.planned_minutes_entry.insert(0, str(planned_minutes))

        # Apply date offsets if set
        start_offset = get_default("start_offset_days")
        if start_offset is not None:
            self.set_date(self.start_date_entry, start_offset)

        due_offset = get_default("due_offset_days")
        if due_offset is not None:
            self.set_date(self.due_date_entry, due_offset)

        self.update_priority_display()

    def on_who_changed(self):
        """Handle when Who field changes - re-apply defaults for fields that are empty."""
        if self.item_id:
            # Don't re-apply defaults when editing existing items
            return

        # Only re-apply to empty fields
        current_importance = self.importance_var.get()
        current_urgency = self.urgency_var.get()
        current_size = self.size_var.get()
        current_value = self.value_var.get()
        current_group = self.group_var.get()
        current_category = self.category_var.get()
        current_planned = self.planned_minutes_entry.get()

        # Get new who-specific defaults
        who = self.who_var.get()
        who_defaults = self.db_manager.get_defaults("who", who)
        system_defaults = self.db_manager.get_defaults("system")

        # Helper to get default value with precedence
        def get_default(field_name):
            if who_defaults:
                val = getattr(who_defaults, field_name, None)
                if val is not None:
                    return val
            if system_defaults:
                val = getattr(system_defaults, field_name, None)
                if val is not None:
                    return val
            return None

        # Re-apply defaults only to empty fields
        if not current_importance:
            importance = get_default("importance")
            if importance is not None:
                for k, v in PriorityFactors.IMPORTANCE.items():
                    if v == importance:
                        self.importance_var.set(f"{k} ({v})")
                        break

        if not current_urgency:
            urgency = get_default("urgency")
            if urgency is not None:
                for k, v in PriorityFactors.URGENCY.items():
                    if v == urgency:
                        self.urgency_var.set(f"{k} ({v})")
                        break

        if not current_size:
            size = get_default("size")
            if size is not None:
                for k, v in PriorityFactors.SIZE.items():
                    if v == size:
                        self.size_var.set(f"{k} ({v})")
                        break

        if not current_value:
            value = get_default("value")
            if value is not None:
                for k, v in PriorityFactors.VALUE.items():
                    if v == value:
                        self.value_var.set(f"{k} ({v})")
                        break

        if not current_group:
            group = get_default("group")
            if group:
                self.group_var.set(group)

        if not current_category:
            category = get_default("category")
            if category:
                self.category_var.set(category)

        if not current_planned:
            planned_minutes = get_default("planned_minutes")
            if planned_minutes is not None:
                self.planned_minutes_entry.delete(0, "end")
                self.planned_minutes_entry.insert(0, str(planned_minutes))

        # Apply date offsets if dates are empty
        if not self.start_date_entry.get():
            start_offset = get_default("start_offset_days")
            if start_offset is not None:
                self.set_date(self.start_date_entry, start_offset)

        if not self.due_date_entry.get():
            due_offset = get_default("due_offset_days")
            if due_offset is not None:
                self.set_date(self.due_date_entry, due_offset)

        self.update_priority_display()

    def on_who_click(self, event=None):
        """Handle click in Who field - show all contacts if field is empty or has selection."""
        # Wait a moment for click to complete
        self.after(50, self._show_contacts_on_click)

    def _show_contacts_on_click(self):
        """Show contacts after click delay."""
        current_text = self.who_var.get().strip()

        # If field is empty or user clicked, show all contacts
        if not current_text:
            self.show_contact_suggestions(None)
        else:
            # Show filtered contacts if there's text
            contacts = self.db_manager.search_contacts(
                current_text, active_only=True)
            if contacts:
                self.show_contact_suggestions(contacts)

    def on_who_search(self, event=None):
        """Handle typing in Who field - show matching contacts."""
        search_term = self.who_var.get().strip()

        # Cancel any pending hide job
        if self.suggestions_hide_job:
            self.after_cancel(self.suggestions_hide_job)
            self.suggestions_hide_job = None

        # Hide suggestions if field is empty
        if not search_term:
            self.hide_contact_suggestions()
            self.selected_contact_id = None
            return

        # Search contacts
        contacts = self.db_manager.search_contacts(
            search_term, active_only=True)

        # Show suggestions
        self.show_contact_suggestions(contacts)

    def show_contact_suggestions(self, contacts=None):
        """Show dropdown with contact suggestions."""
        # Cancel any pending hide job
        if self.suggestions_hide_job:
            self.after_cancel(self.suggestions_hide_job)
            self.suggestions_hide_job = None

        # Hide existing suggestions
        self.hide_contact_suggestions()

        # Get all contacts if none provided
        if contacts is None:
            contacts = self.db_manager.get_all_contacts(active_only=True)

        if not contacts:
            return

        # Update widget to get accurate positioning
        self.who_entry.update_idletasks()

        # Get absolute position of who_entry
        entry_x = self.who_entry.winfo_rootx() - self.winfo_rootx()
        entry_y = self.who_entry.winfo_rooty() - self.winfo_rooty()
        entry_height = self.who_entry.winfo_height()

        # Create suggestions frame positioned below the entry
        # Use regular frame (not scrollable) since we limit to 10 items
        # This prevents scrollbar interference with Title field navigation
        self.contact_suggestions_frame = ctk.CTkFrame(
            self,
            fg_color="gray20",
            width=318,
            # Height for up to 10 items
            height=min(len(contacts[:10]) * 35 + 10, 360)
        )
        self.contact_suggestions_frame.place(
            x=entry_x,
            y=entry_y + entry_height + 2
        )

        # Bind click outside to hide dropdown
        self.bind('<Button-1>', self.on_click_outside_dropdown, add='+')

        # Limit to 10 suggestions
        for idx, contact in enumerate(contacts[:10]):
            btn = ctk.CTkButton(
                self.contact_suggestions_frame,
                text=f"{contact.name}" +
                (f" ({contact.contact_type})" if contact.contact_type else ""),
                anchor="w",
                **button_style("secondary"),
                height=30,
                command=lambda c=contact: self.select_contact(c)
            )
            btn.pack(fill="x", padx=2, pady=1)

        # Raise to top
        self.contact_suggestions_frame.lift()

    def cancel_hide_suggestions(self):
        """Cancel scheduled hide of suggestions."""
        if self.suggestions_hide_job:
            self.after_cancel(self.suggestions_hide_job)
            self.suggestions_hide_job = None

    def schedule_hide_suggestions(self):
        """Schedule hiding suggestions after a delay."""
        if self.suggestions_hide_job:
            self.after_cancel(self.suggestions_hide_job)
        self.suggestions_hide_job = self.after(
            300, self.hide_contact_suggestions)

    def hide_contact_suggestions(self):
        """Hide contact suggestions dropdown."""
        if self.contact_suggestions_frame:
            self.contact_suggestions_frame.destroy()
            self.contact_suggestions_frame = None
        if self.suggestions_hide_job:
            self.after_cancel(self.suggestions_hide_job)
            self.suggestions_hide_job = None

    def on_click_outside_dropdown(self, event):
        """Hide dropdown when clicking outside of it."""
        if not self.contact_suggestions_frame:
            return

        # Get the widget that was clicked
        clicked_widget = event.widget

        # Check if click is inside the dropdown or the who_entry
        if clicked_widget == self.who_entry or clicked_widget == self.contact_suggestions_frame:
            return

        # Check if clicked widget is a child of the dropdown
        parent = clicked_widget
        while parent:
            if parent == self.contact_suggestions_frame:
                return
            parent = parent.master if hasattr(parent, 'master') else None

        # Click was outside - hide the dropdown
        self.hide_contact_suggestions()

    def select_contact(self, contact):
        """Select a contact from the suggestions."""
        self.who_var.set(contact.name)
        self.selected_contact_id = contact.id

        # Hide suggestions immediately
        self.hide_contact_suggestions()

        # Move focus to title field
        self.after(50, lambda: self.title_entry.focus_set())

        # Re-apply defaults for this contact
        self.on_who_changed()

    def add_new_contact(self):
        """Open dialog to add a new contact and select it."""
        from .edit_contact import EditContactDialog

        # Hide dropdown before opening dialog
        self.hide_contact_suggestions()

        # Get current text as suggested name
        suggested_name = self.who_var.get().strip()

        dialog = EditContactDialog(self, self.db_manager, contact_id=None)

        # Pre-fill name if provided
        if suggested_name:
            dialog.name_var.set(suggested_name)

        dialog.wait_window()

        # If a contact was created, search for it and select it
        if suggested_name:
            contact = self.db_manager.get_contact_by_name(suggested_name)
            if contact:
                self.select_contact(contact)

    def extract_factor_value(self, text: str) -> Optional[int]:
        """Extract numeric value from factor string like 'High (10)'."""
        if not text:
            return None
        try:
            return int(text.split("(")[1].split(")")[0])
        except Exception:
            return None

    def save_item(self):
        """Save the item."""
        try:
            # Create or update item
            if self.item_id:
                item = self.item
            else:
                item = ActionItem(who="", title="")

            # Set fields
            item.who = self.who_var.get().strip()
            item.contact_id = self.selected_contact_id
            item.title = build_action_item_title(
                self.title_context_entry.get(),
                self.title_entry.get(),
            ).strip()
            if item.item_type == "week":
                item.title = self._canonical_weekly_tactic_title(
                    item.title,
                    item.annual_plan_element_id,
                    item.start_date,
                )
            item.description = self.description_text.get(
                "1.0", "end").strip() or None
            item.next_action = self.next_action_text.get(
                "1.0", "end").strip() or None
            item.start_date = self.start_date_entry.get().strip() or None
            item.due_date = self.due_date_entry.get().strip() or None
            item.is_meeting = self.is_meeting_var.get()

            # Priority factors
            item.importance = self.extract_factor_value(
                self.importance_var.get())
            item.urgency = self.extract_factor_value(self.urgency_var.get())
            item.size = self.extract_factor_value(self.size_var.get())
            item.value = self.extract_factor_value(self.value_var.get())

            # Organization
            item.group = self.group_var.get().strip() or None
            item.category = self.category_var.get().strip() or None

            # Planned minutes
            planned_text = self.planned_minutes_entry.get().strip()
            item.planned_minutes = int(planned_text) if planned_text else None

            # VSP fields
            # Week Action (from dropdown if available, otherwise from constructor)
            week_action_display = self.week_action_var.get().strip()
            if week_action_display and week_action_display != "(None)" and hasattr(self, 'week_action_options'):
                # User selected a week action from dropdown
                item.week_action_id = self.week_action_options.get(
                    week_action_display)
            elif week_action_display == "(None)":
                # User explicitly selected "(None)" to clear the week action
                item.week_action_id = None
            elif not self.item_id:
                # New item: use constructor parameter if no dropdown selection
                item.week_action_id = self.week_action_id
            # For existing items with no dropdown change, week_action_id remains unchanged

            # Segment Description (from constructor for new items)
            if not self.item_id:
                item.segment_description_id = self.segment_description_id

            # Validate dates: due date must be >= start date
            if item.start_date and item.due_date:
                try:
                    start = datetime.strptime(
                        item.start_date, "%Y-%m-%d").date()
                    due = datetime.strptime(item.due_date, "%Y-%m-%d").date()
                    if due < start:
                        self.error_label.configure(
                            text="Error: Due date cannot be before Start date")
                        return
                except ValueError:
                    # Let the validator handle invalid date formats
                    pass

            # Validate
            errors = Validator.validate_action_item(item)
            if errors:
                self.error_label.configure(text=errors[0].message)
                return

            # Save
            if self.item_id:
                self.db_manager.update_action_item(item)
            else:
                self.db_manager.create_action_item(item, apply_defaults=True)
                self.item_id = item.id  # Update item_id after creating new item
                self.item = item  # Store the item reference

            # Clear error message on successful save
            self.error_label.configure(text="✓ Saved")
            # Reset the message after 2 seconds
            self.after(2000, lambda: self.error_label.configure(text=""))

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")

    def save_and_new(self):
        """Save and open a new item editor."""
        callback = self.on_close_callback  # Save callback before save closes this dialog
        self.save_item()
        if self.winfo_exists():
            # Item was saved successfully (window still exists)
            self.on_dialog_close()
            ItemEditorDialog(self.master, self.db_manager,
                             vps_manager=self.vps_manager, on_close_callback=callback)

    def save_and_close(self):
        """Save the item and close the dialog."""
        self.save_item()
        # Only close if save was successful (no error shown)
        if self.winfo_exists() and not self.error_label.cget("text").startswith("Error:"):
            self.on_dialog_close()

    def duplicate_item(self):
        """Save current changes, duplicate the saved item, and open it in a new editor."""
        if self.item_id:
            # First save any current changes
            self.save_item()

            # Check if save was successful (no error)
            if self.winfo_exists() and not self.error_label.cget("text").startswith("Error:"):
                # Now duplicate the saved version
                new_id = self.db_manager.duplicate_action_item(self.item_id)
                if new_id:
                    # Open the duplicate in a NEW editor window (don't close current one)
                    ItemEditorDialog(self.master, self.db_manager, new_id,
                                     vps_manager=self.vps_manager, on_close_callback=self.on_close_callback)

    def create_followup(self):
        """Create a follow-up item linked to the current item."""
        if self.item_id:
            new_id = self.db_manager.create_followup_item(self.item_id)
            self.on_dialog_close()
            if new_id:
                ItemEditorDialog(self.master, self.db_manager, new_id,
                                 vps_manager=self.vps_manager, on_close_callback=self.on_close_callback)

    def complete_item(self):
        """Mark item as complete."""
        if self.item_id:
            self.db_manager.complete_action_item(self.item_id)
            self.on_dialog_close()

    def delete_item(self):
        """Delete the item with confirmation."""
        if not self.item_id:
            return

        # Get item for title
        item = self.db_manager.get_action_item(self.item_id)
        if not item:
            return

        # Check if item has children - prevent deletion if it does
        children = self.db_manager.get_children(self.item_id)
        if children:
            # Show error message - deletion not allowed
            error_dialog = ctk.CTkToplevel(self)
            error_dialog.title("Cannot Delete")
            error_dialog.geometry("400x150")
            error_dialog.transient(self)
            error_dialog.grab_set()

            # Center on parent
            error_dialog.update_idletasks()
            x = self.winfo_rootx() + (self.winfo_width() - 400) // 2
            y = self.winfo_rooty() + (self.winfo_height() - 150) // 2
            error_dialog.geometry(f"400x150+{x}+{y}")

            message = (
                f"Cannot delete this item.\n\n"
                f"This item has {len(children)} child item(s).\n"
                f"Please remove or reassign the children first."
            )

            ctk.CTkLabel(
                error_dialog,
                text=message,
                wraplength=350,
                justify="center"
            ).pack(pady=20)

            ctk.CTkButton(
                error_dialog,
                text="OK",
                command=error_dialog.destroy,
                width=100
            ).pack(pady=10)

            return  # Don't proceed with deletion

        # Create confirmation dialog
        dialog = DeleteConfirmDialog(self, item.title)
        dialog.wait_window()

        if dialog.confirmed:
            # Delete the item
            self.db_manager.delete_action_item(self.item_id)
            self.on_dialog_close()

    def update_priority_display(self):
        """Update the priority score display."""
        importance = self.extract_factor_value(self.importance_var.get()) or 0
        urgency = self.extract_factor_value(self.urgency_var.get()) or 0
        size = self.extract_factor_value(self.size_var.get()) or 0
        value = self.extract_factor_value(self.value_var.get()) or 0

        if any(f == 0 for f in [importance, urgency, size, value]):
            score = 0
        else:
            score = importance * urgency * size * value

        self.priority_label.configure(
            text=f"{score} ({importance}×{urgency}×{size}×{value})"
        )

    def start_resize(self, event):
        """Start resizing the text fields."""
        self.resizing = True
        self.resize_start_y = event.y_root

    def do_resize(self, event):
        """Handle the resizing between panel 1 (top form) and panel 2 (tabs)."""
        if not self.resizing:
            return
        if not self.is_single_column:
            return

        delta = event.y_root - self.resize_start_y
        self.resize_start_y = event.y_root

        top_height = self.left_col.cget("height") or self.left_col.winfo_height()
        middle_height = self.right_col.cget("height") or self.right_col.winfo_height()

        new_top_height = max(260, int(top_height + delta))
        new_middle_height = max(220, int(middle_height - delta))

        self.left_col.grid_propagate(False)
        self.right_col.grid_propagate(False)
        self.left_col.configure(height=new_top_height)
        self.right_col.configure(height=new_middle_height)
        self.tabview.configure(height=max(180, new_middle_height - 24))

    def on_resize(self, event):
        """Handle window resize to switch between 2-column and 1-column layout."""
        if event.widget != self:
            return

        width = event.width
        # Only update if width changed significantly (avoid flickering)
        if abs(width - self.last_width) < 50:
            return

        self.last_width = width

        # Switch to single column if window is narrow
        if width < 900:
            # Single column layout
            self.is_single_column = True
            self.left_col.grid(row=0, column=0, columnspan=2,
                               sticky="nsew", padx=0, pady=(0, 5))
            self.separator_frame.grid(
                row=1, column=0, columnspan=2, sticky="ew", padx=0, pady=(0, 5)
            )
            self.right_col.grid(row=2, column=0, columnspan=2,
                                sticky="nsew", padx=0, pady=(0, 0))
        else:
            # Two column layout
            self.is_single_column = False
            self.separator_frame.grid_forget()
            self.left_col.grid_propagate(True)
            self.right_col.grid_propagate(True)
            self.left_col.grid(
                row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)
            self.right_col.grid(
                row=0, column=1, sticky="nsew", padx=(5, 0), pady=0)

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        # Schedule centering after dialog is fully rendered
        self.after(10, self._do_center)

    def _do_center(self):
        """Actually perform the centering after dialog is rendered."""
        # Use fixed dimensions from geometry call
        dialog_width = 600
        dialog_height = 1000

        # Force complete update of both windows
        self.master.update()
        self.update()

        # Get parent window position and size using rootx/rooty for absolute screen coordinates
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure dialog is not positioned off-screen
        x = max(0, x)
        y = max(0, y)

        # Set geometry with position
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Final update to apply positioning
        self.update_idletasks()

    def on_dialog_close(self):
        """Handle dialog close event - call callback and destroy."""
        if self.on_close_callback:
            try:
                self.on_close_callback()
            except Exception:
                pass  # Ignore callback errors during close
        self.destroy()

    def view_parent_item(self, parent_id: str):
        """Open the parent item in a new editor dialog."""
        callback = self.on_close_callback  # Save callback before destroying
        self.destroy()
        ItemEditorDialog(self.master, self.db_manager, parent_id,
                         vps_manager=self.vps_manager, on_close_callback=callback)

    def create_sub_item(self):
        """Create one child task for each line in the Next Action field."""
        if not self.item_id:
            return

        # Get the Next Action text
        next_action_text = self.next_action_text.get("1.0", "end-1c").strip()

        if not next_action_text:
            import tkinter.messagebox as messagebox
            messagebox.showwarning(
                "No Next Actions",
                "Please add tasks to the Next Action field (one per line) before creating tasks."
            )
            return

        # Split into lines and filter out empty lines
        lines = [line.strip()
                 for line in next_action_text.split('\n') if line.strip()]

        if not lines:
            import tkinter.messagebox as messagebox
            messagebox.showwarning(
                "No Next Actions",
                "Please add tasks to the Next Action field (one per line) before creating tasks."
            )
            return

        # Get the current item
        parent_item = self.db_manager.get_action_item(self.item_id)
        if not parent_item:
            return

        # Create one child item for each line
        created_count = 0
        for line in lines:
            # Create new child item
            child_item = ActionItem(
                who=parent_item.who,
                contact_id=parent_item.contact_id,
                title=f"{parent_item.title} - {line}",  # Append line as suffix
                description=line,  # Line contents as description
                next_action=None,
                parent_id=self.item_id,  # Set as child of current item
                start_date=parent_item.start_date,  # Same dates
                due_date=parent_item.due_date,
                importance=parent_item.importance,
                urgency=parent_item.urgency,
                size=parent_item.size,
                value=parent_item.value,
                group=parent_item.group,
                category=parent_item.category,
                planned_minutes=parent_item.planned_minutes,
                week_action_id=parent_item.week_action_id,
                segment_description_id=parent_item.segment_description_id,
                is_habit=parent_item.is_habit,
                status="open"
            )

            # Save the child item
            self.db_manager.create_action_item(
                child_item, apply_defaults=False)
            created_count += 1

        # Show success message
        import tkinter.messagebox as messagebox
        messagebox.showinfo(
            "Tasks Created",
            f"Created {created_count} child task(s) from Next Action list."
        )

        # Refresh the display if there's a callback
        if self.on_close_callback:
            try:
                self.on_close_callback()
            except Exception:
                pass

    def show_related(self):
        """Show list of related items (parent and children) in a new dialog."""
        if not self.item_id:
            return

        # Open related items dialog
        ShowRelatedDialog(self, self.db_manager, self.item_id, self.item.title if self.item else "Item",
                          vps_manager=self.vps_manager, on_close_callback=self.on_close_callback)

    def set_parent(self):
        """Open dialog to set/change the parent item."""
        if not self.item_id:
            return

        # Open set parent dialog
        SetParentDialog(self, self.db_manager, self.item_id, self.item.title if self.item else "Item",
                        vps_manager=self.vps_manager, on_close_callback=self.on_close_callback)

    def set_weekly_tactic(self):
        """Open dialog to set/change the weekly tactic association."""
        if not self.vps_manager:
            messagebox.showinfo("Weekly Tactic", "VSP data is not available.")
            return

        current_title = self.item.title if self.item else (self.title_entry.get().strip() or "Action Item")
        anchor_date = self._get_anchor_date()
        dialog = SetWeeklyTacticDialog(
            parent=self,
            db_manager=self.db_manager,
            vps_manager=self.vps_manager,
            item_id=self.item_id,
            item_title=current_title,
            first_day_of_week=self.first_day_of_week,
            anchor_date=anchor_date,
            segment_name_map=self.segment_name_map,
            on_select=self.apply_weekly_tactic_selection
        )
        self.logger.info(
            "[set_weekly_tactic] opened_dialog item_id=%s item_title=%s anchor=%s",
            self.item_id,
            current_title,
            anchor_date.isoformat(),
        )
        dialog.wait_window()

    def apply_weekly_tactic_selection(self, week_action_id: Optional[str], segment_id: Optional[str],
                                      display: str, week_item_id: Optional[str]):
        """Callback after selecting a weekly tactic."""
        if self.item_id:
            current_item = self.db_manager.get_action_item(self.item_id)
            if current_item:
                self.logger.info(
                    "[apply_weekly_tactic_selection] item_id=%s selected_week_action_id=%s selected_week_item_id=%s segment_id=%s",
                    self.item_id,
                    week_action_id,
                    week_item_id,
                    segment_id,
                )
                if week_item_id and week_item_id != current_item.id:
                    current_item.parent_id = week_item_id
                if week_action_id:
                    current_item.week_action_id = week_action_id
                current_item.segment_description_id = segment_id or current_item.segment_description_id
                if current_item.item_type == "week":
                    selected_week_item = self.db_manager.get_action_item(week_item_id) if week_item_id else None
                    if selected_week_item:
                        current_item.title = selected_week_item.title
                    current_item.title = self._canonical_weekly_tactic_title(
                        current_item.title,
                        current_item.annual_plan_element_id,
                        current_item.start_date,
                    )
                self.db_manager.update_action_item(current_item)

            self.destroy()
            ItemEditorDialog(
                self.master,
                self.db_manager,
                self.item_id,
                vps_manager=self.vps_manager,
                on_close_callback=self.on_close_callback
            )
        else:
            self.week_action_id = week_action_id
            if segment_id:
                self.segment_description_id = segment_id
            if display not in self.week_action_options:
                self.week_action_options[display] = week_action_id
                self.week_action_display_values.append(display)
                self.week_action_combo.configure(values=self.week_action_display_values)
            self.week_action_var.set(display)

    def create_calendar_event(self):
        """Create a Google Calendar event linked to this item."""
        if not self.item_id:
            # Save the item first if it's new
            if not self.save_item_if_needed():
                return

        # Open calendar dialog
        from .calendar_dialog import CalendarEventDialog
        dialog = CalendarEventDialog(self, self.db_manager, self.item_id)
        dialog.wait_window()

        # Refresh item data and notes display to show the new calendar link
        if dialog.result:
            # Reload the item to get updated is_meeting and meeting_start_time
            self.item = self.db_manager.get_action_item(self.item_id)
            # Update the is_meeting checkbox to reflect the change
            self.is_meeting_var.set(self.item.is_meeting)
            # Update the meeting time display
            if self.item.meeting_start_time:
                meeting_display = self.item.meeting_start_time[:16].replace(
                    'T', ' ')
                self.meeting_time_label.configure(text=meeting_display)
            else:
                self.meeting_time_label.configure(text="Not scheduled")
            # Refresh notes/links display
            self.load_notes()

    def load_notes(self):
        """Load and display Obsidian notes for this item."""
        if not self.item_id:
            return

        # Clear current notes
        for widget in self.notes_frame.winfo_children():
            widget.destroy()

        # Get notes (obsidian_note type links)
        links = self.db_manager.get_item_links(self.item_id)
        notes = [link for link in links if link.link_type == "obsidian_note"]

        if not notes:
            ctk.CTkLabel(
                self.notes_frame,
                text="No notes yet",
                text_color="gray"
            ).pack(pady=10)
            return

        # Display each note
        for note in notes:
            self.create_note_row(note)

    def create_note_row(self, note: ItemLink):
        """Create a row for a note link."""
        frame = ctk.CTkFrame(self.notes_frame)
        frame.pack(fill="x", pady=2, padx=5)

        # Note icon and label
        label_text = note.label or "Untitled Note"
        ctk.CTkLabel(frame, text=f"📝 {label_text}", anchor="w").pack(
            side="left", fill="x", expand=True, padx=5)

        # Open button
        btn_open = ctk.CTkButton(
            frame,
            text="Open",
            width=60,
            command=lambda: self.open_note(note)
        )
        btn_open.pack(side="left", padx=2)

        # Delete button
        btn_delete = ctk.CTkButton(
            frame,
            text="×",
            width=30,
            **button_style("danger"),
            command=lambda: self.delete_note(note.id)
        )
        btn_delete.pack(side="left", padx=2)

    def save_item_if_needed(self) -> bool:
        """
        Save the item if it's new (no item_id yet).
        Returns True if successful or already has ID, False if validation fails.
        """
        if self.item_id:
            # Already has an ID, nothing to do
            return True

        try:
            # Create new item
            item = ActionItem(who="", title="")

            # Set fields
            item.who = self.who_var.get().strip()
            item.contact_id = self.selected_contact_id
            item.title = build_action_item_title(
                self.title_context_entry.get(),
                self.title_entry.get(),
            ).strip()
            if item.item_type == "week":
                item.title = self._canonical_weekly_tactic_title(
                    item.title,
                    item.annual_plan_element_id,
                    item.start_date,
                )
            item.description = self.description_text.get(
                "1.0", "end").strip() or None
            item.next_action = self.next_action_text.get(
                "1.0", "end").strip() or None
            item.start_date = self.start_date_entry.get().strip() or None
            item.due_date = self.due_date_entry.get().strip() or None
            item.is_meeting = self.is_meeting_var.get()

            # Priority factors
            item.importance = self.extract_factor_value(
                self.importance_var.get())
            item.urgency = self.extract_factor_value(self.urgency_var.get())
            item.size = self.extract_factor_value(self.size_var.get())
            item.value = self.extract_factor_value(self.value_var.get())

            # Organization
            item.group = self.group_var.get().strip() or None
            item.category = self.category_var.get().strip() or None

            # Planned minutes
            planned_text = self.planned_minutes_entry.get().strip()
            item.planned_minutes = int(planned_text) if planned_text else None

            # Validate dates
            if item.start_date and item.due_date:
                try:
                    start = datetime.strptime(
                        item.start_date, "%Y-%m-%d").date()
                    due = datetime.strptime(item.due_date, "%Y-%m-%d").date()
                    if due < start:
                        self.error_label.configure(
                            text="Error: Due date cannot be before Start date")
                        return False
                except ValueError:
                    pass

            # Validate
            errors = Validator.validate_action_item(item)
            if errors:
                self.error_label.configure(text=errors[0].message)
                return False

            # Save and get the ID
            self.db_manager.create_action_item(item, apply_defaults=True)
            self.item_id = item.id
            self.item = item

            # Clear the notes frame and reload to show it's ready for notes
            for widget in self.notes_frame.winfo_children():
                widget.destroy()
            self.load_notes()

            # Update window title
            self.title("Edit Action Item")

            return True

        except Exception as e:
            self.error_label.configure(text=f"Error saving item: {str(e)}")
            return False

    def create_note(self):
        """Open dialog to create a new Obsidian note."""
        # Save item first if it's new
        if not self.save_item_if_needed():
            return

        # Check if Obsidian is configured
        from ..app_settings import AppSettings
        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(
                text="Error: Please configure Obsidian vault in Settings first")
            return

        try:
            CreateNoteDialog(self, self.db_manager, "action_item",
                             self.item_id, self.item.title if self.item else "Item")
        except Exception as e:
            self.error_label.configure(
                text=f"Error opening note dialog: {str(e)}")

    def link_existing_note(self):
        """Open dialog to link an existing note file."""
        # Save item first if it's new
        if not self.save_item_if_needed():
            return

        LinkNoteDialog(self, self.db_manager, "action_item", self.item_id)

    def open_note(self, note: ItemLink):
        """Open note in Obsidian."""
        from ..app_settings import AppSettings
        from ..obsidian_utils import open_in_obsidian

        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(
                text="Error: Obsidian vault not configured in Settings")
            return

        try:
            open_in_obsidian(note.url, settings.obsidian_vault_path)
        except Exception as e:
            self.error_label.configure(text=f"Error opening note: {str(e)}")

    def delete_note(self, note_id: str):
        """Delete a note link."""
        # Ask for confirmation
        # For simplicity, just delete without confirmation for now
        self.db_manager.delete_item_link(note_id)
        self.load_notes()


class ShowRelatedDialog(ctk.CTkToplevel):
    """Dialog for showing related items (parent and children)."""

    def __init__(self, parent, db_manager: 'DatabaseManager', current_item_id: str, current_title: str, vps_manager=None, on_close_callback=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_item_id = current_item_id
        self.current_title = current_title
        self.vps_manager = vps_manager
        self.on_close_callback = on_close_callback
        self.palette = semantic_colors()

        self.title(f"Related Items: {current_title}")
        self.geometry("900x700")

        # Create UI
        self.create_ui()

        # Load related items
        self.refresh()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.center_on_parent()

    def create_ui(self):
        """Create the UI components."""
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            header_frame,
            text=f"Related Items: {self.current_title}",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=10, pady=10)

        # Scrollable frame for related items list
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Button frame
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)

        btn_close = ctk.CTkButton(
            btn_frame, text="Close", command=self.destroy, width=100, **button_style("primary"))
        btn_close.pack(side="right", padx=5)

    def refresh(self):
        """Refresh the list of related items (parent and children)."""
        # Clear current list
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        current_row = 0

        # Get current item to check for parent
        current_item = self.db_manager.get_action_item(self.current_item_id)

        # Show parent section if exists
        if current_item and current_item.parent_id:
            parent_item = self.db_manager.get_action_item(
                current_item.parent_id)
            if parent_item:
                # Parent section header
                parent_header = ctk.CTkFrame(
                    self.scroll_frame, fg_color=self.palette["primary"])
                parent_header.grid(row=current_row, column=0,
                                   sticky="ew", pady=(0, 5), padx=5)
                ctk.CTkLabel(
                    parent_header,
                    text="PARENT ITEM",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=self.palette["on_primary"]
                ).pack(pady=5)
                current_row += 1

                # Create header row for parent
                self.create_header_row(current_row)
                current_row += 1

                # Display parent
                self.create_item_row(parent_item, current_row)
                current_row += 1

                # Add spacing
                ctk.CTkLabel(self.scroll_frame, text="").grid(
                    row=current_row, column=0, pady=10)
                current_row += 1

        # Get children
        children = self.db_manager.get_children(self.current_item_id)

        # Show children section
        if children:
            # Children section header
            children_header = ctk.CTkFrame(
                self.scroll_frame, fg_color=self.palette["primary"])
            children_header.grid(row=current_row, column=0,
                                 sticky="ew", pady=(0, 5), padx=5)
            ctk.CTkLabel(
                children_header,
                text="CHILD ITEMS",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=self.palette["on_primary"]
            ).pack(pady=5)
            current_row += 1

            # Create header row for children
            self.create_header_row(current_row)
            current_row += 1

            # Display each child
            for child in children:
                self.create_item_row(child, current_row)
                current_row += 1
        else:
            # Only show "no children" message if there's also no parent
            if not (current_item and current_item.parent_id):
                ctk.CTkLabel(
                    self.scroll_frame,
                    text="No related items found",
                    font=ctk.CTkFont(size=14),
                    text_color=self.palette["body_text"],
                ).grid(row=current_row, column=0, pady=20)
            elif current_row > 0:
                # There is a parent but no children
                children_header = ctk.CTkFrame(
                    self.scroll_frame, fg_color=self.palette["primary"])
                children_header.grid(
                    row=current_row, column=0, sticky="ew", pady=(0, 5), padx=5)
                ctk.CTkLabel(
                    children_header,
                    text="CHILD ITEMS",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=self.palette["on_primary"]
                ).pack(pady=5)
                current_row += 1

                ctk.CTkLabel(
                    self.scroll_frame,
                    text="No child items found",
                    font=ctk.CTkFont(size=12),
                    text_color=self.palette["body_text"],
                ).grid(row=current_row, column=0, pady=10)

    def create_header_row(self, row: int):
        """Create a header row for items."""
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color=self.palette["surface_subtle"])
        header_frame.grid(row=row, column=0, sticky="ew", pady=(0, 5), padx=5)
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="Immediate Step (Who)",
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
            text_color=self.palette["body_text"],
        ).grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        ctk.CTkLabel(header_frame, text="Priority", width=70, font=ctk.CTkFont(weight="bold"), text_color=self.palette["body_text"]).grid(
            row=0, column=1, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Due Date", width=110, font=ctk.CTkFont(weight="bold"), text_color=self.palette["body_text"]).grid(
            row=0, column=2, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Status", width=80, font=ctk.CTkFont(weight="bold"), text_color=self.palette["body_text"]).grid(
            row=0, column=3, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Actions", width=80, font=ctk.CTkFont(weight="bold"), text_color=self.palette["body_text"]).grid(
            row=0, column=4, padx=5, pady=5
        )

    def create_item_row(self, item: ActionItem, row: int):
        """Create a row for an item (parent or child)."""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
        frame.grid_columnconfigure(0, weight=1)

        # Title and who
        info_text = f"{item.title}"
        if item.who:
            info_text += f" ({item.who})"

        title_label = ctk.CTkLabel(
            frame,
            text=info_text,
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=self.palette["body_text"],
        )
        title_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # Priority
        priority_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=70,
            fg_color=self.palette["surface_subtle"],
            text_color=self.palette["body_text"],
        )
        priority_label.grid(row=0, column=1, padx=5, pady=5)

        # Due date
        due_text = item.due_date if item.due_date else "-"
        due_label = ctk.CTkLabel(frame, text=due_text, width=110, text_color=self.palette["body_text"])
        due_label.grid(row=0, column=2, padx=5, pady=5)

        # Status
        status_label = ctk.CTkLabel(
            frame,
            text=item.status.capitalize(),
            width=80,
            text_color=self.palette["success_strong"] if item.status == "completed" else self.palette["body_text"]
        )
        status_label.grid(row=0, column=3, padx=5, pady=5)

        # Edit button
        btn_edit = ctk.CTkButton(
            frame,
            text="Edit",
            width=80,
            command=lambda: self.edit_item(item.id),
            **button_style("primary"),
        )
        btn_edit.grid(row=0, column=4, padx=5, pady=5)

    def edit_item(self, item_id: str):
        """Open editor for an item."""
        # Close this dialog
        self.destroy()
        # Open editor for the item
        ItemEditorDialog(self.master, self.db_manager, item_id,
                         vps_manager=self.vps_manager, on_close_callback=self.on_close_callback)

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()

        # Get dialog dimensions
        dialog_width = 900
        dialog_height = 700

        # Get parent window position
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure not off-screen
        x = max(0, x)
        y = max(0, y)

        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")


class SetParentDialog(ctk.CTkToplevel):
    """Dialog for selecting a parent item."""

    def __init__(self, parent, db_manager: 'DatabaseManager', current_item_id: str, current_item_title: str, vps_manager=None, on_close_callback=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_item_id = current_item_id
        self.current_item_title = current_item_title
        self.parent_dialog = parent
        self.vps_manager = vps_manager
        self.on_close_callback = on_close_callback

        self.title(f"Set Parent for: {current_item_title}")
        self.geometry("900x600")

        # Create UI
        self.create_ui()

        # Load available parents
        self.refresh()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.center_on_parent()

    def create_ui(self):
        """Create the UI components."""
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            header_frame,
            text=f"Select Parent for: {self.current_item_title}",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=10, pady=10)

        # Scrollable frame for item list
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Button frame
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)

        btn_close = ctk.CTkButton(
            btn_frame, text="Cancel", command=self.destroy, width=100)
        btn_close.pack(side="right", padx=5)

    def refresh(self):
        """Refresh the list of available parent items."""
        # Clear current list
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get all items
        all_items = self.db_manager.get_all_items(
            sort_by="priority_score", sort_desc=True)

        # Get descendants of current item (to prevent circular references)
        descendants = self.db_manager.get_subtree(self.current_item_id)
        descendant_ids = {item.id for item in descendants}

        # Filter out current item and its descendants
        available_items = [
            item for item in all_items
            if item.id != self.current_item_id and item.id not in descendant_ids
        ]

        # Create header row
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray25")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5), padx=5)
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="Immediate Step (Who)", anchor="w", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        ctk.CTkLabel(header_frame, text="Priority", width=70, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Due Date", width=110, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=2, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Status", width=80, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=3, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Actions", width=100, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=4, padx=5, pady=5
        )

        # Add "No Parent" option as first row
        row = 1
        no_parent_frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray20")
        no_parent_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
        no_parent_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            no_parent_frame,
            text="[No Parent - Make this a root item]",
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="lightblue"
        ).grid(row=0, column=0, sticky="w", padx=10, pady=5, columnspan=4)

        btn_clear = ctk.CTkButton(
            no_parent_frame,
            text="Clear Parent",
            width=100,
            command=self.clear_parent,
            **button_style("danger"),
        )
        btn_clear.grid(row=0, column=4, padx=5, pady=5)
        row += 1

        # Display each available item
        if not available_items:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No available parent items found",
                font=ctk.CTkFont(size=14)
            ).grid(row=row, column=0, pady=20)
            return

        for item in available_items:
            self.create_item_row(item, row)
            row += 1

    def create_item_row(self, item: ActionItem, row: int):
        """Create a row for a potential parent item."""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
        frame.grid_columnconfigure(0, weight=1)

        # Title and who
        info_text = f"{item.title}"
        if item.who:
            info_text += f" ({item.who})"

        title_label = ctk.CTkLabel(
            frame,
            text=info_text,
            anchor="w",
            font=ctk.CTkFont(size=12)
        )
        title_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # Priority
        priority_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=70,
            fg_color="gray30"
        )
        priority_label.grid(row=0, column=1, padx=5, pady=5)

        # Due date
        due_text = item.due_date if item.due_date else "-"
        due_label = ctk.CTkLabel(frame, text=due_text, width=110)
        due_label.grid(row=0, column=2, padx=5, pady=5)

        # Status
        status_label = ctk.CTkLabel(
            frame,
            text=item.status.capitalize(),
            width=80,
            text_color="green" if item.status == "completed" else "white"
        )
        status_label.grid(row=0, column=3, padx=5, pady=5)

        # Select button
        btn_select = ctk.CTkButton(
            frame,
            text="Select",
            width=100,
            command=lambda: self.select_parent(item.id),
            **button_style("primary"),
        )
        btn_select.grid(row=0, column=4, padx=5, pady=5)

    def select_parent(self, parent_id: str):
        """Set the selected item as parent."""
        # Get the current item and update its parent_id
        current_item = self.db_manager.get_action_item(self.current_item_id)
        if current_item:
            current_item.parent_id = parent_id
            self.db_manager.update_action_item(current_item)

        # Close this dialog
        self.destroy()

        # Close and reopen the parent editor to show updated parent info
        self.parent_dialog.destroy()
        ItemEditorDialog(self.parent_dialog.master, self.db_manager, self.current_item_id,
                         vps_manager=self.vps_manager, on_close_callback=self.on_close_callback)

    def clear_parent(self):
        """Clear the parent (make this a root item)."""
        # Get the current item and clear its parent_id
        current_item = self.db_manager.get_action_item(self.current_item_id)
        if current_item:
            current_item.parent_id = None
            self.db_manager.update_action_item(current_item)

        # Close this dialog
        self.destroy()

        # Close and reopen the parent editor to show updated parent info
        self.parent_dialog.destroy()
        ItemEditorDialog(self.parent_dialog.master, self.db_manager, self.current_item_id,
                         vps_manager=self.vps_manager, on_close_callback=self.on_close_callback)

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()

        # Get dialog dimensions
        dialog_width = 900
        dialog_height = 600

        # Get parent window position
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure not off-screen
        x = max(0, x)
        y = max(0, y)

        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")


class SetWeeklyTacticDialog(ctk.CTkToplevel):
    """Dialog for selecting a weekly tactic within a limited window."""

    def __init__(self, parent, db_manager: 'DatabaseManager', vps_manager: 'VPSManager',
                 item_id: Optional[str], item_title: str, first_day_of_week: int,
                 anchor_date: date,
                 segment_name_map: Dict[str, str], on_select):
        super().__init__(parent)
        self.db_manager = db_manager
        self.vps_manager = vps_manager
        self.logger = _get_weekly_debug_logger()
        self.item_id = item_id
        self.item_title = item_title
        self.first_day_of_week = first_day_of_week
        self.anchor_date = anchor_date
        self.segment_name_map = segment_name_map
        self.on_select = on_select
        self.current_selection: Optional[str] = None
        self.rolling_mode = True

        self.month_default_label = "Rolling Window (Prev/Current/Next)"
        self.month_past_week_label = "Past Week"
        self.month_current_week_label = "Current Week"
        self.month_next_week_label = "Next Week"
        self.month_all_label = "All Weeks"
        self.month_filter_var = ctk.StringVar(value=self.month_default_label)
        self.month_lookup: Dict[str, Tuple[int, int]] = {}
        self.month_options = self._build_month_options()

        self.title(f"Set Weekly Tactic for: {item_title}")
        self.geometry("900x520")

        self.prev_start = date.today()
        self.current_start = date.today()
        self.next_start = date.today()
        self._set_rolling_window_range()

        self.segment_filter_var = ctk.StringVar(value="All Segments")
        self.subsegment_filter_var = ctk.StringVar(value="All SubSegments")
        self.category_filter_var = ctk.StringVar(value="All Categories")
        self.segments = self.vps_manager.get_all_segments()
        self.segment_options = ["All Segments"] + [seg["name"] for seg in self.segments]
        self.subsegment_options = ["All SubSegments"]
        self.category_options = ["All Categories"]
        self.segment_colors_by_id = self.vps_manager.get_segment_colors_by_id()
        self.segment_colors, self.subsegment_colors = load_latest_lineage_color_maps(self.vps_manager)
        self.category_colors = {
            (
                (row.get("segment_name", "") or "").strip().lower(),
                (row.get("subsegment_name", "") or "").strip().lower(),
                (row.get("name", "") or "").strip().lower(),
            ): (row.get("color_hex") or "").strip()
            for row in self.vps_manager.get_vision_categories()
        }

        self.create_ui()
        self.logger.info(
            "[set_weekly_dialog:init] item_id=%s title=%s anchor=%s month_options=%d segments=%d",
            self.item_id,
            self.item_title,
            self.anchor_date.isoformat() if self.anchor_date else None,
            len(self.month_options),
            len(self.segment_options),
        )
        self.refresh_actions()

        self.transient(parent)
        self.grab_set()
        self.center_on_parent()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=10)
        header.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(
            header,
            text="Select a Weekly Tactic",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(5, 12))

        ctk.CTkLabel(header, text="Month Filter:").grid(row=0, column=1, sticky="e", padx=5, pady=3)
        self.month_combo = ctk.CTkComboBox(
            header,
            values=self.month_options,
            variable=self.month_filter_var,
            width=220,
            command=lambda _: self._on_month_filter_change()
        )
        self.month_combo.grid(row=0, column=2, sticky="w", padx=5, pady=3)

        ctk.CTkLabel(header, text="Segment Filter:").grid(row=0, column=3, sticky="e", padx=5, pady=3)
        self.segment_combo = ctk.CTkComboBox(
            header,
            values=self.segment_options,
            variable=self.segment_filter_var,
            width=200,
            command=lambda _: self._on_segment_filter_change()
        )
        self.segment_combo.grid(row=0, column=4, sticky="w", padx=5, pady=3)

        ctk.CTkLabel(header, text="SubSegment Filter:").grid(row=1, column=1, sticky="e", padx=5, pady=3)
        self.subsegment_combo = ctk.CTkComboBox(
            header,
            values=self.subsegment_options,
            variable=self.subsegment_filter_var,
            width=200,
            command=lambda _: self._on_subsegment_filter_change()
        )
        self.subsegment_combo.grid(row=1, column=2, sticky="w", padx=5, pady=3)

        ctk.CTkLabel(header, text="Category Filter:").grid(row=1, column=3, sticky="e", padx=5, pady=3)
        self.category_combo = ctk.CTkComboBox(
            header,
            values=self.category_options,
            variable=self.category_filter_var,
            width=200,
            command=lambda _: self.refresh_actions()
        )
        self.category_combo.grid(row=1, column=4, sticky="w", padx=5, pady=3)

        self.list_frame = ctk.CTkScrollableFrame(self, height=360)
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.list_frame.grid_columnconfigure(0, weight=1)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btn_frame, text="Close", command=self.destroy, width=100).pack(side="right")

    def refresh_actions(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        selected_segment_name = self.segment_filter_var.get()
        segment_ids = None
        if selected_segment_name != "All Segments":
            seg = next((s for s in self.segments if s["name"] == selected_segment_name), None)
            if seg:
                segment_ids = [seg["id"]]

        self.logger.info(
            "[set_weekly_dialog:refresh] month=%s segment=%s range=%s..%s rolling_mode=%s",
            self.month_filter_var.get(),
            selected_segment_name,
            self.range_start.isoformat(),
            self.range_end.isoformat(),
            self.rolling_mode,
        )
        week_items = self._get_week_items_for_current_window(segment_ids)
        self.logger.info("[set_weekly_dialog:refresh] initial_count=%d", len(week_items))
        allow_auto_fallback = self.month_filter_var.get() == self.month_default_label

        if not week_items:
            # Auto-switch to the latest defined month if the rolling window is empty.
            if allow_auto_fallback:
                month_labels = [option for option in self.month_options if option in self.month_lookup]
                latest_label = month_labels[0] if month_labels else None
            else:
                latest_label = None
            if latest_label:
                self.month_filter_var.set(latest_label)
                self._set_month_range(*self.month_lookup[latest_label])
                week_items = self._get_week_items_for_current_window(segment_ids)
                self.logger.info(
                    "[set_weekly_dialog:refresh] fallback_latest_month=%s count=%d",
                    latest_label,
                    len(week_items),
                )

        if not week_items and allow_auto_fallback and self.month_filter_var.get() != self.month_all_label:
            # Fall back to showing the entire archive.
            self.month_filter_var.set(self.month_all_label)
            if self._set_all_weeks_range():
                week_items = self._get_week_items_for_current_window(segment_ids)
                self.logger.info(
                    "[set_weekly_dialog:refresh] fallback_all_weeks count=%d",
                    len(week_items),
                )

        if not week_items:
            self.logger.warning("[set_weekly_dialog:refresh] no_results_after_fallbacks")
            ctk.CTkLabel(
                self.list_frame,
                text="No weekly tactics found for the selected window.",
                text_color="gray"
            ).grid(row=0, column=0, pady=20, padx=5)
            return

        self._refresh_subsegment_options(week_items)
        selected_subsegment = self.subsegment_filter_var.get()
        if selected_subsegment != "All SubSegments":
            week_items = [
                action for action in week_items
                if (action.get("ape_subsegment_name") or "").strip() == selected_subsegment
            ]
        self._refresh_category_options(week_items)
        selected_category = self.category_filter_var.get()
        if selected_category != "All Categories":
            week_items = [
                action for action in week_items
                if (action.get("ape_category_name") or "").strip() == selected_category
            ]

        if not week_items:
            ctk.CTkLabel(
                self.list_frame,
                text="No weekly tactics found for the selected filters.",
                text_color="gray"
            ).grid(row=0, column=0, pady=20, padx=5)
            return

        header = ctk.CTkFrame(self.list_frame, fg_color="gray25")
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Week", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(header, text="Segment", width=150, font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(header, text="Immediate Step", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(header, text="Action", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, padx=5, pady=5)

        row = 1
        for week_item in week_items:
            segment_id = week_item.get("segment_description_id")
            segment_name = (week_item.get("ape_segment_name") or self.segment_name_map.get(segment_id) or "").strip()
            subsegment_name = (week_item.get("ape_subsegment_name") or "").strip()
            category_name = (week_item.get("ape_category_name") or "").strip()

            segment_color, subsegment_color = resolve_lineage_colors(
                segment_name,
                subsegment_name,
                self.vps_manager,
                self.segment_colors,
                self.subsegment_colors,
            )
            row_color = self.category_colors.get(
                (
                    segment_name.lower(),
                    subsegment_name.lower(),
                    category_name.lower(),
                ),
                "",
            ) or subsegment_color or self.segment_colors_by_id.get(segment_id, "gray20")
            text_color = pick_text_color(row_color)

            frame = ctk.CTkFrame(self.list_frame, fg_color=row_color)
            frame.grid(row=row, column=0, sticky="ew", padx=5, pady=2)
            frame.grid_columnconfigure(2, weight=1)

            week_label = self._week_label(week_item.get("start_date"))
            ctk.CTkLabel(frame, text=week_label, width=120, anchor="w", text_color=text_color).grid(row=0, column=0, padx=10, pady=5, sticky="w")

            seg_name = self.segment_name_map.get(week_item.get("segment_description_id"), "-")
            ctk.CTkLabel(frame, text=seg_name or "-", width=150, anchor="w", text_color=text_color).grid(row=0, column=1, padx=5, pady=5, sticky="w")

            ctk.CTkLabel(frame, text=week_item.get("title") or "-", anchor="w", text_color=text_color).grid(row=0, column=2, padx=5, pady=5, sticky="w")

            display = self._format_week_action_display(week_item)
            btn = ctk.CTkButton(
                frame,
                text="Select",
                width=80,
                command=lambda wi=week_item, disp=display: self._select_week_action(wi, disp),
                **button_style("primary"),
            )
            btn.grid(row=0, column=3, padx=5, pady=5)
            row += 1

    def _on_segment_filter_change(self):
        self.subsegment_filter_var.set("All SubSegments")
        self.category_filter_var.set("All Categories")
        self.refresh_actions()

    def _on_subsegment_filter_change(self):
        self.category_filter_var.set("All Categories")
        self.refresh_actions()

    def _refresh_subsegment_options(self, week_items: List[Dict[str, Any]]):
        subsegments = sorted(
            {
                (item.get("ape_subsegment_name") or "").strip()
                for item in week_items
                if (item.get("ape_subsegment_name") or "").strip()
            },
            key=str.casefold,
        )
        options = ["All SubSegments"] + subsegments
        current = self.subsegment_filter_var.get()
        if current not in options:
            self.subsegment_filter_var.set("All SubSegments")
        self.subsegment_options = options
        self.subsegment_combo.configure(values=self.subsegment_options)

    def _refresh_category_options(self, week_items: List[Dict[str, Any]]):
        categories = sorted(
            {
                (item.get("ape_category_name") or "").strip()
                for item in week_items
                if (item.get("ape_category_name") or "").strip()
            },
            key=str.casefold,
        )
        options = ["All Categories"] + categories
        current = self.category_filter_var.get()
        if current not in options:
            self.category_filter_var.set("All Categories")
        self.category_options = options
        self.category_combo.configure(values=self.category_options)

    def _select_week_action(self, week_item: Dict[str, Any], display: str):
        self.on_select(
            week_item.get("week_action_id"),
            week_item.get("segment_description_id"),
            display,
            week_item.get("id")
        )
        self.logger.info(
            "[set_weekly_dialog:select] week_item_id=%s week_action_id=%s segment_id=%s title=%s",
            week_item.get("id"),
            week_item.get("week_action_id"),
            week_item.get("segment_description_id"),
            week_item.get("title"),
        )
        self.destroy()

    def _format_week_action_display(self, week_action: Dict[str, Any]) -> str:
        start = week_action.get("week_start_date") or week_action.get("start_date") or "-"
        end = week_action.get("week_end_date") or week_action.get("due_date") or "-"
        seg_name = self.segment_name_map.get(week_action.get("segment_description_id"), "").strip()
        seg_suffix = f" [{seg_name}]" if seg_name else ""
        title = week_action.get("title") or "(untitled)"
        return f"{title} [{start} - {end}]{seg_suffix}"

    def _week_label(self, start_date_str: Optional[str]) -> str:
        if not start_date_str:
            return "-"
        label = start_date_str
        if self.rolling_mode:
            if start_date_str == self.current_start.isoformat():
                label += " (Current)"
            elif start_date_str == self.prev_start.isoformat():
                label += " (Previous)"
            elif start_date_str == self.next_start.isoformat():
                label += " (Next)"
        return label

    def _text_color_for_background(self, color_hex: str) -> str:
        value = (color_hex or "").strip()
        if value.startswith("#") and len(value) == 7:
            try:
                r = int(value[1:3], 16)
                g = int(value[3:5], 16)
                b = int(value[5:7], 16)
                luminance = (0.299 * r) + (0.587 * g) + (0.114 * b)
                return "black" if luminance > 160 else "white"
            except ValueError:
                pass
        return "white"

    def _build_month_options(self) -> list:
        self.month_lookup = {}
        options = [
            self.month_default_label,
            self.month_past_week_label,
            self.month_current_week_label,
            self.month_next_week_label,
            self.month_all_label,
        ]
        try:
            months = self.vps_manager.get_weekly_action_item_months()
        except Exception:
            months = []

        seen = set()
        for entry in months:
            year = entry.get("year")
            month = entry.get("month")
            if not year or not month:
                continue
            label = f"{calendar.month_name[month]} {year}"
            if label in seen:
                continue
            seen.add(label)
            self.month_lookup[label] = (year, month)
            options.append(label)
        return options

    def _align_to_week_start(self, value: date) -> date:
        offset = (value.weekday() - self.first_day_of_week) % 7
        return value - timedelta(days=offset)

    def _align_to_week_end(self, value: date) -> date:
        last_day_index = (self.first_day_of_week + 6) % 7
        offset = (last_day_index - value.weekday()) % 7
        return value + timedelta(days=offset)

    def _set_rolling_window_range(self):
        self.prev_start, self.current_start, self.next_start = self._compute_week_starts()
        anchor = self.anchor_date or date.today()
        start = self._align_to_week_start(anchor - timedelta(days=21))
        end = self._align_to_week_end(anchor + timedelta(days=7))
        self.range_start = start
        self.range_end = end
        self.rolling_mode = True

    def _set_month_range(self, year: int, month: int):
        self.rolling_mode = False
        month_start = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        month_end = date(year, month, last_day)
        self.range_start = self._align_to_week_start(month_start)
        self.range_end = self._align_to_week_end(month_end)

    def _set_specific_week_range(self, week_start: date):
        self.rolling_mode = True
        aligned_start = self._align_to_week_start(week_start)
        self.range_start = aligned_start
        self.range_end = aligned_start + timedelta(days=6)

    def _set_all_weeks_range(self) -> bool:
        self.rolling_mode = False
        bounds = self.vps_manager.get_weekly_action_item_bounds()
        if not bounds:
            return False
        min_start = date.fromisoformat(bounds[0])
        max_start = date.fromisoformat(bounds[1])
        self.range_start = self._align_to_week_start(min_start)
        self.range_end = self._align_to_week_end(max_start)
        return True

    def _on_month_filter_change(self):
        selection = self.month_filter_var.get()
        if selection == self.month_default_label:
            self._set_rolling_window_range()
        elif selection == self.month_past_week_label:
            self._set_specific_week_range(self.prev_start)
        elif selection == self.month_current_week_label:
            self._set_specific_week_range(self.current_start)
        elif selection == self.month_next_week_label:
            self._set_specific_week_range(self.next_start)
        elif selection == self.month_all_label:
            if not self._set_all_weeks_range():
                self.month_filter_var.set(self.month_default_label)
                self._set_rolling_window_range()
        else:
            target = self.month_lookup.get(selection)
            if target:
                self._set_month_range(*target)
        self.refresh_actions()

    def _compute_week_starts(self):
        anchor = self.anchor_date or date.today()
        offset = (anchor.weekday() - self.first_day_of_week) % 7
        current = anchor - timedelta(days=offset)
        prev = current - timedelta(days=7)
        nxt = current + timedelta(days=7)
        return prev, current, nxt

    def _get_week_items_for_current_window(self, segment_ids: Optional[List[str]]):
        if self.month_filter_var.get() == self.month_all_label:
            actions = self.vps_manager.get_weekly_action_items(ape_only=True)
            if segment_ids:
                segment_set = set(segment_ids)
                actions = [
                    action for action in actions
                    if action.get("segment_description_id") in segment_set
                ]
            self.logger.info(
                "[set_weekly_dialog:get_items] mode=all_weeks segment_filter=%s count=%d",
                segment_ids,
                len(actions),
            )
            return actions

        actions = self.vps_manager.get_weekly_action_items_in_range(
            self.range_start.isoformat(),
            self.range_end.isoformat(),
            segment_ids=segment_ids,
            ape_only=True,
        )
        self.logger.info(
            "[set_weekly_dialog:get_items] mode=range segment_filter=%s count=%d",
            segment_ids,
            len(actions),
        )
        return actions

    def center_on_parent(self):
        self.update_idletasks()
        dialog_width = 900
        dialog_height = 520
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        self.geometry(f"{dialog_width}x{dialog_height}+{max(0, x)}+{max(0, y)}")


class CreateNoteDialog(ctk.CTkToplevel):
    """Dialog for creating a new Obsidian note."""

    def __init__(self, parent, db_manager, entity_type: str, entity_id: str, entity_title: str):
        super().__init__(parent)
        self.db_manager = db_manager
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.entity_title = entity_title
        self.parent_window = parent

        self.title(f"Create Note for: {entity_title}")
        self.geometry("500x300")

        self.create_form()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Ensure dialog is visible and on top
        self.lift()
        self.focus_force()

        # Center on parent
        self.center_on_parent()

    def create_form(self):
        """Create the form."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Note title
        ctk.CTkLabel(main_frame, text="Note Title:").pack(pady=(0, 5))
        self.title_var = ctk.StringVar(value=f"{self.entity_title} Notes")
        self.title_entry = ctk.CTkEntry(
            main_frame, textvariable=self.title_var, width=400)
        self.title_entry.pack(pady=(0, 15))

        # Initial content (optional)
        ctk.CTkLabel(main_frame, text="Initial Content (optional):").pack(
            pady=(0, 5))
        self.content_text = ctk.CTkTextbox(main_frame, width=400, height=100)
        self.content_text.pack(pady=(0, 15))

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 0))

        btn_create = ctk.CTkButton(
            btn_frame,
            text="Create & Open",
            command=self.create_note,
            **button_style("primary"),
            width=120
        )
        btn_create.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancel", command=self.destroy, width=100)
        btn_cancel.pack(side="left", padx=5)

        # Error label
        self.error_label = ctk.CTkLabel(
            main_frame, text="", text_color="red", wraplength=400)
        self.error_label.pack(pady=(10, 0))

    def create_note(self):
        """Create the note file and link it."""
        from ..app_settings import AppSettings
        from ..obsidian_utils import create_obsidian_note, open_in_obsidian
        from ..models import ItemLink, ContactLink, ProjectBoardLink

        title = self.title_var.get().strip()
        if not title:
            self.error_label.configure(text="Error: Note title is required")
            return

        content = self.content_text.get("1.0", "end-1c").strip()

        # Load settings
        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(
                text="Error: Obsidian vault not configured in Settings")
            return

        try:
            # Get additional metadata based on entity type
            who = None
            due_date = None
            priority_score = None

            if self.entity_type == "action_item":
                item = self.db_manager.get_action_item(self.entity_id)
                if item:
                    who = item.who
                    due_date = item.due_date
                    priority_score = item.priority_score
            elif self.entity_type == "project_board":
                board = self.db_manager.get_project_board(self.entity_id)
                if board and board.importance is not None:
                    priority_score = board.importance

            # Create note file
            file_path = create_obsidian_note(
                vault_path=settings.obsidian_vault_path,
                subfolder=settings.obsidian_notes_subfolder,
                entity_type=self.entity_type,
                entity_id=self.entity_id,
                title=title,
                initial_content=content,
                who=who,
                due_date=due_date,
                priority_score=priority_score
            )

            # Create link in database
            if self.entity_type == "action_item":
                link = ItemLink(
                    item_id=self.entity_id,
                    url=file_path,
                    label=title,
                    link_type="obsidian_note"
                )
                self.db_manager.add_item_link(link)
            elif self.entity_type == "contact":
                link = ContactLink(
                    contact_id=int(self.entity_id),
                    url=file_path,
                    label=title,
                    link_type="obsidian_note"
                )
                self.db_manager.add_contact_link(link)
            elif self.entity_type == "project_board":
                link = ProjectBoardLink(
                    project_board_id=self.entity_id,
                    url=file_path,
                    label=title,
                    link_type="obsidian_note"
                )
                self.db_manager.add_project_board_link(link)

            # Open in Obsidian
            open_in_obsidian(file_path, settings.obsidian_vault_path)

            # Close dialog and refresh parent
            self.destroy()
            if hasattr(self.parent_window, 'load_notes'):
                self.parent_window.load_notes()

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()

        # Get dialog dimensions
        dialog_width = 500
        dialog_height = 300

        # Get parent window position
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure not off-screen
        x = max(0, x)
        y = max(0, y)

        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")


class LinkNoteDialog(ctk.CTkToplevel):
    """Dialog for linking an existing note file."""

    def __init__(self, parent, db_manager, entity_type: str, entity_id: str):
        super().__init__(parent)
        self.db_manager = db_manager
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.parent_window = parent
        self.available_notes = []

        self.title("Link Existing Note")
        self.geometry("600x500")

        self.create_form()
        self.load_available_notes()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Search/filter by note title
        ctk.CTkLabel(main_frame, text="Search Notes:", font=ctk.CTkFont(
            size=12, weight="bold")).pack(pady=(0, 5))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add('write', lambda *args: self.filter_notes())
        self.search_entry = ctk.CTkEntry(main_frame, textvariable=self.search_var, width=500,
                                         placeholder_text="Search by title, or use file:name or tag:tagname")
        self.search_entry.pack(pady=(0, 10))

        # Display label
        ctk.CTkLabel(main_frame, text="Display Label (optional):").pack(
            pady=(0, 5))
        self.label_var = ctk.StringVar()
        self.label_entry = ctk.CTkEntry(
            main_frame, textvariable=self.label_var, width=500)
        self.label_entry.pack(pady=(0, 15))

        # Available notes list
        ctk.CTkLabel(main_frame, text="Available Notes:", font=ctk.CTkFont(
            size=12, weight="bold")).pack(pady=(0, 5))

        self.notes_frame = ctk.CTkScrollableFrame(main_frame, height=200)
        self.notes_frame.pack(fill="both", expand=True, pady=(0, 15))
        self.notes_frame.grid_columnconfigure(0, weight=1)

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 0))

        btn_browse = ctk.CTkButton(
            btn_frame,
            text="Browse Files...",
            command=self.browse_file,
            width=120
        )
        btn_browse.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancel", command=self.destroy, width=100)
        btn_cancel.pack(side="left", padx=5)

        # Error label
        self.error_label = ctk.CTkLabel(
            main_frame, text="", text_color="red", wraplength=500)
        self.error_label.pack(pady=(10, 0))

    def load_available_notes(self):
        """Load all markdown files from vault (searches entire vault)."""
        from ..app_settings import AppSettings
        from pathlib import Path
        import re

        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(
                text="Error: Obsidian vault not configured in Settings")
            return

        vault_path = Path(settings.obsidian_vault_path)
        if not vault_path.exists():
            self.error_label.configure(text="Error: Vault path does not exist")
            return

        # Search entire vault, not just GetMoreDone subfolder
        search_path = vault_path

        # Find all .md files
        try:
            self.available_notes = []
            for md_file in search_path.rglob("*.md"):
                # Extract tags from frontmatter
                tags = []
                try:
                    content = md_file.read_text(encoding='utf-8')
                    # Look for YAML frontmatter
                    frontmatter_match = re.match(
                        r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                    if frontmatter_match:
                        frontmatter = frontmatter_match.group(1)
                        # Extract tags (supports: tags: [tag1, tag2] or tags:\n- tag1\n- tag2)
                        tags_match = re.search(
                            r'tags:\s*\[(.*?)\]', frontmatter)
                        if tags_match:
                            tags = [t.strip().strip('"\'')
                                    for t in tags_match.group(1).split(',')]
                        else:
                            # Look for YAML list format
                            tags_lines = re.findall(
                                r'^\s*-\s*(.+)$', frontmatter, re.MULTILINE)
                            if 'tags:' in frontmatter:
                                tags = [t.strip()
                                        for t in tags_lines if t.strip()]

                    # Also look for inline tags (#tag format)
                    inline_tags = re.findall(r'#(\w+)', content)
                    tags.extend(inline_tags)
                    tags = list(set(tags))  # Remove duplicates
                except Exception:
                    pass  # If we can't read tags, continue anyway

                self.available_notes.append({
                    'path': str(md_file),
                    'title': md_file.stem,
                    'relative': str(md_file.relative_to(vault_path)),
                    'tags': tags
                })

            # Sort by title
            self.available_notes.sort(key=lambda x: x['title'].lower())

            # Display notes
            self.filter_notes()

        except Exception as e:
            self.error_label.configure(text=f"Error loading notes: {str(e)}")

    def filter_notes(self):
        """Filter notes based on search text with support for file: and tag: prefixes."""
        # Clear current list
        for widget in self.notes_frame.winfo_children():
            widget.destroy()

        search_text = self.search_var.get().strip()

        if not search_text:
            # No search text - show all notes (up to 50)
            filtered = self.available_notes[:50]
        else:
            # Parse search prefixes (Obsidian-style)
            search_lower = search_text.lower()

            if search_lower.startswith("file:"):
                # Search by filename only
                query = search_text[5:].strip().lower()
                filtered = [
                    n for n in self.available_notes if query in n['title'].lower()]
            elif search_lower.startswith("tag:"):
                # Search by tags
                query = search_text[4:].strip().lower()
                filtered = [n for n in self.available_notes
                            if any(query in tag.lower() for tag in n.get('tags', []))]
            else:
                # Default: search in title (case-insensitive contains)
                query = search_text.lower()
                filtered = [
                    n for n in self.available_notes if query in n['title'].lower()]

        if not filtered:
            ctk.CTkLabel(
                self.notes_frame,
                text="No notes found" if search_text else "No notes in vault",
                text_color="gray"
            ).pack(pady=20)
            return

        # Display filtered notes
        for note in filtered[:50]:  # Limit to 50 results
            self.create_note_row(note)

    def create_note_row(self, note: dict):
        """Create a row for a note."""
        frame = ctk.CTkFrame(self.notes_frame)
        frame.pack(fill="x", pady=2, padx=5)

        # Note info
        info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            info_frame,
            text=note['title'],
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=5)

        ctk.CTkLabel(
            info_frame,
            text=note['relative'],
            anchor="w",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        ).pack(anchor="w", padx=5)

        # Display tags if present
        if note.get('tags'):
            # Show first 5 tags
            tags_text = " ".join([f"#{tag}" for tag in note['tags'][:5]])
            ctk.CTkLabel(
                info_frame,
                text=tags_text,
                anchor="w",
                font=ctk.CTkFont(size=9),
                text_color="#6B7280"
            ).pack(anchor="w", padx=5)

        # Select button
        btn_select = ctk.CTkButton(
            frame,
            text="Link This",
            width=80,
            command=lambda: self.link_note_file(note['path'], note['title']),
            **button_style("primary"),
        )
        btn_select.pack(side="right", padx=5)

    def link_note_file(self, file_path: str, default_label: str):
        """Link the selected note file."""
        from ..models import ItemLink, ContactLink, ProjectBoardLink
        from pathlib import Path

        # Get label (use custom if provided, otherwise use note title)
        label = self.label_var.get().strip() or default_label

        try:
            # Create link in database
            if self.entity_type == "action_item":
                link = ItemLink(
                    item_id=self.entity_id,
                    url=file_path,
                    label=label,
                    link_type="obsidian_note"
                )
                self.db_manager.add_item_link(link)
            elif self.entity_type == "contact":
                link = ContactLink(
                    contact_id=int(self.entity_id),
                    url=file_path,
                    label=label,
                    link_type="obsidian_note"
                )
                self.db_manager.add_contact_link(link)
            elif self.entity_type == "project_board":
                link = ProjectBoardLink(
                    project_board_id=self.entity_id,
                    url=file_path,
                    label=label,
                    link_type="obsidian_note"
                )
                self.db_manager.add_project_board_link(link)

            # Close dialog and refresh parent
            self.destroy()
            if hasattr(self.parent_window, 'load_notes'):
                self.parent_window.load_notes()

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")

    def browse_file(self):
        """Browse for a markdown file (fallback option)."""
        from tkinter import filedialog
        from ..app_settings import AppSettings
        from pathlib import Path

        settings = AppSettings.load()

        # Start in vault folder if configured
        initial_dir = None
        if settings.obsidian_vault_path:
            notes_folder = settings.get_notes_folder()
            if notes_folder and notes_folder.exists():
                initial_dir = str(notes_folder)
            else:
                initial_dir = settings.obsidian_vault_path

        file_path = filedialog.askopenfilename(
            title="Select Markdown Note",
            initialdir=initial_dir,
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
        )

        if file_path:
            # Get title from filename
            title = Path(file_path).stem

            # Link the file
            self.link_note_file(file_path, title)


class DeleteConfirmDialog(ctk.CTkToplevel):
    """Confirmation dialog for deleting an item."""

    def __init__(self, parent, item_title: str):
        super().__init__(parent)

        self.confirmed = False

        self.title("Confirm Delete")
        self.geometry("400x150")

        # Center on parent
        self.transient(parent)
        self.grab_set()

        # Message
        message = f"Are you sure you want to delete:\n\n{item_title}\n\nThis action cannot be undone."
        ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=12),
            wraplength=350
        ).pack(pady=20, padx=20)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            command=self.cancel
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Delete",
            width=100,
            **button_style("danger"),
            command=self.confirm
        ).pack(side="left", padx=5)

    def confirm(self):
        """Confirm deletion."""
        self.confirmed = True
        self.destroy()

    def cancel(self):
        """Cancel deletion."""
        self.confirmed = False
        self.destroy()


class DeleteChildrenWarningDialog(ctk.CTkToplevel):
    """Warning dialog when deleting item with children."""

    def __init__(self, parent, num_children: int):
        super().__init__(parent)

        self.confirmed = False

        self.title("Warning: Item Has Children")
        self.geometry("450x180")

        # Center on parent
        self.transient(parent)
        self.grab_set()

        # Message
        message = (
            f"This item has {num_children} child item(s).\n\n"
            "Deleting this item will NOT delete the children.\n"
            "Child items will become root items (no parent).\n\n"
            "Do you want to continue?"
        )
        ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=12),
            wraplength=400
        ).pack(pady=20, padx=20)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            command=self.cancel
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Delete Anyway",
            width=120,
            **button_style("danger"),
            command=self.confirm
        ).pack(side="left", padx=5)

    def confirm(self):
        """Confirm deletion."""
        self.confirmed = True
        self.destroy()

    def cancel(self):
        """Cancel deletion."""
        self.confirmed = False
        self.destroy()
