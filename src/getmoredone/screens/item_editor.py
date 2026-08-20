"""
Item editor dialog for creating and editing action items.
"""

import calendar
import logging
import re
import customtkinter as ctk
import tkinter as tk
from datetime import datetime, timedelta, date
from typing import Optional, TYPE_CHECKING, Dict, Any, Tuple, List

from ..models import ActionItem, PriorityFactors, ItemLink, Status
from .week_collision_notice import notify_weekly_tactic_changes
from .. import week_calendar
from .. import weekly_tactic_titles
from ..validation import Validator
from ..app_settings import AppSettings
from ..color_contrast import pick_text_color
from ..date_utils import increment_date
from ..paths import app_data_dir_path
from ..theme import button_style, combo_box_style, semantic_colors, status_text_color
from .item_editor_contacts import ItemEditorContactsMixin
from .item_editor_form import ItemEditorFormMixin
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
from .item_editor_project_dialog import SetProjectDialog
from .project_link_notice import (
    ape_outcome_for_change,
    confirm_exclusive_relink,
    describe_single_relink,
)
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors
# Still used by _canonical_weekly_tactic_title, which is about Weekly Tactic
# titles, not the removed Context field.
from .title_format import split_action_item_title

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


class ItemEditorDialog(ItemEditorContactsMixin, ItemEditorFormMixin,
                       ItemEditorNotesMixin, ctk.CTkToplevel):
    """Dialog for creating/editing action items."""

    def __init__(self, parent, db_manager: 'DatabaseManager', item_id: Optional[str] = None,
                 week_action_id: Optional[str] = None, segment_description_id: Optional[str] = None,
                 vps_manager: Optional['VPSManager'] = None, on_close_callback=None,
                 focus_tab: Optional[str] = None, x: Optional[int] = None, y: Optional[int] = None):
        super().__init__(parent)
        self.withdraw()

        self.db_manager = db_manager
        self.vps_manager = vps_manager
        self.logger = _get_weekly_debug_logger()
        self.item_id = item_id
        self.item: Optional[ActionItem] = None
        self.week_action_id = week_action_id
        self.segment_description_id = segment_description_id
        self.focus_tab = focus_tab
        self.specified_x = x
        self.specified_y = y
        self.week_action_options = {}  # legacy; kept for callers outside this file
        self.week_action_display_values = ["(None)"]
        self.pending_weekly_tactic_id = None  # chosen before a new item is saved
        self._follow_chosen_tactic = False    # that choice was deliberate (WT-D1)
        # PL2/PL4.2 — the Project the item is filed under. ``_loaded_project_id``
        # is the baseline the dialog opened with; the link is only written when
        # the user actually changes it, so an ordinary Save can never clear a
        # project (or, through clear_item_project_links, the item's APE).
        self._selected_project_id: Optional[str] = None
        self._loaded_project_id: Optional[str] = None
        self._loaded_extra_project_links = 0
        self._extra_project_links = 0
        self._project_choice_made = False
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
            self._load_project_baseline()
            if self.item and self.item.item_type == "week":
                self.title("Edit Weekly Tactic")
            else:
                self.title("Edit Action Item")
        else:
            self.title("New Action Item")

        self.geometry("920x550")
        # Allow the user to resize the editor window; the draggable sash
        # between the two columns (see create_form) rebalances the split.
        self.resizable(True, True)
        self.minsize(700, 500)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.palette = semantic_colors()

        # Width of the right-hand (metadata/tabs) column; adjusted by dragging
        # the sash between the two columns.
        self.right_pane_width = 350

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

        # Center and reveal after widgets have been created to avoid blank shells on macOS.
        self._finalize_dialog_window()

    def create_form(self):
        """Create the form layout with responsive two-column design."""
        # Main container frame
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        main_frame.grid_columnconfigure(0, weight=1)  # Left column (fills)
        main_frame.grid_columnconfigure(1, weight=0)  # Draggable sash
        main_frame.grid_columnconfigure(2, weight=0)  # Right column - fixed width
        main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame = main_frame

        # Left column - Primary Info
        left_col = ctk.CTkFrame(main_frame)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 0))
        left_col.grid_columnconfigure(1, weight=1)
        self.left_col = left_col

        # Draggable sash between the two columns.
        self.sash = ctk.CTkFrame(main_frame, width=6, corner_radius=3,
                                 cursor="sb_h_double_arrow",
                                 fg_color=("gray70", "gray30"))
        self.sash.grid(row=0, column=1, sticky="ns", padx=4)
        self.sash.grid_propagate(False)
        self.sash.bind("<Button-1>", self._start_sash_drag)
        self.sash.bind("<B1-Motion>", self._do_sash_drag)

        # Right column - Metadata, Tabs, and Actions
        right_col = ctk.CTkFrame(main_frame, width=self.right_pane_width)
        right_col.grid(row=0, column=2, sticky="nsew", padx=(0, 0))
        right_col.grid_propagate(False)
        right_col.grid_columnconfigure(0, weight=1) # Content fills the panel width
        right_col.grid_rowconfigure(0, weight=1) # Tabview takes most space
        right_col.grid_rowconfigure(1, weight=0) # Action buttons at bottom
        self.right_col = right_col

        # === LEFT COLUMN CONTENT ===
        row_l = 0

        # Header: Type Badge & Contact
        header_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        header_frame.grid(row=row_l, column=0, columnspan=2, sticky="ew", pady=(5, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        self.record_type_badge = ctk.CTkLabel(
            header_frame, text="Action Item", font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8, padx=10, pady=2
        )
        self.record_type_badge.grid(row=0, column=0, padx=(10, 10))

        ctk.CTkLabel(header_frame, text="Who:").grid(row=0, column=1, sticky="w")
        self.who_var = ctk.StringVar()
        self.who_entry = ctk.CTkEntry(header_frame, textvariable=self.who_var)
        self.who_entry.grid(row=0, column=2, sticky="ew", padx=(5, 10))
        self.who_entry.bind('<KeyRelease>', self.on_who_search)
        self.who_entry.bind('<FocusOut>', lambda e: self.on_who_changed())
        row_l += 1

        # Title. The Context box that used to sit in front of it is gone: it was
        # never a field of its own, only the front half of this same title
        # string, and it only ever read back out of a title whose prefix ended
        # in a week marker (W8) — so most items showed it empty while their
        # title still carried the prefix. Title now holds, and saves, the whole
        # stored title verbatim.
        # Tests: tests/test_item_editor_no_context.py
        title_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        title_frame.grid(row=row_l, column=0, columnspan=2, sticky="ew", pady=5)
        title_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(title_frame, text="Title:").grid(row=0, column=0, sticky="w", padx=10)
        self.title_entry = ctk.CTkEntry(title_frame)
        self.title_entry.grid(row=0, column=1, sticky="ew", padx=(5, 10))
        row_l += 1

        # Action Plan — where this item sits in the plan. Both values are set
        # through the "Set Project" / "Set Wk Tactic" buttons, so the fields
        # here are read-only labels; only the original-week stamp is typed.
        # These used to live on the Organization tab.
        # Spec:  docs/implementation_plan_2026-08-19_item_editor_project_link.md#pl9
        # Tests: tests/test_item_editor_layout.py
        plan_frame = ctk.CTkFrame(left_col)
        plan_frame.grid(row=row_l, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        plan_frame.grid_columnconfigure(1, weight=1)
        self.action_plan_frame = plan_frame

        ctk.CTkLabel(
            plan_frame, text="Action Plan", font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(6, 2))

        ctk.CTkLabel(plan_frame, text="Project:").grid(
            row=1, column=0, sticky="w", padx=(10, 5), pady=2)
        self.project_label = ctk.CTkLabel(
            plan_frame, text=self.NO_PROJECT_TEXT, anchor="w",
            text_color=status_text_color("muted"),
        )
        self.project_label.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=2)

        ctk.CTkLabel(plan_frame, text="Wk Tactic:").grid(
            row=2, column=0, sticky="w", padx=(10, 5), pady=2)
        self.weekly_tactic_label = ctk.CTkLabel(
            plan_frame, text=self.NO_TACTIC_TEXT, anchor="w",
            text_color=status_text_color("muted"),
        )
        self.weekly_tactic_label.grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=2)

        # WT-M3.A.3 — the original-week stamp, editable by hand (WT-D3).
        ctk.CTkLabel(plan_frame, text="Orig. Week:").grid(
            row=3, column=0, sticky="w", padx=(10, 5), pady=(2, 8))
        self.weekly_tactic_start_var = ctk.StringVar()
        self.weekly_tactic_start_entry = ctk.CTkEntry(
            plan_frame, width=120, textvariable=self.weekly_tactic_start_var,
            placeholder_text="YYYY-MM-DD",
        )
        self.weekly_tactic_start_entry.grid(
            row=3, column=1, sticky="w", padx=(0, 10), pady=(2, 8))
        row_l += 1

        self.refresh_weekly_tactic_display()
        self.refresh_project_display()

        # Parent Info (if applicable)
        if self.item and self.item.parent_id:
            parent_item = self.db_manager.get_action_item(self.item.parent_id)
            if parent_item:
                p_info = ctk.CTkLabel(left_col, text=f"Parent: {parent_item.title}", 
                                     font=ctk.CTkFont(size=11), text_color=semantic_colors()["muted_text"])
                p_info.grid(row=row_l, column=0, columnspan=2, sticky="w", padx=10)
                row_l += 1

        # Description
        ctk.CTkLabel(left_col, text="Description:").grid(row=row_l, column=0, sticky="nw", padx=10, pady=(5, 0))
        row_l += 1
        left_col.grid_rowconfigure(row_l, weight=1) # Make Description row expand
        self.description_text = ctk.CTkTextbox(left_col, height=100)
        self.description_text.grid(row=row_l, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 10))
        row_l += 1

        # Next Action
        ctk.CTkLabel(left_col, text="Next Action:").grid(row=row_l, column=0, sticky="nw", padx=10, pady=(5, 0))
        row_l += 1
        left_col.grid_rowconfigure(row_l, weight=1) # Make Next Action row expand
        self.next_action_text = ctk.CTkTextbox(left_col, height=100)
        self.next_action_text.grid(row=row_l, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 10))
        row_l += 1

        # Planned Minutes
        planned_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        planned_frame.grid(row=row_l, column=0, columnspan=2, sticky="w", pady=5)
        ctk.CTkLabel(planned_frame, text="Planned Minutes:").pack(side="left", padx=10)
        self.planned_minutes_entry = ctk.CTkEntry(planned_frame, width=80)
        self.planned_minutes_entry.pack(side="left")
        row_l += 1

        # === RIGHT COLUMN CONTENT ===
        # Tabview
        self.tabview = ctk.CTkTabview(right_col)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        self.tab_dates = self.tabview.add("Dates")
        self.tab_priority = self.tabview.add("Priority")
        self.tab_org = self.tabview.add("Organization")
        self.tab_notes = self.tabview.add("Notes")

        self._setup_dates_tab(self.tab_dates)
        self._setup_priority_tab(self.tab_priority)
        self._setup_org_tab(self.tab_org)
        self._setup_notes_tab(self.tab_notes)

        # Action Buttons Area
        btn_container = ctk.CTkScrollableFrame(right_col, height=180, fg_color="transparent")
        btn_container.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        btn_container.grid_columnconfigure((0, 1), weight=1)

        # Primary Row
        p_row = ctk.CTkFrame(btn_container, fg_color="transparent")
        p_row.pack(fill="x", pady=2)
        self.btn_save_close = ctk.CTkButton(p_row, text="Save & Close", command=self.save_and_close, **button_style("primary"))
        self.btn_save_close.pack(side="left", fill="x", expand=True, padx=2)
        self.btn_save = ctk.CTkButton(p_row, text="Save", command=self.save_item, **button_style("secondary"))
        self.btn_save.pack(side="left", fill="x", expand=True, padx=2)

        # Secondary Actions (Grid for better fit)
        # PL10 — the pairings: Cancel sits beside Timer, Add Follow-up beside
        # Add Subtasks, Set Parent beside Show Related, Set Wk Tactic beside
        # Set Project. Cancel must exist on every path the dialog can take, so
        # on a new item (no Timer) it pairs with Save + New, and on a completed
        # item (no Timer either) it stands alone.
        # Spec:  docs/implementation_plan_2026-08-19_item_editor_project_link.md#pl10
        # Tests: tests/test_item_editor_layout.py::test_pl10_button_pairs_share_a_row
        s_frame = ctk.CTkFrame(btn_container, fg_color="transparent")
        s_frame.pack(fill="x", pady=5)
        s_frame.grid_columnconfigure((0, 1), weight=1)

        row_s = 0
        self.btn_cancel = ctk.CTkButton(s_frame, text="Cancel", command=self.destroy, **button_style("secondary"))

        # Always available secondary
        if not self.item_id:
            self.btn_save_new = ctk.CTkButton(s_frame, text="Save + New", command=self.save_and_new, **button_style("secondary"))
            self.btn_save_new.grid(row=row_s, column=0, sticky="ew", padx=2, pady=2)
            self.btn_cancel.grid(row=row_s, column=1, sticky="ew", padx=2, pady=2)
            row_s += 1

        # Existing item secondary
        if self.item_id:
            # Focus timer (working mode) — only while the item is still open.
            if self.item and self.item.status != Status.COMPLETED:
                self.btn_timer = ctk.CTkButton(
                    s_frame, text="⏱ Timer", command=self.start_timer,
                    **button_style("secondary"))
                self.btn_timer.grid(row=row_s, column=0,
                                    sticky="ew", padx=2, pady=(2, 6))
                self.btn_cancel.grid(row=row_s, column=1,
                                     sticky="ew", padx=2, pady=(2, 6))
            else:
                self.btn_cancel.grid(row=row_s, column=0,
                                     sticky="ew", padx=2, pady=(2, 6))
            row_s += 1

            self.btn_followup = ctk.CTkButton(s_frame, text="Add Follow-up", command=self.create_followup, **button_style("secondary"))
            self.btn_followup.grid(row=row_s, column=0, sticky="ew", padx=2, pady=2)
            self.btn_create_tasks = ctk.CTkButton(s_frame, text="Add Subtasks", command=self.create_sub_item, **button_style("secondary"))
            self.btn_create_tasks.grid(row=row_s, column=1, sticky="ew", padx=2, pady=2)
            row_s += 1

            self.btn_set_parent = ctk.CTkButton(s_frame, text="Set Parent", command=self.set_parent, **button_style("secondary"))
            self.btn_set_parent.grid(row=row_s, column=0, sticky="ew", padx=2, pady=2)
            self.btn_show_related = ctk.CTkButton(s_frame, text="Show Related", command=self.show_related, **button_style("secondary"))
            self.btn_show_related.grid(row=row_s, column=1, sticky="ew", padx=2, pady=2)
            row_s += 1

        # PL10.4 — filing controls exist on a *new* item too. The whole point of
        # the feature is to create an Action Item and file it under a Project —
        # creating that Project if need be — without leaving this screen, so
        # putting the button behind "save it first" would make the headline case
        # unreachable from the UI (P25). Both pickers already hold the choice for
        # an unsaved item and apply it on insert.
        self.btn_set_weekly = ctk.CTkButton(s_frame, text="Set Wk Tactic", command=self.set_weekly_tactic, **button_style("secondary"))
        self.btn_set_weekly.grid(row=row_s, column=0, sticky="ew", padx=2, pady=2)
        self.btn_set_project = ctk.CTkButton(s_frame, text="Set Project", command=self.set_project, **button_style("secondary"))
        self.btn_set_project.grid(row=row_s, column=1, sticky="ew", padx=2, pady=2)
        row_s += 1

        if self.item_id:
            # Destructive/Status
            self.btn_complete = ctk.CTkButton(s_frame, text="Complete", command=self.complete_item, **button_style("success"))
            self.btn_complete.grid(row=row_s, column=0, sticky="ew", padx=2, pady=2)
            self.btn_delete = ctk.CTkButton(s_frame, text="Delete", command=self.delete_item, **button_style("danger"))
            self.btn_delete.grid(row=row_s, column=1, sticky="ew", padx=2, pady=2)

        # Status Label
        self.error_label = ctk.CTkLabel(btn_container, text="", text_color=status_text_color("error"), wraplength=350)
        self.error_label.pack(fill="x", pady=5)

    def _setup_dates_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        r = 0
        
        # Start Date
        ctk.CTkLabel(tab, text="Start:").grid(row=r, column=0, sticky="w", padx=10, pady=5)
        f = ctk.CTkFrame(tab, fg_color="transparent")
        f.grid(row=r, column=1, sticky="w", padx=5)
        self.start_date_entry = ctk.CTkEntry(f, width=110)
        self.start_date_entry.pack(side="left", padx=2)
        ctk.CTkButton(f, text="-", width=28, command=lambda: self.adjust_date(self.start_date_entry, -1)).pack(side="left", padx=1)
        ctk.CTkButton(f, text="+", width=28, command=lambda: self.adjust_date(self.start_date_entry, 1)).pack(side="left", padx=1)
        ctk.CTkButton(f, text="T", width=28, command=lambda: self.set_date(self.start_date_entry, 0)).pack(side="left", padx=1)
        self.start_date_entry.bind("<FocusOut>", lambda e: self.validate_and_adjust_due_date())
        r += 1

        # Due Date
        ctk.CTkLabel(tab, text="Due:").grid(row=r, column=0, sticky="w", padx=10, pady=5)
        f = ctk.CTkFrame(tab, fg_color="transparent")
        f.grid(row=r, column=1, sticky="w", padx=5)
        self.due_date_entry = ctk.CTkEntry(f, width=110)
        self.due_date_entry.pack(side="left", padx=2)
        ctk.CTkButton(f, text="-", width=28, command=lambda: self.adjust_date(self.due_date_entry, -1)).pack(side="left", padx=1)
        ctk.CTkButton(f, text="+", width=28, command=lambda: self.adjust_date(self.due_date_entry, 1)).pack(side="left", padx=1)
        ctk.CTkButton(f, text="T", width=28, command=lambda: self.set_date(self.due_date_entry, 0)).pack(side="left", padx=1)
        self.due_date_entry.bind("<FocusOut>", lambda e: self.validate_due_date_on_edit())
        r += 1

        # Is Meeting
        self.is_meeting_var = ctk.BooleanVar()
        ctk.CTkCheckBox(tab, text="Scheduled Meeting", variable=self.is_meeting_var).grid(row=r, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        r += 1

        # Calendar Button
        ctk.CTkButton(tab, text="📅 Manage Calendar Event", command=self.create_calendar_event, **button_style("secondary")).grid(row=r, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        r += 1

        # Info labels
        self.meeting_time_label = ctk.CTkLabel(tab, text="Not scheduled", font=ctk.CTkFont(size=11))
        self.meeting_time_label.grid(row=r, column=0, columnspan=2, sticky="w", padx=10)
        r += 1
        
        self.original_due_date_label = ctk.CTkLabel(tab, text="Orig Due: -", font=ctk.CTkFont(size=11))
        self.original_due_date_label.grid(row=r, column=0, columnspan=2, sticky="w", padx=10)
        r += 1
        
        self.completed_at_label = ctk.CTkLabel(tab, text="Done: -", font=ctk.CTkFont(size=11))
        self.completed_at_label.grid(row=r, column=0, columnspan=2, sticky="w", padx=10)

    def _setup_priority_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        r = 0
        
        factors = [
            ("Importance:", "importance_var", "importance_combo", PriorityFactors.IMPORTANCE),
            ("Urgency:", "urgency_var", "urgency_combo", PriorityFactors.URGENCY),
            ("Effort:", "size_var", "size_combo", PriorityFactors.SIZE),
            ("Value:", "value_var", "value_combo", PriorityFactors.VALUE),
        ]
        
        for label, var_name, combo_name, options in factors:
            ctk.CTkLabel(tab, text=label).grid(row=r, column=0, sticky="w", padx=10, pady=5)
            vals = [f"{k} ({v})" for k, v in options.items()]
            var = ctk.StringVar()
            setattr(self, var_name, var)
            combo = ctk.CTkComboBox(tab, values=vals, variable=var, **combo_box_style(), 
                                   command=lambda _: self.update_priority_display())
            combo.grid(row=r, column=1, sticky="ew", padx=5, pady=5)
            setattr(self, combo_name, combo)
            r += 1
            
        self.priority_label = ctk.CTkLabel(tab, text="Score: 0", font=ctk.CTkFont(weight="bold", size=14))
        self.priority_label.grid(row=r, column=0, columnspan=2, pady=10)

    def _setup_org_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        r = 0
        
        # Group
        ctk.CTkLabel(tab, text="Group:").grid(row=r, column=0, sticky="w", padx=10, pady=5)
        self.group_var = ctk.StringVar()
        groups = self.db_manager.get_distinct_groups()
        self.group_combo = ctk.CTkComboBox(tab, values=groups or [""], variable=self.group_var, **combo_box_style())
        self.group_combo.grid(row=r, column=1, sticky="ew", padx=5, pady=5)
        r += 1
        
        # Category
        ctk.CTkLabel(tab, text="Category:").grid(row=r, column=0, sticky="w", padx=10, pady=5)
        self.category_var = ctk.StringVar()
        categories = self.db_manager.get_distinct_categories()
        self.category_combo = ctk.CTkComboBox(tab, values=categories or [""], variable=self.category_var, **combo_box_style())
        self.category_combo.grid(row=r, column=1, sticky="ew", padx=5, pady=5)

        # PL8 — the Weekly Tactic display and the original-week stamp used to
        # sit here. They now live in the Action Plan block in the left column,
        # beside the Project, so the whole "where does this item sit in the
        # plan" picture is visible without opening a tab.
        # Spec:  docs/implementation_plan_2026-08-19_item_editor_project_link.md#pl8
        # Tests: tests/test_item_editor_layout.py::test_pl8_org_tab_has_no_weekly_widgets

    NO_TACTIC_TEXT = "(none)"
    NO_PROJECT_TEXT = "(none)"

    def refresh_weekly_tactic_display(self):
        """Show the linked Weekly Tactic's title, or an explicit "(none)".

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6a2
        Tests: tests/test_item_editor_weekly_tactic_ui.py::test_wt_m6a2_org_tab_shows_current_tactic_or_none
        """
        tactic_id = getattr(self.item, "weekly_tactic_id", None) if self.item else None
        tactic = self.db_manager.get_action_item(tactic_id) if tactic_id else None
        if tactic is None:
            text = self.NO_TACTIC_TEXT
            stale = getattr(self.item, "weekly_tactic_start_date", None) if self.item else None
            if stale:
                # WT-M3.A.4 — a stamp whose tactic was deleted is surfaced, not
                # silently reused.
                text = f"{self.NO_TACTIC_TEXT} — originally week of {stale}"
        else:
            text = f"{tactic.title} ({tactic.start_date} to {tactic.due_date})"
        self.weekly_tactic_label.configure(text=text)

    def _load_project_baseline(self):
        """Read the item's current Project link(s) as the change baseline.

        Purpose: PL2/PL4.2 — remember what the dialog opened with, so save only
                 touches the link when the user actually changed it.
        Spec:    docs/implementation_plan_2026-08-19_item_editor_project_link.md#pl2
        Tests:   tests/test_item_editor_project_link.py::test_pl2_action_plan_shows_current_project
        """
        if not self.item_id:
            return
        board_ids = self.db_manager.get_project_board_ids_for_item(self.item_id)
        self._loaded_project_id = board_ids[0] if board_ids else None
        self._selected_project_id = self._loaded_project_id
        # PL2.2 — an item may already carry several links (the Projects screen's
        # "link existing items" dialog is not exclusive). Count them so they are
        # surfaced rather than silently hidden behind the first one.
        self._loaded_extra_project_links = max(0, len(board_ids) - 1)
        self._extra_project_links = self._loaded_extra_project_links

    def refresh_project_display(self):
        """Show the Project the item is filed under, or an explicit "(none)".

        Spec:  docs/implementation_plan_2026-08-19_item_editor_project_link.md#pl2
        Tests: tests/test_item_editor_project_link.py::test_pl2_1_unlinked_shows_none
        """
        board_id = self._selected_project_id
        board = self.db_manager.get_project_board(board_id) if board_id else None
        if board is None:
            # A link pointing at a deleted board is surfaced, not read as "none".
            text = self.NO_PROJECT_TEXT if not board_id else "(project no longer exists)"
        else:
            text = board.title
            if self._extra_project_links:
                text = f"{text}  (+{self._extra_project_links} more)"
        self.project_label.configure(text=text)

    def set_project(self):
        """Open the Project picker (PL5). Also creates a Project inline."""
        if self._is_weekly_tactic_record():
            # PL6 — a Weekly Tactic's title is derived from its Annual Plan
            # Element, and filing it under a project would re-stamp that APE.
            return
        current_title = self.item.title if self.item else (
            self.title_entry.get().strip() or "Action Item")
        dialog = SetProjectDialog(
            self, self.db_manager,
            item_title=current_title,
            current_board_id=self._selected_project_id,
            on_select=self.apply_project_selection,
        )
        dialog.wait_window()

    def apply_project_selection(self, board_id: Optional[str]):
        """Record the chosen Project; the link itself is written by save_item.

        Deferring the write keeps one save path for both a brand-new item (no
        row to link yet) and an existing one, and means Cancel really cancels.
        """
        if board_id != self._loaded_project_id:
            # One rule, one question, three surfaces. Filing is exclusive, so
            # changing the project removes every other board this item sits on
            # AND replaces its Annual Plan Element with the new board's;
            # clearing removes the lot and nulls the plan element outright.
            #
            # This used to be two narrow guards — one for "the item has *extra*
            # links", one for "the target is None" — and between them a
            # singly-filed item could be moved to another board, silently
            # trading its Annual Plan Element for that board's, while the
            # Projects dialog and the Scheduler both asked about exactly that
            # (P5, P13: the guards were scoped to two symptoms rather than to
            # the write). ``confirm_exclusive_relink`` returns True when
            # nothing would be lost, so picking a project for an unfiled item
            # with no plan element is still never interrupted.
            # Tests: tests/test_item_editor_project_link.py::test_c2_1_the_editor_asks_before_swapping_a_plan_element
            if self._loaded_extra_project_links:
                # More than one link to drop: that count is the thing worth
                # naming, and this dialog names it.
                if not self._confirm_dropping_extra_project_links(board_id):
                    return
            elif self.item_id and not confirm_exclusive_relink(
                    self, self.db_manager, [self.item_id], board_id):
                return

        self._selected_project_id = board_id
        self._project_choice_made = True
        # An exclusive re-link replaces every existing link, so any extra ones
        # are about to go; only an unchanged selection keeps them.
        self._extra_project_links = (
            self._loaded_extra_project_links
            if board_id == self._loaded_project_id else 0
        )
        self.refresh_project_display()

    def _confirm_dropping_extra_project_links(self, board_id: Optional[str]) -> bool:
        """Ask before an exclusive re-link unfiles the item from other boards."""
        import tkinter.messagebox as messagebox

        count = self._loaded_extra_project_links + 1
        target = None
        if board_id:
            board = self.db_manager.get_project_board(board_id)
            target = board.title if board else "the selected project"
        # BP1 — the Projects screen asks the same question in the same words.
        # ``clears_ape`` has to be passed, not defaulted: this is the *only*
        # dialog a multi-filed item gets (the guard below it is scoped to
        # items with no extra links), so letting it default to False deleted
        # the Annual Plan Element warning from the one path that shows it
        # (sweep pass 4, P22 — a new parameter with a default that silently
        # changes an existing call site).
        # One implementation of "what happens to the Annual Plan Element",
        # shared with the other two surfaces. The editor had a third copy that
        # read ``self.item`` (loaded at open, so stale if the row changed
        # elsewhere) and lacked the unreadable-board guard, so it re-opened
        # S2-8 in the one dialog a multi-filed item ever gets (P5/P19).
        question = describe_single_relink(
            count, target,
            ape_outcome=ape_outcome_for_change(
                self.db_manager, self.item_id, board_id))
        return messagebox.askyesno("Change Project", question, parent=self)

    def _apply_project_link(self, item_id: str) -> bool:
        """Write the Project link, but only when the user changed it (PL4.2).

        ``clear_item_project_links`` also nulls the item's Annual Plan Element,
        so firing it on an untouched dialog would quietly strip the APE from
        every item saved without a project (P13 — the guard must scope to the
        change, not to the save).

        Returns True when a link was actually written or cleared.
        """
        if not self._project_choice_made:
            return False
        if self._selected_project_id == self._loaded_project_id:
            return False
        if self._selected_project_id:
            self.db_manager.link_item_to_project_exclusive(
                self._selected_project_id, item_id)
        else:
            self.db_manager.clear_item_project_links(item_id)
        self._loaded_project_id = self._selected_project_id
        self._loaded_extra_project_links = 0
        self._extra_project_links = 0
        self._project_choice_made = False
        return True

    def _setup_notes_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        btns = ctk.CTkFrame(tab, fg_color="transparent")
        btns.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        ctk.CTkButton(btns, text="+ Create", width=80, command=self.create_note).pack(side="left", padx=2)
        ctk.CTkButton(btns, text="🔗 Link", width=80, command=self.link_existing_note).pack(side="left", padx=2)
        
        self.notes_frame = ctk.CTkScrollableFrame(tab, height=200)
        self.notes_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.notes_frame.grid_columnconfigure(0, weight=1)
        
        if self.item_id:
            self.load_notes()
        else:
            ctk.CTkLabel(self.notes_frame, text="Notes available after save", font=ctk.CTkFont(size=11)).pack(pady=20)

    def load_week_actions(self):
        """Removed — WT-M6.A.1.

        This queried the legacy ``week_actions`` table to fill an Org-tab combo.
        That table is empty on every database and the column it fed
        (``action_items.week_action_id``) is NULL on all 646 rows (WT-F6/WT-F7),
        so the control could never show anything. The Org tab now shows the real
        Weekly Tactic from ``weekly_tactic_id``.

        Kept as a no-op rather than deleted, because it is a public method and
        removing it outright would break any caller not in this file.

        Tests: tests/test_item_editor_weekly_tactic_ui.py::test_wt_m6a1_org_tab_never_queries_legacy_table
        """
        return

    def _get_week_window_range(self):
        """WT-M2.B — week boundaries from the one helper (WT-F2c)."""
        anchor = self._get_anchor_date()
        start = week_calendar.week_start(anchor - timedelta(days=21), self.first_day_of_week)
        end = week_calendar.week_end(anchor + timedelta(days=7), self.first_day_of_week)
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
                    # WT-M2.B.2 — the title's week number follows the configured
                    # rule, and carries its year internally (WT-F2a/WT-F2b).
                    canonical = weekly_tactic_titles.canonical_weekly_tactic_title(
                        ape["key_field"],
                        start_date,
                        week_calendar.WeekCalendar.from_settings(),
                    )
                    if canonical:
                        return canonical
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
            # PL6 — a Weekly Tactic cannot be filed under a Project: the link
            # would re-stamp its Annual Plan Element, which its canonical title
            # is derived from.
            self._set_project_button_state("disabled")
            return

        self.record_type_badge.configure(
            text="Action Item",
            fg_color=palette["surface_subtle"],
            text_color=palette["body_text"],
        )
        self._set_project_button_state("normal")

    def _set_project_button_state(self, state: str):
        """Enable/disable Set Project; the button only exists on saved items."""
        button = getattr(self, "btn_set_project", None)
        if button is not None:
            button.configure(state=state)

    def load_item_data(self):
        """Load item data into form fields."""
        if not self.item:
            return

        self.who_var.set(self.item.who)
        self.selected_contact_id = self.item.contact_id
        self._apply_record_type_ui()
        if self._is_weekly_tactic_record():
            canonical_title = self._canonical_weekly_tactic_title(
                self.item.title,
                self.item.annual_plan_element_id,
                self.item.start_date,
            )
            if canonical_title and canonical_title != (self.item.title or "").strip():
                self.item.title = canonical_title
                # A week item: the re-file skips these entirely (WT-INV6 and the
                # item_type guard), so there is never a cascade to report here.
                self.db_manager.update_action_item(self.item, normalize_week_dates=False)
            self.title_entry.insert(0, canonical_title)
        else:
            # The whole stored title, prefix and all — splitting it here and
            # rejoining it on save is what the Context box did, and it silently
            # dropped any prefix the splitter did not recognise.
            self.title_entry.insert(0, self.item.title or "")

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

        # WT-M6.A — the Weekly Tactic display and its original-week stamp.
        if self.item.weekly_tactic_start_date:
            self.weekly_tactic_start_var.set(self.item.weekly_tactic_start_date)
        self.refresh_weekly_tactic_display()
        self.refresh_project_display()

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

    def save_item(self) -> bool:
        """Save the item. Returns True on success, False on validation/save error."""
        try:
            is_new = not self.item_id
            if not is_new and self.item is None:
                # The row this editor was opened on no longer exists — deleted
                # from a list, or from a second editor window. Before BP3 this
                # raised AttributeError and showed the exception; afterwards
                # ``build_item_from_form(None)`` fabricated a brand-new
                # ActionItem with a fresh id, the save took the *update* branch,
                # and ``update_action_item`` reports True for a row it did not
                # match — so the editor said "Saved" and discarded every edit
                # (P2: a failure that reports success; P12: the refactor turned
                # a loud failure into a silent one).
                # Tests: tests/test_item_editor_missing_row.py
                self.error_label.configure(
                    text="Error: this item no longer exists — it was deleted elsewhere")
                return False
            item = self.build_item_from_form(None if is_new else self.item)
            if is_new:
                self.apply_new_item_fields(item)

            error = self.validate_item_for_save(item)
            if error:
                self.error_label.configure(text=error)
                return False

            if is_new:
                self.insert_new_item(item)
            else:
                self.db_manager.update_action_item(item)
                # WT-M6.B.5 — the main Save button is the ordinary way a start date
                # changes, and completion re-filing is what triggers a year rollover.
                notify_weekly_tactic_changes(self.db_manager, self)
                # PL3/PL4 — the Project link, applied on both branches.
                if self._apply_project_link(item.id):
                    # Linking writes the board's Annual Plan Element onto the
                    # row, so re-read rather than keep a stale in-memory copy.
                    self.item = self.db_manager.get_action_item(item.id) or item
                self.refresh_project_display()

            # Clear error message on successful save
            self.error_label.configure(text="✓ Saved")
            # Reset the message after 2 seconds
            self.after(2000, lambda: self.error_label.configure(text=""))
            return True

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")
            return False

    def save_and_new(self):
        """Save and open a new item editor."""
        callback = self.on_close_callback  # Save callback before save closes this dialog
        # Only close + reopen if the save actually succeeded; on a validation
        # error save_item() shows the reason and returns False, so we stay put.
        if self.save_item():
            self.on_dialog_close()
            ItemEditorDialog(self.master, self.db_manager,
                             vps_manager=self.vps_manager, on_close_callback=callback)

    def save_and_close(self):
        """Save the item and close the dialog."""
        # Close only on a successful save (False => validation/save error shown).
        if self.save_item():
            self.on_dialog_close()

    def create_followup(self):
        """Save pending edits, create a follow-up item, and open it alongside.

        Purpose: PL11 — the one "make another item from this one" path. The
                 separate Duplicate button is gone; ``create_followup_item``
                 builds its copy through the ``ActionItem`` constructor and
                 then carries the weekly lineage (WT-M5.C.1) and the project
                 link, which the constructor drops. (It has never gone through
                 ``duplicate_action_item``, which this said until 2026-08-19
                 and which now has no caller in ``src/`` at all.)
        Spec:    docs/implementation_plan_2026-08-19_item_editor_project_link.md#pl11
        Tests:   tests/test_item_editor_layout.py::test_pl11_followup_saves_first

        Saves first — that guard existed only on the old Duplicate path, so a
        follow-up used to be built from the stored row while the edits on
        screen were silently left behind (P5: the sibling call was unhardened).
        """
        if not self.item_id or not self.save_item():
            return

        new_id = self.db_manager.create_followup_item(self.item_id)
        if not new_id:
            return

        # Open the follow-up in a NEW editor window, offset from this one.
        # We do NOT call on_dialog_close() here because we want both open.
        ItemEditorDialog(self.master, self.db_manager, new_id,
                         vps_manager=self.vps_manager, on_close_callback=self.on_close_callback,
                         x=self.winfo_x() + 100, y=self.winfo_y() + 40)

    def start_timer(self):
        """Save pending edits, then open the focus timer (working mode) for this item."""
        # Save-first so the timer reflects what's on screen (planned minutes, notes).
        # If validation fails, save_item() shows the reason and we stop here.
        if not self.save_item():
            return
        if not self.item or self.item.status == Status.COMPLETED:
            return

        # Snapshot the fields the timer can also change, so on close we can tell
        # which ones the user edited *here* meanwhile and leave those untouched.
        self._pre_timer_field_values = self._current_timer_field_values()

        from .timer_window import TimerWindow
        TimerWindow(self, self.db_manager, self.item,
                    on_close=self._on_timer_closed)

    def _current_timer_field_values(self) -> dict:
        """Snapshot of the editor fields the timer can also change."""
        return {
            "description": self.description_text.get("1.0", "end").strip(),
            "next_action": self.next_action_text.get("1.0", "end").strip(),
            "planned_minutes": self.planned_minutes_entry.get().strip(),
        }

    def _on_timer_closed(self):
        """After the timer closes, pick up note edits / completion it made."""
        # The timer can edit the notes and can complete the item (Finished/Continue).
        if self.winfo_exists():
            self._reload_editable_notes()
            self._refresh_timer_button_state()
        if self.on_close_callback:
            try:
                self.on_close_callback()
            except Exception:
                pass

    def _refresh_timer_button_state(self):
        """Disable the Timer button once the item is completed (e.g. the timer's
        Finished/Continue completed it), so it can't reopen on a done item."""
        btn = getattr(self, "btn_timer", None)
        if btn is None:
            return
        try:
            if self.item and self.item.status == Status.COMPLETED:
                btn.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass  # widget torn down during window close

    def _reload_editable_notes(self):
        """Re-read fields the timer can change (notes, next-action, planned
        minutes) from the DB, but keep any field the user edited in this editor
        while the timer was open — only reload the ones they left untouched, so a
        non-modal edit here isn't clobbered by the reload."""
        if not self.item_id:
            return
        fresh = self.db_manager.get_action_item(self.item_id)
        if not fresh:
            return
        self.item = fresh
        snap = getattr(self, "_pre_timer_field_values", {})
        try:
            current = self._current_timer_field_values()
        except (tk.TclError, AttributeError):
            return  # widgets gone (window closing)
        try:
            # A field is safe to reload only if the user hasn't changed it here
            # since the timer opened (current value still equals the snapshot).
            if current["description"] == snap.get("description"):
                self.description_text.delete("1.0", "end")
                if fresh.description:
                    self.description_text.insert("1.0", fresh.description)
            if current["next_action"] == snap.get("next_action"):
                self.next_action_text.delete("1.0", "end")
                if fresh.next_action:
                    self.next_action_text.insert("1.0", fresh.next_action)
            if current["planned_minutes"] == snap.get("planned_minutes"):
                self.planned_minutes_entry.delete(0, "end")
                if fresh.planned_minutes is not None:
                    self.planned_minutes_entry.insert(0, str(fresh.planned_minutes))
        except (tk.TclError, AttributeError):
            pass  # widgets may be gone if the window is closing

    def complete_item(self):
        """Mark item as complete."""
        if self.item_id:
            self.db_manager.complete_action_item(self.item_id)
            # Completion is what triggers a year rollover — finishing in
            # January something planned for last December.
            notify_weekly_tactic_changes(self.db_manager, self)
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

    def _start_sash_drag(self, event):
        """Begin dragging the sash between the left and right columns."""
        self._sash_start_x = event.x_root
        self._sash_start_width = self.right_col.winfo_width()

    def _do_sash_drag(self, event):
        """Resize the right column as the user drags the sash.

        Dragging right shrinks the right (metadata/tabs) column and gives the
        space to the left column; dragging left does the reverse. The width is
        clamped so neither column can be squeezed out.
        """
        delta = event.x_root - self._sash_start_x
        new_width = self._sash_start_width - delta

        total = self.main_frame.winfo_width()
        # Leave room for the left column and the sash itself.
        max_right = max(300, total - 320)
        new_width = int(max(280, min(new_width, max_right)))

        self.right_pane_width = new_width
        self.right_col.configure(width=new_width)

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        # Schedule centering after dialog is fully rendered
        self.after(10, self._do_center)

    def _finalize_dialog_window(self):
        """Render, position, and show the dialog only after child widgets exist."""
        self.update_idletasks()
        self._do_center()
        self.deiconify()
        self.after_idle(self._show_dialog_contents)

    def _show_dialog_contents(self):
        """Finish showing the dialog after the window is visible."""
        self.lift()
        self.focus_force()
        self.update_idletasks()

    def _do_center(self):
        """Actually perform the centering after dialog is rendered."""
        self.master.update_idletasks()

        dialog_width = 920
        dialog_height = 680 # Increased to accommodate buttons

        if self.specified_x is not None and self.specified_y is not None:
            # Use specified coordinates
            x = self.specified_x
            y = self.specified_y
        else:
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
                    # WT-D11 / WT-F9 — the tactic link has its own column. This
                    # used to write parent_id, which silently destroyed any
                    # subtask hierarchy the item was part of.
                    current_item.weekly_tactic_id = week_item_id
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
                # follow_tactic: the user picked this week explicitly, so the
                # item's dates move to it (WT-D1) rather than the week being
                # re-derived from the dates.
                self.db_manager.update_action_item(current_item, follow_tactic=True)
                # WT-M6.B.5 — say what the cascade built before this dialog is
                # torn down and reopened, or the report is discarded unseen.
                notify_weekly_tactic_changes(self.db_manager, self)

            # This path tears the dialog down and reopens it, so a Project
            # picked but not yet saved would be discarded without a word — and
            # Set Wk Tactic now sits directly beside Set Project, which is
            # exactly the sequence that loses it (P2).
            self._apply_project_link(self.item_id)

            self.destroy()
            ItemEditorDialog(
                self.master,
                self.db_manager,
                self.item_id,
                vps_manager=self.vps_manager,
                on_close_callback=self.on_close_callback
            )
        else:
            # A new item, not yet saved: remember the choice for the insert.
            self.week_action_id = week_action_id
            # follow_tactic is applied when this item is finally created —
            # save_item passes it, so the choice is not discarded the way it
            # was on the update path.
            self.pending_weekly_tactic_id = week_item_id
            if segment_id:
                self.segment_description_id = segment_id
            self.weekly_tactic_label.configure(text=display or self.NO_TACTIC_TEXT)

    def create_calendar_event(self):
        """Create a Google Calendar event linked to this item."""
        # ``save_item_if_needed`` carries the deleted-row guard, but calling it
        # only for a *new* item scoped that guard out of the case it exists
        # for: a saved editor whose row has since been deleted reaches
        # ``self.item.is_meeting`` below on a None and raises inside a Tk
        # callback, where this app has nowhere to show it (P13/P5).
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
