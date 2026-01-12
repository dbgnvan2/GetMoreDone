"""
All Items screen - table view of all action items.
"""

import customtkinter as ctk
from typing import TYPE_CHECKING

from ..models import Status

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class AllItemsScreen(ctk.CTkFrame):
    """Screen showing all items in a table format."""

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
        """Create header with filters and controls."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(5, weight=1)

        # Title
        title = ctk.CTkLabel(
            header,
            text="All Items",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=10)

        # Status filter
        ctk.CTkLabel(header, text="Status:").grid(row=0, column=1, padx=(20, 5), pady=10)
        self.status_var = ctk.StringVar(value="open")
        self.status_combo = ctk.CTkComboBox(
            header,
            values=["open", "completed", "canceled", "all"],
            variable=self.status_var,
            width=120,
            command=lambda _: self.refresh()
        )
        self.status_combo.grid(row=0, column=2, padx=5, pady=10)

        # Who filter
        ctk.CTkLabel(header, text="Who:").grid(row=0, column=3, padx=(20, 5), pady=10)
        who_values = ["All"] + self.db_manager.get_distinct_who_values()
        self.who_var = ctk.StringVar(value="All")
        self.who_combo = ctk.CTkComboBox(
            header,
            values=who_values,
            variable=self.who_var,
            width=150,
            command=lambda _: self.refresh()
        )
        self.who_combo.grid(row=0, column=4, padx=5, pady=10)

        # New Item button
        btn_new = ctk.CTkButton(
            header,
            text="+ New Item",
            command=self.create_new_item
        )
        btn_new.grid(row=0, column=6, padx=10, pady=10)

    def refresh(self):
        """Refresh the list of items."""
        # Clear current items
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get filters
        status_filter = None if self.status_var.get() == "all" else self.status_var.get()
        who_filter = None if self.who_var.get() == "All" else self.who_var.get()

        # Get items
        items = self.db_manager.get_all_items(
            status_filter=status_filter,
            who_filter=who_filter,
            sort_by="due_date",
            sort_desc=False
        )

        if not items:
            label = ctk.CTkLabel(
                self.scroll_frame,
                text="No items found",
                font=ctk.CTkFont(size=14)
            )
            label.grid(row=0, column=0, pady=20)
            return

        # Create table header
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray25")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5), padx=5)
        header_frame.grid_columnconfigure(1, weight=1)

        headers = ["✓", "Title", "Who", "Due", "Priority", "Status", "Actions"]
        col_weights = [0, 1, 0, 0, 0, 0, 0]

        for col, (header_text, weight) in enumerate(zip(headers, col_weights)):
            header_frame.grid_columnconfigure(col, weight=weight)
            ctk.CTkLabel(
                header_frame,
                text=header_text,
                font=ctk.CTkFont(weight="bold")
            ).grid(row=0, column=col, padx=5, pady=5, sticky="w")

        # Create item rows
        for idx, item in enumerate(items, start=1):
            item_frame = ctk.CTkFrame(self.scroll_frame)
            item_frame.grid(row=idx, column=0, sticky="ew", pady=2, padx=5)
            item_frame.grid_columnconfigure(1, weight=1)

            # Checkbox
            if item.status == Status.OPEN:
                var = ctk.BooleanVar(value=False)
                checkbox = ctk.CTkCheckBox(
                    item_frame,
                    text="",
                    variable=var,
                    width=30,
                    command=lambda i=item.id: self.complete_item(i)
                )
                checkbox.grid(row=0, column=0, padx=5, pady=5)
            else:
                ctk.CTkLabel(item_frame, text="✓").grid(row=0, column=0, padx=5, pady=5)

            # Title
            ctk.CTkLabel(
                item_frame,
                text=item.title,
                anchor="w"
            ).grid(row=0, column=1, sticky="w", padx=5, pady=5)

            # Who
            ctk.CTkLabel(item_frame, text=item.who, width=100).grid(row=0, column=2, padx=5, pady=5)

            # Due date
            ctk.CTkLabel(
                item_frame,
                text=item.due_date or "-",
                width=100
            ).grid(row=0, column=3, padx=5, pady=5)

            # Priority
            ctk.CTkLabel(
                item_frame,
                text=str(item.priority_score),
                width=80
            ).grid(row=0, column=4, padx=5, pady=5)

            # Status
            ctk.CTkLabel(item_frame, text=item.status, width=80).grid(row=0, column=5, padx=5, pady=5)

            # Edit button
            btn_edit = ctk.CTkButton(
                item_frame,
                text="Edit",
                width=60,
                command=lambda i=item.id: self.edit_item(i)
            )
            btn_edit.grid(row=0, column=6, padx=2, pady=5)

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
