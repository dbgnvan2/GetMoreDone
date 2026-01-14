"""
Main application window for GetMoreDone.
"""

import customtkinter as ctk
from typing import Optional

from .db_manager import DatabaseManager


class GetMoreDoneApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # Configure window
        self.title("GetMoreDone")
        self.geometry("1200x700")

        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize database
        self.db_manager = DatabaseManager()

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
        self.sidebar.grid_rowconfigure(10, weight=1)

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

        self.btn_plan = ctk.CTkButton(
            self.sidebar,
            text="Plan",
            command=self.show_plan
        )
        self.btn_plan.grid(row=5, column=0, padx=20, pady=10)

        self.btn_completed = ctk.CTkButton(
            self.sidebar,
            text="Completed",
            command=self.show_completed
        )
        self.btn_completed.grid(row=6, column=0, padx=20, pady=10)

        self.btn_contacts = ctk.CTkButton(
            self.sidebar,
            text="Contacts",
            command=self.show_contacts
        )
        self.btn_contacts.grid(row=7, column=0, padx=20, pady=10)

        self.btn_defaults = ctk.CTkButton(
            self.sidebar,
            text="Defaults",
            command=self.show_defaults
        )
        self.btn_defaults.grid(row=8, column=0, padx=20, pady=10)

        self.btn_stats = ctk.CTkButton(
            self.sidebar,
            text="Stats",
            command=self.show_stats
        )
        self.btn_stats.grid(row=9, column=0, padx=20, pady=10)

        self.btn_settings = ctk.CTkButton(
            self.sidebar,
            text="Settings",
            command=self.show_settings
        )
        self.btn_settings.grid(row=10, column=0, padx=20, pady=10)

    def clear_content(self):
        """Clear current screen from content area."""
        if self.current_screen:
            self.current_screen.destroy()
            self.current_screen = None

    def show_today(self):
        """Show Today screen."""
        from .screens.today import TodayScreen
        self.clear_content()
        self.current_screen = TodayScreen(self.content_frame, self.db_manager)
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

    def show_plan(self):
        """Show Plan screen."""
        from .screens.plan import PlanScreen
        self.clear_content()
        self.current_screen = PlanScreen(self.content_frame, self.db_manager, self)
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
        from .screens.settings import SettingsScreen
        self.clear_content()
        self.current_screen = SettingsScreen(self.content_frame, self.db_manager, self)
        self.current_screen.grid(row=0, column=0, sticky="nsew")

    def refresh_current_screen(self):
        """Refresh the current screen (useful after edits)."""
        if hasattr(self.current_screen, 'refresh'):
            self.current_screen.refresh()

    def on_closing(self):
        """Handle window closing."""
        self.db_manager.close()
        self.destroy()


def main():
    """Application entry point."""
    app = GetMoreDoneApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
