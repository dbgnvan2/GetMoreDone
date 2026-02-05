"""
Drag Schedule screen - drag items onto date boxes to reschedule.
"""

import customtkinter as ctk
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

from ..models import ActionItem

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class DragScheduleScreen(ctk.CTkFrame):
    """Screen with drag-and-drop scheduling onto date boxes."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app

        self.drag_label = None
        self.drag_item: Optional[ActionItem] = None
        self.drag_hover_frame = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.create_header()
        self.create_body()
        self.refresh()

    def create_header(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(6, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Drag Schedule",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=10)

        ctk.CTkLabel(header, text="Next").grid(
            row=0, column=1, padx=(20, 5), pady=10)

        self.days_var = ctk.StringVar(value="7")
        self.days_combo = ctk.CTkComboBox(
            header,
            values=["1", "3", "7", "14", "30"],
            variable=self.days_var,
            width=80,
            command=lambda _: self.refresh()
        )
        self.days_combo.grid(row=0, column=2, padx=5, pady=10)

        ctk.CTkLabel(header, text="days").grid(
            row=0, column=3, sticky="w", padx=5, pady=10)

        ctk.CTkLabel(header, text="Who:").grid(
            row=0, column=4, padx=(20, 5), pady=10)

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

        help_text = ctk.CTkLabel(
            header,
            text="Drag a Next Item onto a date box to reschedule",
            text_color="gray70"
        )
        help_text.grid(row=0, column=6, sticky="e", padx=10, pady=10)

    def create_body(self):
        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left: Next Items list
        left_frame = ctk.CTkFrame(body)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left_frame,
            text="Next Items",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        self.items_frame = ctk.CTkScrollableFrame(left_frame, label_text="")
        self.items_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.items_frame.grid_columnconfigure(0, weight=1)

        # Right: Date boxes
        right_frame = ctk.CTkFrame(body)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right_frame,
            text="Date Boxes",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        self.dates_frame = ctk.CTkScrollableFrame(right_frame, label_text="")
        self.dates_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.dates_frame.grid_columnconfigure(0, weight=1)

    def refresh(self):
        for widget in self.items_frame.winfo_children():
            widget.destroy()
        for widget in self.dates_frame.winfo_children():
            widget.destroy()

        self.date_boxes = []

        items = self.load_items()
        if not items:
            ctk.CTkLabel(
                self.items_frame,
                text="No next items",
                font=ctk.CTkFont(size=14)
            ).grid(row=0, column=0, pady=20)
        else:
            row = 0
            for item in items:
                item_row = self.create_item_row(item)
                item_row.grid(row=row, column=0, sticky="ew", pady=4, padx=4)
                row += 1

        self.build_date_boxes()

    def load_items(self):
        n_days = int(self.days_var.get())
        who_filter = None if self.who_var.get() == "All" else self.who_var.get()

        upcoming = self.db_manager.get_upcoming_items(n_days, who_filter)
        all_open = self.db_manager.get_all_items(
            status_filter="open",
            who_filter=who_filter,
            sort_by="priority_score",
            sort_desc=True
        )
        no_date = [item for item in all_open if not item.start_date and not item.due_date]
        no_date_ids = {item.id for item in no_date}

        items = no_date[:]
        for item in upcoming:
            if item.id not in no_date_ids:
                items.append(item)
        return items

    def create_item_row(self, item: ActionItem):
        frame = ctk.CTkFrame(self.items_frame)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)

        date_text = item.start_date or item.due_date or ""

        title_label = ctk.CTkLabel(
            frame,
            text=item.title,
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="ew", padx=10, pady=6)

        date_label = ctk.CTkLabel(
            frame,
            text=date_text,
            text_color="gray70"
        )
        date_label.grid(row=0, column=1, sticky="e", padx=10, pady=6)

        self.bind_drag_handlers(frame, item)
        self.bind_drag_handlers(title_label, item)
        self.bind_drag_handlers(date_label, item)
        return frame

    def build_date_boxes(self):
        n_days = int(self.days_var.get())
        today = datetime.now().date()

        for i in range(n_days):
            day = today + timedelta(days=i)
            date_str = day.strftime("%Y-%m-%d")
            label_text = f"{day.strftime('%a')}\n{day.strftime('%b %d, %Y')}"

            frame = ctk.CTkFrame(self.dates_frame, height=70, fg_color="gray20")
            frame.grid(row=i, column=0, sticky="ew", padx=6, pady=6)
            frame.grid_columnconfigure(0, weight=1)

            label = ctk.CTkLabel(
                frame,
                text=label_text,
                justify="center"
            )
            label.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

            self.date_boxes.append({"frame": frame, "date": date_str})

    def bind_drag_handlers(self, widget, item: ActionItem):
        widget.bind("<ButtonPress-1>", lambda e: self.start_drag(e, item))
        widget.bind("<B1-Motion>", self.on_drag_motion)
        widget.bind("<ButtonRelease-1>", self.on_drag_release)

    def start_drag(self, event, item: ActionItem):
        self.drag_item = item
        if self.drag_label is None:
            self.drag_label = ctk.CTkLabel(
                self,
                text=item.title,
                fg_color="gray30",
                text_color="white",
                corner_radius=6,
                padx=8,
                pady=4
            )
        else:
            self.drag_label.configure(text=item.title)

        self.drag_label.lift()
        self.update_drag_position()

    def on_drag_motion(self, _event):
        if not self.drag_item or not self.drag_label:
            return
        self.update_drag_position()
        self.update_hover_target()

    def on_drag_release(self, _event):
        if not self.drag_item:
            return

        target_date = self.get_drop_target_date()
        self.clear_hover_target()

        if target_date:
            self.db_manager.reschedule_item(
                self.drag_item.id,
                target_date,
                target_date,
                "Drag-and-drop schedule"
            )
            self.refresh()

        if self.drag_label:
            self.drag_label.place_forget()
        self.drag_item = None

    def update_drag_position(self):
        if not self.drag_label:
            return
        x_root = self.winfo_pointerx()
        y_root = self.winfo_pointery()
        x = x_root - self.winfo_rootx() + 10
        y = y_root - self.winfo_rooty() + 10
        self.drag_label.place(x=x, y=y)

    def get_drop_target_date(self) -> Optional[str]:
        x_root = self.winfo_pointerx()
        y_root = self.winfo_pointery()

        for box in self.date_boxes:
            frame = box["frame"]
            if not frame.winfo_ismapped():
                continue
            x1 = frame.winfo_rootx()
            y1 = frame.winfo_rooty()
            x2 = x1 + frame.winfo_width()
            y2 = y1 + frame.winfo_height()
            if x1 <= x_root <= x2 and y1 <= y_root <= y2:
                return box["date"]
        return None

    def update_hover_target(self):
        x_root = self.winfo_pointerx()
        y_root = self.winfo_pointery()
        hovered = None

        for box in self.date_boxes:
            frame = box["frame"]
            if not frame.winfo_ismapped():
                continue
            x1 = frame.winfo_rootx()
            y1 = frame.winfo_rooty()
            x2 = x1 + frame.winfo_width()
            y2 = y1 + frame.winfo_height()
            if x1 <= x_root <= x2 and y1 <= y_root <= y2:
                hovered = frame
                break

        if hovered is self.drag_hover_frame:
            return

        self.clear_hover_target()
        if hovered:
            hovered.configure(fg_color="gray35")
            self.drag_hover_frame = hovered

    def clear_hover_target(self):
        if self.drag_hover_frame:
            self.drag_hover_frame.configure(fg_color="gray20")
            self.drag_hover_frame = None
