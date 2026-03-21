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
from ..theme import button_style, combo_box_style, semantic_colors, status_text_color
from .item_editor_contacts import ItemEditorContactsMixin
from .item_editor_notes import ItemEditorNotesMixin
from .item_editor_dialogs import (
    CreateNoteDialog,
    DeleteChildrenWarningDialog,
    DeleteConfirmDialog,
    LinkNoteDialog,
    SetParentDialog,
    SetWeeklyTacticDialog,
    ShowRelatedDialog,
)
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


class ItemEditorDialog(ItemEditorContactsMixin, ItemEditorNotesMixin, ctk.CTkToplevel):
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
            main_frame, height=5, fg_color=self.palette["border"], cursor="sb_v_double_arrow")
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
                    left_col, fg_color=self.palette["surface_subtle"], corner_radius=8)
                parent_frame.grid(row=row_l, column=0, columnspan=2,
                                  sticky="ew", padx=10, pady=(5, 10))

                ctk.CTkLabel(
                    parent_frame,
                    text=f"Sub-item of: {parent_item.title}",
                    font=ctk.CTkFont(size=12),
                    text_color=status_text_color("info")
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
            **combo_box_style(),
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
            **combo_box_style(),
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
            **combo_box_style(),
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
            **combo_box_style(),
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
                                           ""], variable=self.group_var, width=180, **combo_box_style())
        self.group_combo.grid(row=tab2_row, column=1,
                              sticky="w", padx=10, pady=5)
        tab2_row += 1

        # Category
        ctk.CTkLabel(self.tab_organization, text="Category:").grid(
            row=tab2_row, column=0, sticky="w", padx=10, pady=5)
        categories = self.db_manager.get_distinct_categories()
        self.category_var = ctk.StringVar(value="")
        self.category_combo = ctk.CTkComboBox(self.tab_organization, values=categories if categories else [
                                              ""], variable=self.category_var, width=180, **combo_box_style())
        self.category_combo.grid(
            row=tab2_row, column=1, sticky="w", padx=10, pady=5)
        tab2_row += 1

        # Weekly Tactic (VSP Integration)
        ctk.CTkLabel(self.tab_organization, text="Weekly Tactic:").grid(
            row=tab2_row, column=0, sticky="w", padx=10, pady=5)
        self.week_action_var = ctk.StringVar(value="")
        self.week_action_combo = ctk.CTkComboBox(self.tab_organization, values=[
                                                 ""], variable=self.week_action_var, width=250, **combo_box_style())
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
            text_color=status_text_color("muted")
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
            text_color=status_text_color("success")
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
                text_color=status_text_color("muted")
            ).grid(row=0, column=0, pady=10)

        # === BUTTONS ===
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        # Row 1: Primary actions
        top_row = ctk.CTkFrame(btn_frame, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 5))

        action_btn_width = 110

        btn_save = ctk.CTkButton(top_row, text="Save",
                                 command=self.save_item, width=action_btn_width, **button_style("primary"))
        btn_save.pack(side="left", padx=2)

        btn_save_close = ctk.CTkButton(
            top_row, text="Save & Close", command=self.save_and_close, width=action_btn_width, **button_style("primary"))
        btn_save_close.pack(side="left", padx=2)

        if not self.item_id:
            btn_save_new = ctk.CTkButton(
                top_row, text="Save + New", command=self.save_and_new, width=action_btn_width, **button_style("secondary"))
            btn_save_new.pack(side="left", padx=2)

        if self.item_id:
            btn_duplicate = ctk.CTkButton(
                top_row, text="Duplicate", command=self.duplicate_item, width=action_btn_width, **button_style("secondary"))
            btn_duplicate.pack(side="left", padx=2)

            btn_followup = ctk.CTkButton(
                top_row, text="Add Follow-up", command=self.create_followup, width=action_btn_width, **button_style("secondary"))
            btn_followup.pack(side="left", padx=2)

        # Error label
        self.error_label = ctk.CTkLabel(
            top_row, text="", text_color=status_text_color("error"), wraplength=600)
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
