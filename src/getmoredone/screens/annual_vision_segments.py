"""Annual Vision Segments screen with drag/drop from Vision Elements."""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class AnnualVisionSegmentsScreen(ctk.CTkFrame):
    """Drag vision elements into annual list to create AVE + APE records."""

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app
        self.drag_index: Optional[int] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.year_var = ctk.StringVar(value=str(datetime.now().year))
        self.left_items = []  # list of dict vision elements
        self.segment_colors = {}

        self.create_ui()
        self.refresh_lists()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(header, text="Annual Vision Segments", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=8, pady=8, sticky="w"
        )
        ctk.CTkLabel(header, text="Year:").grid(row=0, column=1, padx=(18, 4), pady=8)
        self.year_entry = ctk.CTkEntry(header, width=90, textvariable=self.year_var)
        self.year_entry.grid(row=0, column=2, padx=4, pady=8)
        ctk.CTkButton(header, text="Load Year", width=100, command=self.refresh_lists).grid(
            row=0, column=3, padx=6, pady=8
        )
        ctk.CTkButton(header, text="Add Selected >>", width=120, command=self.add_selected).grid(
            row=0, column=4, padx=6, pady=8
        )
        ctk.CTkButton(header, text="Refresh", width=90, command=self.refresh_lists).grid(
            row=0, column=5, padx=6, pady=8
        )

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(body, text="Vision Elements (drag from here)", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )
        ctk.CTkLabel(body, text="Annual Vision Elements (drop here)", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, sticky="w", padx=8, pady=(8, 4)
        )

        left_frame = ctk.CTkFrame(body)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        right_frame = ctk.CTkFrame(body)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(0, 8))
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        self.left_list = tk.Listbox(left_frame, exportselection=False)
        self.left_list.grid(row=0, column=0, sticky="nsew")
        self.right_list = tk.Listbox(right_frame, exportselection=False)
        self.right_list.grid(row=0, column=0, sticky="nsew")

        self.left_list.bind("<ButtonPress-1>", self.on_left_press)
        self.left_list.bind("<ButtonRelease-1>", self.on_left_release)
        self.right_list.bind("<ButtonRelease-1>", self.on_right_release)

    def _parse_year(self) -> Optional[int]:
        try:
            return int(self.year_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Year", "Enter a valid year, e.g. 2026.")
            return None

    def refresh_lists(self):
        year = self._parse_year()
        if year is None:
            return

        self.segment_colors = self.vps_manager.get_segment_color_map()
        self.left_items = self.vps_manager.get_vision_elements()
        self.left_list.delete(0, tk.END)
        for idx, row in enumerate(self.left_items):
            self.left_list.insert(tk.END, row["key_field"])
            self._apply_row_color(self.left_list, idx, row.get("segment_name", ""))

        self.right_list.delete(0, tk.END)
        for idx, row in enumerate(self.vps_manager.get_annual_vision_elements(year)):
            self.right_list.insert(tk.END, row["key_field"])
            self._apply_row_color(self.right_list, idx, row.get("segment_name", ""))

    def _apply_row_color(self, listbox: tk.Listbox, index: int, segment_name: str):
        color = self.vps_manager.resolve_segment_color(segment_name, self.segment_colors)
        try:
            listbox.itemconfig(
                index,
                bg=color,
                fg="white",
                selectbackground=color,
                selectforeground="white",
            )
        except Exception:
            pass

    def _create_from_index(self, idx: int):
        year = self._parse_year()
        if year is None:
            return
        if idx < 0 or idx >= len(self.left_items):
            return
        item = self.left_items[idx]
        self.vps_manager.create_annual_records_from_vision_element(year, item["id"])
        self.refresh_lists()

    def add_selected(self):
        sel = self.left_list.curselection()
        if not sel:
            return
        self._create_from_index(sel[0])

    def on_left_press(self, event):
        sel = self.left_list.curselection()
        self.drag_index = sel[0] if sel else None

    def on_left_release(self, event):
        # If released over right list, create records.
        widget = self.winfo_containing(event.x_root, event.y_root)
        if self.drag_index is None:
            return
        if widget is self.right_list:
            self._create_from_index(self.drag_index)
        self.drag_index = None

    def on_right_release(self, _event):
        if self.drag_index is not None:
            self._create_from_index(self.drag_index)
            self.drag_index = None
