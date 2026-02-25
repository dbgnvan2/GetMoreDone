"""Annual Plan Element assignment screen (Quarter/Month flags)."""

import customtkinter as ctk
from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

from ..theme import apply_segment_accent, button_style, semantic_colors

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class APEAssignmentScreen(ctk.CTkFrame):
    """Assign APEs to quarters/months by drag/drop and toggles."""

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app
        self.drag_idx: Optional[int] = None
        self.ape_rows = []
        self.selected_ape_id: Optional[str] = None
        self.selected_idx: Optional[int] = None
        self.segment_colors = {}
        self.q_vars = {}
        self.m_vars = {}
        self._syncing_targets = False

        self.year_var = ctk.StringVar(value=str(datetime.now().year))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.create_ui()
        self.refresh_all()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        ctk.CTkLabel(header, text="APE Quarter/Month Assignment", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left", padx=8, pady=8
        )
        ctk.CTkLabel(header, text="Year:").pack(side="left", padx=(16, 4))
        ctk.CTkEntry(header, width=90, textvariable=self.year_var).pack(side="left", padx=4)
        ctk.CTkButton(header, text="Load", width=90, command=self.refresh_all, **button_style("secondary")).pack(side="left", padx=6)

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(body, text="Annual Plan Elements (Left)", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )
        ctk.CTkLabel(body, text="Quarter / Month Targets (Right)", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, sticky="w", padx=8, pady=(8, 4)
        )

        left = ctk.CTkFrame(body)
        left.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        right = ctk.CTkFrame(body)
        right.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(0, 8))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=1)

        self.ape_list = ctk.CTkScrollableFrame(left)
        self.ape_list.grid(row=0, column=0, sticky="nsew")
        self.ape_list.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Quarters").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ctk.CTkLabel(right, text="Months").grid(row=0, column=1, sticky="w", padx=8, pady=4)

        self.q_list = ctk.CTkScrollableFrame(right, label_text="")
        self.q_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.q_list.grid_columnconfigure(0, weight=1)

        self.m_list = ctk.CTkScrollableFrame(right, label_text="")
        self.m_list.grid(row=1, column=1, sticky="nsew", padx=8, pady=(0, 8))
        self.m_list.grid_columnconfigure(0, weight=1)

    def parse_year(self) -> Optional[int]:
        try:
            return int(self.year_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Year", "Enter a valid year.")
            return None

    def refresh_all(self):
        year = self.parse_year()
        if year is None:
            return
        self.segment_colors = self.vps_manager.get_segment_color_map()
        self.ape_rows = self.vps_manager.get_annual_plan_elements(year)
        self._render_ape_rows()
        self.selected_ape_id = None
        self.selected_idx = None
        self.render_targets(None)

    def _render_ape_rows(self):
        for w in self.ape_list.winfo_children():
            w.destroy()
        palette = semantic_colors()
        for idx, row in enumerate(self.ape_rows):
            segment_name = row.get("segment_name", "")
            color = self.vps_manager.resolve_segment_color(segment_name, self.segment_colors)
            bg = palette["selected_tint"] if idx == self.selected_idx else None
            item = ctk.CTkFrame(self.ape_list, fg_color=bg)
            item.grid(row=idx, column=0, sticky="ew", padx=4, pady=2)
            item.grid_columnconfigure(1, weight=1)
            apply_segment_accent(item, color)
            ctk.CTkLabel(item, text=str(idx + 1), width=30).grid(row=0, column=0, padx=5, pady=5)
            label = ctk.CTkLabel(item, text=row.get("key_field", ""), anchor="w")
            label.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            chip = ctk.CTkLabel(item, text=f" {segment_name} ", fg_color=color, text_color="white", corner_radius=6)
            chip.grid(row=0, column=2, padx=5, pady=5)
            for widget in (item, label):
                widget.bind("<Button-1>", lambda _e, i=idx: self.on_select_ape(i))

    def on_select_ape(self, index: int):
        if index < 0 or index >= len(self.ape_rows):
            return
        row = self.ape_rows[index]
        self.selected_ape_id = row["id"]
        self.selected_idx = index
        self._render_ape_rows()
        self.render_targets(row)

    def render_targets(self, row: Optional[dict]):
        self._syncing_targets = True
        for w in self.q_list.winfo_children():
            w.destroy()
        for w in self.m_list.winfo_children():
            w.destroy()
        self.q_vars = {}
        self.m_vars = {}

        for q in range(1, 5):
            checked = bool(row and row.get(f"q{q}", 0) == 1)
            var = ctk.BooleanVar(value=checked)
            self.q_vars[q] = var
            ctk.CTkCheckBox(
                self.q_list,
                text=f"Q{q}",
                variable=var,
                command=lambda qq=q: self.set_quarter(qq),
            ).grid(row=q - 1, column=0, sticky="w", padx=8, pady=4)

        for m in range(1, 13):
            checked = bool(row and row.get(f"m{m}", 0) == 1)
            var = ctk.BooleanVar(value=checked)
            self.m_vars[m] = var
            ctk.CTkCheckBox(
                self.m_list,
                text=f"M{m}",
                variable=var,
                command=lambda mm=m: self.set_month(mm),
            ).grid(row=m - 1, column=0, sticky="w", padx=8, pady=3)
        self._syncing_targets = False

    def _selected_row(self) -> Optional[dict]:
        if not self.selected_ape_id:
            return None
        for r in self.ape_rows:
            if r["id"] == self.selected_ape_id:
                return r
        return None

    def set_quarter(self, q: int):
        if self._syncing_targets:
            return
        row = self._selected_row()
        if not row:
            return
        enabled = bool(self.q_vars[q].get())
        self.vps_manager.set_annual_plan_element_quarter(row["id"], q, enabled)
        self.refresh_row(row["id"])

    def set_month(self, m: int):
        if self._syncing_targets:
            return
        row = self._selected_row()
        if not row:
            return
        enabled = bool(self.m_vars[m].get())
        self.vps_manager.set_annual_plan_element_month(row["id"], m, enabled)
        self.refresh_row(row["id"])

    def refresh_row(self, ape_id: str):
        year = self.parse_year()
        if year is None:
            return
        self.segment_colors = self.vps_manager.get_segment_color_map()
        self.ape_rows = self.vps_manager.get_annual_plan_elements(year)
        self.selected_ape_id = ape_id
        self.selected_idx = next((i for i, r in enumerate(self.ape_rows) if r["id"] == ape_id), None)
        self._render_ape_rows()
        row = self._selected_row()
        self.render_targets(row)

    def on_drag_start(self, _event):
        self.drag_idx = None

    def on_drag_release(self, _event):
        # no-op here; handled in target release
        pass

    def on_target_release(self, event):
        self.drag_idx = None

    def _apply_row_color(self, index: int, segment_name: str):
        return
