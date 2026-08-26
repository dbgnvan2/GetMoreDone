"""Project Boards screen with square project cards and linked action items."""

from __future__ import annotations

import logging
from datetime import date
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk
from PIL import Image

from ..color_contrast import pick_text_color
from ..models import ActionItem, PriorityFactors, ProjectBoard, ProjectBoardStatus
from ..paths import project_root
from .project_link_notice import (
    confirm_exclusive_relink,
    describe_outstanding_multi_links,
)
from .week_collision_notice import notify_weekly_tactic_changes
from ..theme import button_style, combo_box_style, semantic_colors, status_text_color
from ..utils.duration import format_minutes

if TYPE_CHECKING:
    from ..app import GetMoreDoneApp
    from ..db_manager import DatabaseManager

IMPORTANCE_OPTIONS = [f"{k} ({v})" for k, v in PriorityFactors.IMPORTANCE.items()]


class ProjectBoardEditorDialog(ctk.CTkToplevel):
    """Add/edit dialog for a project board."""

    def __init__(
        self,
        parent,
        db_manager: "DatabaseManager",
        board: Optional[ProjectBoard] = None,
    ):
        super().__init__(parent)
        self.db_manager = db_manager
        self.board = board
        self.result: Optional[ProjectBoard | str] = None
        self.ape_rows = self.db_manager.list_annual_plan_element_catalog()
        self.ape_label_to_id: dict[str, str] = {}

        self.title("Edit Project" if board else "New Project")
        self.geometry("760x520")
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def _build(self):
        root = ctk.CTkFrame(self)
        root.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(root, text="Title").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.title_var = ctk.StringVar(value=self.board.title if self.board else "")
        ctk.CTkEntry(root, textvariable=self.title_var).grid(row=0, column=1, sticky="ew", padx=8, pady=8)

        ctk.CTkLabel(root, text="Annual Plan Element (Required)").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ape_labels: list[str] = []
        selected_label = None
        default_projects_label = None

        for row in self.ape_rows:
            label = self._format_ape_label(row)
            self.ape_label_to_id[label] = row["id"]
            ape_labels.append(label)

            # Check if this is "Contribution - Projects - Projects" (default)
            if (row.get("segment_name") == "Contribution" and
                row.get("subsegment_name") == "Projects" and
                row.get("category_name") == "Projects"):
                default_projects_label = label

            # Use current board's APE if set
            if self.board and row["id"] == self.board.annual_plan_element_id:
                selected_label = label

        # Default to Contribution - Projects - Projects if new board or no APE set
        if not selected_label and default_projects_label:
            selected_label = default_projects_label
        elif not selected_label and ape_labels:
            selected_label = ape_labels[0]

        self.ape_var = ctk.StringVar(value=selected_label or "")
        self.ape_combo = ctk.CTkComboBox(
            root,
            values=ape_labels,
            variable=self.ape_var,
            **combo_box_style(),
        )
        self.ape_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=8)

        top_row = ctk.CTkFrame(root, fg_color="transparent")
        top_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        top_row.grid_columnconfigure(1, weight=1)
        top_row.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(top_row, text="Priority").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.priority_var = ctk.StringVar(value=self._importance_label(self.board.importance if self.board else None))
        ctk.CTkComboBox(
            top_row,
            width=160,
            values=IMPORTANCE_OPTIONS,
            variable=self.priority_var,
            **combo_box_style(),
        ).grid(row=0, column=1, sticky="w", padx=8, pady=8)

        # WT-M6.C — project start and end dates. Informational only: never
        # validated, never derived from the items on the board (WT-D9), because
        # a project may span any timeframe.
        # Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6c
        # Tests: tests/test_project_board_dates_ui.py::test_wt_m6c1_project_dates_reach_db_layer
        ctk.CTkLabel(top_row, text="Start").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        self.start_date_var = ctk.StringVar(
            value=(self.board.start_date if self.board else "") or "")
        ctk.CTkEntry(
            top_row, width=160, textvariable=self.start_date_var,
            placeholder_text="YYYY-MM-DD",
        ).grid(row=1, column=1, sticky="w", padx=8, pady=8)

        ctk.CTkLabel(top_row, text="End").grid(row=1, column=2, sticky="w", padx=8, pady=8)
        self.end_date_var = ctk.StringVar(
            value=(self.board.end_date if self.board else "") or "")
        ctk.CTkEntry(
            top_row, width=160, textvariable=self.end_date_var,
            placeholder_text="YYYY-MM-DD",
        ).grid(row=1, column=3, sticky="w", padx=8, pady=8)

        ctk.CTkLabel(top_row, text="Status").grid(row=0, column=2, sticky="w", padx=8, pady=8)
        self.status_var = ctk.StringVar(value=self.board.status if self.board else ProjectBoardStatus.ACTIVE)
        ctk.CTkComboBox(
            top_row,
            width=140,
            values=[
                ProjectBoardStatus.ACTIVE,
                ProjectBoardStatus.PENDING,
                ProjectBoardStatus.COMPLETED,
            ],
            variable=self.status_var,
            **combo_box_style(),
        ).grid(row=0, column=3, sticky="w", padx=8, pady=8)

        ctk.CTkLabel(root, text="Next Step").grid(row=3, column=0, sticky="w", padx=8, pady=8)
        self.next_step_var = ctk.StringVar(value=self.board.next_step or "" if self.board else "")
        ctk.CTkEntry(root, textvariable=self.next_step_var).grid(row=3, column=1, sticky="ew", padx=8, pady=8)

        ctk.CTkLabel(root, text="Notes").grid(row=4, column=0, sticky="nw", padx=8, pady=8)
        self.notes_box = ctk.CTkTextbox(root, height=180)
        self.notes_box.grid(row=4, column=1, sticky="nsew", padx=8, pady=8)
        if self.board and self.board.notes:
            self.notes_box.insert("1.0", self.board.notes)

        actions = ctk.CTkFrame(root, fg_color="transparent")
        actions.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        ctk.CTkButton(actions, text="Cancel", width=90, command=self.cancel, **button_style("secondary")).pack(
            side="right", padx=4
        )
        ctk.CTkButton(actions, text="Save", width=90, command=self.save, **button_style("primary")).pack(
            side="right", padx=4
        )

    def _format_ape_label(self, row: dict) -> str:
        key = (row.get("key_field") or "").strip()
        lineage = " | ".join(
            part for part in [
                row.get("segment_name"),
                row.get("subsegment_name"),
                row.get("category_name"),
            ] if part
        )
        return f"{row.get('year')} - {lineage} - {key}"

    def _importance_label(self, value: Optional[int]) -> str:
        for label, score in PriorityFactors.IMPORTANCE.items():
            if score == value:
                return f"{label} ({score})"
        return IMPORTANCE_OPTIONS[2]

    def _extract_factor_value(self, text: str) -> Optional[int]:
        if "(" in text and ")" in text:
            try:
                return int(text.rsplit("(", 1)[1].rstrip(")"))
            except ValueError:
                return None
        return None

    def save(self):
        if not self.title_var.get().strip():
            messagebox.showerror("Missing Title", "Project title is required.", parent=self)
            return

        selected_label = self.ape_var.get().strip()
        ape_id = self.ape_label_to_id.get(selected_label)

        if not ape_id:
            messagebox.showerror(
                "Annual Plan Element Required",
                "Please select a valid Annual Plan Element before saving.",
                parent=self,
            )
            return

        board = self.board or ProjectBoard(
            title="",
            annual_plan_element_id=ape_id,
        )
        board.title = self.title_var.get().strip()
        board.annual_plan_element_id = ape_id
        board.importance = self._extract_factor_value(self.priority_var.get())
        board.status = self.status_var.get().strip() or ProjectBoardStatus.ACTIVE
        board.next_step = self.next_step_var.get().strip() or None
        board.notes = self.notes_box.get("1.0", "end").strip() or None
        # WT-D9: stored exactly as typed. No validation, no reordering.
        board.start_date = self.start_date_var.get().strip() or None
        board.end_date = self.end_date_var.get().strip() or None
        if board.status == ProjectBoardStatus.COMPLETED and not board.completed_at:
            from datetime import datetime
            board.completed_at = datetime.now().isoformat()
        elif board.status != ProjectBoardStatus.COMPLETED:
            board.completed_at = None
        self.result = board
        self.destroy()

    def cancel(self):
        self.result = "__cancel__"
        self.destroy()


class LinkProjectActionItemsDialog(ctk.CTkToplevel):
    """Attach existing action items to a selected project item."""

    def __init__(self, parent, db_manager: "DatabaseManager", board_id: str, on_linked):
        super().__init__(parent)
        self.db_manager = db_manager
        self.board_id = board_id
        self.on_linked = on_linked
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_args: self.refresh_results())

        # Filter state (AND logic)
        self.filter_completed = False
        self.filter_not_completed = False
        self.filter_linked = False
        self.filter_not_linked = False
        self.checked_items: set[str] = set()

        self.title("Link Action Items")
        self.geometry("900x620")
        self.transient(parent)
        self.grab_set()

        self._build()
        self.refresh_results()

    def _build(self):
        root = ctk.CTkFrame(self)
        root.pack(fill="both", expand=True, padx=12, pady=12)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)

        search = ctk.CTkFrame(root)
        search.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        search.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(search, text="Search").grid(row=0, column=0, padx=8, pady=8)
        ctk.CTkEntry(search, textvariable=self.search_var, placeholder_text="Search title, description, next step, who").grid(
            row=0, column=1, sticky="ew", padx=8, pady=8
        )
        self.btn_link_selected = ctk.CTkButton(
            search, text="Link Selected", width=120, command=self._link_selected_items, **button_style("primary")
        )
        self.btn_link_selected.grid(row=0, column=2, padx=(4, 4), pady=8)
        ctk.CTkButton(search, text="Close", width=90, command=self.destroy, **button_style("secondary")).grid(
            row=0, column=3, padx=8, pady=8
        )

        # Filter buttons (AND logic)
        filters = ctk.CTkFrame(root)
        filters.grid(row=1, column=0, sticky="ew", padx=0, pady=(0, 8))
        filters.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(filters, text="Filter (AND):", text_color=semantic_colors()["muted_text"]).grid(
            row=0, column=0, padx=(8, 12), pady=8
        )

        self.btn_completed = ctk.CTkButton(
            filters, text="✓ Completed", width=110, command=self._toggle_filter_completed, **button_style("secondary")
        )
        self.btn_completed.grid(row=0, column=1, padx=4, pady=8)

        self.btn_not_completed = ctk.CTkButton(
            filters, text="○ Not Completed", width=110, command=self._toggle_filter_not_completed, **button_style("secondary")
        )
        self.btn_not_completed.grid(row=0, column=2, padx=4, pady=8)

        self.btn_linked = ctk.CTkButton(
            filters, text="🔗 Linked", width=110, command=self._toggle_filter_linked, **button_style("secondary")
        )
        self.btn_linked.grid(row=0, column=3, padx=4, pady=8)

        self.btn_not_linked = ctk.CTkButton(
            filters, text="⊘ Not Linked", width=110, command=self._toggle_filter_not_linked, **button_style("secondary")
        )
        self.btn_not_linked.grid(row=0, column=4, padx=4, pady=8)

        self.results = ctk.CTkScrollableFrame(root)
        self.results.grid(row=2, column=0, sticky="nsew")
        self.results.grid_columnconfigure(0, weight=1)

    def refresh_results(self):
        for child in self.results.winfo_children():
            child.destroy()

        linked_ids = {item.id for item in self.db_manager.get_project_board_items(self.board_id)}
        query = self.search_var.get().strip()
        items = self.db_manager.search_items(query) if query else self.db_manager.get_all_items(sort_by="updated_at", sort_desc=True)

        # Apply filters with AND logic
        filtered = []
        for item in items:
            # PL6 — a Weekly Tactic's title and Annual Plan Element are derived
            # from the plan, so it cannot be filed under a project. The item
            # editor disables its Set Project button for one; this dialog was
            # listing them with a working Link button, which is how a tactic
            # could be filed under a project with no plan element and have its
            # own stripped (P5 — one surface enforced the rule, the other did
            # not).
            # Tests: tests/test_project_multi_link.py::test_f2_the_link_dialog_does_not_offer_weekly_tactics
            if item.item_type == "week":
                continue
            is_linked = item.id in linked_ids
            is_completed = item.status == "completed"

            # Apply each active filter
            if self.filter_completed and not is_completed:
                continue
            if self.filter_not_completed and is_completed:
                continue
            if self.filter_linked and not is_linked:
                continue
            if self.filter_not_linked and is_linked:
                continue

            filtered.append(item)

        # The tick state has to match what is on screen. This list is rebuilt
        # on every keystroke in Search and on every filter toggle, and the
        # checkboxes were recreated blank while ``checked_items`` kept its
        # contents — so a user who ticked three rows, typed one character and
        # pressed "Link Selected" re-filed three items they could no longer
        # see. That was survivable while linking was additive; BP1 made it
        # delete the items' existing links (P13 — the state outlived the guard
        # that made it meaningful).
        # Tests: tests/test_project_multi_link.py::test_c1_a_search_cannot_leave_invisible_items_selected
        shown = filtered[:200]
        self.checked_items &= {item.id for item in shown}

        if not filtered:
            ctk.CTkLabel(self.results, text="No action items match the selected filters.", text_color=semantic_colors()["muted_text"]).grid(
                row=0, column=0, padx=10, pady=12, sticky="w"
            )
            return

        for idx, item in enumerate(shown):
            row = ctk.CTkFrame(self.results)
            row.grid(row=idx, column=0, sticky="ew", padx=4, pady=3)
            row.grid_columnconfigure(1, weight=1)

            # Checkbox
            checkbox = ctk.CTkCheckBox(
                row,
                text="",
                width=30,
                command=lambda item_id=item.id: self._on_item_checkbox_toggled(item_id)
            )
            # A row that survived the rebuild keeps its tick, so a search that
            # narrows the list does not silently drop a selection the user can
            # still see.
            if item.id in self.checked_items:
                checkbox.select()
            checkbox.grid(row=0, column=0, rowspan=2, sticky="w", padx=(8, 4), pady=8)

            title = item.title
            meta = f"{item.who or '-'} | Start: {item.start_date or '-'} | Due: {item.due_date or '-'} | Status: {item.status}"
            ctk.CTkLabel(row, text=title, anchor="w", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=1, sticky="w", padx=8, pady=(6, 2)
            )
            ctk.CTkLabel(row, text=meta, anchor="w").grid(
                row=1, column=1, sticky="w", padx=8, pady=(0, 6)
            )
            ctk.CTkButton(
                row,
                text="Link",
                width=72,
                command=lambda item_id=item.id: self._link(item_id),
                **button_style("primary"),
            ).grid(row=0, column=2, rowspan=2, padx=8, pady=8)

    def _link(self, item_id: str):
        """File one item under this board, exclusively (BP1).

        Purpose: an Action Item belongs to exactly one Project. This dialog was
                 the last additive surface; the Scheduler and the item editor
                 already relink exclusively.
        Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp1
        Tests:   tests/test_project_multi_link.py::test_bp1_linking_moves_an_item_between_boards

        An item that sits on other boards loses those links, so it is asked
        about first — the same question the item editor asks (P2).
        """
        if not self._confirm_relink([item_id]):
            return
        # ``link_item_to_project_exclusive`` raises for a Weekly Tactic (PL6).
        # The list no longer offers tactics, so this is unreachable through the
        # UI — but an unguarded raise in a Tk ``command`` goes to a stderr a
        # double-clicked app has nowhere to send, which is how this repo lost a
        # dialog once already. The bulk path beside it is guarded; this one was
        # not (P5).
        try:
            self.db_manager.link_item_to_project_exclusive(self.board_id, item_id)
        except Exception as exc:
            messagebox.showerror("Link Failed", str(exc), parent=self)
            self.refresh_results()
            return
        if item_id in self.checked_items:
            self.checked_items.remove(item_id)
        if self.on_linked and callable(self.on_linked):
            self.on_linked()
        self.refresh_results()

    def _confirm_relink(self, item_ids) -> bool:
        """Ask before an exclusive link unfiles items from other boards.

        The Scheduler's drag-drop asks the same question through the same
        helper — this used to be the only surface that asked, while the more
        destructive one (drag onto "No Project" also clears the Annual Plan
        Element) said nothing (P5).
        """
        return confirm_exclusive_relink(self, self.db_manager, item_ids, self.board_id)

    def _on_item_checkbox_toggled(self, item_id: str):
        if item_id in self.checked_items:
            self.checked_items.remove(item_id)
        else:
            self.checked_items.add(item_id)

    def _toggle_filter_completed(self):
        self.filter_completed = not self.filter_completed
        self._update_filter_button_appearance()
        self.refresh_results()

    def _toggle_filter_not_completed(self):
        self.filter_not_completed = not self.filter_not_completed
        self._update_filter_button_appearance()
        self.refresh_results()

    def _toggle_filter_linked(self):
        self.filter_linked = not self.filter_linked
        self._update_filter_button_appearance()
        self.refresh_results()

    def _toggle_filter_not_linked(self):
        self.filter_not_linked = not self.filter_not_linked
        self._update_filter_button_appearance()
        self.refresh_results()

    def _update_filter_button_appearance(self):
        palette = semantic_colors()
        for btn, is_active in [
            (self.btn_completed, self.filter_completed),
            (self.btn_not_completed, self.filter_not_completed),
            (self.btn_linked, self.filter_linked),
            (self.btn_not_linked, self.filter_not_linked),
        ]:
            if is_active:
                btn.configure(fg_color=palette["primary"], hover_color=palette["primary_hover"])
            else:
                btn.configure(fg_color=palette["surface"], hover_color=palette["surface_hover"])

    def _link_selected_items(self):
        """File every checked item under this board, exclusively (BP1).

        Tests: tests/test_project_multi_link.py::test_bp1_bulk_link_asks_once_before_dropping_links

        One question for the whole batch rather than one per item, but the same
        rule: nothing is unfiled without consent (P2).
        """
        if not self.checked_items:
            return

        selected = list(self.checked_items)
        if not self._confirm_relink(selected):
            return

        # One transaction: a failure part-way through used to leave the first
        # few items moved off their old boards and the rest untouched, with the
        # exception escaping a Tk callback into a stderr a double-clicked app
        # has nowhere to send (P2 — the drop was invisible).
        try:
            with self.db_manager.transaction():
                for item_id in selected:
                    self.db_manager.link_item_to_project_exclusive(self.board_id, item_id)
        except Exception as exc:
            messagebox.showerror(
                "Link Failed",
                f"None of the {len(selected)} selected items were moved: {exc}",
                parent=self,
            )
            self.refresh_results()
            return

        for item_id in selected:
            self.checked_items.discard(item_id)

        if self.on_linked and callable(self.on_linked):
            self.on_linked()
        self.refresh_results()


class BulkEditItemsDialog(ctk.CTkToplevel):
    """Bulk edit dialog for setting Start Date and Priority across multiple items."""

    def __init__(self, parent, db_manager: "DatabaseManager", item_ids: list[str]):
        super().__init__(parent)
        self.db_manager = db_manager
        self.item_ids = item_ids
        self.result: Optional[dict] = None

        self.title("Bulk Edit Items")
        self.geometry("520x380")
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def _build(self):
        root = ctk.CTkFrame(self)
        root.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(3, weight=1)

        # Title
        ctk.CTkLabel(root, text="Bulk Edit Items", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=0, pady=(0, 12)
        )

        # Start Date
        ctk.CTkLabel(root, text="Start Date").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        start_frame = ctk.CTkFrame(root, fg_color="transparent")
        start_frame.grid(row=1, column=1, sticky="ew", padx=8, pady=8)
        start_frame.grid_columnconfigure(0, weight=1)

        self.start_date_var = ctk.StringVar(value="")
        ctk.CTkEntry(start_frame, textvariable=self.start_date_var, placeholder_text="YYYY-MM-DD (leave blank to skip)").grid(
            row=0, column=0, sticky="ew", padx=0, pady=0
        )
        self.start_date_skip_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(start_frame, text="Skip", variable=self.start_date_skip_var).grid(
            row=0, column=1, sticky="w", padx=(8, 0), pady=0
        )

        # Priority
        ctk.CTkLabel(root, text="Priority").grid(row=2, column=0, sticky="w", padx=8, pady=8)
        priority_frame = ctk.CTkFrame(root, fg_color="transparent")
        priority_frame.grid(row=2, column=1, sticky="ew", padx=8, pady=8)
        priority_frame.grid_columnconfigure(0, weight=1)

        priority_options = ["(Skip)"] + IMPORTANCE_OPTIONS
        self.priority_var = ctk.StringVar(value=priority_options[0])
        ctk.CTkComboBox(
            priority_frame,
            values=priority_options,
            variable=self.priority_var,
            **combo_box_style(),
        ).grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        # Info box
        info_frame = ctk.CTkFrame(root)
        info_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=0, pady=(12, 12))
        info_frame.grid_columnconfigure(0, weight=1)

        info_text = f"Updating {len(self.item_ids)} item(s). Leave fields blank or select '(Skip)' to preserve existing values."
        ctk.CTkLabel(
            info_frame,
            text=info_text,
            text_color=semantic_colors()["muted_text"],
            wraplength=480,
            justify="left",
        ).pack(fill="both", expand=True, padx=8, pady=8)

        # Buttons
        actions = ctk.CTkFrame(root, fg_color="transparent")
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        ctk.CTkButton(actions, text="Cancel", width=90, command=self.cancel, **button_style("secondary")).pack(
            side="right", padx=4
        )
        ctk.CTkButton(actions, text="Save", width=90, command=self.save, **button_style("primary")).pack(
            side="right", padx=4
        )

    def save(self):
        start_date = self.start_date_var.get().strip() if not self.start_date_skip_var.get() else None
        priority_label = self.priority_var.get().strip()
        priority = None if priority_label == "(Skip)" else self._extract_priority_value(priority_label)

        # Validate start date if provided
        if start_date:
            try:
                from datetime import date as date_class
                input_date = date_class.fromisoformat(start_date)
                today = date_class.today()
                if input_date < today:
                    messagebox.showerror(
                        "Invalid Date",
                        f"Start date must be today ({today.isoformat()}) or later.",
                        parent=self,
                    )
                    return
            except ValueError:
                messagebox.showerror(
                    "Invalid Date Format",
                    "Please use YYYY-MM-DD format (e.g., 2026-06-15).",
                    parent=self,
                )
                return

        # Require at least one field to be changed
        if not start_date and priority is None:
            messagebox.showwarning(
                "No Changes",
                "Please specify at least one field to update, or click Cancel.",
                parent=self,
            )
            return

        self.result = {
            "item_ids": self.item_ids,
            "start_date": start_date,
            "priority": priority,
        }
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

    def _extract_priority_value(self, text: str) -> Optional[int]:
        if "(" in text and ")" in text:
            try:
                return int(text.rsplit("(", 1)[1].rstrip(")"))
            except ValueError:
                return None
        return None


class NoteActionChooserDialog(ctk.CTkToplevel):
    """Small modal chooser shown when the user clicks the 📄 icon on a project tile.

    Purpose: Ask the user whether they want to create a new Obsidian note or
             link an existing one to the project. Both branches delegate to
             the same CreateNoteDialog / LinkNoteDialog used by Action Items.
    Spec:    docs/implementation_plan_2026-06-06.md (paper-icon-enhancement)
    Tests:   tests/test_project_note_chooser.py::test_choice_is_create
             tests/test_project_note_chooser.py::test_choice_is_link
             tests/test_project_note_chooser.py::test_cancel_returns_none
    """

    CHOICE_CREATE = "create"
    CHOICE_LINK = "link"

    def __init__(self, parent, project_title: str):
        super().__init__(parent)
        self.result: Optional[str] = None

        self.title("Add Note to Project")
        self.geometry("420x220")
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        root = ctk.CTkFrame(self)
        root.pack(fill="both", expand=True, padx=16, pady=16)
        root.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            root,
            text=f"Add a note to:\n{project_title}",
            font=ctk.CTkFont(size=14, weight="bold"),
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        ctk.CTkButton(
            root,
            text="Create New Obsidian Note",
            command=self._choose_create,
            **button_style("primary"),
        ).grid(row=1, column=0, sticky="ew", pady=4)

        ctk.CTkButton(
            root,
            text="Link Existing Obsidian Note",
            command=self._choose_link,
            **button_style("secondary"),
        ).grid(row=2, column=0, sticky="ew", pady=4)

        ctk.CTkButton(
            root,
            text="Cancel",
            command=self.cancel,
            **button_style("secondary"),
        ).grid(row=3, column=0, sticky="ew", pady=(12, 0))

        self.lift()
        self.focus_force()

    def _choose_create(self):
        self.result = self.CHOICE_CREATE
        self.destroy()

    def _choose_link(self):
        self.result = self.CHOICE_LINK
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


def project_time_line(row: dict) -> Optional[str]:
    """The Project record's Time line, or None when the numbers are not known.

    Purpose: PT3 — session count and total time for the project.
    Tests:   tests/test_project_time_totals.py::test_pt31_the_time_line_renders_the_boards_own_numbers
             tests/test_project_time_totals.py::test_pt32_one_session_is_not_pluralised
             tests/test_project_time_totals.py::test_pt33_absent_numbers_render_no_line_rather_than_zero

    A pure function on the row rather than an f-string inside the renderer,
    because the tests over it were asserting their own arithmetic: inverting the
    pluralisation and rendering an entirely different column both left every
    test green (P27).

    Returns None rather than zero when the row has no aggregates. The detail
    pane has a fallback that fetches a board with ``SELECT *``, and rendering
    "0 sessions | 0m" there stated a number the row could not support — every
    other field on that path degrades to blank, which is an honest "unknown"
    (P6/P2).
    """
    if "session_count" not in row or "total_minutes" not in row:
        return None
    sessions = row.get("session_count") or 0
    return (f"Time: {sessions} session{'' if sessions == 1 else 's'}"
            f" | {format_minutes(row.get('total_minutes'))}")


class ProjectBoardsScreen(ctk.CTkFrame):
    """Single project board containing many project items linked to APEs."""

    CARD_WIDTH = 235
    CARD_HEIGHT = 280
    SPLITTER_WIDTH = 8
    MIN_PANEL_WIDTH = 300
    ACTION_BUTTON_WIDTH = 38
    ACTION_BUTTON_HEIGHT = 34
    ACTION_ICON_FONT_SIZE = 22
    ICON_EDIT = "✐"
    ICON_COMPLETE = "✓"
    ICON_PENDING = "◷"
    ICON_DELETE = "🗑"
    ICON_NEW_TASK = "+"
    ICON_NOTES = "📄"

    def __init__(self, parent, db_manager: "DatabaseManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app
        self.selected_board_id: Optional[str] = None
        self.board_rows: list[dict] = []
        self.search_query = ""  # Track search query
        self.show_pending_var = ctk.BooleanVar(value=False)
        self.show_completed_var = ctk.BooleanVar(value=False)
        self.note_width_var = ctk.DoubleVar(value=float(self.CARD_WIDTH))
        self.compact_height_var = ctk.BooleanVar(value=False)
        self._render_after_id = None
        self._split_ratio = 0.6
        self._drag_start_x: Optional[int] = None
        self._drag_start_left: Optional[int] = None
        self._card_columns = 1
        self._dragging_board_id: Optional[str] = None
        self._drag_pointer_start: Optional[tuple[int, int]] = None
        self._drag_threshold = 8
        self._card_frames: dict[str, ctk.CTkFrame] = {}
        self._custom_card_width: int = self.CARD_WIDTH
        self.selected_item_ids: set[str] = set()
        self.item_checkbox_vars: dict[str, ctk.BooleanVar] = {}
        # M4.A.1 — Shared 'Show Completed' toggle filters BOTH the Project
        # Notes list and the Action Items list. Default OFF per user direction
        # ("Clicking on a Project will display all the OPEN Project Notes and
        # Action Items").
        # Spec: docs/implementation_plan_2026-06-06_project_notes.md#M4.A.1
        self.show_completed_items_var = ctk.BooleanVar(value=False)

        # Load Edit Icon
        icon_path = project_root() / "assets" / "icons" / "pencil_vertical.png"
        if icon_path.exists():
            self.edit_icon_image = ctk.CTkImage(
                light_image=Image.open(icon_path),
                dark_image=Image.open(icon_path),
                size=(22, 22),
            )
        else:
            self.edit_icon_image = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build()
        self.refresh()

    def _build(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header.grid_columnconfigure(9, weight=1)

        ctk.CTkLabel(header, text="Project Board", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=8, pady=8, sticky="w"
        )
        self.btn_add_project = ctk.CTkButton(header, text="+ New Project", command=self.add_project, **button_style("primary"))
        self.btn_add_project.grid(
            row=0, column=1, padx=6, pady=8
        )
        self.btn_refresh = ctk.CTkButton(header, text="Refresh", command=self.refresh, **button_style("secondary"))
        self.btn_refresh.grid(
            row=0, column=2, padx=6, pady=8
        )
        ctk.CTkCheckBox(
            header,
            text="Show Pending",
            variable=self.show_pending_var,
            command=self.refresh,
        ).grid(row=0, column=3, padx=8, pady=8)
        ctk.CTkCheckBox(
            header,
            text="Show Complete",
            variable=self.show_completed_var,
            command=self.refresh,
        ).grid(row=0, column=4, padx=8, pady=8)
        ctk.CTkLabel(header, text="Note Size").grid(row=0, column=5, padx=(14, 4), pady=8)
        ctk.CTkSlider(
            header,
            from_=150,
            to=280,
            number_of_steps=26,
            variable=self.note_width_var,
            command=self._on_note_size_slider,
            width=180,
        ).grid(row=0, column=6, padx=4, pady=8)
        self.note_size_value_label = ctk.CTkLabel(header, text=f"{self.CARD_WIDTH}px")
        self.note_size_value_label.grid(row=0, column=7, padx=(0, 8), pady=8, sticky="w")
        ctk.CTkCheckBox(
            header,
            text="Compact Height",
            variable=self.compact_height_var,
            command=self._render_cards,
        ).grid(row=0, column=8, padx=8, pady=8)

        ctk.CTkLabel(
            header,
            text="Project items on the board at left, linked action items at right.",
            text_color=semantic_colors()["muted_text"],
        ).grid(row=0, column=9, padx=8, pady=8, sticky="e")

        # BP2 — rows that predate exclusive filing. Reported where the user can
        # act on them, not only in a start-up log line nobody reads (P25).
        self.multi_link_label = ctk.CTkLabel(
            header,
            text="",
            anchor="w",
            justify="left",
            text_color=status_text_color("warning"),
        )
        self.multi_link_label.grid(row=2, column=0, columnspan=10, padx=8,
                                   pady=(0, 8), sticky="w")

        # Search row
        self.search_entry = ctk.CTkEntry(
            header,
            placeholder_text="Search title, next step, notes...",
            width=240,
        )
        self.search_entry.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="w")
        self.search_entry.bind("<Return>", lambda e: self.perform_search())

        self.btn_search = ctk.CTkButton(
            header,
            text="Search",
            width=80,
            command=self.perform_search,
            **button_style("secondary"),
        )
        self.btn_search.grid(row=1, column=2, padx=6, pady=(0, 8), sticky="w")

        self.btn_clear_search = ctk.CTkButton(
            header,
            text="Clear",
            width=60,
            command=self.clear_search,
            **button_style("secondary"),
        )
        self.btn_clear_search.grid(row=1, column=3, padx=6, pady=(0, 8), sticky="w")

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=0, minsize=520)
        body.grid_columnconfigure(1, weight=0, minsize=self.SPLITTER_WIDTH)
        body.grid_columnconfigure(2, weight=0, minsize=420)
        body.grid_rowconfigure(0, weight=1)
        self.body = body

        left_panel = ctk.CTkFrame(body)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.bind("<Configure>", self._schedule_card_render)
        self.left_panel = left_panel

        ctk.CTkLabel(left_panel, text="Project Items", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=6, pady=(10, 4)
        )
        self.cards_frame = ctk.CTkScrollableFrame(left_panel)
        self.cards_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 10))
        self.cards_frame.grid_columnconfigure(0, weight=1)

        divider = ctk.CTkFrame(
            body,
            width=self.SPLITTER_WIDTH,
            fg_color=semantic_colors()["border"],
            corner_radius=2,
            cursor="sb_h_double_arrow",
        )
        divider.grid(row=0, column=1, sticky="ns", padx=0, pady=0)
        divider.bind("<ButtonPress-1>", self._on_divider_press)
        divider.bind("<B1-Motion>", self._on_divider_drag)
        divider.bind("<ButtonRelease-1>", self._on_divider_release)
        self.divider = divider

        right_panel = ctk.CTkFrame(body)
        right_panel.grid(row=0, column=2, sticky="nsew", padx=(4, 0), pady=0)
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(2, weight=1)
        self.right_panel = right_panel

        self.detail_title = ctk.CTkLabel(
            right_panel,
            text="Select a Project",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.detail_title.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))

        self.detail_meta = ctk.CTkLabel(
            right_panel,
            text="",
            justify="left",
            anchor="w",
            text_color=semantic_colors()["muted_text"],
        )
        self.detail_meta.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))

        self.items_frame = ctk.CTkScrollableFrame(right_panel)
        self.items_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.items_frame.grid_columnconfigure(0, weight=1)
        body.bind("<Configure>", self._on_body_resize)

    def perform_search(self):
        """Perform search and update the view."""
        self.search_query = self.search_entry.get().strip()
        self.refresh()

    def clear_search(self):
        """Clear the search query and refresh."""
        self.search_query = ""
        self.search_entry.delete(0, "end")
        self.refresh()

    def _filter_board_rows(self, rows: list[dict]) -> list[dict]:
        """Filter board rows by the current search query (title, next step, notes, segment/category)."""
        if not self.search_query:
            return rows
        needle = self.search_query.lower()
        fields = (
            "title",
            "next_step",
            "notes",
            "segment_name",
            "subsegment_name",
            "category_name",
            "key_field",
        )
        return [
            row
            for row in rows
            if any(needle in str(row.get(field) or "").lower() for field in fields)
        ]

    def refresh(self):
        self.db_manager.ensure_project_boards_for_all_apes()
        self.board_rows = self._filter_board_rows(
            self.db_manager.get_project_boards(
                show_pending=self.show_pending_var.get(),
                show_completed=self.show_completed_var.get(),
            )
        )
        # If we have a selected ID, verify it still exists in the DB at all
        if self.selected_board_id:
            exists = self.db_manager.get_project_board(self.selected_board_id)
            if not exists:
                self.selected_board_id = None

        # When a search hides the selected board, fall back to a visible one
        if self.search_query and self.selected_board_id:
            visible_ids = {row["id"] for row in self.board_rows}
            if self.selected_board_id not in visible_ids:
                self.selected_board_id = None

        if not self.selected_board_id and self.board_rows:
            self.selected_board_id = self.board_rows[0]["id"]
        self._render_cards()
        self._render_detail()
        self._refresh_multi_link_notice()

    def _refresh_multi_link_notice(self):
        """Show how many items still sit on more than one board (BP2).

        Tests: tests/test_project_multi_link.py::test_bp2_the_projects_screen_reports_the_outstanding_count
        """
        label = getattr(self, "multi_link_label", None)
        if label is None:
            return
        try:
            # One query. A separate count query justified itself as "so the
            # caller that only wants the number does not load every row", and
            # after F4 no caller only wants the number — two queries were just
            # a second way for the banner and its names to disagree (P19).
            items = self.db_manager.get_items_on_multiple_project_boards()
            count = len(items)
        except Exception as exc:
            # A cosmetic banner must not take the whole Projects screen down.
            # The failure goes in the banner as well as the log: blanking the
            # label made "the check failed" look exactly like "nothing to
            # report", and the log line goes to a stderr a double-clicked app
            # has nowhere to send — the comment here used to claim the failure
            # was said out loud while the code said nothing (P2).
            logging.getLogger(__name__).warning(
                "[projects] could not check for multi-project items: %s", exc)
            self._show_multi_link_text(
                "Could not check whether any items are filed under more than "
                "one project.")
            return
        self._show_multi_link_text(describe_outstanding_multi_links(count, items))

    def _show_multi_link_text(self, text: str):
        """Show the banner, or take its row back when there is nothing to say.

        An empty label still occupies its grid row — about 36px of header for
        the state that becomes normal once every item has been re-filed.
        """
        label = self.multi_link_label
        label.configure(text=text)
        if text:
            label.grid()
        else:
            label.grid_remove()

    def _schedule_card_render(self, _event=None):
        if self._render_after_id:
            self.after_cancel(self._render_after_id)
        self._render_after_id = self.after(80, self._render_cards)

    def _on_divider_press(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_left = self.left_panel.winfo_width()

    def _on_divider_drag(self, event):
        if self._drag_start_x is None or self._drag_start_left is None:
            return
        total = self.body.winfo_width() - self.SPLITTER_WIDTH
        if total <= (self.MIN_PANEL_WIDTH * 2):
            return
        delta = event.x_root - self._drag_start_x
        left = self._drag_start_left + delta
        max_left = total - self.MIN_PANEL_WIDTH
        left = max(self.MIN_PANEL_WIDTH, min(max_left, left))
        self._split_ratio = left / total
        self._apply_split()

    def _on_divider_release(self, _event):
        self._drag_start_x = None
        self._drag_start_left = None

    def _on_body_resize(self, _event=None):
        self._apply_split()

    def _apply_split(self):
        total = self.body.winfo_width() - self.SPLITTER_WIDTH
        if total <= 0:
            return
        if total <= (self.MIN_PANEL_WIDTH * 2):
            left = max(self.MIN_PANEL_WIDTH, total // 2)
        else:
            max_left = total - self.MIN_PANEL_WIDTH
            left = int(total * self._split_ratio)
            left = max(self.MIN_PANEL_WIDTH, min(max_left, left))
        right = max(self.MIN_PANEL_WIDTH, total - left)
        self.body.grid_columnconfigure(0, minsize=left)
        self.body.grid_columnconfigure(2, minsize=right)

    def _render_cards(self):
        for child in self.cards_frame.winfo_children():
            child.destroy()
        self._card_frames = {}

        metrics = self._card_metrics()
        width = max(self.cards_frame.winfo_width(), metrics["card_width"] + 40)
        columns = max(1, width // (metrics["card_width"] + 16))
        self._card_columns = columns
        for idx in range(columns):
            self.cards_frame.grid_columnconfigure(idx, weight=1)

        if not self.board_rows:
            empty_text = (
                f'No projects match "{self.search_query}".'
                if self.search_query
                else "No project boards yet. Use + New Project to add one."
            )
            ctk.CTkLabel(
                self.cards_frame,
                text=empty_text,
                text_color=semantic_colors()["muted_text"],
            ).grid(row=0, column=0, padx=12, pady=16, sticky="w")
            return

        for index, row in enumerate(self.board_rows):
            column = index % columns
            grid_row = index // columns
            card = self._create_card(self.cards_frame, row)
            card.grid(row=grid_row, column=column, padx=4, pady=6, sticky="n")
            self._card_frames[row["id"]] = card

    def _create_card(self, parent, row: dict) -> ctk.CTkFrame:
        metrics = self._card_metrics()
        color = (row.get("category_color_hex") or "").strip() or semantic_colors()["selected_tint"]
        text_color = pick_text_color(color)
        selected = row["id"] == self.selected_board_id
        border_color = semantic_colors()["primary"] if selected else semantic_colors()["border"]
        rank = int(row.get("display_order") or 0) + 1
        palette = semantic_colors()

        card = ctk.CTkFrame(
            parent,
            width=metrics["card_width"],
            height=metrics["card_height"],
            fg_color=color,
            border_width=3 if selected else 1,
            border_color=border_color,
            corner_radius=12,
        )
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)
        # Row 0: Top info (rank, lineage)
        # Row 1: Title
        # Row 2: Summary (Next Step, Notes) - EXPANDABLE
        # Row 3: Actions - FIXED
        card.grid_rowconfigure(2, weight=1)

        rank_box_width = 28
        rank_box_height = 28
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=(2, metrics["pad_x"]), pady=(metrics["pad_top"], 2))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            top,
            text=str(rank),
            width=rank_box_width,
            height=rank_box_height,
            corner_radius=7,
            fg_color=palette["surface_subtle"],
            text_color=palette["body_text"],
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 2), sticky="w")
        ctk.CTkLabel(
            top,
            text=f"{row.get('subsegment_name') or '-'} - {row.get('category_name') or '-'}",
            font=ctk.CTkFont(size=max(11, metrics["header_font"] - 2), weight="bold"),
            text_color=text_color,
            anchor="center",
            justify="center",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 2))

        ctk.CTkLabel(
            card,
            text=self._clip(row.get("title"), metrics["title_chars"]),
            font=ctk.CTkFont(size=max(11, metrics["title_font"] - 2)),
            text_color=text_color,
            justify="left",
            anchor="nw",
            wraplength=metrics["wraplength"],
        ).grid(row=1, column=0, sticky="ew", padx=(max(6, metrics["pad_x"] - 4), metrics["pad_x"]), pady=(max(1, metrics["title_pad_top"] - 2), 2))

        summary = ctk.CTkFrame(card, fg_color="transparent")
        summary.grid(row=2, column=0, sticky="nsew", padx=metrics["pad_x"], pady=(2, metrics["summary_pad_bottom"]))
        summary.grid_columnconfigure(0, weight=1)
        summary.grid_rowconfigure(1, weight=1)

        # Show ALL of next step (no clipping)
        next_step_text = (row.get('next_step') or '-').strip()
        ctk.CTkLabel(
            summary,
            text=f"Next: {next_step_text}",
            text_color=text_color,
            justify="left",
            anchor="nw",
            font=ctk.CTkFont(size=metrics["body_font"], weight="bold"),
            wraplength=metrics["wraplength"],
        ).grid(row=0, column=0, sticky="ew")

        # Show as much of notes as possible
        notes_text = (row.get('notes') or '').strip()
        if notes_text:
            ctk.CTkLabel(
                summary,
                text=notes_text,
                text_color=text_color,
                justify="left",
                anchor="nw",
                font=ctk.CTkFont(size=metrics["body_font"] - 1),
                wraplength=metrics["wraplength"],
            ).grid(row=1, column=0, sticky="nsew", pady=(2, 0))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=metrics["pad_x"], pady=(4, metrics["pad_bottom"]))
        for idx in range(6):
            actions.grid_columnconfigure(idx, weight=1)

        ctk.CTkButton(
            actions,
            text="" if self.edit_icon_image else self.ICON_EDIT,
            image=self.edit_icon_image,
            width=self.ACTION_BUTTON_WIDTH,
            height=self.ACTION_BUTTON_HEIGHT,
            font=ctk.CTkFont(size=self.ACTION_ICON_FONT_SIZE, weight="bold"),
            command=lambda b=row["id"]: self.edit_project(b),
            fg_color="#FACC15",
            hover_color="#EAB308",
            text_color="#B91C1C",
            border_width=0,
        ).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        ctk.CTkButton(
            actions,
            text=self.ICON_NEW_TASK,
            width=self.ACTION_BUTTON_WIDTH,
            height=self.ACTION_BUTTON_HEIGHT,
            font=ctk.CTkFont(size=self.ACTION_ICON_FONT_SIZE + 2, weight="bold"),
            command=lambda b=row["id"]: self.create_action_item(b),
            **button_style("secondary"),
        ).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        ctk.CTkButton(
            actions,
            text=self.ICON_NOTES,
            width=self.ACTION_BUTTON_WIDTH,
            height=self.ACTION_BUTTON_HEIGHT,
            font=ctk.CTkFont(size=self.ACTION_ICON_FONT_SIZE, weight="bold"),
            command=lambda b=row["id"]: self.add_note_to_project(b),
            **button_style("secondary"),
        ).grid(row=0, column=2, padx=2, pady=2, sticky="ew")

        ctk.CTkButton(
            actions,
            text=self.ICON_PENDING,
            width=self.ACTION_BUTTON_WIDTH,
            height=self.ACTION_BUTTON_HEIGHT,
            font=ctk.CTkFont(size=self.ACTION_ICON_FONT_SIZE, weight="bold"),
            command=lambda b=row["id"]: self.set_status(b, ProjectBoardStatus.PENDING),
            **button_style("secondary"),
        ).grid(row=0, column=3, padx=2, pady=2, sticky="ew")
        ctk.CTkButton(
            actions,
            text=self.ICON_COMPLETE,
            width=self.ACTION_BUTTON_WIDTH,
            height=self.ACTION_BUTTON_HEIGHT,
            font=ctk.CTkFont(size=self.ACTION_ICON_FONT_SIZE + 2, weight="bold"),
            command=lambda b=row["id"]: self.set_status(b, ProjectBoardStatus.COMPLETED),
            **button_style("secondary"),
        ).grid(row=0, column=4, padx=2, pady=2, sticky="ew")
        ctk.CTkButton(
            actions,
            text=self.ICON_DELETE,
            width=self.ACTION_BUTTON_WIDTH,
            height=self.ACTION_BUTTON_HEIGHT,
            font=ctk.CTkFont(size=self.ACTION_ICON_FONT_SIZE, weight="bold"),
            command=lambda b=row["id"]: self.delete_project(b),
            **button_style("secondary"),
        ).grid(row=0, column=5, padx=2, pady=2, sticky="ew")

        self._bind_note_clicks(card, row["id"], actions)
        return card

    def _render_detail(self):
        for child in self.items_frame.winfo_children():
            child.destroy()

        # Clear selections when rendering new detail view
        self.selected_item_ids.clear()
        self.item_checkbox_vars.clear()

        if not self.selected_board_id:
            self.detail_title.configure(text="Select a Project")
            self.detail_meta.configure(text="")
            return

        board = self.db_manager.get_project_board(self.selected_board_id)
        if not board:
            self.detail_title.configure(text="Select a Project")
            self.detail_meta.configure(text="")
            return

        row = next((item for item in self.board_rows if item["id"] == board.id), None)
        if not row:
            # Try to fetch directly if not in filtered list
            row = dict(self.db_manager.db.conn.execute("SELECT * FROM project_boards WHERE id = ?", (board.id,)).fetchone() or {})
            if row:
                # SELECT * has neither aggregate, and this path is reachable by
                # unticking a status filter while its board is selected. Ask for
                # them rather than showing nothing or, worse, zero.
                row.update(self.db_manager.get_project_time_totals(board.id))
            if not row:
                self.detail_title.configure(text=board.title)
                self.detail_meta.configure(text="")
                return

        self.detail_title.configure(text=row["title"])
        meta_lines = [
            f"{row.get('ape_year') or ''} | {row.get('segment_name') or ''} | {row.get('subsegment_name') or ''} | "
            f"{row.get('category_name') or ''} | Status: {row.get('status')}",
            f"Next Step: {row.get('next_step') or '-'}",
        ]
        time_line = project_time_line(row)
        if time_line:
            meta_lines.append(time_line)
        self.detail_meta.configure(text="\n".join(meta_lines))
        category_color = (row.get("category_color_hex") or "").strip() or semantic_colors()["surface_subtle"]

        toolbar = ctk.CTkFrame(self.items_frame, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=2, pady=(2, 8))
        self.btn_create_action = ctk.CTkButton(toolbar, text="Create Action Item", command=lambda: self.create_action_item(board.id), **button_style("primary"))
        self.btn_create_action.pack(
            side="left", padx=4
        )
        self.btn_link_action = ctk.CTkButton(
            toolbar,
            text="Link Action Item",
            command=lambda: self.link_existing_action_item(board.id),
            fg_color=category_color,
            hover_color=category_color,
            text_color=pick_text_color(category_color),
            border_width=0,
        )
        self.btn_link_action.pack(
            side="left", padx=4
        )
        self.btn_bulk_edit = ctk.CTkButton(
            toolbar,
            text="Bulk Edit",
            command=self.on_bulk_edit_clicked,
            state="disabled",
            **button_style("secondary"),
        )
        self.btn_bulk_edit.pack(side="left", padx=4)
        self.btn_edit_project = ctk.CTkButton(toolbar, text="Edit Project", command=lambda: self.edit_project(board.id), **button_style("secondary"))
        self.btn_edit_project.pack(
            side="left", padx=4
        )
        self.btn_create_note = ctk.CTkButton(toolbar, text="Create Note", command=lambda: self.create_note(board.id), **button_style("secondary"))
        self.btn_create_note.pack(
            side="left", padx=4
        )
        self.btn_link_note = ctk.CTkButton(toolbar, text="Link Note", command=lambda: self.link_note(board.id), **button_style("secondary"))
        self.btn_link_note.pack(
            side="left", padx=4
        )
        self.btn_open_notes = ctk.CTkButton(toolbar, text="Open Notes", command=lambda: self.open_note_picker(board.id), **button_style("secondary"))
        self.btn_open_notes.pack(
            side="left", padx=4
        )
        if board.status != ProjectBoardStatus.ACTIVE:
            self.btn_set_active = ctk.CTkButton(toolbar, text="Set Active", command=lambda: self.set_status(board.id, ProjectBoardStatus.ACTIVE), **button_style("secondary"))
            self.btn_set_active.pack(
                side="left", padx=4
            )

        # M4.A.1 — Shared "Show Completed" toggle above BOTH the Project Notes
        # section and the Action Items section. Toggling refreshes both lists
        # via _render_detail.
        # Spec: docs/implementation_plan_2026-06-06_project_notes.md#M4.A.1, M4.A.2
        shared_filter = ctk.CTkFrame(self.items_frame, fg_color="transparent")
        shared_filter.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 4))
        shared_filter.grid_columnconfigure(0, weight=1)
        ctk.CTkCheckBox(
            shared_filter,
            text="Show Completed",
            variable=self.show_completed_items_var,
            command=self._render_detail,
        ).grid(row=0, column=1, sticky="e", padx=8, pady=4)

        self.notes_links_frame = ctk.CTkFrame(self.items_frame)
        self.notes_links_frame.grid(row=2, column=0, sticky="ew", padx=2, pady=(0, 8))
        self.notes_links_frame.grid_columnconfigure(0, weight=1)
        self.load_notes()

        all_tasks = self.db_manager.get_project_board_items(board.id)
        if not all_tasks:
            ctk.CTkLabel(
                self.items_frame,
                text="No action items linked yet. Use Create Action Item to add the first task.",
                text_color=semantic_colors()["muted_text"],
            ).grid(row=3, column=0, sticky="w", padx=6, pady=12)
            return

        # M4.A.2 — Filter respects the SHARED Show Completed toggle. The toggle
        # itself was rendered above (row 1) and refreshes _render_detail, which
        # re-runs both the notes section and this items section.
        show_completed = self.show_completed_items_var.get()
        tasks = [t for t in all_tasks if show_completed or t.status != "completed"]
        completed_count = sum(1 for t in all_tasks if t.status == "completed")

        # Action Items header — bold section title + Select All + count.
        # The Show Completed checkbox is intentionally NOT here anymore (M4):
        # it lives in the shared filter row above both sections.
        items_header = ctk.CTkFrame(self.items_frame, fg_color="transparent")
        items_header.grid(row=3, column=0, sticky="ew", padx=2, pady=(8, 4))
        items_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            items_header,
            text="Action Items",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 2))

        self.check_all_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            items_header,
            text="Select All",
            variable=self.check_all_var,
            command=self._on_check_all_changed,
            width=24,
            checkbox_width=24,
            checkbox_height=24,
        ).grid(row=1, column=0, sticky="w", padx=6, pady=4)

        if completed_count and not show_completed:
            count_text = f"{len(tasks)} shown • {completed_count} completed hidden"
        else:
            count_text = f"{len(tasks)} item{'s' if len(tasks) != 1 else ''}"
        ctk.CTkLabel(
            items_header,
            text=count_text,
            text_color=semantic_colors()["muted_text"],
            font=ctk.CTkFont(size=12),
        ).grid(row=1, column=1, sticky="e", padx=8, pady=4)

        if not tasks:
            ctk.CTkLabel(
                self.items_frame,
                text=f"All {completed_count} item(s) completed. Enable 'Show Completed' to view them.",
                text_color=semantic_colors()["muted_text"],
            ).grid(row=4, column=0, sticky="w", padx=6, pady=12)
            return

        for idx, item in enumerate(tasks, start=4):
            row_frame = ctk.CTkFrame(self.items_frame)
            row_frame.grid(row=idx, column=0, sticky="ew", padx=2, pady=4)
            row_frame.grid_columnconfigure(1, weight=1)

            checkbox_var = ctk.BooleanVar(value=False)
            self.item_checkbox_vars[item.id] = checkbox_var

            ctk.CTkCheckBox(
                row_frame,
                text="",
                variable=checkbox_var,
                width=24,
                checkbox_width=24,
                checkbox_height=24,
                command=lambda item_id=item.id: self._on_item_checkbox_changed(item_id),
            ).grid(row=0, column=0, rowspan=2, sticky="nw", padx=6, pady=8)

            left = ctk.CTkFrame(row_frame, fg_color="transparent")
            left.grid(row=0, column=1, sticky="ew", padx=8, pady=8)
            left.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                left,
                text=item.title,
                font=ctk.CTkFont(size=15, weight="bold"),
                anchor="w",
                justify="left",
            ).grid(row=0, column=0, sticky="w")
            meta = (
                f"Status: {item.status} | Start: {item.start_date or '-'} | Due: {item.due_date or '-'}\n"
                f"Next: {item.next_action or '-'}"
            )
            ctk.CTkLabel(left, text=meta, justify="left", anchor="w").grid(row=1, column=0, sticky="w", pady=(2, 0))

            actions = ctk.CTkFrame(row_frame, fg_color="transparent")
            actions.grid(row=0, column=2, sticky="e", padx=8, pady=8)
            ctk.CTkButton(actions, text="Edit", width=70, command=lambda item_id=item.id: self.edit_item(item_id), **button_style("secondary")).pack(
                side="left", padx=3
            )
            if item.status == "open":
                ctk.CTkButton(actions, text="Complete", width=82, command=lambda item_id=item.id: self.complete_item(item_id), **button_style("secondary")).pack(
                    side="left", padx=3
                )
            ctk.CTkButton(actions, text="Unlink", width=70, command=lambda item_id=item.id: self.unlink_item(item_id), **button_style("secondary")).pack(
                side="left", padx=3
            )

    def add_project(self):
        dialog = ProjectBoardEditorDialog(self, self.db_manager)
        self.wait_window(dialog)
        if dialog.result in (None, "__cancel__"):
            return
        self.db_manager.create_project_board(dialog.result)
        self.selected_board_id = dialog.result.id
        self.refresh()

    def edit_project(self, board_id: str):
        board = self.db_manager.get_project_board(board_id)
        if not board:
            return
        dialog = ProjectBoardEditorDialog(self, self.db_manager, board)
        self.wait_window(dialog)
        if dialog.result in (None, "__cancel__"):
            return
        self.db_manager.update_project_board(dialog.result)
        self.selected_board_id = board_id
        self.refresh()

    def delete_project(self, board_id: str):
        board = self.db_manager.get_project_board(board_id)
        if not board:
            return
        if not messagebox.askyesno("Delete Project", f"Delete project '{board.title}'?", parent=self):
            return
        self.db_manager.delete_project_board(board_id)
        if self.selected_board_id == board_id:
            self.selected_board_id = None
        self.refresh()

    def set_status(self, board_id: str, status: str):
        self.db_manager.set_project_board_status(board_id, status)
        if status != ProjectBoardStatus.ACTIVE and self.selected_board_id == board_id:
            self.selected_board_id = None
        self.refresh()

    def select_project(self, board_id: str):
        self.selected_board_id = board_id
        self._render_cards()
        self._render_detail()

    def open_project_from_note(self, board_id: str):
        self.selected_board_id = board_id
        self._render_cards()
        self._render_detail()
        self.edit_project(board_id)

    def _on_card_press(self, event, board_id: str):
        self._dragging_board_id = board_id
        self._drag_pointer_start = (event.x_root, event.y_root)

    def _on_card_release(self, event, board_id: str):
        if self._dragging_board_id != board_id:
            return
        moved = False
        if self._drag_pointer_start is not None:
            dx = abs(event.x_root - self._drag_pointer_start[0])
            dy = abs(event.y_root - self._drag_pointer_start[1])
            moved = dx >= self._drag_threshold or dy >= self._drag_threshold

        source_id = self._dragging_board_id
        self._dragging_board_id = None
        self._drag_pointer_start = None

        if moved:
            target_id = self._board_id_at_pointer()
            if target_id and target_id != source_id:
                self._reorder_cards(source_id, target_id)
            return

        self.select_project(board_id)

    def _board_id_at_pointer(self) -> Optional[str]:
        x, y = self.winfo_pointerxy()
        target = self.winfo_containing(x, y)
        while target is not None:
            for board_id, frame in self._card_frames.items():
                if target == frame:
                    return board_id
            target = target.master
        return None

    def _reorder_cards(self, source_id: str, target_id: str):
        ordered_ids = [row["id"] for row in self.board_rows]
        if source_id not in ordered_ids or target_id not in ordered_ids:
            return
        ordered_ids.remove(source_id)
        target_index = ordered_ids.index(target_id)
        ordered_ids.insert(target_index, source_id)
        self.db_manager.set_project_board_order(ordered_ids)
        self.refresh()

    def _on_note_size_slider(self, value):
        self._custom_card_width = int(float(value))
        self.note_size_value_label.configure(text=f"{self._custom_card_width}px")
        self._render_cards()

    def create_action_item(self, board_id: str):
        try:
            board = self.db_manager.get_project_board(board_id)
            if not board:
                return
            
            # Use segment_name from the board rows if available, fallback to 'Project'
            row = next((r for r in self.board_rows if r["id"] == board_id), None)
            who_value = (row or {}).get("segment_name") or "Project"
            
            title = (board.next_step or board.title or "Project Task").strip()
            description_lines = [f"Project: {board.title}"]
            if board.notes:
                description_lines.extend(["", board.notes])
            item = ActionItem(
                who=who_value,
                title=title,
                description="\n".join(description_lines),
                next_action=board.next_step,
                annual_plan_element_id=board.annual_plan_element_id,
                start_date=date.today().isoformat(),
                status="open",
                category="Project Board",
                importance=board.importance,
                urgency=5,  # Default to medium
                size=5,
                value=5,
            )
            item.update_priority_score()
            item_id = self.db_manager.create_action_item(item, apply_defaults=True)
            # Exclusive, like every other filing surface. The item was created
            # one line above so it has nothing to drop and the two calls are
            # equivalent here — but "equivalent by accident of argument" is how
            # the additive path survived everywhere else, and the notice this
            # screen shows tells the user filing *is* exclusive (P5).
            self.db_manager.link_item_to_project_exclusive(board_id, item_id)
            self.selected_board_id = board_id
            
            # We refresh FIRST to update the list, then open the editor
            self.refresh()
            self.edit_item(item_id)
        except Exception as e:
            messagebox.showerror("Error Creating Item", f"Failed to create action item: {str(e)}", parent=self)

    def complete_item(self, item_id: str):
        self.db_manager.complete_action_item(item_id)
        notify_weekly_tactic_changes(self.db_manager, self)
        self.refresh()

    def unlink_item(self, item_id: str):
        if not self.selected_board_id:
            return
        self.db_manager.unlink_action_item_from_project_board(self.selected_board_id, item_id)
        self.refresh()

    def _on_item_checkbox_changed(self, item_id: str):
        if self.item_checkbox_vars[item_id].get():
            self.selected_item_ids.add(item_id)
        else:
            self.selected_item_ids.discard(item_id)
        self._update_bulk_edit_button_state()

    def _on_check_all_changed(self):
        state = self.check_all_var.get()
        self.selected_item_ids.clear()
        for item_id, checkbox_var in self.item_checkbox_vars.items():
            checkbox_var.set(state)
            if state:
                self.selected_item_ids.add(item_id)
        self._update_bulk_edit_button_state()

    def _update_bulk_edit_button_state(self):
        if hasattr(self, "btn_bulk_edit"):
            if self.selected_item_ids:
                self.btn_bulk_edit.configure(state="normal")
            else:
                self.btn_bulk_edit.configure(state="disabled")

    def on_bulk_edit_clicked(self):
        if not self.selected_item_ids:
            return
        dialog = BulkEditItemsDialog(self, self.db_manager, list(self.selected_item_ids))
        self.wait_window(dialog)
        if dialog.result:
            self._apply_bulk_edit(dialog.result)

    def _apply_bulk_edit(self, result: dict):
        item_ids = result["item_ids"]
        start_date = result["start_date"]
        priority = result["priority"]

        if not item_ids:
            return

        try:
            self.db_manager.bulk_update_action_items(item_ids, start_date, priority)
            notify_weekly_tactic_changes(self.db_manager, self)
            self.selected_item_ids.clear()
            self.item_checkbox_vars.clear()
            self.refresh()
        except Exception as e:
            messagebox.showerror("Bulk Edit Error", f"Failed to update items: {str(e)}", parent=self)

    def link_existing_action_item(self, board_id: str):
        dialog = LinkProjectActionItemsDialog(self, self.db_manager, board_id, self.refresh)
        self.wait_window(dialog)

    def edit_item(self, item_id: str):
        from .item_editor import ItemEditorDialog

        # Parent should be the main app window
        ItemEditorDialog(
            self.app,
            self.db_manager,
            item_id=item_id,
            vps_manager=self.app.vps_manager,
            on_close_callback=self.refresh,
        )

    def add_note_to_project(self, board_id: str):
        """Prompt the user to create a new or link an existing Obsidian note.

        Purpose: Handler for the 📄 icon on a project tile.
        Spec:    docs/implementation_plan_2026-06-06.md (paper-icon-enhancement)
        Tests:   tests/test_project_note_chooser.py::test_handler_dispatches_to_create_note
                 tests/test_project_note_chooser.py::test_handler_dispatches_to_link_note
                 tests/test_project_note_chooser.py::test_handler_does_nothing_on_cancel
        """
        board = self.db_manager.get_project_board(board_id)
        if not board:
            return
        chooser = NoteActionChooserDialog(self, board.title)
        self.wait_window(chooser)
        if chooser.result == NoteActionChooserDialog.CHOICE_CREATE:
            self.create_note(board_id)
        elif chooser.result == NoteActionChooserDialog.CHOICE_LINK:
            self.link_note(board_id)
        # cancel/closed → no-op

    def create_note(self, board_id: str):
        board = self.db_manager.get_project_board(board_id)
        if not board:
            return
        from .item_editor_dialogs import CreateNoteDialog
        dialog = CreateNoteDialog(self, self.db_manager, "project_board", board.id, board.title)
        self.wait_window(dialog)
        self.refresh()

    def link_note(self, board_id: str):
        board = self.db_manager.get_project_board(board_id)
        if not board:
            return
        from .item_editor_dialogs import LinkNoteDialog
        dialog = LinkNoteDialog(self, self.db_manager, "project_board", board.id)
        self.wait_window(dialog)
        self.refresh()

    def open_note_picker(self, board_id: str):
        from ..app_settings import AppSettings
        from ..obsidian_utils import open_in_obsidian

        links = self.db_manager.get_project_board_links(board_id)
        if not links:
            messagebox.showinfo("No Notes", "This project has no linked Obsidian notes yet.", parent=self)
            return
        settings = AppSettings.load()
        if not settings.obsidian_vault_path:
            messagebox.showerror("Obsidian Not Set Up", "Configure an Obsidian vault in Settings first.", parent=self)
            return
        if len(links) == 1:
            open_in_obsidian(links[0].url, settings.obsidian_vault_path)
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Project Notes")
        dialog.geometry("520x360")
        dialog.transient(self)
        dialog.grab_set()
        frame = ctk.CTkScrollableFrame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        frame.grid_columnconfigure(0, weight=1)
        for link in links:
            row = ctk.CTkFrame(frame)
            row.pack(fill="x", pady=4)
            label = link.label or link.url
            ctk.CTkLabel(row, text=label, anchor="w").pack(side="left", fill="x", expand=True, padx=8, pady=8)
            ctk.CTkButton(
                row,
                text="Open",
                width=70,
                command=lambda path=link.url: self._open_note_path(path),
                **button_style("secondary"),
            ).pack(side="right", padx=4, pady=4)
            ctk.CTkButton(
                row,
                text="Delete",
                width=70,
                command=lambda link_id=link.id, d=dialog: self.delete_note_link(link_id, d),
                **button_style("danger"),
            ).pack(side="right", padx=4, pady=4)

    def delete_note_link(self, link_id: str, dialog=None):
        self.db_manager.delete_project_board_link(link_id)
        if dialog is not None:
            dialog.destroy()
        self.load_notes()

    def load_notes(self):
        """Render the Project Notes section (visible list of linked notes).

        Purpose: M3 — show Project Notes as a first-class list above Action Items,
                 each row with status + Open/Complete-or-Reopen/Unlink controls.
                 No checkbox, no priority, no dates (per user clarification).
        Spec:    docs/implementation_plan_2026-06-06_project_notes.md#M3
        Tests:   tests/test_project_notes.py::TestM3UI::test_project_notes_header_rendered
                 tests/test_project_notes.py::TestM3UI::test_project_note_row_has_status_buttons_no_checkbox
                 tests/test_project_notes.py::TestM3UI::test_complete_button_updates_status
                 tests/test_project_notes.py::TestM3UI::test_notes_count_label
        """
        if not hasattr(self, "notes_links_frame") or not self.selected_board_id:
            return

        for child in self.notes_links_frame.winfo_children():
            child.destroy()

        # Filter respects the shared Show Completed toggle (added in M4).
        # Default attr is True so this method is safe to call before M4 wiring.
        show_completed = getattr(self, "show_completed_items_var", None)
        include_completed = show_completed.get() if show_completed else True

        all_links = self.db_manager.get_project_board_links(
            self.selected_board_id, include_completed=True
        )
        shown_links = (
            all_links if include_completed
            else [link for link in all_links if link.status != "completed"]
        )
        completed_hidden = sum(1 for link in all_links if link.status == "completed") \
            if not include_completed else 0

        # M3.A.1 — Bold "Project Notes" section header
        header_row = ctk.CTkFrame(self.notes_links_frame, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 2))
        header_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header_row,
            text="Project Notes",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(0, 0))

        # M3.A.4 — Count label
        if completed_hidden:
            count_text = (
                f"{len(shown_links)} shown • {completed_hidden} completed hidden"
            )
        else:
            count_text = (
                f"{len(shown_links)} note{'s' if len(shown_links) != 1 else ''} shown"
            )
        self.notes_count_label = ctk.CTkLabel(
            header_row,
            text=count_text,
            text_color=semantic_colors()["muted_text"],
            font=ctk.CTkFont(size=12),
            anchor="e",
        )
        self.notes_count_label.grid(row=0, column=1, sticky="e", padx=8)

        if not shown_links:
            empty_msg = (
                f"All {completed_hidden} note(s) completed. Enable 'Show Completed' to view them."
                if completed_hidden else
                "No notes linked yet. Use Create Note or Link Note to add one."
            )
            ctk.CTkLabel(
                self.notes_links_frame,
                text=empty_msg,
                text_color=semantic_colors()["muted_text"],
                font=ctk.CTkFont(size=12, slant="italic"),
                anchor="w",
            ).pack(fill="x", pady=(2, 0), padx=6)
            return

        for link in shown_links:
            self._render_project_note_row(link)

    def _render_project_note_row(self, link):
        """Render one Project Note row: label, status pill, Open/Complete-or-Reopen/Unlink.

        Spec:    docs/implementation_plan_2026-06-06_project_notes.md#M3.A.2
        Tests:   tests/test_project_notes.py::TestM3UI::test_project_note_row_has_status_buttons_no_checkbox
        """
        row = ctk.CTkFrame(self.notes_links_frame, fg_color="transparent")
        row.pack(fill="x", pady=2, padx=2)

        label_text = link.label or link.url
        ctk.CTkLabel(
            row,
            text=f"📄 {label_text}",
            anchor="w",
            font=ctk.CTkFont(size=13),
        ).pack(side="left", fill="x", expand=True, padx=4)

        status_color = (
            semantic_colors().get("success_text") or semantic_colors().get("muted_text")
            if link.status == "completed"
            else semantic_colors().get("body_text") or semantic_colors().get("muted_text")
        )
        ctk.CTkLabel(
            row,
            text=link.status,
            text_color=status_color,
            font=ctk.CTkFont(size=12),
            anchor="e",
        ).pack(side="left", padx=(4, 8))

        ctk.CTkButton(
            row,
            text="Open",
            width=60,
            height=24,
            command=lambda path=link.url: self._open_note_path(path),
            **button_style("secondary"),
        ).pack(side="left", padx=2)

        if link.status == "completed":
            ctk.CTkButton(
                row,
                text="Reopen",
                width=70,
                height=24,
                command=lambda lid=link.id: self._on_reopen_project_note(lid),
                **button_style("secondary"),
            ).pack(side="left", padx=2)
        else:
            ctk.CTkButton(
                row,
                text="Complete",
                width=80,
                height=24,
                command=lambda lid=link.id: self._on_complete_project_note(lid),
                **button_style("secondary"),
            ).pack(side="left", padx=2)

        ctk.CTkButton(
            row,
            text="Unlink",
            width=60,
            height=24,
            command=lambda lid=link.id: self.delete_note_link(lid),
            **button_style("danger"),
        ).pack(side="left", padx=2)

    def _on_complete_project_note(self, link_id: str):
        """Mark a Project Note completed and refresh the section.

        Spec: docs/implementation_plan_2026-06-06_project_notes.md#M3.A.3
        Tests: tests/test_project_notes.py::TestM3UI::test_complete_button_updates_status
        """
        self.db_manager.complete_project_note(link_id)
        self.load_notes()

    def _on_reopen_project_note(self, link_id: str):
        """Mark a Project Note open (reverse of complete) and refresh the section.

        Spec: docs/implementation_plan_2026-06-06_project_notes.md#M3.A.3
        Tests: tests/test_project_notes.py::TestM3UI::test_reopen_button_updates_status
        """
        self.db_manager.reopen_project_note(link_id)
        self.load_notes()

    def _open_note_path(self, path: str):
        from ..obsidian_utils import open_in_obsidian
        from ..app_settings import AppSettings
        settings = AppSettings.load()
        if settings.obsidian_vault_path:
            open_in_obsidian(path, settings.obsidian_vault_path)
        else:
            messagebox.showerror("Error", "Obsidian vault path not configured in settings.")

    def _bind_click_recursive(self, widget, callback):
        widget.bind("<Button-1>", callback)
        for child in widget.winfo_children():
            self._bind_click_recursive(child, callback)

    def _bind_note_clicks(self, card, board_id: str, actions):
        def bind_tree(widget):
            if widget == actions:
                return
            widget.bind("<ButtonPress-1>", lambda event, item_id=board_id: self._on_card_press(event, item_id))
            widget.bind("<ButtonRelease-1>", lambda event, item_id=board_id: self._on_card_release(event, item_id))
            for child in widget.winfo_children():
                if child == actions:
                    continue
                bind_tree(child)

        bind_tree(card)

    def _clip(self, value: Optional[str], limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text or "-"
        return text[: max(1, limit - 3)].rstrip() + "..."

    def _card_metrics(self) -> dict[str, int]:
        compact = self.compact_height_var.get()
        metrics = {
            "card_width": 235,
            "card_height": 280,
            "header_font": 15,
            "title_font": 18,
            "body_font": 14,
            "title_chars": 34,
            "next_chars": 34,
            "wraplength": 211,
            "pad_x": 10,
            "pad_top": 10,
            "title_pad_top": 4,
            "summary_pad_bottom": 4,
            "pad_bottom": 10,
        }
        base_width = metrics["card_width"]
        scale = self._custom_card_width / base_width
        metrics["card_width"] = int(self._custom_card_width)
        metrics["card_height"] = max(150, int(metrics["card_height"] * scale))
        metrics["header_font"] = max(10, int(metrics["header_font"] * scale))
        metrics["title_font"] = max(11, int(metrics["title_font"] * scale))
        metrics["body_font"] = max(10, int(metrics["body_font"] * scale))
        metrics["title_chars"] = max(18, int(metrics["title_chars"] * scale))
        metrics["next_chars"] = max(18, int(metrics["next_chars"] * scale))
        metrics["wraplength"] = max(130, metrics["card_width"] - (metrics["pad_x"] * 2) - 4)
        if compact:
            metrics["card_height"] = max(150, metrics["card_height"] - 35)
            metrics["pad_top"] = max(4, metrics["pad_top"] - 2)
            metrics["title_pad_top"] = 2
            metrics["summary_pad_bottom"] = 2
            metrics["pad_bottom"] = max(4, metrics["pad_bottom"] - 2)
        return metrics
