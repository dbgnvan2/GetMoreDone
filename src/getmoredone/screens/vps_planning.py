"""
VPS Planning screen - shows strategic planning hierarchy with collapsible tree view.
"""

import customtkinter as ctk
from typing import Optional, TYPE_CHECKING, Dict, Any, List

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class VPSPlanningScreen(ctk.CTkFrame):
    """Screen showing VPS planning hierarchy in collapsible tree view."""

    def __init__(self, parent, vps_manager: 'VPSManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        # Track expanded/collapsed state
        self.expanded_nodes = set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Create scrollable frame for tree
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Load segments and tree
        self.refresh()

    def create_header(self):
        """Create header with controls."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(1, weight=1)

        # Title
        title = ctk.CTkLabel(
            header,
            text="Visionary Planning System",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=10)

        # Segment filter
        ctk.CTkLabel(header, text="Segment:").grid(row=0, column=2, padx=(20, 5), pady=10)

        self.segment_var = ctk.StringVar(value="all")
        self.segment_combo = ctk.CTkComboBox(
            header,
            values=["all"],
            variable=self.segment_var,
            width=200,
            command=lambda _: self.refresh()
        )
        self.segment_combo.grid(row=0, column=3, padx=5, pady=10)

        # Refresh segments list
        self.update_segment_filter()

        # Expand/Collapse All button
        btn_expand = ctk.CTkButton(
            header,
            text="Expand All",
            command=self.expand_all,
            width=100
        )
        btn_expand.grid(row=0, column=4, padx=5, pady=10)

        btn_collapse = ctk.CTkButton(
            header,
            text="Collapse All",
            command=self.collapse_all,
            width=100
        )
        btn_collapse.grid(row=0, column=5, padx=5, pady=10)

        # New Vision button
        btn_new = ctk.CTkButton(
            header,
            text="+ New Vision",
            command=self.create_new_tl_vision
        )
        btn_new.grid(row=0, column=6, padx=10, pady=10)

    def update_segment_filter(self):
        """Update segment filter dropdown."""
        segments = self.vps_manager.get_all_segments()
        segment_names = ["all"] + [seg['name'] for seg in segments]
        self.segment_combo.configure(values=segment_names)

    def refresh(self):
        """Refresh the planning tree."""
        # Clear current tree
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get selected segment
        selected_segment = self.segment_var.get()

        # Get all segments or filtered segment
        segments = self.vps_manager.get_all_segments()

        if selected_segment != "all":
            segments = [seg for seg in segments if seg['name'] == selected_segment]

        if not segments:
            label = ctk.CTkLabel(
                self.scroll_frame,
                text="No life segments defined. Create your first vision!",
                font=ctk.CTkFont(size=14)
            )
            label.grid(row=0, column=0, pady=20)
            return

        # Display each segment tree
        row = 0
        for segment in segments:
            row = self.display_segment_tree(segment, row)

    def display_segment_tree(self, segment: Dict[str, Any], row: int) -> int:
        """Display a segment and its complete hierarchy."""
        # Segment header (always visible)
        seg_frame = self.create_segment_row(segment)
        seg_frame.grid(row=row, column=0, sticky="ew", pady=5, padx=5)
        row += 1

        # Get TL Visions for this segment
        node_id = f"segment-{segment['id']}"
        if node_id in self.expanded_nodes:
            tl_visions = self.vps_manager.get_tl_visions(segment_id=segment['id'])

            if not tl_visions:
                # Show "no visions" message
                empty_frame = ctk.CTkFrame(self.scroll_frame)
                empty_label = ctk.CTkLabel(
                    empty_frame,
                    text="   └─ No visions yet. Click '+' to create.",
                    font=ctk.CTkFont(size=11),
                    text_color="gray"
                )
                empty_label.pack(anchor="w", padx=10, pady=5)
                empty_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=30)
                row += 1
            else:
                for vision in tl_visions:
                    row = self.display_tl_vision_tree(vision, row, 1)

        return row

    def display_tl_vision_tree(self, vision: Dict[str, Any], row: int, indent: int) -> int:
        """Display a TL Vision and its children."""
        vision_frame = self.create_tl_vision_row(vision, indent)
        vision_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=(indent * 30 + 5, 5))
        row += 1

        node_id = f"tl_vision-{vision['id']}"
        if node_id in self.expanded_nodes:
            annual_visions = self.vps_manager.get_annual_visions(tl_vision_id=vision['id'])

            if not annual_visions:
                row = self.display_empty_message(row, indent + 1, "No annual visions")
            else:
                for av in annual_visions:
                    row = self.display_annual_vision_tree(av, row, indent + 1)

        return row

    def display_annual_vision_tree(self, vision: Dict[str, Any], row: int, indent: int) -> int:
        """Display an Annual Vision and its children."""
        vision_frame = self.create_annual_vision_row(vision, indent)
        vision_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=(indent * 30 + 5, 5))
        row += 1

        node_id = f"annual_vision-{vision['id']}"
        if node_id in self.expanded_nodes:
            annual_plans = self.vps_manager.get_annual_plans(annual_vision_id=vision['id'])

            if not annual_plans:
                row = self.display_empty_message(row, indent + 1, "No annual plans")
            else:
                for plan in annual_plans:
                    row = self.display_annual_plan_tree(plan, row, indent + 1)

        return row

    def display_annual_plan_tree(self, plan: Dict[str, Any], row: int, indent: int) -> int:
        """Display an Annual Plan and its children."""
        plan_frame = self.create_annual_plan_row(plan, indent)
        plan_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=(indent * 30 + 5, 5))
        row += 1

        node_id = f"annual_plan-{plan['id']}"
        if node_id in self.expanded_nodes:
            initiatives = self.vps_manager.get_quarter_initiatives(annual_plan_id=plan['id'])

            if not initiatives:
                row = self.display_empty_message(row, indent + 1, "No quarter initiatives")
            else:
                for initiative in initiatives:
                    row = self.display_quarter_initiative_tree(initiative, row, indent + 1)

        return row

    def display_quarter_initiative_tree(self, initiative: Dict[str, Any], row: int, indent: int) -> int:
        """Display a Quarter Initiative and its children."""
        init_frame = self.create_quarter_initiative_row(initiative, indent)
        init_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=(indent * 30 + 5, 5))
        row += 1

        node_id = f"quarter_initiative-{initiative['id']}"
        if node_id in self.expanded_nodes:
            tactics = self.vps_manager.get_month_tactics(quarter_initiative_id=initiative['id'])

            if not tactics:
                row = self.display_empty_message(row, indent + 1, "No month tactics")
            else:
                for tactic in tactics:
                    row = self.display_month_tactic_tree(tactic, row, indent + 1)

        return row

    def display_month_tactic_tree(self, tactic: Dict[str, Any], row: int, indent: int) -> int:
        """Display a Month Tactic and its children."""
        tactic_frame = self.create_month_tactic_row(tactic, indent)
        tactic_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=(indent * 30 + 5, 5))
        row += 1

        node_id = f"month_tactic-{tactic['id']}"
        if node_id in self.expanded_nodes:
            actions = self.vps_manager.get_week_actions(month_tactic_id=tactic['id'])

            if not actions:
                row = self.display_empty_message(row, indent + 1, "No week actions")
            else:
                for action in actions:
                    row = self.display_week_action_tree(action, row, indent + 1)

        return row

    def display_week_action_tree(self, action: Dict[str, Any], row: int, indent: int) -> int:
        """Display a Week Action and its linked action items."""
        action_frame = self.create_week_action_row(action, indent)
        action_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=(indent * 30 + 5, 5))
        row += 1

        node_id = f"week_action-{action['id']}"
        if node_id in self.expanded_nodes:
            action_items = self.vps_manager.get_action_items_for_week_action(action['id'])

            if not action_items:
                row = self.display_empty_message(row, indent + 1, "No action items")
            else:
                for item in action_items:
                    row = self.display_action_item(item, row, indent + 1)

        return row

    def display_action_item(self, item: Dict[str, Any], row: int, indent: int) -> int:
        """Display an action item (leaf node)."""
        item_frame = self.create_action_item_row(item, indent)
        item_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=(indent * 30 + 5, 5))
        return row + 1

    def display_empty_message(self, row: int, indent: int, message: str) -> int:
        """Display an empty/no children message."""
        empty_frame = ctk.CTkFrame(self.scroll_frame)
        empty_label = ctk.CTkLabel(
            empty_frame,
            text=f"{'  ' * indent}└─ {message}",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        empty_label.pack(anchor="w", padx=10, pady=3)
        empty_frame.grid(row=row, column=0, sticky="ew", pady=1, padx=(indent * 30 + 5, 5))
        return row + 1

    # ========================================================================
    # ROW CREATORS
    # ========================================================================

    def create_segment_row(self, segment: Dict[str, Any]) -> ctk.CTkFrame:
        """Create a row for a segment."""
        node_id = f"segment-{segment['id']}"
        is_expanded = node_id in self.expanded_nodes

        frame = ctk.CTkFrame(self.scroll_frame, fg_color=segment['color_hex'])
        frame.grid_columnconfigure(1, weight=1)

        # Expand/collapse button
        btn_expand = ctk.CTkButton(
            frame,
            text="▼" if is_expanded else "▶",
            width=30,
            command=lambda: self.toggle_node(node_id)
        )
        btn_expand.grid(row=0, column=0, padx=5, pady=5)

        # Segment name
        label = ctk.CTkLabel(
            frame,
            text=f"🎯 {segment['name']}",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        label.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Add button
        btn_add = ctk.CTkButton(
            frame,
            text="+",
            width=30,
            command=lambda: self.add_tl_vision(segment['id'])
        )
        btn_add.grid(row=0, column=2, padx=5, pady=5)

        return frame

    def create_tl_vision_row(self, vision: Dict[str, Any], indent: int) -> ctk.CTkFrame:
        """Create a row for a TL Vision."""
        node_id = f"tl_vision-{vision['id']}"
        is_expanded = node_id in self.expanded_nodes

        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid_columnconfigure(2, weight=1)

        # Indentation
        indent_label = ctk.CTkLabel(frame, text="  " * indent + "└─", font=ctk.CTkFont(family="Courier"))
        indent_label.grid(row=0, column=0, sticky="w")

        # Expand/collapse button
        btn_expand = ctk.CTkButton(
            frame,
            text="▼" if is_expanded else "▶",
            width=25,
            command=lambda: self.toggle_node(node_id)
        )
        btn_expand.grid(row=0, column=1, padx=2, pady=3)

        # Vision title
        label = ctk.CTkLabel(
            frame,
            text=f"📅 {vision['start_year']}-{vision['end_year']}: {vision['title'] or 'Untitled'}",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        label.grid(row=0, column=2, sticky="w", padx=5, pady=3)

        # Action buttons
        btn_add = ctk.CTkButton(frame, text="+", width=25, command=lambda: self.add_annual_vision(vision['id']))
        btn_add.grid(row=0, column=3, padx=2, pady=3)

        btn_edit = ctk.CTkButton(frame, text="✎", width=25, command=lambda: self.edit_tl_vision(vision['id']))
        btn_edit.grid(row=0, column=4, padx=2, pady=3)

        btn_delete = ctk.CTkButton(frame, text="🗑", width=25, command=lambda: self.delete_tl_vision(vision['id']), fg_color="darkred", hover_color="red")
        btn_delete.grid(row=0, column=5, padx=2, pady=3)

        return frame

    def create_annual_vision_row(self, vision: Dict[str, Any], indent: int) -> ctk.CTkFrame:
        """Create a row for an Annual Vision."""
        node_id = f"annual_vision-{vision['id']}"
        is_expanded = node_id in self.expanded_nodes

        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid_columnconfigure(2, weight=1)

        indent_label = ctk.CTkLabel(frame, text="  " * indent + "└─", font=ctk.CTkFont(family="Courier"))
        indent_label.grid(row=0, column=0, sticky="w")

        btn_expand = ctk.CTkButton(frame, text="▼" if is_expanded else "▶", width=25,
                                   command=lambda: self.toggle_node(node_id))
        btn_expand.grid(row=0, column=1, padx=2, pady=3)

        label = ctk.CTkLabel(frame, text=f"📆 {vision['year']}: {vision['title'] or 'Untitled'}",
                            font=ctk.CTkFont(size=12), anchor="w")
        label.grid(row=0, column=2, sticky="w", padx=5, pady=3)

        btn_add = ctk.CTkButton(frame, text="+", width=25, command=lambda: self.add_annual_plan(vision['id']))
        btn_add.grid(row=0, column=3, padx=2, pady=3)

        btn_edit = ctk.CTkButton(frame, text="✎", width=25, command=lambda: self.edit_annual_vision(vision['id']))
        btn_edit.grid(row=0, column=4, padx=2, pady=3)

        btn_delete = ctk.CTkButton(frame, text="🗑", width=25, command=lambda: self.delete_annual_vision(vision['id']), fg_color="darkred", hover_color="red")
        btn_delete.grid(row=0, column=5, padx=2, pady=3)

        return frame

    def create_annual_plan_row(self, plan: Dict[str, Any], indent: int) -> ctk.CTkFrame:
        """Create a row for an Annual Plan."""
        node_id = f"annual_plan-{plan['id']}"
        is_expanded = node_id in self.expanded_nodes

        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid_columnconfigure(2, weight=1)

        indent_label = ctk.CTkLabel(frame, text="  " * indent + "└─", font=ctk.CTkFont(family="Courier"))
        indent_label.grid(row=0, column=0, sticky="w")

        btn_expand = ctk.CTkButton(frame, text="▼" if is_expanded else "▶", width=25,
                                   command=lambda: self.toggle_node(node_id))
        btn_expand.grid(row=0, column=1, padx=2, pady=3)

        status_emoji = {"not_started": "⚪", "in_progress": "🔵", "completed": "✅", "at_risk": "🔴"}.get(plan['status'], "⚪")
        label = ctk.CTkLabel(frame, text=f"{status_emoji} Plan: {plan['theme'] or 'Untitled'}",
                            font=ctk.CTkFont(size=12), anchor="w")
        label.grid(row=0, column=2, sticky="w", padx=5, pady=3)

        btn_add = ctk.CTkButton(frame, text="+", width=25, command=lambda: self.add_quarter_initiative(plan['id']))
        btn_add.grid(row=0, column=3, padx=2, pady=3)

        btn_edit = ctk.CTkButton(frame, text="✎", width=25, command=lambda: self.edit_annual_plan(plan['id']))
        btn_edit.grid(row=0, column=4, padx=2, pady=3)

        btn_delete = ctk.CTkButton(frame, text="🗑", width=25, command=lambda: self.delete_annual_plan(plan['id']), fg_color="darkred", hover_color="red")
        btn_delete.grid(row=0, column=5, padx=2, pady=3)

        return frame

    def create_quarter_initiative_row(self, initiative: Dict[str, Any], indent: int) -> ctk.CTkFrame:
        """Create a row for a Quarter Initiative."""
        node_id = f"quarter_initiative-{initiative['id']}"
        is_expanded = node_id in self.expanded_nodes

        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid_columnconfigure(2, weight=1)

        indent_label = ctk.CTkLabel(frame, text="  " * indent + "└─", font=ctk.CTkFont(family="Courier"))
        indent_label.grid(row=0, column=0, sticky="w")

        btn_expand = ctk.CTkButton(frame, text="▼" if is_expanded else "▶", width=25,
                                   command=lambda: self.toggle_node(node_id))
        btn_expand.grid(row=0, column=1, padx=2, pady=3)

        progress = initiative['progress_pct']
        label = ctk.CTkLabel(frame, text=f"📋 Q{initiative['quarter']}: {initiative['title']} ({progress}%)",
                            font=ctk.CTkFont(size=11), anchor="w")
        label.grid(row=0, column=2, sticky="w", padx=5, pady=3)

        btn_add = ctk.CTkButton(frame, text="+", width=25, command=lambda: self.add_month_tactic(initiative['id']))
        btn_add.grid(row=0, column=3, padx=2, pady=3)

        btn_edit = ctk.CTkButton(frame, text="✎", width=25, command=lambda: self.edit_quarter_initiative(initiative['id']))
        btn_edit.grid(row=0, column=4, padx=2, pady=3)

        btn_delete = ctk.CTkButton(frame, text="🗑", width=25, command=lambda: self.delete_quarter_initiative(initiative['id']), fg_color="darkred", hover_color="red")
        btn_delete.grid(row=0, column=5, padx=2, pady=3)

        return frame

    def create_month_tactic_row(self, tactic: Dict[str, Any], indent: int) -> ctk.CTkFrame:
        """Create a row for a Month Tactic."""
        node_id = f"month_tactic-{tactic['id']}"
        is_expanded = node_id in self.expanded_nodes

        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid_columnconfigure(2, weight=1)

        indent_label = ctk.CTkLabel(frame, text="  " * indent + "└─", font=ctk.CTkFont(family="Courier"))
        indent_label.grid(row=0, column=0, sticky="w")

        btn_expand = ctk.CTkButton(frame, text="▼" if is_expanded else "▶", width=25,
                                   command=lambda: self.toggle_node(node_id))
        btn_expand.grid(row=0, column=1, padx=2, pady=3)

        month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month_name = month_names[tactic['month']]
        label = ctk.CTkLabel(frame, text=f"📌 {month_name}: {tactic['priority_focus']} ({tactic['progress_pct']}%)",
                            font=ctk.CTkFont(size=11), anchor="w")
        label.grid(row=0, column=2, sticky="w", padx=5, pady=3)

        btn_add = ctk.CTkButton(frame, text="+", width=25, command=lambda: self.add_week_action(tactic['id']))
        btn_add.grid(row=0, column=3, padx=2, pady=3)

        btn_edit = ctk.CTkButton(frame, text="✎", width=25, command=lambda: self.edit_month_tactic(tactic['id']))
        btn_edit.grid(row=0, column=4, padx=2, pady=3)

        btn_delete = ctk.CTkButton(frame, text="🗑", width=25, command=lambda: self.delete_month_tactic(tactic['id']), fg_color="darkred", hover_color="red")
        btn_delete.grid(row=0, column=5, padx=2, pady=3)

        return frame

    def create_week_action_row(self, action: Dict[str, Any], indent: int) -> ctk.CTkFrame:
        """Create a row for a Week Action."""
        node_id = f"week_action-{action['id']}"
        is_expanded = node_id in self.expanded_nodes

        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid_columnconfigure(2, weight=1)

        indent_label = ctk.CTkLabel(frame, text="  " * indent + "└─", font=ctk.CTkFont(family="Courier"))
        indent_label.grid(row=0, column=0, sticky="w")

        btn_expand = ctk.CTkButton(frame, text="▼" if is_expanded else "▶", width=25,
                                   command=lambda: self.toggle_node(node_id))
        btn_expand.grid(row=0, column=1, padx=2, pady=3)

        label = ctk.CTkLabel(frame, text=f"✅ Week {action['week_start_date']}: {action['title']}",
                            font=ctk.CTkFont(size=10), anchor="w")
        label.grid(row=0, column=2, sticky="w", padx=5, pady=3)

        btn_add = ctk.CTkButton(frame, text="+ Item", width=40, command=lambda: self.add_action_item(action['id']))
        btn_add.grid(row=0, column=3, padx=2, pady=3)

        btn_edit = ctk.CTkButton(frame, text="✎", width=25, command=lambda: self.edit_week_action(action['id']))
        btn_edit.grid(row=0, column=4, padx=2, pady=3)

        btn_delete = ctk.CTkButton(frame, text="🗑", width=25, command=lambda: self.delete_week_action(action['id']), fg_color="darkred", hover_color="red")
        btn_delete.grid(row=0, column=5, padx=2, pady=3)

        return frame

    def create_action_item_row(self, item: Dict[str, Any], indent: int) -> ctk.CTkFrame:
        """Create a row for an Action Item."""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid_columnconfigure(1, weight=1)

        indent_label = ctk.CTkLabel(frame, text="  " * indent + "└─", font=ctk.CTkFont(family="Courier"))
        indent_label.grid(row=0, column=0, sticky="w")

        status_icon = "✅" if item['status'] == 'completed' else "☐"
        habit_icon = "🔁" if item.get('is_habit') else ""
        percent = f" ({item.get('percent_complete', 0)}%)" if item.get('is_habit') else ""

        label = ctk.CTkLabel(frame, text=f"{status_icon} {habit_icon} {item['title']}{percent}",
                            font=ctk.CTkFont(size=10), anchor="w")
        label.grid(row=0, column=1, sticky="w", padx=5, pady=3)

        btn_edit = ctk.CTkButton(frame, text="✎", width=25, command=lambda: self.edit_action_item(item['id']))
        btn_edit.grid(row=0, column=2, padx=2, pady=3)

        return frame

    # ========================================================================
    # TREE NAVIGATION
    # ========================================================================

    def toggle_node(self, node_id: str):
        """Toggle expand/collapse state of a node."""
        if node_id in self.expanded_nodes:
            self.expanded_nodes.remove(node_id)
        else:
            self.expanded_nodes.add(node_id)
        self.refresh()

    def expand_all(self):
        """Expand all nodes."""
        # Get all segments
        segments = self.vps_manager.get_all_segments()
        for segment in segments:
            self.expanded_nodes.add(f"segment-{segment['id']}")
            # Expand TL Visions
            tl_visions = self.vps_manager.get_tl_visions(segment_id=segment['id'])
            for vision in tl_visions:
                self.expanded_nodes.add(f"tl_vision-{vision['id']}")
                # Could continue expanding all levels, but this gets expensive
        self.refresh()

    def collapse_all(self):
        """Collapse all nodes."""
        self.expanded_nodes.clear()
        self.refresh()

    # ========================================================================
    # CRUD ACTIONS (Placeholder methods - to be implemented with dialogs)
    # ========================================================================

    def create_new_tl_vision(self):
        """Create a new TL Vision."""
        # Get all segments
        segments = self.vps_manager.get_all_segments()

        if not segments:
            # No segments available
            from tkinter import messagebox
            messagebox.showinfo(
                "No Segments",
                "Please create a life segment first before adding visions."
            )
            return

        # If only one segment, use it automatically
        if len(segments) == 1:
            segment_id = segments[0]['id']
            from .vps_editors import TLVisionEditorDialog
            dialog = TLVisionEditorDialog(self, self.vps_manager, segment_id)
            self.wait_window(dialog)
            self.refresh()
            return

        # Multiple segments - show selection dialog
        self.show_segment_selector_dialog(segments)

    def show_segment_selector_dialog(self, segments: List[Dict[str, Any]]):
        """Show a dialog to select which segment to create a vision for."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Life Segment")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()

        # Title
        title_label = ctk.CTkLabel(
            dialog,
            text="Select a Life Segment for your Vision",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title_label.pack(pady=20, padx=20)

        # Create button for each segment
        for segment in segments:
            btn = ctk.CTkButton(
                dialog,
                text=f"🎯 {segment['name']}",
                fg_color=segment['color_hex'],
                command=lambda s=segment['id']: self.on_segment_selected(dialog, s),
                height=40
            )
            btn.pack(pady=5, padx=20, fill="x")

        # Cancel button
        cancel_btn = ctk.CTkButton(
            dialog,
            text="Cancel",
            command=dialog.destroy,
            fg_color="gray"
        )
        cancel_btn.pack(pady=20)

    def on_segment_selected(self, dialog, segment_id: str):
        """Handle segment selection and open TL Vision editor."""
        dialog.destroy()
        from .vps_editors import TLVisionEditorDialog
        editor = TLVisionEditorDialog(self, self.vps_manager, segment_id)
        self.wait_window(editor)
        self.refresh()

    def add_tl_vision(self, segment_id: str):
        """Add a TL Vision to a segment."""
        from .vps_editors import TLVisionEditorDialog
        dialog = TLVisionEditorDialog(self, self.vps_manager, segment_id)
        self.wait_window(dialog)
        self.refresh()

    def add_annual_vision(self, tl_vision_id: str):
        """Add an Annual Vision to a TL Vision."""
        from .vps_editors import AnnualVisionEditorDialog
        tl_vision = self.vps_manager.get_tl_vision(tl_vision_id)
        if tl_vision:
            dialog = AnnualVisionEditorDialog(
                self, self.vps_manager, tl_vision_id, tl_vision['segment_description_id']
            )
            self.wait_window(dialog)
            self.refresh()

    def add_annual_plan(self, annual_vision_id: str):
        """Add an Annual Plan to an Annual Vision."""
        from .vps_editors import AnnualPlanEditorDialog
        annual_vision = self.vps_manager.get_annual_vision(annual_vision_id)
        if annual_vision:
            dialog = AnnualPlanEditorDialog(
                self, self.vps_manager, annual_vision_id, annual_vision['segment_description_id']
            )
            self.wait_window(dialog)
            self.refresh()

    def add_quarter_initiative(self, annual_plan_id: str):
        """Add a Quarter Initiative to an Annual Plan."""
        from .vps_editors import QuarterInitiativeEditorDialog
        plan = self.vps_manager.get_annual_plan(annual_plan_id)
        if plan:
            dialog = QuarterInitiativeEditorDialog(
                self, self.vps_manager, annual_plan_id, plan['segment_description_id']
            )
            self.wait_window(dialog)
            self.refresh()

    def add_month_tactic(self, quarter_initiative_id: str):
        """Add a Month Tactic to a Quarter Initiative."""
        from .vps_editors import MonthTacticEditorDialog
        initiative = self.vps_manager.get_quarter_initiative(quarter_initiative_id)
        if initiative:
            dialog = MonthTacticEditorDialog(
                self, self.vps_manager, quarter_initiative_id, initiative['segment_description_id']
            )
            self.wait_window(dialog)
            self.refresh()

    def add_week_action(self, month_tactic_id: str):
        """Add a Week Action to a Month Tactic."""
        from .vps_editors import WeekActionEditorDialog
        tactic = self.vps_manager.get_month_tactic(month_tactic_id)
        if tactic:
            dialog = WeekActionEditorDialog(
                self, self.vps_manager, month_tactic_id, tactic['segment_description_id']
            )
            self.wait_window(dialog)
            self.refresh()

    def add_action_item(self, week_action_id: str):
        """Add an Action Item to a Week Action."""
        from .vps_editors import ActionItemEditorDialog
        week_action = self.vps_manager.get_week_action(week_action_id)
        if week_action:
            dialog = ActionItemEditorDialog(
                self, self.vps_manager, week_action_id, week_action['segment_description_id']
            )
            self.wait_window(dialog)
            self.refresh()

    def edit_tl_vision(self, vision_id: str):
        """Edit a TL Vision."""
        from .vps_editors import TLVisionEditorDialog
        vision = self.vps_manager.get_tl_vision(vision_id)
        if vision:
            dialog = TLVisionEditorDialog(self, self.vps_manager, vision['segment_description_id'], vision_id)
            self.wait_window(dialog)
            self.refresh()

    def edit_annual_vision(self, vision_id: str):
        """Edit an Annual Vision."""
        from .vps_editors import AnnualVisionEditorDialog
        vision = self.vps_manager.get_annual_vision(vision_id)
        if vision:
            dialog = AnnualVisionEditorDialog(
                self, self.vps_manager, vision['tl_vision_id'],
                vision['segment_description_id'], vision_id
            )
            self.wait_window(dialog)
            self.refresh()

    def edit_annual_plan(self, plan_id: str):
        """Edit an Annual Plan."""
        from .vps_editors import AnnualPlanEditorDialog
        plan = self.vps_manager.get_annual_plan(plan_id)
        if plan:
            dialog = AnnualPlanEditorDialog(
                self, self.vps_manager, plan['annual_vision_id'],
                plan['segment_description_id'], plan_id
            )
            self.wait_window(dialog)
            self.refresh()

    def edit_quarter_initiative(self, initiative_id: str):
        """Edit a Quarter Initiative."""
        from .vps_editors import QuarterInitiativeEditorDialog
        initiative = self.vps_manager.get_quarter_initiative(initiative_id)
        if initiative:
            dialog = QuarterInitiativeEditorDialog(
                self, self.vps_manager, initiative['annual_plan_id'],
                initiative['segment_description_id'], initiative_id
            )
            self.wait_window(dialog)
            self.refresh()

    def edit_month_tactic(self, tactic_id: str):
        """Edit a Month Tactic."""
        from .vps_editors import MonthTacticEditorDialog
        tactic = self.vps_manager.get_month_tactic(tactic_id)
        if tactic:
            dialog = MonthTacticEditorDialog(
                self, self.vps_manager, tactic['quarter_initiative_id'],
                tactic['segment_description_id'], tactic_id
            )
            self.wait_window(dialog)
            self.refresh()

    def edit_week_action(self, action_id: str):
        """Edit a Week Action."""
        from .vps_editors import WeekActionEditorDialog
        action = self.vps_manager.get_week_action(action_id)
        if action:
            dialog = WeekActionEditorDialog(
                self, self.vps_manager, action['month_tactic_id'],
                action['segment_description_id'], action_id
            )
            self.wait_window(dialog)
            self.refresh()

    def edit_action_item(self, item_id: str):
        """Edit an Action Item."""
        from .vps_editors import ActionItemEditorDialog
        item = self.vps_manager.get_action_item(item_id)
        if item:
            dialog = ActionItemEditorDialog(
                self, self.vps_manager, item['week_action_id'],
                item['segment_description_id'], item_id
            )
            self.wait_window(dialog)
            self.refresh()

    # ========================================================================
    # DELETE METHODS
    # ========================================================================

    def _confirm_delete(self, entity_type: str, entity_name: str) -> bool:
        """Show confirmation dialog for deletion."""
        from tkinter import messagebox
        return messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete this {entity_type}?\n\n{entity_name}\n\nThis action cannot be undone.",
            icon='warning'
        )

    def _show_error_has_children(self, entity_type: str):
        """Show error message when deletion fails due to child records."""
        from tkinter import messagebox
        messagebox.showerror(
            "Cannot Delete",
            f"Cannot delete this {entity_type} because it has child records.\n\nPlease delete all child records first."
        )

    def delete_tl_vision(self, vision_id: str):
        """Delete a TL Vision."""
        vision = self.vps_manager.get_tl_vision(vision_id)
        if vision:
            if self._confirm_delete("TL Vision", vision['title']):
                result = self.vps_manager.delete_tl_vision(vision_id)
                if result:
                    self.refresh()
                else:
                    self._show_error_has_children("TL Vision")

    def delete_annual_vision(self, vision_id: str):
        """Delete an Annual Vision."""
        vision = self.vps_manager.get_annual_vision(vision_id)
        if vision:
            if self._confirm_delete("Annual Vision", vision['title']):
                result = self.vps_manager.delete_annual_vision(vision_id)
                if result:
                    self.refresh()
                else:
                    self._show_error_has_children("Annual Vision")

    def delete_annual_plan(self, plan_id: str):
        """Delete an Annual Plan."""
        plan = self.vps_manager.get_annual_plan(plan_id)
        if plan:
            if self._confirm_delete("Annual Plan", plan['theme']):
                result = self.vps_manager.delete_annual_plan(plan_id)
                if result:
                    self.refresh()
                else:
                    self._show_error_has_children("Annual Plan")

    def delete_quarter_initiative(self, initiative_id: str):
        """Delete a Quarter Initiative."""
        initiative = self.vps_manager.get_quarter_initiative(initiative_id)
        if initiative:
            if self._confirm_delete("Quarter Initiative", initiative['title']):
                result = self.vps_manager.delete_quarter_initiative(initiative_id)
                if result:
                    self.refresh()
                else:
                    self._show_error_has_children("Quarter Initiative")

    def delete_month_tactic(self, tactic_id: str):
        """Delete a Month Tactic."""
        tactic = self.vps_manager.get_month_tactic(tactic_id)
        if tactic:
            if self._confirm_delete("Month Tactic", tactic['priority_focus']):
                result = self.vps_manager.delete_month_tactic(tactic_id)
                if result:
                    self.refresh()
                else:
                    self._show_error_has_children("Month Tactic")

    def delete_week_action(self, action_id: str):
        """Delete a Week Action."""
        action = self.vps_manager.get_week_action(action_id)
        if action:
            if self._confirm_delete("Week Action", action['title']):
                result = self.vps_manager.delete_week_action(action_id)
                if result:
                    self.refresh()
                else:
                    self._show_error_has_children("Week Action")
