"""
Main application window for GetMoreDone.
"""

import customtkinter as ctk
import os
import sys
from datetime import datetime
from typing import Optional

from .db_manager import DatabaseManager
from .paths import app_data_dir_path
from .vps_manager import VPSManager


class GetMoreDoneApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # Configure window
        today = datetime.now()
        day_of_week = today.strftime("%A")
        date_str = today.strftime("%B %d, %Y")
        mode_tag = "[PROD]" if getattr(sys, "frozen", False) else "[DEV]"
        self.title(f"GetMoreDone {mode_tag} - {day_of_week}, {date_str}")
        self.geometry("1200x700")

        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize database
        self.db_manager = DatabaseManager()

        # Initialize VPS manager with shared db_manager
        self.vps_manager = VPSManager(db_manager=self.db_manager)

        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create sidebar
        self.create_sidebar()

        # Create main content area
        self.content_frame = ctk.CTkFrame(self, corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Current screen
        self.current_screen = None

        # Show default screen
        self.show_upcoming()

    def create_sidebar(self):
        """Create navigation sidebar."""
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(18, weight=1)

        # Logo/title
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="GetMoreDone",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Navigation buttons
        self.btn_today = ctk.CTkButton(
            self.sidebar,
            text="Today",
            command=self.show_today,
            fg_color="darkgreen",
            hover_color="green"
        )
        self.btn_today.grid(row=1, column=0, padx=20, pady=10)

        self.btn_upcoming = ctk.CTkButton(
            self.sidebar,
            text="Upcoming",
            command=self.show_upcoming
        )
        self.btn_upcoming.grid(row=2, column=0, padx=20, pady=10)

        self.btn_all_items = ctk.CTkButton(
            self.sidebar,
            text="All Items",
            command=self.show_all_items
        )
        self.btn_all_items.grid(row=3, column=0, padx=20, pady=10)

        self.btn_hierarchical = ctk.CTkButton(
            self.sidebar,
            text="Hierarchical",
            command=self.show_hierarchical
        )
        self.btn_hierarchical.grid(row=4, column=0, padx=20, pady=10)

        self.btn_vps_planning = ctk.CTkButton(
            self.sidebar,
            text="VPS Planning",
            command=self.show_vps_planning,
            fg_color="purple",
            hover_color="mediumpurple"
        )
        self.btn_vps_planning.grid(row=5, column=0, padx=20, pady=10)

        self.btn_vision_planning = ctk.CTkButton(
            self.sidebar,
            text="Vision Planning",
            command=self.show_vision_planning,
            fg_color="#5B2D8E",
            hover_color="#7B4DBE"
        )
        self.btn_vision_planning.grid(row=6, column=0, padx=20, pady=10)

        self.btn_plan = ctk.CTkButton(
            self.sidebar,
            text="Plan",
            command=self.show_plan
        )
        self.btn_plan.grid(row=7, column=0, padx=20, pady=10)

        self.btn_drag_schedule = ctk.CTkButton(
            self.sidebar,
            text="Drag Schedule",
            command=self.show_drag_schedule
        )
        self.btn_drag_schedule.grid(row=8, column=0, padx=20, pady=10)

        self.btn_completed = ctk.CTkButton(
            self.sidebar,
            text="Completed",
            command=self.show_completed
        )
        self.btn_completed.grid(row=9, column=0, padx=20, pady=10)

        self.btn_contacts = ctk.CTkButton(
            self.sidebar,
            text="Contacts",
            command=self.show_contacts
        )
        self.btn_contacts.grid(row=10, column=0, padx=20, pady=10)

        self.btn_defaults = ctk.CTkButton(
            self.sidebar,
            text="Defaults",
            command=self.show_defaults
        )
        self.btn_defaults.grid(row=11, column=0, padx=20, pady=10)

        self.btn_stats = ctk.CTkButton(
            self.sidebar,
            text="Stats",
            command=self.show_stats
        )
        self.btn_stats.grid(row=12, column=0, padx=20, pady=10)

        self.btn_settings = ctk.CTkButton(
            self.sidebar,
            text="Settings",
            command=self.show_settings
        )
        self.btn_settings.grid(row=13, column=0, padx=20, pady=10)

        self.btn_vision_planning_hub = ctk.CTkButton(
            self.sidebar,
            text="Vision Planning",
            command=self.show_vision_planning_hub,
            fg_color="#0E7490",
            hover_color="#0891B2"
        )
        self.btn_vision_planning_hub.grid(row=13, column=0, padx=20, pady=10)

    def clear_content(self):
        """Clear current screen from content area."""
        if self.current_screen:
            self.current_screen.destroy()
            self.current_screen = None

    def show_today(self):
        """Show Today screen."""
        from .screens.today import TodayScreen
        self.clear_content()
        self.current_screen = TodayScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_upcoming(self):
        """Show Upcoming screen."""
        from .screens.upcoming import UpcomingScreen
        self.clear_content()
        self.current_screen = UpcomingScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_all_items(self):
        """Show All Items screen."""
        from .screens.all_items import AllItemsScreen
        self.clear_content()
        self.current_screen = AllItemsScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_hierarchical(self):
        """Show Hierarchical screen."""
        from .screens.hierarchical import HierarchicalScreen
        self.clear_content()
        self.current_screen = HierarchicalScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_vps_planning(self):
        """Show VPS Planning screen."""
        from .screens.vps_planning import VPSPlanningScreen
        self.clear_content()
        self.current_screen = VPSPlanningScreen(self.content_frame, self.vps_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_vision_planning(self):
        """Show Vision Planning screen."""
        from .screens.vision_planning import VisionPlanningScreen
        self.clear_content()
        self.current_screen = VisionPlanningScreen(self.content_frame, self.vps_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_plan(self):
        """Show Plan screen."""
        from .screens.plan import PlanScreen
        self.clear_content()
        self.current_screen = PlanScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_drag_schedule(self):
        """Show Drag Schedule screen."""
        from .screens.drag_schedule import DragScheduleScreen
        self.clear_content()
        self.current_screen = DragScheduleScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_completed(self):
        """Show Completed screen."""
        from .screens.completed import CompletedScreen
        self.clear_content()
        self.current_screen = CompletedScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_contacts(self):
        """Show Contacts management screen."""
        from .screens.manage_contacts import ManageContactsScreen
        self.clear_content()
        self.current_screen = ManageContactsScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_defaults(self):
        """Show Defaults screen."""
        from .screens.defaults import DefaultsScreen
        self.clear_content()
        self.current_screen = DefaultsScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_stats(self):
        """Show Stats screen."""
        from .screens.stats import StatsScreen
        self.clear_content()
        self.current_screen = StatsScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_settings(self):
        """Show Settings screen."""
        try:
            from .screens.settings import SettingsScreen
            self.clear_content()
            self.current_screen = SettingsScreen(self.content_frame, self.db_manager, self)
            self.current_screen.grid(row=0, column=0, sticky="nsew")
        except Exception as e:
            # In packaged apps, import/GUI errors may only go to stderr; show a dialog too.
            import traceback
            from tkinter import messagebox

            traceback.print_exc()
            messagebox.showerror(
                "Settings Error",
                f"Could not open Settings.\n\n{e}\n\nDetails were printed to the console/log.",
            )

    def show_vision_elements(self):
        """Show Vision Elements screen."""
        from .screens.vision_elements import VisionElementsScreen
        self.clear_content()
        self.current_screen = VisionElementsScreen(self.content_frame, self.vps_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_vision_planning_hub(self):
        """Show Vision Planning Hub screen."""
        from .screens.vision_planning_hub import VisionPlanningHubScreen
        self.clear_content()
        self.current_screen = VisionPlanningHubScreen(self.content_frame, self.vps_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_annual_vision_segments(self):
        """Show Annual Vision Segments screen."""
        from .screens.annual_vision_segments import AnnualVisionSegmentsScreen
        self.clear_content()
        self.current_screen = AnnualVisionSegmentsScreen(self.content_frame, self.vps_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_ape_assignment(self):
        """Show APE Assignment screen."""
        from .screens.ape_assignment import APEAssignmentScreen
        self.clear_content()
        self.current_screen = APEAssignmentScreen(self.content_frame, self.vps_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_ape_period_view(self):
        """Show APE Period View screen."""
        from .screens.ape_period_view import APEPeriodViewScreen
        self.clear_content()
        self.current_screen = APEPeriodViewScreen(self.content_frame, self.vps_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_weekly_items(self):
        """Show APE Weekly screen."""
        from .screens.weekly_items import WeeklyItemsScreen
        self.clear_content()
        self.current_screen = WeeklyItemsScreen(self.content_frame, self.vps_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def refresh_current_screen(self):
        """Refresh the current screen (useful after edits)."""
        if hasattr(self.current_screen, 'refresh'):
            self.current_screen.refresh()

    def on_closing(self):
        """Handle window closing."""
        self.db_manager.close()
        self.vps_manager.close()
        self.destroy()


def acquire_single_instance_lock() -> Optional[int]:
    """Acquire app-wide lock; return file descriptor if successful, else None."""
    lock_path = app_data_dir_path() / "app.lock"

    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    except OSError:
        return None

    try:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (ImportError, OSError):
        os.close(fd)
        return None

    try:
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("utf-8"))
    except OSError:
        # Keep lock even if PID write fails
        pass

    return fd


def release_single_instance_lock(lock_fd: Optional[int]):
    """Release app-wide lock file descriptor."""
    if lock_fd is None:
        return

    try:
        import fcntl
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    except (ImportError, OSError):
        pass

    try:
        os.close(lock_fd)
    except OSError:
        pass


def main():
    """Application entry point."""
    lock_fd = acquire_single_instance_lock()
    if lock_fd is None:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        messagebox.showwarning(
            "GetMoreDone Already Running",
            "Another GetMoreDone instance is already open.\n\n"
            "Please close the other app window before launching this one."
        )
        root.destroy()
        return

    app = GetMoreDoneApp()
    app._single_instance_lock_fd = lock_fd
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    try:
        app.mainloop()
    finally:
        release_single_instance_lock(lock_fd)


if __name__ == "__main__":
    main()
