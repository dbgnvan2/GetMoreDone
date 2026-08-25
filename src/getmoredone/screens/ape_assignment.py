"""Annual Plan Element assignment screen (Quarter/Month flags)."""

import customtkinter as ctk
import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

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
        self.segment_colors = {}

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
        ctk.CTkButton(header, text="Load", width=90, command=self.refresh_all).pack(side="left", padx=6)

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

        self.ape_list = tk.Listbox(left, exportselection=False)
        self.ape_list.grid(row=0, column=0, sticky="nsew")
        self.ape_list.bind("<<ListboxSelect>>", self.on_select_ape)
        self.ape_list.bind("<ButtonPress-1>", self.on_drag_start)
        self.ape_list.bind("<ButtonRelease-1>", self.on_drag_release)

        ctk.CTkLabel(right, text="Quarters").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ctk.CTkLabel(right, text="Months").grid(row=0, column=1, sticky="w", padx=8, pady=4)

        self.q_list = tk.Listbox(right, exportselection=False, height=8)
        self.q_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.q_list.bind("<Double-Button-1>", self.toggle_quarter)
        self.q_list.bind("<ButtonRelease-1>", self.on_target_release)

        self.m_list = tk.Listbox(right, exportselection=False, height=14)
        self.m_list.grid(row=1, column=1, sticky="nsew", padx=8, pady=(0, 8))
        self.m_list.bind("<Double-Button-1>", self.toggle_month)
        self.m_list.bind("<ButtonRelease-1>", self.on_target_release)

    def parse_year(self) -> Optional[int]:
        try:
            return int(self.year_var.get().strip())
        except ValueError:
            show_toast(self, "Enter a valid year.", "error")
            return None

    def refresh_all(self):
        year = self.parse_year()
        if year is None:
            return
        self.segment_colors = self.vps_manager.get_segment_color_map()
        self.ape_rows = self.vps_manager.get_annual_plan_elements(year)
        self.ape_list.delete(0, tk.END)
        for idx, row in enumerate(self.ape_rows):
            self.ape_list.insert(tk.END, row["key_field"])
            self._apply_row_color(idx, row.get("segment_name", ""))
        self.selected_ape_id = None
        self.render_targets(None)

    def on_select_ape(self, _event):
        sel = self.ape_list.curselection()
        if not sel:
            return
        row = self.ape_rows[sel[0]]
        self.selected_ape_id = row["id"]
        self.render_targets(row)

    def render_targets(self, row: Optional[dict]):
        self.q_list.delete(0, tk.END)
        self.m_list.delete(0, tk.END)

        for q in range(1, 5):
            checked = bool(row and row.get(f"q{q}", 0) == 1)
            self.q_list.insert(tk.END, f"[{'x' if checked else ' '}] Q{q}")

        for m in range(1, 13):
            checked = bool(row and row.get(f"m{m}", 0) == 1)
            self.m_list.insert(tk.END, f"[{'x' if checked else ' '}] M{m}")

    def _selected_row(self) -> Optional[dict]:
        if not self.selected_ape_id:
            return None
        for r in self.ape_rows:
            if r["id"] == self.selected_ape_id:
                return r
        return None

    def toggle_quarter(self, _event=None):
        row = self._selected_row()
        if not row:
            return
        sel = self.q_list.curselection()
        if not sel:
            return
        q = sel[0] + 1
        enabled = not bool(row.get(f"q{q}", 0) == 1)
        self.vps_manager.set_annual_plan_element_quarter(row["id"], q, enabled)
        self.refresh_row(row["id"])

    def toggle_month(self, _event=None):
        row = self._selected_row()
        if not row:
            return
        sel = self.m_list.curselection()
        if not sel:
            return
        m = sel[0] + 1
        enabled = not bool(row.get(f"m{m}", 0) == 1)
        self.vps_manager.set_annual_plan_element_month(row["id"], m, enabled)
        self.refresh_row(row["id"])

    def refresh_row(self, ape_id: str):
        year = self.parse_year()
        if year is None:
            return
        self.segment_colors = self.vps_manager.get_segment_color_map()
        self.ape_rows = self.vps_manager.get_annual_plan_elements(year)
        self.ape_list.delete(0, tk.END)
        for idx, row in enumerate(self.ape_rows):
            self.ape_list.insert(tk.END, row["key_field"])
            self._apply_row_color(idx, row.get("segment_name", ""))
        self.selected_ape_id = ape_id
        row = self._selected_row()
        self.render_targets(row)

    def on_drag_start(self, _event):
        sel = self.ape_list.curselection()
        self.drag_idx = sel[0] if sel else None

    def on_drag_release(self, _event):
        # no-op here; handled in target release
        pass

    def on_target_release(self, event):
        if self.drag_idx is None:
            return
        if self.drag_idx < 0 or self.drag_idx >= len(self.ape_rows):
            self.drag_idx = None
            return

        row = self.ape_rows[self.drag_idx]
        self.selected_ape_id = row["id"]
        widget = event.widget

        if widget is self.q_list:
            idx = self.q_list.nearest(event.y)
            q = idx + 1
            if 1 <= q <= 4:
                self.vps_manager.set_annual_plan_element_quarter(row["id"], q, True)
                self.refresh_row(row["id"])
        elif widget is self.m_list:
            idx = self.m_list.nearest(event.y)
            m = idx + 1
            if 1 <= m <= 12:
                self.vps_manager.set_annual_plan_element_month(row["id"], m, True)
                self.refresh_row(row["id"])

        self.drag_idx = None

    def _apply_row_color(self, index: int, segment_name: str):
        color = self.vps_manager.resolve_segment_color(segment_name, self.segment_colors)
        try:
            self.ape_list.itemconfig(
                index,
                bg=color,
                fg="white",
                selectbackground=color,
                selectforeground="white",
            )
        except Exception:
            pass
