"""View APEs assigned to a selected quarter and month, then create weekly Action Items."""

import customtkinter as ctk
from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

from ..app_settings import AppSettings
from ..theme import apply_segment_accent, button_style, semantic_colors

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class APEPeriodViewScreen(ctk.CTkFrame):
    """Filter Annual Plan Elements by Year + Quarter + Month and create weekly Action Items."""

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        self.year_var = ctk.StringVar(value=str(datetime.now().year))
        self.q_var = ctk.StringVar(value="1")
        self.m_var = ctk.StringVar(value=str(datetime.now().month))

        self.ape_rows = []
        self.selected_ape_id: Optional[str] = None
        self.week_vars = {}
        self.segment_colors = {}
        self.selected_idx: Optional[int] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.create_ui()
        self.refresh()

    def create_ui(self):
        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        ctk.CTkLabel(top, text="APE by Quarter/Month", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left", padx=8, pady=8
        )

        ctk.CTkLabel(top, text="Year").pack(side="left", padx=(20, 4))
        ctk.CTkEntry(top, width=90, textvariable=self.year_var).pack(side="left", padx=4)

        ctk.CTkLabel(top, text="Quarter").pack(side="left", padx=(12, 4))
        ctk.CTkComboBox(top, width=80, values=["1", "2", "3", "4"], variable=self.q_var).pack(side="left", padx=4)

        ctk.CTkLabel(top, text="Month").pack(side="left", padx=(12, 4))
        ctk.CTkComboBox(top, width=80, values=[str(i) for i in range(1, 13)], variable=self.m_var).pack(side="left", padx=4)

        ctk.CTkButton(top, text="Load", width=90, command=self.refresh, **button_style("secondary")).pack(side="left", padx=10)

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(body, text="APEs In Period", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )
        ctk.CTkLabel(body, text="Select Weeks", font=ctk.CTkFont(weight="bold")).grid(
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

        self.ape_list = ctk.CTkScrollableFrame(left)
        self.ape_list.grid(row=0, column=0, sticky="nsew")
        self.ape_list.grid_columnconfigure(0, weight=1)

        self.week_info_label = ctk.CTkLabel(right, text="")
        self.week_info_label.grid(row=0, column=0, sticky="w", padx=8, pady=4)

        self.week_scroll = ctk.CTkScrollableFrame(right)
        self.week_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.week_scroll.grid_columnconfigure(0, weight=1)

        actions = ctk.CTkFrame(right)
        actions.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        actions.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            actions,
            text="Create Week Action Items",
            command=self.create_week_items_for_selected_ape,
            **button_style("primary"),
            width=220,
        ).grid(row=0, column=0, sticky="w")

        self.status_label = ctk.CTkLabel(actions, text="", text_color="gray")
        self.status_label.grid(row=0, column=1, sticky="w", padx=10)

    def _parse_period(self):
        try:
            year = int(self.year_var.get().strip())
            quarter = int(self.q_var.get().strip())
            month = int(self.m_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Period", "Enter valid numeric Year, Quarter, and Month values.")
            return None

        if quarter not in (1, 2, 3, 4) or month < 1 or month > 12:
            messagebox.showerror("Invalid Period", "Quarter must be 1-4 and Month must be 1-12.")
            return None

        return year, quarter, month

    def refresh(self):
        parsed = self._parse_period()
        if not parsed:
            return
        year, quarter, month = parsed

        self.segment_colors = self.vps_manager.get_segment_color_map()
        self.ape_rows = self.vps_manager.get_annual_plan_elements_for_period(year, quarter, month)
        self.selected_idx = None
        self._render_ape_rows()

        self.selected_ape_id = None
        self.render_week_options()
        self.status_label.configure(text=f"Loaded {len(self.ape_rows)} APE record(s).", text_color="gray")

    def render_week_options(self):
        for child in self.week_scroll.winfo_children():
            child.destroy()

        self.week_vars = {}

        parsed = self._parse_period()
        if not parsed:
            return
        year, _quarter, month = parsed

        settings = AppSettings.load()
        first_day = int(getattr(settings, "first_day_of_week", 0))
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if first_day < 0 or first_day > 6:
            first_day = 0

        self.week_info_label.configure(text=f"Week starts use: {day_names[first_day]}")
        week_options = self.vps_manager.get_month_week_starts(year, month, first_day)

        if not week_options:
            ctk.CTkLabel(self.week_scroll, text="No week options available for this month.").grid(
                row=0, column=0, sticky="w", padx=6, pady=4
            )
            return

        for idx, wk in enumerate(week_options):
            var = ctk.BooleanVar(value=False)
            self.week_vars[wk["week_start_date"]] = var
            text = f"[{wk['week_start_date']}] {wk['label']}"
            ctk.CTkCheckBox(self.week_scroll, text=text, variable=var).grid(
                row=idx, column=0, sticky="w", padx=6, pady=4
            )

    def _find_selected_ape(self) -> Optional[dict]:
        if not self.selected_ape_id:
            return None
        for row in self.ape_rows:
            if row["id"] == self.selected_ape_id:
                return row
        return None

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
            lbl = ctk.CTkLabel(item, text=row.get("key_field", ""), anchor="w")
            lbl.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            chip = ctk.CTkLabel(item, text=f" {segment_name} ", fg_color=color, text_color="white", corner_radius=6)
            chip.grid(row=0, column=2, padx=5, pady=5)
            for widget in (item, lbl):
                widget.bind("<Button-1>", lambda _e, i=idx: self.on_select_ape(i))

    def on_select_ape(self, index: int):
        if index < 0 or index >= len(self.ape_rows):
            return
        row = self.ape_rows[index]
        self.selected_ape_id = row["id"]
        self.selected_idx = index
        self._render_ape_rows()

        parsed = self._parse_period()
        if not parsed:
            return
        year, _quarter, month = parsed

        existing = set(self.vps_manager.get_existing_week_item_starts_for_ape(row["id"], year, month))
        for week_start, var in self.week_vars.items():
            var.set(week_start in existing)

        self.status_label.configure(text=f"Selected: {row['key_field']}", text_color="gray")

    def create_week_items_for_selected_ape(self):
        row = self._find_selected_ape()
        if not row:
            messagebox.showwarning("No APE Selected", "Select an Annual Plan Element first.")
            return

        selected_weeks = [ws for ws, var in self.week_vars.items() if bool(var.get())]
        if not selected_weeks:
            messagebox.showwarning("No Weeks Selected", "Check at least one week.")
            return

        parsed = self._parse_period()
        if not parsed:
            return
        year, _quarter, month = parsed

        result = self.vps_manager.create_week_action_items_for_ape(
            row["id"], year, month, selected_weeks
        )

        self.status_label.configure(
            text=f"Created {result['created_count']} week item(s); skipped {result['skipped_count']} existing.",
            text_color="green",
        )
        messagebox.showinfo(
            "Week Action Items Created",
            f"Created {result['created_count']} week item(s).\nSkipped {result['skipped_count']} existing week(s).",
        )

    def _apply_row_color(self, index: int, segment_name: str):
        return
