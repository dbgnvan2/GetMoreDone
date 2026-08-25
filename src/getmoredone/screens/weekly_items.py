"""APE Weekly screen: weekly action items on the left and related actions on the right."""

import customtkinter as ctk
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox
from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class WeeklyItemsScreen(ctk.CTkFrame):
    """Show APE weekly action items for a selected week and related actions."""

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        self.week_options: List[str] = []
        self.week_var = ctk.StringVar(value="")

        self.weekly_items: List[Dict[str, Any]] = []
        self.selected_weekly_item: Optional[Dict[str, Any]] = None

        self.related_actions: List[Dict[str, Any]] = []
        self.segment_colors = {}

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
            text="APE Weekly",
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

        ctk.CTkLabel(body, text="APE Weekly Items", font=ctk.CTkFont(weight="bold")).grid(
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
            text="Open Weekly Action",
            command=self.open_selected_weekly_item,
            width=140,
        ).pack(side="left", padx=6, pady=6)

        ctk.CTkButton(
            actions,
            text="Open Action",
            command=self.open_selected_action_item,
            width=120,
        ).pack(side="left", padx=6, pady=6)

    def refresh(self):
        self.segment_colors = self.vps_manager.get_segment_color_map()
        weekly_items = self.vps_manager.get_weekly_action_items(ape_only=True)
        unique_starts = sorted({wi["start_date"] for wi in weekly_items if wi.get("start_date")})
        unique_starts.reverse()
        self.week_options = unique_starts

        if not self.week_options:
            self.week_combo.configure(values=[""])
            self.week_var.set("")
            self.weekly_list.delete(0, tk.END)
            self.actions_list.delete(0, tk.END)
            self.status_label.configure(text="No weekly action items found.")
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
            show_toast(self, "No weekly items exist for the current week.", "info")

    def load_selected_week(self):
        week_start = self.week_var.get().strip()
        if not week_start:
            return

        self.weekly_items = self.vps_manager.get_weekly_action_items(
            week_start_date=week_start,
            ape_only=True,
        )

        self.weekly_list.delete(0, tk.END)
        self.actions_list.delete(0, tk.END)
        self.related_actions = []
        self.selected_weekly_item = None

        for wi in self.weekly_items:
            title = (wi.get("title") or "(untitled)").strip()
            due = wi.get("due_date", "")
            self.weekly_list.insert(tk.END, f"{title}  [{week_start} - {due}]")
            idx = self.weekly_list.size() - 1
            segment_name = wi.get("ape_segment_name") or wi.get("who") or ""
            self._apply_listbox_color(self.weekly_list, idx, segment_name)

        self.status_label.configure(text=f"{len(self.weekly_items)} weekly item(s) for {week_start}")

    def on_select_weekly_item(self, _event=None):
        selection = self.weekly_list.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx < 0 or idx >= len(self.weekly_items):
            return

        self.selected_weekly_item = self.weekly_items[idx]
        self.related_actions = self.vps_manager.get_related_actions_for_weekly_item(self.selected_weekly_item["id"])

        self.actions_list.delete(0, tk.END)
        for action in self.related_actions:
            title = (action.get("title") or "(untitled)").strip()
            start = action.get("start_date") or ""
            status = action.get("status") or "open"
            self.actions_list.insert(tk.END, f"{title}  [{start}] ({status})")
            idx = self.actions_list.size() - 1
            segment_name = self.selected_weekly_item.get("ape_segment_name") or self.selected_weekly_item.get("who") or ""
            self._apply_listbox_color(self.actions_list, idx, segment_name)

        self.status_label.configure(
            text=f"{len(self.related_actions)} related action item(s) for selected weekly item"
        )

    def create_action_item_for_selected_weekly(self):
        if not self.selected_weekly_item:
            show_toast(self, "Select a weekly item on the left first.", "warning")
            return
        from ..models import ActionItem

        dialog = ctk.CTkInputDialog(text="Action Item title:", title="New Related Action")
        title = (dialog.get_input() or "").strip()
        if not title:
            return

        weekly = self.selected_weekly_item
        item = ActionItem(
            who=weekly.get("who") or "",
            title=title,
            description=f"Related to weekly item: {weekly.get('title') or ''}",
            parent_id=weekly["id"],
            start_date=weekly.get("start_date"),
            due_date=weekly.get("start_date"),
            category=weekly.get("category"),
            annual_plan_element_id=weekly.get("annual_plan_element_id"),
            item_type="daily",
        )
        self.app.db_manager.create_action_item(item, apply_defaults=False)
        self.on_action_editor_closed()

    def open_selected_weekly_item(self):
        """Open the selected weekly action item in the editor."""
        if not self.selected_weekly_item:
            show_toast(self, "Select a weekly item on the left first.", "warning")
            return

        from .item_editor import ItemEditorDialog

        ItemEditorDialog(
            self,
            self.app.db_manager,
            item_id=self.selected_weekly_item["id"],
            vps_manager=self.vps_manager,
            on_close_callback=self.on_action_editor_closed,
        )

    def on_action_editor_closed(self):
        if self.selected_weekly_item:
            self.related_actions = self.vps_manager.get_related_actions_for_weekly_item(self.selected_weekly_item["id"])
            self.actions_list.delete(0, tk.END)
            for action in self.related_actions:
                title = (action.get("title") or "(untitled)").strip()
                start = action.get("start_date") or ""
                status = action.get("status") or "open"
                self.actions_list.insert(tk.END, f"{title}  [{start}] ({status})")
                idx = self.actions_list.size() - 1
                segment_name = self.selected_weekly_item.get("ape_segment_name") or self.selected_weekly_item.get("who") or ""
                self._apply_listbox_color(self.actions_list, idx, segment_name)

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

    def _apply_listbox_color(self, listbox: tk.Listbox, index: int, segment_name: str):
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
