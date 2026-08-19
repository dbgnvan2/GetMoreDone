"""Render one list screen and report each row's grid columns.

Purpose: the column-contiguity check in test_item_editor_no_context.py runs
         this in a **subprocess**. CustomTkinter does not tolerate several CTk
         roots in one interpreter — building a full screen after other tests
         have already created and destroyed roots hangs the run — so the render
         gets its own process, and the test gets a hard timeout.

Not named ``test_*`` on purpose: it is a helper, not a test.

Usage: python tests/render_list_screen.py <module> <ScreenClass>
Prints one "OK <cols>" or "GAP <cols>" line per rendered row; exit 0 always
unless it genuinely fails to render.
"""

import importlib
import pathlib
import sys
import tempfile
from datetime import date
from unittest.mock import MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import customtkinter as ctk

from src.getmoredone.models import ActionItem
from src.getmoredone.vps_manager import VPSManager


def main(module: str, attr: str) -> int:
    vps = VPSManager(str(pathlib.Path(tempfile.mkdtemp()) / "render.db"))
    manager = vps.db_manager
    today = date.today().isoformat()
    for title in ["PW|LS|Blog - W8 - write blog 3", "Call the plumber"]:
        manager.create_action_item(
            ActionItem(who="Self", title=title, start_date=today, due_date=today,
                       importance=10, urgency=10, size=5, value=5),
            apply_defaults=False)

    window = ctk.CTk()
    window.withdraw()
    app = MagicMock()
    app.vps_manager = vps
    screen_cls = getattr(
        importlib.import_module(f"src.getmoredone.screens.{module}"), attr)
    screen = screen_cls(window, manager, app)
    screen.pack(fill="both", expand=True)
    window.update()

    printed = 0
    # Scoped to the list area: the toolbars above it grid controls with a
    # deliberate spacer gap, which is not what this checks.
    for node in screen.scroll_frame.winfo_children():
        gridded = [c for c in node.winfo_children() if c.grid_info()]
        if len(gridded) < 5 or not all(
                str(c.grid_info().get("row")) == "0" for c in gridded):
            continue
        columns = sorted({int(c.grid_info()["column"]) for c in gridded})
        status = "OK" if columns == list(range(len(columns))) else "GAP"
        print(f"{status} {columns}")
        printed += 1

    if not printed:
        print("NOROWS")
    window.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
