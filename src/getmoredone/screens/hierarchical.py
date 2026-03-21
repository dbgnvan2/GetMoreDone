"""
Hierarchical screen - shows items in parent-child tree view.
"""

import customtkinter as ctk
from typing import Optional, TYPE_CHECKING, List

from ..models import ActionItem, Status
from ..color_contrast import pick_text_color
from .item_lineage import lineage_for_item, LINEAGE_COL_CHARS
from .segment_color_utils import resolve_segment_color_for_item
from ..theme import apply_segment_accent, semantic_colors, button_style, list_row_font
from .title_format import (
    split_action_item_title,
    format_column_text,
    responsive_column_chars,
    CONTEXT_COL_CHARS,
    CONTACT_COL_CHARS,
)

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class HierarchicalScreen(ctk.CTkFrame):
    """Screen showing action items in hierarchical tree view."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app
        self.search_query = ""  # Track search query
        self.segment_colors_by_id = {}
        self.segment_colors_by_name = {}
        self._parent_segment_cache = {}
        self._ape_segment_cache = {}
        self._ape_lineage_cache = {}
        self._week_action_segment_cache = {}
        self._item_lineage_cache = {}
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
            text="Hierarchical View",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=10)

        # Search entry
        self.search_entry = ctk.CTkEntry(
            header,
            placeholder_text="Search title, description, next action...",
            width=200
        )
        self.search_entry.grid(row=0, column=1, padx=5, pady=10)
        self.search_entry.bind("<Return>", lambda e: self.perform_search())

        # Search button
        btn_search = ctk.CTkButton(
            header,
            text="Search",
            width=80,
            **button_style("secondary"),
            command=self.perform_search
        )
        btn_search.grid(row=0, column=2, padx=5, pady=10)

        # Status filter
        ctk.CTkLabel(header, text="Status:").grid(
            row=0, column=4, padx=(20, 5), pady=10)

        self.status_var = ctk.StringVar(value="open")
        self.status_combo = ctk.CTkComboBox(
            header,
            values=["open", "completed", "all"],
            variable=self.status_var,
            width=120,
            command=lambda _: self.refresh()
        )
        self.status_combo.grid(row=0, column=5, padx=5, pady=10)

        # New Item button
        btn_new = ctk.CTkButton(
            header,
            text="+ New Item",
            **button_style("primary"),
            command=self.create_new_item
        )
        btn_new.grid(row=0, column=6, padx=10, pady=10)

    def perform_search(self):
        """Perform search and update the view."""
        self.search_query = self.search_entry.get().strip()
        self.refresh()

    def refresh(self):
        """Refresh the hierarchical list."""
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
            self._ape_lineage_cache = {}
            self._week_action_segment_cache = {}
            self._item_lineage_cache = {}

            # Get status filter
            status = self.status_var.get()
            status_filter = None if status == "all" else status

            # Get items (use search if query exists, otherwise get root items)
            if self.search_query:
                all_items = self.db_manager.search_items(self.search_query)
                # Apply status filter to search results
                if status_filter:
                    all_items = [
                        item for item in all_items if item.status == status_filter]
                # For search results, show all matching items (not just roots)
                root_items = all_items
            else:
                # Get root items (items with no parent)
                root_items = self.db_manager.get_root_items(
                    status_filter=status_filter)

            if not root_items:
                label = ctk.CTkLabel(
                    self.scroll_frame,
                    text="No root items found",
                    font=ctk.CTkFont(size=14)
                )
                label.grid(row=0, column=0, pady=20)
                return

            # Display each item
            row = 0
            if self.search_query:
                # For search results, display items in a flat list
                for item in root_items:
                    item_frame = self.create_item_row(item, 0)
                    item_frame.grid(row=row, column=0,
                                    sticky="ew", pady=2, padx=5)
                    row += 1
            else:
                # Display root items and their children recursively
                for item in root_items:
                    row = self.display_item_tree(item, row, 0)
        finally:
            # Restore scroll_frame to grid - this ensures it's shown even if an error occurs
            self.scroll_frame.grid(**grid_info)

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
        item_frame.grid(row=row, column=0, sticky="ew", pady=2,
                        padx=(indent_level * 30 + 5, 5))
        row += 1

        # Get and display children
        children = self.db_manager.get_children(item.id)
        for child in children:
            row = self.display_item_tree(child, row, indent_level + 1)

        return row

    def create_item_row(self, item: ActionItem, indent_level: int) -> ctk.CTkFrame:
        """Create a row for an action item."""
        palette = self.palette
        row_text = palette["row_text"]
        segment_color = resolve_segment_color_for_item(
            item,
            self.segment_colors_by_id,
            self.segment_colors_by_name,
            self.db_manager,
            self._parent_segment_cache,
            self._ape_segment_cache,
            self._week_action_segment_cache,
        )
        if item.status == Status.COMPLETED:
            bg_color = palette["success_tint"]
        elif item.importance == 20 or item.urgency == 20:
            bg_color = palette["critical_tint"]
        else:
            bg_color = None
        frame = ctk.CTkFrame(self.scroll_frame, fg_color=bg_color)
        apply_segment_accent(frame, segment_color)
        frame.grid_columnconfigure(0, weight=1)
        limits = responsive_column_chars(max(self.winfo_width(), self.scroll_frame.winfo_width()))
        parsed = split_action_item_title(item.title)
        _segment_name, subsegment_name, category_name = lineage_for_item(
            item,
            self.db_manager,
            self._item_lineage_cache,
            self._ape_lineage_cache,
            self._week_action_segment_cache,
        )

        # Calculate left padding for indentation
        indent_padding = (indent_level * 30, 5)

        # Title with indentation indicator for child rows.
        title_text = parsed.title
        if item.group:
            title_text += f" [{item.group}]"

        # Add indentation indicator for child items
        if indent_level > 0:
            indicator = "└─ "
            title_text = indicator + title_text

        title_label = ctk.CTkLabel(
            frame,
            text=title_text,
            font=ctk.CTkFont(
                size=14, family="Courier" if indent_level > 0 else None),
            anchor="w",
            text_color=row_text,
        )
        title_label.grid(row=0, column=0, sticky="ew",
                         padx=indent_padding, pady=5)
        title_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_item(item_id))

        ctk.CTkLabel(
            frame,
            text=format_column_text(subsegment_name or "-", limits["subsegment"]),
            width=max(56, limits["subsegment"] * 8),
            anchor="w",
            text_color=row_text,
            font=list_row_font(),
        ).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(
            frame,
            text=format_column_text(category_name or "-", limits["category"]),
            width=max(56, limits["category"] * 8),
            anchor="w",
            text_color=row_text,
            font=list_row_font(),
        ).grid(row=0, column=2, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(
            frame,
            text=format_column_text(parsed.context, limits["context"]),
            width=max(90, limits["context"] * 8),
            anchor="w",
            text_color=row_text,
            font=list_row_font(),
        ).grid(row=0, column=3, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(
            frame,
            text=format_column_text(item.who, limits["who"]),
            width=max(52, limits["who"] * 8),
            anchor="w",
            text_color=row_text,
            font=list_row_font(),
        ).grid(row=0, column=4, padx=5, pady=5, sticky="w")

        # Priority score
        is_priority_critical = item.importance == 20 or item.urgency == 20
        score_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=60,
            fg_color=palette["danger"] if is_priority_critical else "transparent",
            text_color=pick_text_color(palette["danger"]) if is_priority_critical else row_text,
            corner_radius=6 if is_priority_critical else 0,
            font=list_row_font()
        )
        score_label.grid(row=0, column=5, padx=5, pady=5)

        # Due date
        if item.due_date:
            due_label = ctk.CTkLabel(
                frame,
                text=f"Due: {item.due_date}",
                width=110,
                text_color=row_text,
                font=list_row_font()
            )
            due_label.grid(row=0, column=6, padx=5, pady=5)
        else:
            # Empty space to maintain alignment
            ctk.CTkLabel(frame, text="", width=110).grid(
                row=0, column=6, padx=5, pady=5)

        # Child count
        children = self.db_manager.get_children(item.id)
        if children:
            child_count_label = ctk.CTkLabel(
                frame,
                text=f"({len(children)} sub)",
                width=70,
                text_color=row_text,
                font=list_row_font()
            )
            child_count_label.grid(row=0, column=7, padx=5, pady=5)
        else:
            # Empty space to maintain alignment
            ctk.CTkLabel(frame, text="", width=70).grid(
                row=0, column=7, padx=5, pady=5)

        return frame

    def complete_item(self, item_id: str):
        """Mark item as complete."""
        self.db_manager.complete_action_item(item_id)
        self.refresh()

    def edit_item(self, item_id: str):
        """Open item editor."""
        from .item_editor import ItemEditorDialog
        ItemEditorDialog(self, self.db_manager, item_id,
                         vps_manager=self.app.vps_manager, on_close_callback=self.refresh)

    def create_new_item(self):
        """Open item editor for new item."""
        from .item_editor import ItemEditorDialog
        ItemEditorDialog(self, self.db_manager,
                         vps_manager=self.app.vps_manager, on_close_callback=self.refresh)
