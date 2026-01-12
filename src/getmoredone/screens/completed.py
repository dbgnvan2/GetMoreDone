"""
Completed screen - view completed items.
"""

import customtkinter as ctk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class CompletedScreen(ctk.CTkFrame):
    """Screen showing completed items."""

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
        header.grid_columnconfigure(3, weight=1)

        # Title
        title = ctk.CTkLabel(
            header,
            text="Completed Items",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=10)

        # Days back selector
        ctk.CTkLabel(header, text="Last").grid(row=0, column=1, padx=(20, 5), pady=10)

        self.days_var = ctk.StringVar(value="30")
        self.days_combo = ctk.CTkComboBox(
            header,
            values=["7", "30", "90", "365"],
            variable=self.days_var,
            width=80,
            command=lambda _: self.refresh()
        )
        self.days_combo.grid(row=0, column=2, padx=5, pady=10)

        ctk.CTkLabel(header, text="days").grid(row=0, column=3, sticky="w", padx=5, pady=10)

        # Who filter
        ctk.CTkLabel(header, text="Who:").grid(row=0, column=4, padx=(20, 5), pady=10)

        who_values = ["All"] + self.db_manager.get_distinct_who_values()
        self.who_var = ctk.StringVar(value="All")
        self.who_combo = ctk.CTkComboBox(
            header,
            values=who_values,
            variable=self.who_var,
            width=150,
            command=lambda _: self.refresh()
        )
        self.who_combo.grid(row=0, column=5, padx=5, pady=10)

    def refresh(self):
        """Refresh the list of completed items."""
        # Clear current items
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get filters
        days_back = int(self.days_var.get())
        who_filter = None if self.who_var.get() == "All" else self.who_var.get()

        # Get items
        items = self.db_manager.get_completed_items(days_back, who_filter)

        if not items:
            label = ctk.CTkLabel(
                self.scroll_frame,
                text="No completed items",
                font=ctk.CTkFont(size=14)
            )
            label.grid(row=0, column=0, pady=20)
            return

        # Display items
        for idx, item in enumerate(items):
            item_frame = ctk.CTkFrame(self.scroll_frame)
            item_frame.grid(row=idx, column=0, sticky="ew", pady=2, padx=5)
            item_frame.grid_columnconfigure(1, weight=1)

            # Checkmark
            ctk.CTkLabel(item_frame, text="✓", width=30).grid(row=0, column=0, padx=5, pady=5)

            # Title and info
            info_text = f"{item.title}"
            if item.who:
                info_text += f" ({item.who})"

            title_label = ctk.CTkLabel(
                item_frame,
                text=info_text,
                font=ctk.CTkFont(size=12),
                anchor="w"
            )
            title_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)

            # Completed date
            if item.completed_at:
                completed_label = ctk.CTkLabel(
                    item_frame,
                    text=f"Completed: {item.completed_at[:10]}",
                    width=150
                )
                completed_label.grid(row=0, column=2, padx=5, pady=5)

            # Priority score
            score_label = ctk.CTkLabel(
                item_frame,
                text=f"P:{item.priority_score}",
                width=60
            )
            score_label.grid(row=0, column=3, padx=5, pady=5)

            # View button
            btn_view = ctk.CTkButton(
                item_frame,
                text="View",
                width=60,
                command=lambda i=item.id: self.view_item(i)
            )
            btn_view.grid(row=0, column=4, padx=2, pady=5)

    def view_item(self, item_id: str):
        """View item details."""
        from .item_editor import ItemEditorDialog
        dialog = ItemEditorDialog(self, self.db_manager, item_id)
        dialog.wait_window()
        self.refresh()
