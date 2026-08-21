"""
Main application window for GetMoreDone.
"""

import customtkinter as ctk
import os
import sys
from datetime import datetime
from typing import Optional

from . import branding
from .app_settings import AppSettings
from .db_manager import DatabaseManager
from .paths import app_data_dir_path
from .screens.project_link_notice import describe_outstanding_multi_links
from .theme import apply_theme_settings, button_style
from .utils.app_icon import set_app_icon
from .vps_manager import VPSManager


class GetMoreDoneApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # Load settings first so startup theme matches persisted preferences.
        self.settings = AppSettings.load()
        apply_theme_settings(self.settings)

        # Configure window
        today = datetime.now()
        day_of_week = today.strftime("%A")
        date_str = today.strftime("%B %d, %Y")
        mode_tag = "[PROD]" if getattr(sys, "frozen", False) else "[DEV]"
        self.title(branding.window_title(mode_tag, day_of_week, date_str))
        self.geometry("1200x700")

        # Show the GMD brand check-mark icon instead of the default Python
        # launcher rocket (macOS Dock + Windows/Linux taskbar). Cosmetic and
        # fully guarded, so it can never block startup.
        set_app_icon(self)

        # Initialize database
        self.db_manager = DatabaseManager()

        # Initialize VSP manager with shared db_manager
        self.vps_manager = VPSManager(db_manager=self.db_manager)

        # Backfill legacy action items so they carry segment ids
        try:
            updated_segments = self.db_manager.backfill_action_item_segments()
            if updated_segments:
                print(f"[VSP] Backfilled segment ids on {updated_segments} action item(s).")
        except Exception as exc:
            print(f"[WARN] Unable to backfill action item segments: {exc}")

        # Normalize obvious legacy title/who formatting.
        try:
            normalized = self.db_manager.normalize_title_who_fields()
            if normalized:
                print(f"[DATA] Normalized title/who fields on {normalized} action item(s).")
        except Exception as exc:
            print(f"[WARN] Unable to normalize title/who fields: {exc}")

        # BP2 — filing an Action Item under a Project is exclusive on every
        # surface now, but rows created before that can still sit on several
        # boards. Report the count; never resolve it here, because resolving
        # means deleting links the user was never asked about (P2). The
        # Projects screen shows the same count, and each item is resolved when
        # it is next re-filed.
        try:
            multi_linked = self.db_manager.get_items_on_multiple_project_boards()
            notice = describe_outstanding_multi_links(len(multi_linked), multi_linked)
            if notice:
                print(f"[DATA] {notice}")
        except Exception as exc:
            print(f"[WARN] Unable to count multi-project action items: {exc}")

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

    def apply_theme_preferences(self):
        """Apply the active settings theme and refresh visible UI."""
        apply_theme_settings(self.settings)
        self._apply_sidebar_button_styles()
        self._rebuild_active_screen()

    def _rebuild_active_screen(self):
        """Recreate active screen so new theme colors apply immediately."""
        active_name = getattr(self, "active_nav_button", None)
        if not active_name:
            return
        show_methods = {
            "today": self.show_today,
            "upcoming": self.show_upcoming,
            "all_items": self.show_all_items,
            "hierarchical": self.show_hierarchical,
            "project_boards": self.show_project_boards,
            "vision_planning": self.show_vision_planning_hub,
            "plan": self.show_plan,
            "drag_schedule": self.show_drag_schedule,
            "completed": self.show_completed,
            "contacts": self.show_contacts,
            "defaults": self.show_defaults,
            "stats": self.show_stats,
            "settings": self.show_settings,
        }
        show_fn = show_methods.get(active_name)
        if show_fn is not None:
            show_fn()

    def create_sidebar(self):
        """Create navigation sidebar."""
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(19, weight=1)

        # Logo/title
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text=branding.APP_DISPLAY_NAME,
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Navigation buttons
        self.nav_buttons = {}
        self.btn_today = ctk.CTkButton(
            self.sidebar,
            text="Today",
            command=self.show_today,
            fg_color="transparent",
            border_width=1
        )
        self.btn_today.grid(row=1, column=0, padx=20, pady=10)
        self.nav_buttons["today"] = self.btn_today

        self.btn_upcoming = ctk.CTkButton(
            self.sidebar,
            text="Upcoming",
            command=self.show_upcoming,
            fg_color="transparent",
            border_width=1
        )
        self.btn_upcoming.grid(row=2, column=0, padx=20, pady=10)
        self.nav_buttons["upcoming"] = self.btn_upcoming

        self.btn_all_items = ctk.CTkButton(
            self.sidebar,
            text="All Items",
            command=self.show_all_items,
            fg_color="transparent",
            border_width=1
        )
        self.btn_all_items.grid(row=3, column=0, padx=20, pady=10)
        self.nav_buttons["all_items"] = self.btn_all_items

        self.btn_hierarchical = ctk.CTkButton(
            self.sidebar,
            text="Hierarchical",
            command=self.show_hierarchical,
            fg_color="transparent",
            border_width=1
        )
        self.btn_hierarchical.grid(row=4, column=0, padx=20, pady=10)
        self.nav_buttons["hierarchical"] = self.btn_hierarchical

        self.btn_drag_schedule = ctk.CTkButton(
            self.sidebar,
            text="Schedule",
            command=self.show_drag_schedule,
            fg_color="transparent",
            border_width=1
        )
        self.btn_drag_schedule.grid(row=5, column=0, padx=20, pady=10)
        self.nav_buttons["drag_schedule"] = self.btn_drag_schedule

        self.btn_project_boards = ctk.CTkButton(
            self.sidebar,
            text="Projects",
            command=self.show_project_boards,
            fg_color="transparent",
            border_width=1
        )
        self.btn_project_boards.grid(row=6, column=0, padx=20, pady=10)
        self.nav_buttons["project_boards"] = self.btn_project_boards

        self.btn_completed = ctk.CTkButton(
            self.sidebar,
            text="Completed",
            command=self.show_completed,
            fg_color="transparent",
            border_width=1
        )
        self.btn_completed.grid(row=7, column=0, padx=20, pady=10)
        self.nav_buttons["completed"] = self.btn_completed

        self.btn_stats = ctk.CTkButton(
            self.sidebar,
            text="Status",
            command=self.show_stats,
            fg_color="transparent",
            border_width=1
        )
        self.btn_stats.grid(row=9, column=0, padx=20, pady=10)
        self.nav_buttons["stats"] = self.btn_stats

        self.btn_contacts = ctk.CTkButton(
            self.sidebar,
            text="Contacts",
            command=self.show_contacts,
            fg_color="transparent",
            border_width=1
        )
        self.btn_contacts.grid(row=10, column=0, padx=20, pady=10)
        self.nav_buttons["contacts"] = self.btn_contacts

        self.btn_vps_planning = ctk.CTkButton(
            self.sidebar,
            text="VSP Plan",
            command=self.show_vision_planning_hub,
            fg_color="transparent",
            border_width=1
        )
        self.btn_vps_planning.grid(row=11, column=0, padx=20, pady=10)
        self.nav_buttons["vision_planning"] = self.btn_vps_planning

        self.btn_plan = ctk.CTkButton(
            self.sidebar,
            text="Plan",
            command=self.show_plan,
            fg_color="transparent",
            border_width=1
        )
        self.btn_plan.grid(row=12, column=0, padx=20, pady=10)
        self.nav_buttons["plan"] = self.btn_plan

        self.btn_defaults = ctk.CTkButton(
            self.sidebar,
            text="Defaults",
            command=self.show_defaults,
            fg_color="transparent",
            border_width=1
        )
        self.btn_defaults.grid(row=13, column=0, padx=20, pady=10)
        self.nav_buttons["defaults"] = self.btn_defaults

        self.btn_settings = ctk.CTkButton(
            self.sidebar,
            text="Settings",
            command=self.show_settings,
            fg_color="transparent",
            border_width=1
        )
        self.btn_settings.grid(row=14, column=0, padx=20, pady=10)
        self.nav_buttons["settings"] = self.btn_settings
        self._apply_sidebar_button_styles()

    def _apply_sidebar_button_styles(self):
        active_name = getattr(self, "active_nav_button", "")
        for name, button in self.nav_buttons.items():
            if name == active_name:
                button.configure(
                    **button_style("primary"),
                )
            else:
                button.configure(
                    **button_style("secondary"),
                )

    def _set_active_nav(self, name: str):
        self.active_nav_button = name
        self._apply_sidebar_button_styles()

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
        self._set_active_nav("today")

    def show_upcoming(self):
        """Show Upcoming screen."""
        from .screens.upcoming import UpcomingScreen
        self.clear_content()
        self.current_screen = UpcomingScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")
        self._set_active_nav("upcoming")

    def show_all_items(self):
        """Show All Items screen."""
        from .screens.all_items import AllItemsScreen
        self.clear_content()
        self.current_screen = AllItemsScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")
        self._set_active_nav("all_items")

    def show_hierarchical(self):
        """Show Hierarchical screen."""
        from .screens.hierarchical import HierarchicalScreen
        self.clear_content()
        self.current_screen = HierarchicalScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")
        self._set_active_nav("hierarchical")

    def show_vps_planning(self):
        """Backwards-compatible entrypoint for Vision Planning hub."""
        self.show_vision_planning_hub()

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
        self._set_active_nav("plan")

    def show_drag_schedule(self):
        """Show Drag Schedule screen."""
        from .screens.drag_schedule import DragScheduleScreen
        self.clear_content()
        self.current_screen = DragScheduleScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")
        self._set_active_nav("drag_schedule")

    def show_project_boards(self):
        """Show Project Boards screen."""
        from .screens.project_boards import ProjectBoardsScreen
        self.clear_content()
        self.current_screen = ProjectBoardsScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")
        self._set_active_nav("project_boards")

    def show_completed(self):
        """Show Completed screen."""
        from .screens.completed import CompletedScreen
        self.clear_content()
        self.current_screen = CompletedScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")
        self._set_active_nav("completed")

    def show_contacts(self):
        """Show Contacts management screen."""
        from .screens.manage_contacts import ManageContactsScreen
        self.clear_content()
        self.current_screen = ManageContactsScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")
        self._set_active_nav("contacts")

    def show_defaults(self):
        """Show Defaults screen."""
        from .screens.defaults import DefaultsScreen
        self.clear_content()
        self.current_screen = DefaultsScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")
        self._set_active_nav("defaults")

    def show_stats(self):
        """Show Stats screen."""
        from .screens.stats import StatsScreen
        self.clear_content()
        self.current_screen = StatsScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")
        self._set_active_nav("stats")

    def show_settings(self):
        """Show Settings screen."""
        try:
            from .screens.settings import SettingsScreen
            self.clear_content()
            self.current_screen = SettingsScreen(self.content_frame, self.db_manager, self)
            self.current_screen.grid(row=0, column=0, sticky="nsew")
            self._set_active_nav("settings")
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
        self._set_active_nav("vision_planning")

    def show_annual_vision_segments(self):
        """Show Annual Plan Elements screen."""
        from .screens.annual_vision_segments import AnnualVisionSegmentsScreen
        self.clear_content()
        self.current_screen = AnnualVisionSegmentsScreen(self.content_frame, self.vps_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def show_annual_vision_elements(self):
        """Compatibility alias for Annual Plan Elements navigation."""
        self.show_annual_vision_segments()

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
