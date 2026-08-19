"""Project picker for the Action Item editor.

Purpose: PL1/PL5 — let the item editor file an Action Item under a Project,
         clear that link, or create a brand-new Project without leaving the
         editor.
Spec:    docs/implementation_plan_2026-08-19_item_editor_project_link.md#pl1
Tests:   tests/test_item_editor_project_link.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import customtkinter as ctk

from ..models import ProjectBoardStatus
from ..theme import button_style, semantic_colors, status_text_color

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager


class SetProjectDialog(ctk.CTkToplevel):
    """Pick the Project an Action Item is filed under."""

    #: Statuses offered for a *new* choice. A completed project is never
    #: offered, but one already linked to this item is still listed (PL1) so
    #: the current value can never silently vanish from the picker.
    SELECTABLE_STATUSES = (ProjectBoardStatus.ACTIVE, ProjectBoardStatus.PENDING)

    def __init__(
        self,
        parent,
        db_manager: "DatabaseManager",
        item_title: str = "Action Item",
        current_board_id: Optional[str] = None,
        on_select: Optional[Callable[[Optional[str]], None]] = None,
    ):
        super().__init__(parent)
        self.db_manager = db_manager
        self.item_title = item_title
        self.current_board_id = current_board_id
        self.on_select = on_select
        self.palette = semantic_colors()
        self.search_text = ""

        self.title(f"Set Project for: {item_title}")
        self.geometry("760x560")
        self.transient(parent)

        self.create_ui()
        self.refresh()

        self.grab_set()
        self.center_on_parent()

    # ------------------------------------------------------------------ UI

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=10)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="Select Project", font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=10)

        self.search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            header, textvariable=self.search_var, placeholder_text="Search projects…"
        )
        search_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        search_entry.bind("<KeyRelease>", self._on_search)

        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(
            btn_frame, text="+ New Project", width=140,
            command=self.create_new_project, **button_style("primary"),
        ).pack(side="left", padx=5, pady=8)

        ctk.CTkButton(
            btn_frame, text="Clear Project", width=130,
            command=self.clear_project, **button_style("secondary"),
        ).pack(side="left", padx=5, pady=8)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            command=self.destroy, **button_style("secondary"),
        ).pack(side="right", padx=5, pady=8)

    def _on_search(self, _event=None):
        self.search_text = self.search_var.get().strip().lower()
        self.refresh()

    # --------------------------------------------------------------- data

    def load_boards(self) -> List[Dict[str, Any]]:
        """Selectable projects, plus the current one whatever its status (PL1).

        A completed project is not offered as a new choice, but if the item is
        already filed under one it stays in the list — dropping it would hide
        the item's own current value.
        """
        rows = self.db_manager.get_project_boards(
            show_pending=True, show_completed=True
        )
        return [
            row for row in rows
            if row.get("status") in self.SELECTABLE_STATUSES
            or row.get("id") == self.current_board_id
        ]

    def _matches_search(self, row: Dict[str, Any]) -> bool:
        if not self.search_text:
            return True
        haystack = " ".join(
            str(row.get(key) or "") for key in
            ("title", "segment_name", "subsegment_name", "category_name", "key_field")
        ).lower()
        return self.search_text in haystack

    @staticmethod
    def lineage_label(row: Dict[str, Any]) -> str:
        """The project's Annual Plan Element lineage, for disambiguation."""
        parts = [
            row.get("segment_name"),
            row.get("subsegment_name"),
            row.get("category_name"),
            row.get("key_field"),
        ]
        return " | ".join(str(part).strip() for part in parts if str(part or "").strip())

    # ------------------------------------------------------------- render

    def refresh(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        rows = [row for row in self.load_boards() if self._matches_search(row)]

        if not rows:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No projects match." if self.search_text else
                     "No projects yet — use “+ New Project”.",
                text_color=status_text_color("muted"),
            ).grid(row=0, column=0, sticky="w", padx=12, pady=16)
            return

        for index, row in enumerate(rows):
            self._render_row(row, index)

    def _render_row(self, row: Dict[str, Any], index: int):
        is_current = row.get("id") == self.current_board_id
        card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=self.palette["surface_subtle"] if is_current else "transparent",
        )
        card.grid(row=index, column=0, sticky="ew", padx=5, pady=3)
        card.grid_columnconfigure(0, weight=1)

        title = str(row.get("title") or "(untitled project)")
        if is_current:
            title = f"✓ {title}"
        ctk.CTkLabel(
            card, text=title, anchor="w", font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        detail_bits = [self.lineage_label(row)]
        status = str(row.get("status") or "")
        if status and status != ProjectBoardStatus.ACTIVE:
            detail_bits.append(status.capitalize())
        open_count = row.get("open_item_count") or 0
        detail_bits.append(f"{open_count} open")
        ctk.CTkLabel(
            card, text=" · ".join(bit for bit in detail_bits if bit), anchor="w",
            font=ctk.CTkFont(size=11), text_color=status_text_color("muted"),
        ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))

        ctk.CTkButton(
            card, text="Select", width=90,
            command=lambda board_id=row.get("id"): self.select_project(board_id),
            **button_style("primary" if not is_current else "secondary"),
        ).grid(row=0, column=1, rowspan=2, padx=10, pady=8)

    # ------------------------------------------------------------ actions

    def select_project(self, board_id: str):
        self._finish(board_id)

    def clear_project(self):
        self._finish(None)

    def _finish(self, board_id: Optional[str]):
        if self.on_select:
            self.on_select(board_id)
        self.destroy()

    def create_new_project(self):
        """Create a Project inline and select it (PL5).

        Reuses the Projects screen's own editor dialog so the two entry points
        cannot drift on required fields (the Annual Plan Element in particular).
        """
        from .project_boards import ProjectBoardEditorDialog

        dialog = ProjectBoardEditorDialog(self, self.db_manager)
        self.wait_window(dialog)
        result = getattr(dialog, "result", None)
        if result in (None, "__cancel__"):
            return

        self.db_manager.create_project_board(result)
        self._finish(result.id)

    # ------------------------------------------------------------ window

    def center_on_parent(self):
        self.update_idletasks()
        width, height = 760, 560
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_w = self.master.winfo_width()
        parent_h = self.master.winfo_height()
        x = parent_x + (parent_w // 2) - (width // 2)
        y = parent_y + (parent_h // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
