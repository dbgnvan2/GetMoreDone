"""
Stats screen - planned vs actual time statistics.
"""

import customtkinter as ctk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class StatsScreen(ctk.CTkFrame):
    """Screen showing planned vs actual statistics."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Create scrollable frame for stats
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Load stats
        self.refresh()

    def create_header(self):
        """Create header."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        title = ctk.CTkLabel(
            header,
            text="Statistics - Planned vs Actual",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(side="left", padx=10, pady=10)

        btn_refresh = ctk.CTkButton(
            header,
            text="Refresh",
            command=self.refresh
        )
        btn_refresh.pack(side="right", padx=10, pady=10)

    def refresh(self):
        """Refresh statistics."""
        # Clear current content
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get stats
        stats = self.db_manager.get_planned_vs_actual_stats()

        if not stats:
            label = ctk.CTkLabel(
                self.scroll_frame,
                text="No statistics available (no items with planned minutes and work logs)",
                font=ctk.CTkFont(size=14)
            )
            label.grid(row=0, column=0, pady=20)
            return

        # Summary section
        total_planned = sum(s['planned_minutes'] for s in stats)
        total_actual = sum(s['actual_minutes'] for s in stats)
        total_variance = total_actual - total_planned

        summary_frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray25")
        summary_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10), padx=5)
        summary_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            summary_frame,
            text="Summary",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=5)

        summary_text = f"Total Planned: {total_planned}m  |  Total Actual: {total_actual}m  |  Variance: {total_variance:+d}m"
        ctk.CTkLabel(summary_frame, text=summary_text).grid(row=1, column=0, sticky="w", padx=10, pady=5)

        # Accuracy
        if total_planned > 0:
            accuracy = (total_actual / total_planned) * 100
            accuracy_text = f"Accuracy: {accuracy:.1f}% (actual/planned)"
            ctk.CTkLabel(summary_frame, text=accuracy_text).grid(row=2, column=0, sticky="w", padx=10, pady=5)

        # Table header
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray30")
        header_frame.grid(row=1, column=0, sticky="ew", pady=(10, 2), padx=5)
        header_frame.grid_columnconfigure(0, weight=1)

        headers = ["Title", "Who", "Category", "Effort-Cost", "Planned", "Actual", "Variance"]
        for col, header_text in enumerate(headers):
            ctk.CTkLabel(
                header_frame,
                text=header_text,
                font=ctk.CTkFont(weight="bold")
            ).grid(row=0, column=col, padx=5, pady=5, sticky="w")

        # Item rows
        for idx, stat in enumerate(stats, start=2):
            item_frame = ctk.CTkFrame(self.scroll_frame)
            item_frame.grid(row=idx, column=0, sticky="ew", pady=2, padx=5)
            item_frame.grid_columnconfigure(0, weight=1)

            # Title
            ctk.CTkLabel(
                item_frame,
                text=stat['title'][:40],
                anchor="w"
            ).grid(row=0, column=0, sticky="w", padx=5, pady=5)

            # Who
            ctk.CTkLabel(item_frame, text=stat['who'], width=100).grid(row=0, column=1, padx=5, pady=5)

            # Category
            ctk.CTkLabel(item_frame, text=stat['category'] or "-", width=100).grid(row=0, column=2, padx=5, pady=5)

            # Effort-Cost (Size internally)
            ctk.CTkLabel(item_frame, text=stat['size'] or "-", width=60).grid(row=0, column=3, padx=5, pady=5)

            # Planned
            ctk.CTkLabel(item_frame, text=f"{stat['planned_minutes']}m", width=80).grid(row=0, column=4, padx=5, pady=5)

            # Actual
            ctk.CTkLabel(item_frame, text=f"{stat['actual_minutes']}m", width=80).grid(row=0, column=5, padx=5, pady=5)

            # Variance
            variance = stat['variance']
            variance_color = "green" if variance <= 0 else "red"
            ctk.CTkLabel(
                item_frame,
                text=f"{variance:+d}m",
                width=80,
                text_color=variance_color
            ).grid(row=0, column=6, padx=5, pady=5)

        # Insights section
        insights_frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray25")
        insights_frame.grid(row=len(stats)+2, column=0, sticky="ew", pady=(10, 0), padx=5)

        ctk.CTkLabel(
            insights_frame,
            text="Insights",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # Calculate average variance by effort-cost (size)
        by_size = {}
        for stat in stats:
            size = stat['size'] or "Unknown"
            if size not in by_size:
                by_size[size] = {'count': 0, 'total_variance': 0}
            by_size[size]['count'] += 1
            by_size[size]['total_variance'] += stat['variance']

        insights_text = "Average Variance by Effort-Cost:\n"
        for size, data in by_size.items():
            avg_variance = data['total_variance'] / data['count']
            insights_text += f"  {size}: {avg_variance:+.1f}m (across {data['count']} items)\n"

        ctk.CTkLabel(insights_frame, text=insights_text, justify="left").pack(anchor="w", padx=10, pady=(0, 10))
