"""
Completed screen - view completed items.
"""

import customtkinter as ctk
from typing import TYPE_CHECKING

from ..color_contrast import pick_text_color
from .segment_color_utils import resolve_segment_color_for_item
from .week_collision_notice import notify_weekly_tactic_changes
from ..theme import apply_segment_accent, semantic_colors, button_style, combo_box_style, list_row_font
from .title_format import (
    split_action_item_title,
    format_column_text,
    CONTEXT_COL_CHARS,
    CONTACT_COL_CHARS,
)

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class CompletedScreen(ctk.CTkFrame):
    """Screen showing completed items."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app
        self.segment_colors_by_id = {}
        self.segment_colors_by_name = {}
        self._parent_segment_cache = {}
        self._ape_segment_cache = {}
        self._week_action_segment_cache = {}
        # Track column visibility state (default: collapsed)
        self.columns_expanded = False
        self.palette = semantic_colors()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Create scrollable frame for items
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.grid(
            row=1, column=0, sticky="nsew", padx=10, pady=10)
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
        ctk.CTkLabel(header, text="Last").grid(
            row=0, column=1, padx=(20, 5), pady=10)

        self.days_var = ctk.StringVar(value="30")
        self.days_combo = ctk.CTkComboBox(
            header,
            values=["7", "30", "90", "365"],
            variable=self.days_var,
            width=80,
            command=lambda _: self.refresh()
        )
        self.days_combo.grid(row=0, column=2, padx=5, pady=10)

        ctk.CTkLabel(header, text="days").grid(
            row=0, column=3, sticky="w", padx=5, pady=10)

        # Who filter
        ctk.CTkLabel(header, text="Who:").grid(
            row=0, column=4, padx=(20, 5), pady=10)

        who_values = ["All"] + self.db_manager.get_distinct_who_values()
        self.who_var = ctk.StringVar(value="All")
        self.who_combo = ctk.CTkComboBox(
            header,
            values=who_values,
            variable=self.who_var,
            width=150,
            **combo_box_style(),
            command=lambda _: self.refresh()
        )
        self.who_combo.grid(row=0, column=5, padx=5, pady=10)

        # Expand/Collapse button
        self.expand_collapse_btn = ctk.CTkButton(
            header,
            text="Expand",
            width=100,
            **button_style("secondary"),
            command=self.toggle_columns
        )
        self.expand_collapse_btn.grid(row=0, column=6, padx=5, pady=10)

        # Stats label (count and total time)
        self.stats_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.palette["body_text"]
        )
        self.stats_label.grid(row=0, column=7, padx=(20, 10), pady=10)

    def toggle_columns(self):
        """Toggle between expanded and collapsed column view."""
        self.columns_expanded = not self.columns_expanded
        self.expand_collapse_btn.configure(
            text="Expand" if not self.columns_expanded else "Collapse")
        self.refresh()

    def refresh(self):
        """Refresh the list of completed items."""
        self.palette = semantic_colors()
        # Temporarily remove scroll_frame from grid to prevent flickering during rebuild
        grid_info = self.scroll_frame.grid_info()
        self.scroll_frame.grid_remove()

        try:
            # Clear current items
            for widget in self.scroll_frame.winfo_children():
                widget.destroy()

            # Refresh VSP segment color cache
            self.segment_colors_by_id = self.app.vps_manager.get_segment_colors_by_id()
            self.segment_colors_by_name = self.app.vps_manager.get_segment_color_map()
            self._parent_segment_cache = {}
            self._ape_segment_cache = {}
            self._week_action_segment_cache = {}

            # Get filters
            days_back = int(self.days_var.get())
            who_filter = None if self.who_var.get() == "All" else self.who_var.get()

            # Get items
            items = self.db_manager.get_completed_items(days_back, who_filter)

            # Calculate stats
            count = len(items)
            total_minutes = sum(
                item.planned_minutes for item in items if item.planned_minutes)

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
            self.stats_label.configure(
                text=f"Count: {count} | Time: {time_str}")

            if not items:
                label = ctk.CTkLabel(
                    self.scroll_frame,
                    text="No completed items",
                    font=ctk.CTkFont(size=14)
                )
                label.grid(row=0, column=0, pady=20)
                return

            # Display items
            palette = self.palette
            row_text = palette["row_text"]
            for idx, item in enumerate(items):
                segment_color = resolve_segment_color_for_item(
                    item,
                    self.segment_colors_by_id,
                    self.segment_colors_by_name,
                    self.db_manager,
                    self._parent_segment_cache,
                    self._ape_segment_cache,
                    self._week_action_segment_cache,
                )
                is_critical = (item.importance == 20 or item.urgency == 20)
                if is_critical:
                    bg_color = palette["critical_tint"]
                else:
                    bg_color = None
                item_frame = ctk.CTkFrame(self.scroll_frame, fg_color=bg_color)
                apply_segment_accent(item_frame, segment_color)
                item_frame.grid(row=idx, column=0, sticky="ew", pady=2, padx=5)
                item_frame.grid_columnconfigure(1, weight=1)
                parsed = split_action_item_title(item.title)

                # Checkmark
                ctk.CTkLabel(item_frame, text="✓", width=30, text_color=palette["success_strong"]).grid(
                    row=0, column=0, padx=5, pady=5)

                title_cell = ctk.CTkFrame(item_frame, fg_color="transparent")
                title_cell.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
                title_cell.grid_columnconfigure(1, weight=1)
                if item.item_type == "week":
                    ctk.CTkLabel(
                        title_cell,
                        text="WT",
                        width=28,
                        corner_radius=6,
                        fg_color=palette["success_strong"],
                        text_color=palette["on_strong"],
                        font=ctk.CTkFont(size=11, weight="bold"),
                    ).grid(row=0, column=0, padx=(0, 6), sticky="w")
                title_label = ctk.CTkLabel(
                    title_cell,
                    text=parsed.title,
                    font=list_row_font(),
                    anchor="w",
                    text_color=row_text,
                )
                title_label.grid(row=0, column=1, sticky="ew")
                title_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_item(item_id))

                # Context
                ctk.CTkLabel(
                    item_frame,
                    text=format_column_text(parsed.context, CONTEXT_COL_CHARS),
                    width=140,
                    anchor="w",
                    text_color=row_text,
                    font=list_row_font(),
                ).grid(row=0, column=2, padx=5, pady=5, sticky="w")

                # Who
                ctk.CTkLabel(
                    item_frame,
                    text=format_column_text(item.who, CONTACT_COL_CHARS),
                    width=110,
                    anchor="w",
                    text_color=row_text,
                    font=list_row_font(),
                ).grid(row=0, column=3, padx=5, pady=5, sticky="w")

                # Completed date
                if item.completed_at:
                    completed_label = ctk.CTkLabel(
                        item_frame,
                        text=f"Completed: {item.completed_at[:10]}",
                        width=150,
                        text_color=row_text,
                        font=list_row_font()
                    )
                    completed_label.grid(row=0, column=4, padx=5, pady=5)

                # Priority score
                is_priority_critical = item.importance == 20 or item.urgency == 20
                score_label = ctk.CTkLabel(
                    item_frame,
                    text=f"P:{item.priority_score}",
                    width=60,
                    fg_color=self.palette["danger"] if is_priority_critical else "transparent",
                    text_color=pick_text_color(self.palette["danger"]) if is_priority_critical else row_text,
                    corner_radius=6 if is_priority_critical else 0,
                    font=list_row_font()
                )
                score_label.grid(row=0, column=5, padx=5, pady=5)

                # Factor chips (I, U, E, V) - only shown when expanded
                col_offset = 0
                if self.columns_expanded:
                    factors_frame = ctk.CTkFrame(
                        item_frame, fg_color="transparent")
                    factors_frame.grid(row=0, column=6, padx=5, pady=5)
                    columns = [
                        ("G", item.group, 120),
                        ("C", item.category, 120),
                        ("I", item.importance, 40),
                        ("U", item.urgency, 40),
                        ("E", item.size, 40),
                        ("V", item.value, 40),
                    ]
                    for factor_col, (label, value, width) in enumerate(columns):
                        text = f"{label}:{value}" if value not in (None, "") else ""
                        label_kwargs = {
                            "text": text,
                            "width": width,
                            "anchor": "w",
                            "font": list_row_font(),
                            "text_color": row_text,
                        }
                        if label in ("I", "U") and str(value).strip() == "20":
                            label_kwargs["fg_color"] = self.palette["danger"]
                            label_kwargs["text_color"] = pick_text_color(self.palette["danger"])
                            label_kwargs["corner_radius"] = 6
                        ctk.CTkLabel(factors_frame, **label_kwargs).grid(
                            row=0, column=factor_col, padx=2)
                    col_offset = 1

                # Uncomplete button
                btn_uncomplete = ctk.CTkButton(
                    item_frame,
                    text="Reopen",
                    width=70,
                    **button_style("secondary"),
                    command=lambda i=item.id: self.uncomplete_item(i)
                )
                btn_uncomplete.grid(row=0, column=7+col_offset, padx=2, pady=5)
        finally:
            # Restore scroll_frame to grid - this ensures it's shown even if an error occurs
            self.scroll_frame.grid(**grid_info)

    def edit_item(self, item_id: str):
        """Edit item details."""
        from .item_editor import ItemEditorDialog
        ItemEditorDialog(self, self.db_manager, item_id,
                         vps_manager=self.app.vps_manager, on_close_callback=self.refresh)

    def uncomplete_item(self, item_id: str):
        """Reopen a completed item."""
        self.db_manager.uncomplete_action_item(item_id)
        notify_weekly_tactic_changes(self.db_manager, self)
        self.refresh()
