"""Weekly Items screen: weekly tactics on the left and linked action items on the right."""

import customtkinter as ctk
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox
from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class WeeklyItemsScreen(ctk.CTkFrame):
    """Show weekly tactics for a selected week and their related action items."""

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        self.week_options: List[str] = []
        self.week_var = ctk.StringVar(value="")

        self.weekly_items: List[Dict[str, Any]] = []
        self.selected_week_action: Optional[Dict[str, Any]] = None

        self.related_actions: List[Dict[str, Any]] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.create_ui()
        self.refresh()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(
            header,
            text="Weekly Items",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, padx=(10, 20), pady=10)

        ctk.CTkLabel(header, text="Week Start:").grid(row=0, column=1, padx=(0, 5), pady=10)

        self.week_combo = ctk.CTkComboBox(header, width=170, values=[""], variable=self.week_var)
        self.week_combo.grid(row=0, column=2, padx=5, pady=10)

        ctk.CTkButton(header, text="Load", width=90, command=self.load_selected_week).grid(
            row=0, column=3, padx=5, pady=10
        )

        ctk.CTkButton(header, text="This Week", width=90, command=self.jump_to_current_week).grid(
            row=0, column=4, padx=5, pady=10
        )

        self.status_label = ctk.CTkLabel(header, text="", text_color="gray")
        self.status_label.grid(row=0, column=6, sticky="w", padx=10, pady=10)

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(body, text="Weekly Tactics", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )
        ctk.CTkLabel(body, text="Related Action Items", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, sticky="w", padx=8, pady=(8, 4)
        )

        left = ctk.CTkFrame(body)
        left.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        right = ctk.CTkFrame(body)
        right.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(0, 8))
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.weekly_list = tk.Listbox(left, exportselection=False)
        self.weekly_list.grid(row=0, column=0, sticky="nsew")
        self.weekly_list.bind("<<ListboxSelect>>", self.on_select_weekly_item)

        self.actions_list = tk.Listbox(right, exportselection=False)
        self.actions_list.grid(row=0, column=0, sticky="nsew")
        self.actions_list.bind("<Double-Button-1>", self.open_selected_action_item)

        actions = ctk.CTkFrame(body)
        actions.grid(row=2, column=1, sticky="ew", padx=(4, 8), pady=(0, 8))

        ctk.CTkButton(
            actions,
            text="+ Action Item",
            command=self.create_action_item_for_selected_weekly,
            width=120,
        ).pack(side="left", padx=6, pady=6)

        ctk.CTkButton(
            actions,
            text="Open Action",
            command=self.open_selected_action_item,
            width=120,
        ).pack(side="left", padx=6, pady=6)

    def refresh(self):
        week_actions = self.vps_manager.get_week_actions(active_only=False)
        unique_starts = sorted({wa["week_start_date"] for wa in week_actions if wa.get("week_start_date")})
        unique_starts.reverse()
        self.week_options = unique_starts

        if not self.week_options:
            self.week_combo.configure(values=[""])
            self.week_var.set("")
            self.weekly_list.delete(0, tk.END)
            self.actions_list.delete(0, tk.END)
            self.status_label.configure(text="No weekly tactics found.")
            return

        self.week_combo.configure(values=self.week_options)
        if self.week_var.get() not in self.week_options:
            self.week_var.set(self.week_options[0])

        self.load_selected_week()

    def jump_to_current_week(self):
        today = date.today()
        current_week_start = (today - timedelta(days=today.weekday())).isoformat()

        if current_week_start in self.week_options:
            self.week_var.set(current_week_start)
            self.load_selected_week()
        else:
            messagebox.showinfo("Week Not Found", "No weekly tactics exist for the current week.")

    def load_selected_week(self):
        week_start = self.week_var.get().strip()
        if not week_start:
            return

        self.weekly_items = self.vps_manager.get_week_actions(
            week_start_date=week_start,
            active_only=False,
        )

        self.weekly_list.delete(0, tk.END)
        self.actions_list.delete(0, tk.END)
        self.related_actions = []
        self.selected_week_action = None

        for wa in self.weekly_items:
            title = (wa.get("title") or "(untitled)").strip()
            end_date = wa.get("week_end_date", "")
            self.weekly_list.insert(tk.END, f"{title}  [{week_start} - {end_date}]")

        self.status_label.configure(text=f"{len(self.weekly_items)} weekly item(s) for {week_start}")

    def on_select_weekly_item(self, _event=None):
        selection = self.weekly_list.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx < 0 or idx >= len(self.weekly_items):
            return

        self.selected_week_action = self.weekly_items[idx]
        self.related_actions = self.vps_manager.get_action_items_for_week_action(self.selected_week_action["id"])

        self.actions_list.delete(0, tk.END)
        for action in self.related_actions:
            title = (action.get("title") or "(untitled)").strip()
            start = action.get("start_date") or ""
            status = action.get("status") or "open"
            self.actions_list.insert(tk.END, f"{title}  [{start}] ({status})")

        self.status_label.configure(
            text=f"{len(self.related_actions)} related action item(s) for selected weekly tactic"
        )

    def create_action_item_for_selected_weekly(self):
        if not self.selected_week_action:
            messagebox.showwarning("No Weekly Item Selected", "Select a weekly item on the left first.")
            return

        from .item_editor import ItemEditorDialog

        ItemEditorDialog(
            self,
            self.app.db_manager,
            week_action_id=self.selected_week_action["id"],
            segment_description_id=self.selected_week_action.get("segment_description_id"),
            vps_manager=self.vps_manager,
            on_close_callback=self.on_action_editor_closed,
        )

    def on_action_editor_closed(self):
        if self.selected_week_action:
            self.related_actions = self.vps_manager.get_action_items_for_week_action(self.selected_week_action["id"])
            self.actions_list.delete(0, tk.END)
            for action in self.related_actions:
                title = (action.get("title") or "(untitled)").strip()
                start = action.get("start_date") or ""
                status = action.get("status") or "open"
                self.actions_list.insert(tk.END, f"{title}  [{start}] ({status})")

    def open_selected_action_item(self, _event=None):
        if not self.related_actions:
            return

        selection = self.actions_list.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx < 0 or idx >= len(self.related_actions):
            return

        action_id = self.related_actions[idx]["id"]

        from .item_editor import ItemEditorDialog

        ItemEditorDialog(
            self,
            self.app.db_manager,
            item_id=action_id,
            vps_manager=self.vps_manager,
            on_close_callback=self.on_action_editor_closed,
        )
