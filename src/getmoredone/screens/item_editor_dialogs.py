"""Supporting dialog classes extracted from item_editor.py."""

from __future__ import annotations

import calendar
import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import customtkinter as ctk
from tkinter import filedialog, messagebox

from ..app_settings import AppSettings
from ..color_contrast import pick_text_color
from ..models import ActionItem, ItemLink
from ..paths import app_data_dir_path
from ..theme import button_style, combo_box_style, semantic_colors, status_text_color
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors
from .title_format import split_action_item_title
from .item_editor_confirm_dialogs import DeleteChildrenWarningDialog, DeleteConfirmDialog
from .item_editor_note_dialogs import CreateNoteDialog, LinkNoteDialog
from .item_editor_weekly_tactic_dialog import SetWeeklyTacticDialog

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


class ShowRelatedDialog(ctk.CTkToplevel):
    """Dialog for showing related items (parent and children)."""

    def __init__(self, parent, db_manager: 'DatabaseManager', current_item_id: str, current_title: str, vps_manager=None, on_close_callback=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_item_id = current_item_id
        self.current_title = current_title
        self.vps_manager = vps_manager
        self.on_close_callback = on_close_callback
        self.palette = semantic_colors()

        self.title(f"Related Items: {current_title}")
        self.geometry("900x700")

        # Create UI
        self.create_ui()

        # Load related items
        self.refresh()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.center_on_parent()

    def create_ui(self):
        """Create the UI components."""
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            header_frame,
            text=f"Related Items: {self.current_title}",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=10, pady=10)

        # Scrollable frame for related items list
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Button frame
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)

        btn_close = ctk.CTkButton(
            btn_frame, text="Close", command=self.destroy, width=100, **button_style("secondary"))
        btn_close.pack(side="right", padx=5)

    def refresh(self):
        """Refresh the list of related items (parent and children)."""
        # Clear current list
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        current_row = 0

        # Get current item to check for parent
        current_item = self.db_manager.get_action_item(self.current_item_id)

        # Show parent section if exists
        if current_item and current_item.parent_id:
            parent_item = self.db_manager.get_action_item(
                current_item.parent_id)
            if parent_item:
                # Parent section header
                parent_header = ctk.CTkFrame(
                    self.scroll_frame, fg_color=self.palette["primary"])
                parent_header.grid(row=current_row, column=0,
                                   sticky="ew", pady=(0, 5), padx=5)
                ctk.CTkLabel(
                    parent_header,
                    text="PARENT ITEM",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=self.palette["on_primary"]
                ).pack(pady=5)
                current_row += 1

                # Create header row for parent
                self.create_header_row(current_row)
                current_row += 1

                # Display parent
                self.create_item_row(parent_item, current_row)
                current_row += 1

                # Add spacing
                ctk.CTkLabel(self.scroll_frame, text="").grid(
                    row=current_row, column=0, pady=10)
                current_row += 1

        # Get children
        children = self.db_manager.get_children(self.current_item_id)

        # Show children section
        if children:
            # Children section header
            children_header = ctk.CTkFrame(
                self.scroll_frame, fg_color=self.palette["primary"])
            children_header.grid(row=current_row, column=0,
                                 sticky="ew", pady=(0, 5), padx=5)
            ctk.CTkLabel(
                children_header,
                text="CHILD ITEMS",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=self.palette["on_primary"]
            ).pack(pady=5)
            current_row += 1

            # Create header row for children
            self.create_header_row(current_row)
            current_row += 1

            # Display each child
            for child in children:
                self.create_item_row(child, current_row)
                current_row += 1
        else:
            # Only show "no children" message if there's also no parent
            if not (current_item and current_item.parent_id):
                ctk.CTkLabel(
                    self.scroll_frame,
                    text="No related items found",
                    font=ctk.CTkFont(size=14),
                    text_color=self.palette["body_text"],
                ).grid(row=current_row, column=0, pady=20)
            elif current_row > 0:
                # There is a parent but no children
                children_header = ctk.CTkFrame(
                    self.scroll_frame, fg_color=self.palette["primary"])
                children_header.grid(
                    row=current_row, column=0, sticky="ew", pady=(0, 5), padx=5)
                ctk.CTkLabel(
                    children_header,
                    text="CHILD ITEMS",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=self.palette["on_primary"]
                ).pack(pady=5)
                current_row += 1

                ctk.CTkLabel(
                    self.scroll_frame,
                    text="No child items found",
                    font=ctk.CTkFont(size=12),
                    text_color=self.palette["body_text"],
                ).grid(row=current_row, column=0, pady=10)

    def create_header_row(self, row: int):
        """Create a header row for items."""
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color=self.palette["surface_subtle"])
        header_frame.grid(row=row, column=0, sticky="ew", pady=(0, 5), padx=5)
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="Immediate Step (Who)",
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
            text_color=self.palette["body_text"],
        ).grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        ctk.CTkLabel(header_frame, text="Priority", width=70, font=ctk.CTkFont(weight="bold"), text_color=self.palette["body_text"]).grid(
            row=0, column=1, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Due Date", width=110, font=ctk.CTkFont(weight="bold"), text_color=self.palette["body_text"]).grid(
            row=0, column=2, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Status", width=80, font=ctk.CTkFont(weight="bold"), text_color=self.palette["body_text"]).grid(
            row=0, column=3, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Actions", width=80, font=ctk.CTkFont(weight="bold"), text_color=self.palette["body_text"]).grid(
            row=0, column=4, padx=5, pady=5
        )

    def create_item_row(self, item: ActionItem, row: int):
        """Create a row for an item (parent or child)."""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
        frame.grid_columnconfigure(0, weight=1)

        # Title and who
        info_text = f"{item.title}"
        if item.who:
            info_text += f" ({item.who})"

        title_label = ctk.CTkLabel(
            frame,
            text=info_text,
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=self.palette["body_text"],
        )
        title_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # Priority
        priority_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=70,
            fg_color=self.palette["surface_subtle"],
            text_color=self.palette["body_text"],
        )
        priority_label.grid(row=0, column=1, padx=5, pady=5)

        # Due date
        due_text = item.due_date if item.due_date else "-"
        due_label = ctk.CTkLabel(frame, text=due_text, width=110, text_color=self.palette["body_text"])
        due_label.grid(row=0, column=2, padx=5, pady=5)

        # Status
        status_label = ctk.CTkLabel(
            frame,
            text=item.status.capitalize(),
            width=80,
            text_color=self.palette["success_strong"] if item.status == "completed" else self.palette["body_text"]
        )
        status_label.grid(row=0, column=3, padx=5, pady=5)

        # Edit button
        btn_edit = ctk.CTkButton(
            frame,
            text="Edit",
            width=80,
            command=lambda: self.edit_item(item.id),
            **button_style("secondary"),
        )
        btn_edit.grid(row=0, column=4, padx=5, pady=5)

    def edit_item(self, item_id: str):
        """Open editor for an item."""
        from .item_editor import ItemEditorDialog

        # Close this dialog
        self.destroy()
        # Open editor for the item
        ItemEditorDialog(self.master, self.db_manager, item_id,
                         vps_manager=self.vps_manager, on_close_callback=self.on_close_callback)

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()

        # Get dialog dimensions
        dialog_width = 900
        dialog_height = 700

        # Get parent window position
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure not off-screen
        x = max(0, x)
        y = max(0, y)

        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")


class SetParentDialog(ctk.CTkToplevel):
    """Dialog for selecting a parent item."""

    def __init__(self, parent, db_manager: 'DatabaseManager', current_item_id: str, current_item_title: str, vps_manager=None, on_close_callback=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_item_id = current_item_id
        self.current_item_title = current_item_title
        self.parent_dialog = parent
        self.vps_manager = vps_manager
        self.on_close_callback = on_close_callback

        self.title(f"Set Parent for: {current_item_title}")
        self.geometry("900x600")

        # Create UI
        self.create_ui()

        # Load available parents
        self.refresh()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.center_on_parent()

    def create_ui(self):
        """Create the UI components."""
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            header_frame,
            text=f"Select Parent for: {self.current_item_title}",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=10, pady=10)

        # Scrollable frame for item list
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Button frame
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)

        btn_close = ctk.CTkButton(
            btn_frame, text="Cancel", command=self.destroy, width=100)
        btn_close.pack(side="right", padx=5)

    def refresh(self):
        """Refresh the list of available parent items."""
        # Clear current list
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get all items
        all_items = self.db_manager.get_all_items(
            sort_by="priority_score", sort_desc=True)

        # Get descendants of current item (to prevent circular references)
        descendants = self.db_manager.get_subtree(self.current_item_id)
        descendant_ids = {item.id for item in descendants}

        # Filter out current item and its descendants
        available_items = [
            item for item in all_items
            if item.id != self.current_item_id and item.id not in descendant_ids
        ]

        # Create header row
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color=self.palette["surface_subtle"])
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5), padx=5)
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="Immediate Step (Who)", anchor="w", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        ctk.CTkLabel(header_frame, text="Priority", width=70, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Due Date", width=110, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=2, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Status", width=80, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=3, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Actions", width=100, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=4, padx=5, pady=5
        )

        # Add "No Parent" option as first row
        row = 1
        no_parent_frame = ctk.CTkFrame(self.scroll_frame, fg_color=self.palette["surface_subtle"])
        no_parent_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
        no_parent_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            no_parent_frame,
            text="[No Parent - Make this a root item]",
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=status_text_color("info")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=5, columnspan=4)

        btn_clear = ctk.CTkButton(
            no_parent_frame,
            text="Clear Parent",
            width=100,
            command=self.clear_parent,
            **button_style("danger"),
        )
        btn_clear.grid(row=0, column=4, padx=5, pady=5)
        row += 1

        # Display each available item
        if not available_items:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No available parent items found",
                font=ctk.CTkFont(size=14)
            ).grid(row=row, column=0, pady=20)
            return

        for item in available_items:
            self.create_item_row(item, row)
            row += 1

    def create_item_row(self, item: ActionItem, row: int):
        """Create a row for a potential parent item."""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
        frame.grid_columnconfigure(0, weight=1)

        # Title and who
        info_text = f"{item.title}"
        if item.who:
            info_text += f" ({item.who})"

        title_label = ctk.CTkLabel(
            frame,
            text=info_text,
            anchor="w",
            font=ctk.CTkFont(size=12)
        )
        title_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # Priority
        priority_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=70,
            fg_color=self.palette["surface_subtle"]
        )
        priority_label.grid(row=0, column=1, padx=5, pady=5)

        # Due date
        due_text = item.due_date if item.due_date else "-"
        due_label = ctk.CTkLabel(frame, text=due_text, width=110)
        due_label.grid(row=0, column=2, padx=5, pady=5)

        # Status
        status_label = ctk.CTkLabel(
            frame,
            text=item.status.capitalize(),
            width=80,
            text_color=status_text_color("success") if item.status == "completed" else self.palette["body_text"]
        )
        status_label.grid(row=0, column=3, padx=5, pady=5)

        # Select button
        btn_select = ctk.CTkButton(
            frame,
            text="Select",
            width=100,
            command=lambda: self.select_parent(item.id),
            **button_style("primary"),
        )
        btn_select.grid(row=0, column=4, padx=5, pady=5)

    def select_parent(self, parent_id: str):
        """Set the selected item as parent."""
        from .item_editor import ItemEditorDialog

        # Get the current item and update its parent_id
        current_item = self.db_manager.get_action_item(self.current_item_id)
        if current_item:
            current_item.parent_id = parent_id
            self.db_manager.update_action_item(current_item)

        # Close this dialog
        self.destroy()

        # Close and reopen the parent editor to show updated parent info
        self.parent_dialog.destroy()
        ItemEditorDialog(self.parent_dialog.master, self.db_manager, self.current_item_id,
                         vps_manager=self.vps_manager, on_close_callback=self.on_close_callback)

    def clear_parent(self):
        """Clear the parent (make this a root item)."""
        from .item_editor import ItemEditorDialog

        # Get the current item and clear its parent_id
        current_item = self.db_manager.get_action_item(self.current_item_id)
        if current_item:
            current_item.parent_id = None
            self.db_manager.update_action_item(current_item)

        # Close this dialog
        self.destroy()

        # Close and reopen the parent editor to show updated parent info
        self.parent_dialog.destroy()
        ItemEditorDialog(self.parent_dialog.master, self.db_manager, self.current_item_id,
                         vps_manager=self.vps_manager, on_close_callback=self.on_close_callback)

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()

        # Get dialog dimensions
        dialog_width = 900
        dialog_height = 600

        # Get parent window position
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure not off-screen
        x = max(0, x)
        y = max(0, y)

        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
