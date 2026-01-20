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
        self.columns_expanded = True  # Track column visibility state

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

        # Expand/Collapse button
        self.expand_collapse_btn = ctk.CTkButton(
            header,
            text="Collapse",
            width=100,
            command=self.toggle_columns
        )
        self.expand_collapse_btn.grid(row=0, column=6, padx=5, pady=10)

        # Stats label (count and total time)
        self.stats_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="lightblue"
        )
        self.stats_label.grid(row=0, column=7, padx=(20, 10), pady=10)

    def toggle_columns(self):
        """Toggle between expanded and collapsed column view."""
        self.columns_expanded = not self.columns_expanded
        self.expand_collapse_btn.configure(text="Expand" if not self.columns_expanded else "Collapse")
        self.refresh()

    def refresh(self):
        """Refresh the list of completed items."""
        # Temporarily remove scroll_frame from grid to prevent flickering during rebuild
        grid_info = self.scroll_frame.grid_info()
        self.scroll_frame.grid_remove()

        try:
            # Clear current items
            for widget in self.scroll_frame.winfo_children():
                widget.destroy()

            # Get filters
            days_back = int(self.days_var.get())
            who_filter = None if self.who_var.get() == "All" else self.who_var.get()

            # Get items
            items = self.db_manager.get_completed_items(days_back, who_filter)

            # Calculate stats
            count = len(items)
            total_minutes = sum(item.planned_minutes for item in items if item.planned_minutes)

            # Format total time
            if total_minutes >= 60:
                hours = total_minutes // 60
                minutes = total_minutes % 60
                if minutes > 0:
                    time_str = f"{hours}h {minutes}m"
                else:
                    time_str = f"{hours}h"
            else:
                time_str = f"{total_minutes}m" if total_minutes > 0 else "0m"

            # Update stats label
            self.stats_label.configure(text=f"Count: {count} | Time: {time_str}")

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
                # RED background for critical items (even when completed)
                is_critical = (item.importance == 20 or item.urgency == 20)
                bg_color = "darkred" if is_critical else None
                item_frame = ctk.CTkFrame(self.scroll_frame, fg_color=bg_color)
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

                # Factor chips (I, U, E, V) - only shown when expanded
                col_offset = 0
                if self.columns_expanded:
                    factors_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
                    factors_frame.grid(row=0, column=4, padx=5, pady=5)
                    factor_col = 0
                    if item.importance:
                        ctk.CTkLabel(factors_frame, text=f"I:{item.importance}", width=40).grid(row=0, column=factor_col, padx=2)
                        factor_col += 1
                    if item.urgency:
                        ctk.CTkLabel(factors_frame, text=f"U:{item.urgency}", width=40).grid(row=0, column=factor_col, padx=2)
                        factor_col += 1
                    if item.size:
                        ctk.CTkLabel(factors_frame, text=f"E:{item.size}", width=40).grid(row=0, column=factor_col, padx=2)
                        factor_col += 1
                    if item.value:
                        ctk.CTkLabel(factors_frame, text=f"V:{item.value}", width=40).grid(row=0, column=factor_col, padx=2)
                        factor_col += 1
                    col_offset = 1

                # Edit button
                btn_edit = ctk.CTkButton(
                    item_frame,
                    text="Edit",
                    width=60,
                    command=lambda i=item.id: self.edit_item(i)
                )
                btn_edit.grid(row=0, column=4+col_offset, padx=2, pady=5)

                # Uncomplete button
                btn_uncomplete = ctk.CTkButton(
                    item_frame,
                    text="Reopen",
                    width=70,
                    fg_color="orange",
                    hover_color="darkorange",
                    command=lambda i=item.id: self.uncomplete_item(i)
                )
                btn_uncomplete.grid(row=0, column=5+col_offset, padx=2, pady=5)
        finally:
            # Restore scroll_frame to grid - this ensures it's shown even if an error occurs
            self.scroll_frame.grid(**grid_info)

    def edit_item(self, item_id: str):
        """Edit item details."""
        from .item_editor import ItemEditorDialog
        dialog = ItemEditorDialog(self, self.db_manager, item_id, vps_manager=self.app.vps_manager)
        dialog.wait_window()
        self.refresh()

    def uncomplete_item(self, item_id: str):
        """Reopen a completed item."""
        self.db_manager.uncomplete_action_item(item_id)
        self.refresh()
