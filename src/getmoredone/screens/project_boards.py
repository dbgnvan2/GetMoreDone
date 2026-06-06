"""Project Boards screen with square project cards and linked action items."""

from __future__ import annotations

from datetime import date
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk
from PIL import Image

from ..color_contrast import pick_text_color
from ..models import ActionItem, PriorityFactors, ProjectBoard, ProjectBoardStatus
from ..paths import project_root
from ..theme import button_style, combo_box_style, semantic_colors

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

        ctk.CTkLabel(root, text="Annual Plan Element").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ape_labels: list[str] = ["(Optional: No linked APE)"]
        selected_label = ape_labels[0]
        for row in self.ape_rows:
            label = self._format_ape_label(row)
            self.ape_label_to_id[label] = row["id"]
            ape_labels.append(label)
            if self.board and row["id"] == self.board.annual_plan_element_id:
                selected_label = label
        
        self.ape_var = ctk.StringVar(value=selected_label)
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
        ape_id = self.ape_label_to_id.get(self.ape_var.get())

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

        self.title("Link Action Items")
        self.geometry("760x520")
        self.transient(parent)
        self.grab_set()

        self._build()
        self.refresh_results()

    def _build(self):
        root = ctk.CTkFrame(self)
        root.pack(fill="both", expand=True, padx=12, pady=12)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        search = ctk.CTkFrame(root)
        search.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        search.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(search, text="Search").grid(row=0, column=0, padx=8, pady=8)
        ctk.CTkEntry(search, textvariable=self.search_var, placeholder_text="Search title, description, next step, who").grid(
            row=0, column=1, sticky="ew", padx=8, pady=8
        )
        ctk.CTkButton(search, text="Close", width=90, command=self.destroy, **button_style("secondary")).grid(
            row=0, column=2, padx=8, pady=8
        )

        self.results = ctk.CTkScrollableFrame(root)
        self.results.grid(row=1, column=0, sticky="nsew")
        self.results.grid_columnconfigure(0, weight=1)

    def refresh_results(self):
        for child in self.results.winfo_children():
            child.destroy()

        linked_ids = {item.id for item in self.db_manager.get_project_board_items(self.board_id)}
        query = self.search_var.get().strip()
        items = self.db_manager.search_items(query) if query else self.db_manager.get_all_items(status_filter="open", sort_by="updated_at", sort_desc=True)

        filtered = [item for item in items if item.id not in linked_ids]
        if not filtered:
            ctk.CTkLabel(self.results, text="No action items available to link.", text_color=semantic_colors()["muted_text"]).grid(
                row=0, column=0, padx=10, pady=12, sticky="w"
            )
            return

        for idx, item in enumerate(filtered[:100]):
            row = ctk.CTkFrame(self.results)
            row.grid(row=idx, column=0, sticky="ew", padx=4, pady=3)
            row.grid_columnconfigure(0, weight=1)
            title = item.title
            meta = f"{item.who or '-'} | Start: {item.start_date or '-'} | Due: {item.due_date or '-'}"
            ctk.CTkLabel(row, text=title, anchor="w", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, sticky="w", padx=8, pady=(6, 2)
            )
            ctk.CTkLabel(row, text=meta, anchor="w").grid(
                row=1, column=0, sticky="w", padx=8, pady=(0, 6)
            )
            ctk.CTkButton(
                row,
                text="Link",
                width=72,
                command=lambda item_id=item.id: self._link(item_id),
                **button_style("primary"),
            ).grid(row=0, column=1, rowspan=2, padx=8, pady=8)

    def _link(self, item_id: str):
        self.db_manager.link_action_item_to_project_board(self.board_id, item_id)
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
        self.selected_item_ids: set[str] = {}
        self.item_checkbox_vars: dict[str, ctk.BooleanVar] = {}

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

    def refresh(self):
        self.db_manager.ensure_project_boards_for_all_apes()
        self.board_rows = self.db_manager.get_project_boards(
            show_pending=self.show_pending_var.get(),
            show_completed=self.show_completed_var.get(),
        )
        # If we have a selected ID, verify it still exists in the DB at all
        if self.selected_board_id:
            exists = self.db_manager.get_project_board(self.selected_board_id)
            if not exists:
                self.selected_board_id = None
        
        if not self.selected_board_id and self.board_rows:
            self.selected_board_id = self.board_rows[0]["id"]
        self._render_cards()
        self._render_detail()

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
            ctk.CTkLabel(
                self.cards_frame,
                text="No project boards yet. Use + New Project to add one.",
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
            command=lambda b=row["id"]: self.open_note_picker(b),
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
            if not row:
                self.detail_title.configure(text=board.title)
                self.detail_meta.configure(text="")
                return

        self.detail_title.configure(text=row["title"])
        self.detail_meta.configure(
            text=(
                f"{row.get('ape_year') or ''} | {row.get('segment_name') or ''} | {row.get('subsegment_name') or ''} | "
                f"{row.get('category_name') or ''} | Status: {row.get('status')}\n"
                f"Next Step: {row.get('next_step') or '-'}"
            )
        )
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

        self.notes_links_frame = ctk.CTkFrame(self.items_frame)
        self.notes_links_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 8))
        self.notes_links_frame.grid_columnconfigure(0, weight=1)
        self.load_notes()

        tasks = self.db_manager.get_project_board_items(board.id)
        if not tasks:
            ctk.CTkLabel(
                self.items_frame,
                text="No action items linked yet. Use Create Action Item to add the first task.",
                text_color=semantic_colors()["muted_text"],
            ).grid(row=2, column=0, sticky="w", padx=6, pady=12)
            return

        for idx, item in enumerate(tasks, start=2):
            row_frame = ctk.CTkFrame(self.items_frame)
            row_frame.grid(row=idx, column=0, sticky="ew", padx=2, pady=4)
            row_frame.grid_columnconfigure(1, weight=1)

            checkbox_var = ctk.BooleanVar(value=False)
            self.item_checkbox_vars[item.id] = checkbox_var
            checkbox_var.trace_add("write", lambda *_args, item_id=item.id: self._on_item_checkbox_changed(item_id))

            ctk.CTkCheckBox(
                row_frame,
                text="",
                variable=checkbox_var,
                width=24,
                checkbox_width=24,
                checkbox_height=24,
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
            self.db_manager.link_action_item_to_project_board(board_id, item_id)
            self.selected_board_id = board_id
            
            # We refresh FIRST to update the list, then open the editor
            self.refresh()
            self.edit_item(item_id)
        except Exception as e:
            messagebox.showerror("Error Creating Item", f"Failed to create action item: {str(e)}", parent=self)

    def complete_item(self, item_id: str):
        self.db_manager.complete_action_item(item_id)
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
        if not hasattr(self, "notes_links_frame") or not self.selected_board_id:
            return

        for child in self.notes_links_frame.winfo_children():
            child.destroy()

        links = self.db_manager.get_project_board_links(self.selected_board_id)
        if not links:
            ctk.CTkLabel(
                self.notes_links_frame,
                text="No notes linked to this project.",
                text_color=semantic_colors()["muted_text"],
                font=ctk.CTkFont(size=12, slant="italic"),
            ).pack(pady=4)
            return

        for link in links:
            row = ctk.CTkFrame(self.notes_links_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            label = link.label or link.url
            ctk.CTkLabel(
                row, 
                text=f"📄 {label}", 
                anchor="w",
                font=ctk.CTkFont(size=13)
            ).pack(side="left", fill="x", expand=True, padx=4)
            
            ctk.CTkButton(
                row,
                text="Open",
                width=60,
                height=24,
                command=lambda path=link.url: self._open_note_path(path),
                **button_style("secondary"),
            ).pack(side="left", padx=2)
            
            ctk.CTkButton(
                row,
                text="Remove",
                width=60,
                height=24,
                command=lambda lid=link.id: self.delete_note_link(lid),
                **button_style("danger"),
            ).pack(side="left", padx=2)

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
