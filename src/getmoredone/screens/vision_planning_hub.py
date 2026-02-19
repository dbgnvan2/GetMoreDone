"""Vision Planning Hub screen with in-screen navigation for planning sub-screens."""

import customtkinter as ctk
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class VisionPlanningHubScreen(ctk.CTkFrame):
    """Single entrypoint for Vision Planning screens."""

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        self.current_screen: Optional[ctk.CTkFrame] = None
        self.nav_buttons = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.create_ui()
        self.open_screen("vision_elements")

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="Vision Planning",
            font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 2))

        ctk.CTkLabel(
            header,
            text="Unified workspace for vision elements, annual segments, APE planning, and APE weekly execution",
            text_color="#94A3B8"
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))

        nav = ctk.CTkFrame(self)
        nav.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        buttons = [
            ("Vision Elements", "vision_elements", "#0E7490", "#0891B2"),
            ("Annual Vision Segments", "annual_vision_segments", "#2563EB", "#1D4ED8"),
            ("APE Assignment", "ape_assignment", "#0D9488", "#0F766E"),
            ("APE Period View", "ape_period_view", "#D97706", "#B45309"),
            ("APE Weekly", "ape_weekly", "#0284C7", "#0369A1"),
        ]

        for i, (label, key, fg, hover) in enumerate(buttons):
            btn = ctk.CTkButton(
                nav,
                text=label,
                command=lambda k=key: self.open_screen(k),
                fg_color=fg,
                hover_color=hover,
                width=170
            )
            btn.grid(row=0, column=i, padx=6, pady=8)
            self.nav_buttons[key] = btn

        self.content = ctk.CTkFrame(self)
        self.content.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def open_screen(self, key: str):
        if self.current_screen:
            self.current_screen.destroy()
            self.current_screen = None

        from .vision_elements import VisionElementsScreen
        from .annual_vision_segments import AnnualVisionSegmentsScreen
        from .ape_assignment import APEAssignmentScreen
        from .ape_period_view import APEPeriodViewScreen
        from .weekly_items import WeeklyItemsScreen

        mapping = {
            "vision_elements": VisionElementsScreen,
            "annual_vision_segments": AnnualVisionSegmentsScreen,
            "ape_assignment": APEAssignmentScreen,
            "ape_period_view": APEPeriodViewScreen,
            "ape_weekly": WeeklyItemsScreen,
        }
        screen_cls = mapping.get(key, VisionElementsScreen)
        self.current_screen = screen_cls(self.content, self.vps_manager, self.app)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(border_width=2, border_color="#E2E8F0")
            else:
                btn.configure(border_width=0)
