"""
Hierarchical screen - shows items in parent-child tree view.
"""

import customtkinter as ctk
from typing import Optional, TYPE_CHECKING, List

from ..models import ActionItem

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class HierarchicalScreen(ctk.CTkFrame):
    """Screen showing action items in hierarchical tree view."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Create scrollable frame for items
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Load items
        self.refresh()

    def create_header(self):
        """Create header with controls."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(1, weight=1)

        # Title
        title = ctk.CTkLabel(
            header,
            text="Hierarchical View",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=10)

        # Status filter
        ctk.CTkLabel(header, text="Status:").grid(row=0, column=2, padx=(20, 5), pady=10)

        self.status_var = ctk.StringVar(value="open")
        self.status_combo = ctk.CTkComboBox(
            header,
            values=["open", "completed", "all"],
            variable=self.status_var,
            width=120,
            command=lambda _: self.refresh()
        )
        self.status_combo.grid(row=0, column=3, padx=5, pady=10)

        # New Item button
        btn_new = ctk.CTkButton(
            header,
            text="+ New Item",
            command=self.create_new_item
        )
        btn_new.grid(row=0, column=4, padx=10, pady=10)

    def refresh(self):
        """Refresh the hierarchical list."""
        # Clear current items
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get status filter
        status = self.status_var.get()
        status_filter = None if status == "all" else status

        # Get root items (items with no parent)
        root_items = self.db_manager.get_root_items(status_filter=status_filter)

        if not root_items:
            label = ctk.CTkLabel(
                self.scroll_frame,
                text="No root items found",
                font=ctk.CTkFont(size=14)
            )
            label.grid(row=0, column=0, pady=20)
            return

        # Display each root item and its children recursively
        row = 0
        for item in root_items:
            row = self.display_item_tree(item, row, 0)

    def display_item_tree(self, item: ActionItem, row: int, indent_level: int) -> int:
        """
        Display an item and its children recursively.

        Args:
            item: The item to display
            row: Current row number
            indent_level: Indentation level (0 for root, 1 for child, etc.)

        Returns:
            Next available row number
        """
        # Create item row
        item_frame = self.create_item_row(item, indent_level)
        item_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=(indent_level * 30 + 5, 5))
        row += 1

        # Get and display children
        children = self.db_manager.get_children(item.id)
        for child in children:
            row = self.display_item_tree(child, row, indent_level + 1)

        return row

    def create_item_row(self, item: ActionItem, indent_level: int) -> ctk.CTkFrame:
        """Create a row for an action item."""
        # RED background for critical items
        is_critical = (item.importance == 20 or item.urgency == 20)
        bg_color = "darkred" if is_critical else None
        frame = ctk.CTkFrame(self.scroll_frame, fg_color=bg_color)
        frame.grid_columnconfigure(0, weight=1)

        # Calculate left padding for indentation
        indent_padding = (indent_level * 30, 5)

        # Title with indentation (left-aligned for main items, indented for children)
        info_text = f"{item.title}"
        if item.who:
            info_text += f" ({item.who})"
        if item.group:
            info_text += f" [{item.group}]"

        # Add indentation indicator for child items
        if indent_level > 0:
            indicator = "└─ "
            info_text = indicator + info_text

        title_label = ctk.CTkLabel(
            frame,
            text=info_text,
            font=ctk.CTkFont(size=12, family="Courier" if indent_level > 0 else None),
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w", padx=indent_padding, pady=5)

        # Priority score
        score_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=60,
            fg_color="gray30"
        )
        score_label.grid(row=0, column=1, padx=5, pady=5)

        # Due date
        if item.due_date:
            due_label = ctk.CTkLabel(
                frame,
                text=f"Due: {item.due_date}",
                width=110
            )
            due_label.grid(row=0, column=2, padx=5, pady=5)
        else:
            # Empty space to maintain alignment
            ctk.CTkLabel(frame, text="", width=110).grid(row=0, column=2, padx=5, pady=5)

        # Child count
        children = self.db_manager.get_children(item.id)
        if children:
            child_count_label = ctk.CTkLabel(
                frame,
                text=f"({len(children)} sub)",
                width=70,
                text_color="lightblue"
            )
            child_count_label.grid(row=0, column=3, padx=5, pady=5)
        else:
            # Empty space to maintain alignment
            ctk.CTkLabel(frame, text="", width=70).grid(row=0, column=3, padx=5, pady=5)

        # Edit button
        btn_edit = ctk.CTkButton(
            frame,
            text="Edit",
            width=60,
            command=lambda: self.edit_item(item.id)
        )
        btn_edit.grid(row=0, column=4, padx=5, pady=5)

        return frame

    def complete_item(self, item_id: str):
        """Mark item as complete."""
        self.db_manager.complete_action_item(item_id)
        self.refresh()

    def edit_item(self, item_id: str):
        """Open item editor."""
        from .item_editor import ItemEditorDialog
        dialog = ItemEditorDialog(self, self.db_manager, item_id)
        dialog.wait_window()
        self.refresh()

    def create_new_item(self):
        """Open item editor for new item."""
        from .item_editor import ItemEditorDialog
        dialog = ItemEditorDialog(self, self.db_manager)
        dialog.wait_window()
        self.refresh()
