"""
Vision Planning Screen - unified workspace for vision elements, annual segments,
APE planning, and APE weekly execution.
"""

import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from typing import Optional, TYPE_CHECKING, List, Dict, Any

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class VisionSegmentEditorDialog(ctk.CTkToplevel):
    """Dialog for creating / editing a Vision Segment (Segment + SubSegment + Category)."""

    def __init__(self, parent, vps_manager: 'VPSManager',
                 vision_segment: Optional[dict] = None):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.vision_segment = vision_segment
        self.result = None

        title = "Edit Vision Segment" if vision_segment else "New Vision Segment"
        self.title(title)
        self.geometry("480x320")
        self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_form()
        if vision_segment:
            self._load_data()

        self.transient(parent)

    def _build_form(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        frame.grid_columnconfigure(1, weight=1)

        # Segment dropdown
        ctk.CTkLabel(frame, text="Segment *", anchor="w").grid(
            row=0, column=0, sticky="w", padx=5, pady=5)
        segments = self.vps_manager.get_all_segments(active_only=True)
        self._segments = segments
        seg_names = [s['name'] for s in segments]
        self.segment_var = ctk.StringVar(
            value=seg_names[0] if seg_names else "")
        self.segment_menu = ctk.CTkOptionMenu(
            frame, variable=self.segment_var,
            values=seg_names if seg_names else ["(no segments)"])
        self.segment_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # SubSegment
        ctk.CTkLabel(frame, text="SubSegment *", anchor="w").grid(
            row=1, column=0, sticky="w", padx=5, pady=5)
        self.subsegment_entry = ctk.CTkEntry(frame)
        self.subsegment_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        # Category
        ctk.CTkLabel(frame, text="Category *", anchor="w").grid(
            row=2, column=0, sticky="w", padx=5, pady=5)
        self.category_entry = ctk.CTkEntry(frame)
        self.category_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        # Order index
        ctk.CTkLabel(frame, text="Order", anchor="w").grid(
            row=3, column=0, sticky="w", padx=5, pady=5)
        self.order_entry = ctk.CTkEntry(frame, width=80)
        self.order_entry.insert(0, "0")
        self.order_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ctk.CTkButton(btn_frame, text="Save", command=self._save,
                      fg_color="green", width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy,
                      fg_color="gray", width=120).pack(side="left", padx=5)

    def _load_data(self):
        vs = self.vision_segment
        # Set segment dropdown
        seg_name = vs.get('segment_name', '')
        names = [s['name'] for s in self._segments]
        if seg_name in names:
            self.segment_var.set(seg_name)
        # SubSegment / Category
        self.subsegment_entry.insert(0, vs.get('subsegment', ''))
        self.category_entry.insert(0, vs.get('category', ''))
        self.order_entry.delete(0, 'end')
        self.order_entry.insert(0, str(vs.get('order_index', 0)))

    def _save(self):
        subsegment = self.subsegment_entry.get().strip()
        category = self.category_entry.get().strip()
        if not subsegment or not category:
            show_toast(self, "SubSegment and Category are required.", "error")
            return

        seg_name = self.segment_var.get()
        seg = next((s for s in self._segments if s['name'] == seg_name), None)
        if seg is None:
            show_toast(self, "Please select a valid Segment.", "error")
            return

        try:
            order = int(self.order_entry.get().strip() or "0")
        except ValueError:
            order = 0

        try:
            if self.vision_segment:
                self.vps_manager.update_vision_segment(
                    self.vision_segment['id'],
                    segment_id=seg['id'],
                    subsegment=subsegment,
                    category=category,
                    order_index=order
                )
            else:
                self.vps_manager.create_vision_segment(
                    segment_id=seg['id'],
                    subsegment=subsegment,
                    category=category,
                    order_index=order
                )
            self.result = True
            self.destroy()
        except Exception as e:
            show_toast(self, f"Failed to save: {e}", "error")


class VisionPlanningScreen(ctk.CTkFrame):
    """Unified Vision Planning workspace with tabbed interface."""

    def __init__(self, parent, vps_manager: 'VPSManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_tabs()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        ctk.CTkLabel(
            header, text="Vision Planning",
            font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(8, 0))
        ctk.CTkLabel(
            header,
            text="Unified workspace for vision elements, annual segments, "
                 "APE planning, and APE weekly execution",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).grid(row=1, column=0, sticky="w", padx=15, pady=(0, 8))

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        tab_vs = self.tabview.add("Vision Elements")
        tab_avs = self.tabview.add("Annual Vision Segments")
        tab_ape_a = self.tabview.add("APE Assignment")
        tab_ape_p = self.tabview.add("APE Period View")
        tab_ape_w = self.tabview.add("APE Weekly")

        tab_vs.grid_columnconfigure(0, weight=1)
        tab_vs.grid_rowconfigure(0, weight=1)
        tab_avs.grid_columnconfigure(0, weight=1)
        tab_avs.grid_rowconfigure(0, weight=1)

        self._build_vision_segments_tab(tab_vs)
        self._build_annual_vision_segments_tab(tab_avs)
        self._build_placeholder_tab(tab_ape_a, "APE Assignment")
        self._build_placeholder_tab(tab_ape_p, "APE Period View")
        self._build_placeholder_tab(tab_ape_w, "APE Weekly")

        # Reload left panel whenever Annual Vision Segments tab is focused
        self.tabview.configure(command=self._on_tab_changed)

    def _on_tab_changed(self):
        """Refresh Annual Vision Segments left panel when its tab is selected."""
        if self.tabview.get() == "Annual Vision Segments":
            self._load_all_vision_elements()

    # ------------------------------------------------------------------
    # Vision Elements tab
    # ------------------------------------------------------------------

    def _build_vision_segments_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(parent)
        toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        ctk.CTkLabel(
            toolbar, text="Vision Elements",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(side="left", padx=10, pady=8)
        ctk.CTkButton(
            toolbar, text="+ Add", width=80,
            command=self._add_vision_segment
        ).pack(side="right", padx=10, pady=8)
        ctk.CTkButton(
            toolbar, text="Refresh", width=80, fg_color="gray",
            command=self._refresh_vision_segments_tab
        ).pack(side="right", padx=5, pady=8)

        # Scrollable list
        self.vs_scroll = ctk.CTkScrollableFrame(parent)
        self.vs_scroll.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.vs_scroll.grid_columnconfigure(0, weight=1)

        self._refresh_vision_segments_tab()

    def _refresh_vision_segments_tab(self):
        """Reload and display all vision segments."""
        for w in self.vs_scroll.winfo_children():
            w.destroy()

        items = self.vps_manager.get_vision_segments()

        if not items:
            ctk.CTkLabel(
                self.vs_scroll,
                text="No vision segments yet. Click '+ Add' to create one.",
                text_color="gray"
            ).grid(row=0, column=0, padx=20, pady=20)
            return

        # Column headers
        hdr = ctk.CTkFrame(self.vs_scroll)
        hdr.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        hdr.grid_columnconfigure(1, weight=1)
        hdr.grid_columnconfigure(2, weight=1)
        hdr.grid_columnconfigure(3, weight=1)
        for col, label in enumerate(["#", "Segment", "SubSegment", "Category"], start=0):
            anchor = "center" if col == 0 else "w"
            ctk.CTkLabel(
                hdr, text=label,
                font=ctk.CTkFont(weight="bold"), anchor=anchor
            ).grid(row=0, column=col, sticky="ew", padx=8, pady=4)

        for idx, item in enumerate(items, start=1):
            self._create_vs_row(idx, item)

    def _create_vs_row(self, row_num: int, item: dict):
        row_frame = ctk.CTkFrame(self.vs_scroll)
        row_frame.grid(row=row_num, column=0, sticky="ew", padx=5, pady=2)
        row_frame.grid_columnconfigure(1, weight=1)
        row_frame.grid_columnconfigure(2, weight=1)
        row_frame.grid_columnconfigure(3, weight=1)

        # Row number
        ctk.CTkLabel(row_frame, text=str(row_num), width=30,
                     anchor="center").grid(row=0, column=0, padx=5, pady=4)

        color = item.get('segment_color') or "#888888"
        # Segment badge
        seg_btn = ctk.CTkButton(
            row_frame, text=item.get('segment_name', ''),
            fg_color=color, hover_color=color,
            text_color="white", width=130, height=28, corner_radius=6,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        seg_btn.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        # SubSegment badge
        subseg_btn = ctk.CTkButton(
            row_frame, text=item.get('subsegment', ''),
            fg_color=color, hover_color=color,
            text_color="white", width=130, height=28, corner_radius=6,
            font=ctk.CTkFont(size=12)
        )
        subseg_btn.grid(row=0, column=2, sticky="w", padx=8, pady=4)

        # Category badge
        cat_btn = ctk.CTkButton(
            row_frame, text=item.get('category', ''),
            fg_color=color, hover_color=color,
            text_color="white", width=130, height=28, corner_radius=6,
            font=ctk.CTkFont(size=12)
        )
        cat_btn.grid(row=0, column=3, sticky="w", padx=8, pady=4)

        # Edit / Delete
        ctk.CTkButton(
            row_frame, text="Edit", width=60,
            command=lambda i=item: self._edit_vision_segment(i)
        ).grid(row=0, column=4, padx=5, pady=4)
        ctk.CTkButton(
            row_frame, text="Del", width=50,
            fg_color="darkred", hover_color="red",
            command=lambda i=item: self._delete_vision_segment(i)
        ).grid(row=0, column=5, padx=(0, 5), pady=4)

    def _add_vision_segment(self):
        dlg = VisionSegmentEditorDialog(self, self.vps_manager)
        self.wait_window(dlg)
        if dlg.result:
            self._refresh_vision_segments_tab()
            # Also keep annual tab in sync if it was ever loaded
            if hasattr(self, '_avs_elements_scroll'):
                self._load_all_vision_elements()

    def _edit_vision_segment(self, item: dict):
        dlg = VisionSegmentEditorDialog(self, self.vps_manager, vision_segment=item)
        self.wait_window(dlg)
        if dlg.result:
            self._refresh_vision_segments_tab()
            if hasattr(self, '_avs_elements_scroll'):
                self._load_all_vision_elements()

    def _delete_vision_segment(self, item: dict):
        if messagebox.askyesno(
            "Confirm Delete",
            f"Delete '{item['subsegment']} / {item['category']}'?\n"
            "This will also remove it from all annual assignments.",
            parent=self
        ):
            self.vps_manager.delete_vision_segment(item['id'])
            self._refresh_vision_segments_tab()
            if hasattr(self, '_avs_elements_scroll'):
                self._load_all_vision_elements()

    # ------------------------------------------------------------------
    # Annual Vision Segments tab
    # ------------------------------------------------------------------

    def _build_annual_vision_segments_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # Top controls
        ctrl = ctk.CTkFrame(parent)
        ctrl.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))

        ctk.CTkLabel(
            ctrl, text="Annual Vision Segments",
            font=ctk.CTkFont(size=15, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=8)

        ctk.CTkLabel(ctrl, text="Year:").grid(row=0, column=1, padx=(20, 5), pady=8)
        self._avs_year_var = ctk.StringVar(value=str(datetime.now().year))
        year_entry = ctk.CTkEntry(ctrl, textvariable=self._avs_year_var, width=70)
        year_entry.grid(row=0, column=2, pady=8)

        ctk.CTkButton(
            ctrl, text="Load Year", width=90,
            command=self._avs_load_year
        ).grid(row=0, column=3, padx=10, pady=8)

        ctk.CTkButton(
            ctrl, text="Save", width=70, fg_color="green",
            command=self._avs_save
        ).grid(row=0, column=4, padx=5, pady=8)

        ctk.CTkButton(
            ctrl, text="Refresh", width=80, fg_color="gray",
            command=self._avs_refresh_both
        ).grid(row=0, column=5, padx=5, pady=8)

        # Two-panel body
        body = ctk.CTkFrame(parent)
        body.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)  # separator
        body.grid_columnconfigure(2, weight=1)
        body.grid_rowconfigure(1, weight=1)

        # Left panel header
        ctk.CTkLabel(
            body,
            text="Vision Elements (check elements to add to the year and hit save)",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))

        # Right panel header (dynamic label)
        self._avs_right_label_var = ctk.StringVar(
            value=f"Annual Vision Elements for the year {self._avs_year_var.get()}")
        ctk.CTkLabel(
            body, textvariable=self._avs_right_label_var,
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=2, sticky="w", padx=10, pady=(8, 0))

        # Vertical separator
        sep = ctk.CTkFrame(body, width=2, fg_color="gray")
        sep.grid(row=0, column=1, rowspan=2, sticky="ns", padx=5, pady=5)

        # Left scrollable
        self._avs_elements_scroll = ctk.CTkScrollableFrame(body)
        self._avs_elements_scroll.grid(
            row=1, column=0, sticky="nsew", padx=(5, 0), pady=5)
        self._avs_elements_scroll.grid_columnconfigure(0, weight=1)

        # Right scrollable
        self._avs_annual_scroll = ctk.CTkScrollableFrame(body)
        self._avs_annual_scroll.grid(
            row=1, column=2, sticky="nsew", padx=(0, 5), pady=5)
        self._avs_annual_scroll.grid_columnconfigure(0, weight=1)

        # Track checkboxes: vs_id → BooleanVar
        self._avs_checkboxes: Dict[str, ctk.BooleanVar] = {}

        # Initial load
        self._load_all_vision_elements()
        self._load_annual_vision_elements()

    def _avs_load_year(self):
        """Load a new year's assignments."""
        self._avs_right_label_var.set(
            f"Annual Vision Elements for the year {self._avs_year_var.get()}")
        self._load_all_vision_elements()
        self._load_annual_vision_elements()

    def _avs_refresh_both(self):
        """Reload both panels from the database."""
        self._load_all_vision_elements()
        self._load_annual_vision_elements()

    def _load_all_vision_elements(self):
        """
        Reload the LEFT panel (all vision segments) from the database.

        This is called:
        - On initial build
        - When the Annual Vision Segments tab is selected
        - After any CRUD operation on Vision Segments
        - When Refresh or Load Year is pressed
        """
        for w in self._avs_elements_scroll.winfo_children():
            w.destroy()
        self._avs_checkboxes.clear()

        items = self.vps_manager.get_vision_segments()  # always fresh from DB

        if not items:
            ctk.CTkLabel(
                self._avs_elements_scroll,
                text="No vision segments defined.\nCreate some on the Vision Segments tab.",
                text_color="gray"
            ).grid(row=0, column=0, padx=20, pady=20)
            return

        # Get already-assigned IDs for the current year
        try:
            year = int(self._avs_year_var.get())
        except ValueError:
            year = datetime.now().year

        assigned_ids = set(self.vps_manager.get_annual_vision_segment_ids(year))

        # Column headers
        self._avs_col_headers(self._avs_elements_scroll, show_checkbox=True)

        for idx, item in enumerate(items, start=1):
            var = ctk.BooleanVar(value=item['id'] in assigned_ids)
            self._avs_checkboxes[item['id']] = var
            self._create_avs_left_row(idx, item, var)

    def _load_annual_vision_elements(self):
        """Reload the RIGHT panel (annual assignments for the selected year)."""
        for w in self._avs_annual_scroll.winfo_children():
            w.destroy()

        try:
            year = int(self._avs_year_var.get())
        except ValueError:
            year = datetime.now().year

        items = self.vps_manager.get_annual_vision_segments(year)

        if not items:
            ctk.CTkLabel(
                self._avs_annual_scroll,
                text=f"No elements saved for {year} yet.\n"
                     "Check items on the left and click Save.",
                text_color="gray"
            ).grid(row=0, column=0, padx=20, pady=20)
            return

        self._avs_col_headers(self._avs_annual_scroll, show_checkbox=False)

        for idx, item in enumerate(items, start=1):
            self._create_avs_right_row(idx, item, year)

    def _avs_col_headers(self, parent, show_checkbox: bool):
        hdr = ctk.CTkFrame(parent)
        hdr.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        col_offset = 1 if show_checkbox else 0
        hdr.grid_columnconfigure(col_offset + 1, weight=1)
        hdr.grid_columnconfigure(col_offset + 2, weight=1)
        hdr.grid_columnconfigure(col_offset + 3, weight=1)

        if show_checkbox:
            ctk.CTkLabel(hdr, text="", width=28).grid(row=0, column=0, padx=2)

        for col, label in enumerate(["#", "Segment", "SubSegment", "Category"],
                                     start=col_offset):
            anchor = "center" if label == "#" else "w"
            ctk.CTkLabel(
                hdr, text=label,
                font=ctk.CTkFont(weight="bold"), anchor=anchor
            ).grid(row=0, column=col, sticky="ew", padx=8, pady=4)

    def _create_avs_left_row(self, row_num: int, item: dict, var: ctk.BooleanVar):
        row_frame = ctk.CTkFrame(self._avs_elements_scroll)
        row_frame.grid(row=row_num, column=0, sticky="ew", padx=5, pady=2)
        row_frame.grid_columnconfigure(2, weight=1)
        row_frame.grid_columnconfigure(3, weight=1)
        row_frame.grid_columnconfigure(4, weight=1)

        # Checkbox
        cb = ctk.CTkCheckBox(row_frame, text="", variable=var, width=28)
        cb.grid(row=0, column=0, padx=(5, 0), pady=4)

        ctk.CTkLabel(row_frame, text=str(row_num), width=30,
                     anchor="center").grid(row=0, column=1, padx=5, pady=4)

        color = item.get('segment_color') or "#888888"
        for col, key in zip([2, 3, 4], ['segment_name', 'subsegment', 'category']):
            ctk.CTkButton(
                row_frame, text=item.get(key, ''),
                fg_color=color, hover_color=color,
                text_color="white", width=120, height=28, corner_radius=6,
                font=ctk.CTkFont(size=12)
            ).grid(row=0, column=col, sticky="w", padx=8, pady=4)

    def _create_avs_right_row(self, row_num: int, item: dict, year: int):
        row_frame = ctk.CTkFrame(self._avs_annual_scroll)
        row_frame.grid(row=row_num, column=0, sticky="ew", padx=5, pady=2)
        row_frame.grid_columnconfigure(1, weight=1)
        row_frame.grid_columnconfigure(2, weight=1)
        row_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(row_frame, text=str(row_num), width=30,
                     anchor="center").grid(row=0, column=0, padx=5, pady=4)

        color = item.get('segment_color') or "#888888"
        for col, key in zip([1, 2, 3], ['segment_name', 'subsegment', 'category']):
            ctk.CTkButton(
                row_frame, text=item.get(key, ''),
                fg_color=color, hover_color=color,
                text_color="white", width=120, height=28, corner_radius=6,
                font=ctk.CTkFont(size=12)
            ).grid(row=0, column=col, sticky="w", padx=8, pady=4)

        ctk.CTkButton(
            row_frame, text="Edit", width=55,
            command=lambda i=item: self._avs_edit_item(i)
        ).grid(row=0, column=4, padx=5, pady=4)

        ctk.CTkButton(
            row_frame, text="Del", width=45,
            fg_color="darkred", hover_color="red",
            command=lambda i=item, y=year: self._avs_delete_item(i, y)
        ).grid(row=0, column=5, padx=(0, 5), pady=4)

    def _avs_save(self):
        """Save the checked vision elements as the annual assignments for the year."""
        try:
            year = int(self._avs_year_var.get())
        except ValueError:
            show_toast(self, "Invalid year.", "error")
            return

        selected_ids = [
            vs_id for vs_id, var in self._avs_checkboxes.items() if var.get()
        ]
        self.vps_manager.save_annual_vision_segments(year, selected_ids)
        self._load_annual_vision_elements()

    def _avs_edit_item(self, item: dict):
        """Edit the underlying vision segment from the annual view."""
        vs = self.vps_manager.get_vision_segment(item['id'])
        if not vs:
            return
        dlg = VisionSegmentEditorDialog(self, self.vps_manager, vision_segment=vs)
        self.wait_window(dlg)
        if dlg.result:
            self._refresh_vision_segments_tab()
            self._avs_refresh_both()

    def _avs_delete_item(self, item: dict, year: int):
        """Remove a vision segment from the annual assignments (not from master list)."""
        if messagebox.askyesno(
            "Confirm Remove",
            f"Remove '{item['subsegment']} / {item['category']}' from year {year}?\n"
            "(The segment remains in the master Vision Segments list.)",
            parent=self
        ):
            self.vps_manager.delete_annual_vision_segment_item(item['id'], year)
            self._load_all_vision_elements()
            self._load_annual_vision_elements()

    # ------------------------------------------------------------------
    # Placeholder tabs
    # ------------------------------------------------------------------

    def _build_placeholder_tab(self, parent, name: str):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        ctk.CTkLabel(
            parent,
            text=f"{name}\n\n(Coming soon)",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).grid(row=0, column=0, padx=20, pady=40)
