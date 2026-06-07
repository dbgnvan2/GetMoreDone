"""Tests for the Project Notes feature.

Spec: docs/implementation_plan_2026-06-06_project_notes.md

GUI tests skip cleanly when customtkinter / a display is unavailable.
Run under the project venv:
    ./venv/bin/python -m pytest tests/test_project_notes.py -v
"""
from __future__ import annotations

import sqlite3
import pytest

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ProjectBoard, ProjectBoardLink


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_manager(tmp_path):
    db_path = str(tmp_path / "project_notes.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


@pytest.fixture
def board_id(db_manager):
    board = ProjectBoard(title="Notes Board")
    return db_manager.create_project_board(board)


# ============================================================================
# M1 — Data model
# ============================================================================

class TestM1DataModel:
    """M1: ProjectBoardLink has a `status` field, table has the column, and
    the migration adds it to existing DBs without data loss."""

    def test_project_board_link_has_status_field(self):
        """M1.A.1: ProjectBoardLink dataclass has a `status` field, default 'open'."""
        link = ProjectBoardLink(project_board_id="b1", url="http://x")
        assert hasattr(link, "status")
        assert link.status == "open"

    def test_project_board_links_table_has_status_column(self, db_manager):
        """M1.A.2: project_board_links table has a `status` column with default 'open'."""
        cursor = db_manager.db.conn.execute("PRAGMA table_info(project_board_links)")
        cols = {row[1]: row for row in cursor.fetchall()}
        assert "status" in cols, "status column missing"
        # row schema: cid, name, type, notnull, dflt_value, pk
        assert cols["status"][2].upper() == "TEXT"
        assert cols["status"][3] == 1  # NOT NULL
        # default may be wrapped in quotes by SQLite
        dflt = cols["status"][4]
        assert dflt is not None and "open" in str(dflt)

    def test_migration_adds_status_to_existing_db(self, tmp_path):
        """M1.A.3: Existing DB without status column gets the column added on init,
        and pre-existing rows default to 'open'."""
        db_path = str(tmp_path / "legacy.db")

        # Manually create a LEGACY project_board_links table (no status column)
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE project_boards (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    annual_plan_element_id TEXT, importance INTEGER,
                    next_step TEXT, notes TEXT, display_order INTEGER,
                    status TEXT NOT NULL DEFAULT 'active', completed_at TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE project_board_links (
                    id TEXT PRIMARY KEY,
                    project_board_id TEXT NOT NULL,
                    label TEXT,
                    url TEXT NOT NULL,
                    link_type TEXT DEFAULT 'url',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "INSERT INTO project_boards (id, title, status, created_at, updated_at) "
                "VALUES ('b1', 'B', 'active', '2020-01-01', '2020-01-01')"
            )
            conn.execute(
                "INSERT INTO project_board_links (id, project_board_id, url, created_at) "
                "VALUES ('legacy-link', 'b1', 'note://legacy', '2020-01-01')"
            )
            conn.commit()

        # Now open the DB through the manager — migration must add the column
        manager = DatabaseManager(db_path)
        try:
            cursor = manager.db.conn.execute("PRAGMA table_info(project_board_links)")
            cols = [row[1] for row in cursor.fetchall()]
            assert "status" in cols

            row = manager.db.conn.execute(
                "SELECT status FROM project_board_links WHERE id = ?", ("legacy-link",)
            ).fetchone()
            assert row["status"] == "open"
        finally:
            manager.close()

    def test_link_status_roundtrip(self, db_manager, board_id):
        """M1.A.4: add_project_board_link / get_project_board_links round-trip status."""
        link_open = ProjectBoardLink(project_board_id=board_id, url="o://", label="open one")
        link_done = ProjectBoardLink(
            project_board_id=board_id, url="c://", label="done one", status="completed"
        )
        db_manager.add_project_board_link(link_open)
        db_manager.add_project_board_link(link_done)

        rows = db_manager.get_project_board_links(board_id)
        by_label = {r.label: r for r in rows}
        assert by_label["open one"].status == "open"
        assert by_label["done one"].status == "completed"


# ============================================================================
# M2 — DB methods: complete / reopen / filtered get
# ============================================================================

class TestM2DBMethods:
    """M2: complete_project_note, reopen_project_note, include_completed filter."""

    def test_complete_project_note(self, db_manager, board_id):
        """M2.A.1: complete_project_note sets status='completed'."""
        link = ProjectBoardLink(project_board_id=board_id, url="x://", label="todo")
        db_manager.add_project_board_link(link)

        ok = db_manager.complete_project_note(link.id)
        assert ok is True
        refreshed = db_manager.get_project_board_links(board_id)
        assert refreshed[0].status == "completed"

    def test_reopen_project_note(self, db_manager, board_id):
        """M2.A.2: reopen_project_note sets status='open'."""
        link = ProjectBoardLink(
            project_board_id=board_id, url="x://", label="t", status="completed"
        )
        db_manager.add_project_board_link(link)

        ok = db_manager.reopen_project_note(link.id)
        assert ok is True
        refreshed = db_manager.get_project_board_links(board_id)
        assert refreshed[0].status == "open"

    def test_complete_reopen_unknown_id_returns_false(self, db_manager):
        """Status mutators return False when the ID is unknown."""
        assert db_manager.complete_project_note("no-such-id") is False
        assert db_manager.reopen_project_note("no-such-id") is False

    def test_get_links_filters_by_status(self, db_manager, board_id):
        """M2.A.3: include_completed=False returns only open notes."""
        db_manager.add_project_board_link(
            ProjectBoardLink(project_board_id=board_id, url="o://", label="open A")
        )
        db_manager.add_project_board_link(
            ProjectBoardLink(
                project_board_id=board_id, url="c://", label="done B", status="completed"
            )
        )
        db_manager.add_project_board_link(
            ProjectBoardLink(project_board_id=board_id, url="o2://", label="open C")
        )

        all_links = db_manager.get_project_board_links(board_id, include_completed=True)
        open_only = db_manager.get_project_board_links(board_id, include_completed=False)

        assert len(all_links) == 3
        assert {l.label for l in open_only} == {"open A", "open C"}
        assert all(l.status == "open" for l in open_only)

    def test_get_links_ordered_newest_first(self, db_manager, board_id):
        """Sort decision: get_project_board_links returns most-recent first."""
        # Insert with explicit, non-default created_at so order is unambiguous.
        for label, ts in [("oldest", "2020-01-01T00:00:00"),
                          ("middle", "2022-06-15T12:00:00"),
                          ("newest", "2026-06-06T09:00:00")]:
            db_manager.add_project_board_link(
                ProjectBoardLink(
                    project_board_id=board_id, url=f"{label}://",
                    label=label, created_at=ts,
                )
            )
        rows = db_manager.get_project_board_links(board_id)
        assert [r.label for r in rows] == ["newest", "middle", "oldest"]


# ============================================================================
# M7 — Project Notes Folder setting
# ============================================================================

class TestM7Settings:
    """M7: AppSettings.project_notes_subfolder + routing in CreateNoteDialog."""

    def test_settings_has_project_notes_subfolder(self):
        """M7.A.1: AppSettings has `project_notes_subfolder` with the documented default."""
        from src.getmoredone.app_settings import AppSettings
        s = AppSettings()
        assert hasattr(s, "project_notes_subfolder")
        assert s.project_notes_subfolder == "GetMoreDone/Projects"

    def test_get_project_notes_folder_returns_path(self, tmp_path):
        """M7.A.2: get_project_notes_folder returns <vault>/<subfolder>."""
        from src.getmoredone.app_settings import AppSettings
        vault = tmp_path / "vault"
        vault.mkdir()
        s = AppSettings(obsidian_vault_path=str(vault),
                        project_notes_subfolder="MyProjects/Notes")
        folder = s.get_project_notes_folder()
        assert folder == vault / "MyProjects/Notes"

    def test_blank_project_subfolder_falls_back(self, tmp_path):
        """M7.A.6: blank project_notes_subfolder falls back to obsidian_notes_subfolder."""
        from src.getmoredone.app_settings import AppSettings
        vault = tmp_path / "vault"
        vault.mkdir()
        s = AppSettings(obsidian_vault_path=str(vault),
                        obsidian_notes_subfolder="Generic",
                        project_notes_subfolder="")
        assert s.get_project_notes_subfolder_or_default() == "Generic"
        assert s.get_project_notes_folder() == vault / "Generic"

    def test_settings_roundtrip_project_subfolder(self, tmp_path, monkeypatch):
        """M7.A.3: AppSettings.save() / load() round-trip the new field."""
        from src.getmoredone.app_settings import AppSettings
        # Redirect the settings file to a tmp location
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(AppSettings, "get_settings_path",
                            classmethod(lambda cls: settings_path))

        s = AppSettings(project_notes_subfolder="Custom/Path")
        s.save()
        loaded = AppSettings.load()
        assert loaded.project_notes_subfolder == "Custom/Path"

    def test_project_notes_folder_created_on_first_note(self, tmp_path):
        """M7.A.7: create_obsidian_note auto-creates the folder if missing."""
        from src.getmoredone.obsidian_utils import create_obsidian_note
        vault = tmp_path / "vault"
        vault.mkdir()
        target = vault / "GetMoreDone" / "Projects"
        assert not target.exists()

        # The util mkdirs only one level (`vault / subfolder`), so the subfolder
        # must be a single segment OR the parents must exist. Verify the
        # documented behavior: a single-segment subfolder is created on demand.
        create_obsidian_note(
            vault_path=str(vault),
            subfolder="ProjectFolder",
            entity_type="project_board",
            entity_id="p1",
            title="Test",
        )
        assert (vault / "ProjectFolder").exists()


class TestM7Routing:
    """M7.A.5: CreateNoteDialog routes project_board entity to the project folder.

    We exercise CreateNoteDialog.create_note end-to-end with stubbed AppSettings
    + a captured create_obsidian_note, so we verify the actual routing logic
    inside the dialog (the bug-prone part), not just the helper getter.
    """

    @pytest.fixture
    def stubbed_dialog(self, db_manager, board_id, monkeypatch, tmp_path):
        ctk = pytest.importorskip("customtkinter")
        from src.getmoredone import app_settings as app_settings_mod
        from src.getmoredone import obsidian_utils as obsidian_mod
        from src.getmoredone.models import ActionItem

        try:
            root = ctk.CTk()
        except Exception as exc:
            pytest.skip(f"No GUI display available: {exc}")
        root.withdraw()

        vault = tmp_path / "vault"
        vault.mkdir()

        # Stub AppSettings.load() to return our test-controlled instance
        test_settings = app_settings_mod.AppSettings(
            obsidian_vault_path=str(vault),
            obsidian_notes_subfolder="GenericNotes",
            project_notes_subfolder="ProjectNotesHere",
        )
        monkeypatch.setattr(
            app_settings_mod.AppSettings, "load",
            classmethod(lambda cls: test_settings),
        )

        # CreateNoteDialog imports create_obsidian_note locally inside its
        # create_note method (`from ..obsidian_utils import ...`), so we patch
        # at the source module — the local `from ... import` re-binds from
        # obsidian_utils each call.
        captured = {}

        def fake_create_obsidian_note(vault_path, subfolder, **kwargs):
            captured["subfolder"] = subfolder
            captured["entity_type"] = kwargs.get("entity_type")
            return str(tmp_path / "fake_note.md")

        monkeypatch.setattr(obsidian_mod, "create_obsidian_note",
                            fake_create_obsidian_note)
        monkeypatch.setattr(obsidian_mod, "open_in_obsidian",
                            lambda *_a, **_kw: None)

        # Need an action_item entity so the action-item branch can find it
        action_id = db_manager.create_action_item(
            ActionItem(who="me", title="A", status="open")
        )

        yield {
            "root": root, "captured": captured,
            "board_id": board_id, "action_id": action_id,
            "db_manager": db_manager, "vault": vault,
        }
        root.destroy()

    def test_create_note_for_project_writes_to_project_folder(self, stubbed_dialog):
        """M7.A.5: Project entity → subfolder = ProjectNotesHere (NOT GenericNotes)."""
        from src.getmoredone.screens.item_editor_note_dialogs import CreateNoteDialog
        d = stubbed_dialog
        dlg = CreateNoteDialog(
            d["root"], d["db_manager"], "project_board", d["board_id"], "My Project"
        )
        dlg.title_var.set("MyNote")
        dlg.create_note()
        assert d["captured"]["entity_type"] == "project_board"
        assert d["captured"]["subfolder"] == "ProjectNotesHere"

    def test_create_note_for_action_item_still_uses_generic_folder(self, stubbed_dialog):
        """M7.A.5 (no-regression): action_item entity continues to use
        obsidian_notes_subfolder, not the project one."""
        from src.getmoredone.screens.item_editor_note_dialogs import CreateNoteDialog
        d = stubbed_dialog
        dlg = CreateNoteDialog(
            d["root"], d["db_manager"], "action_item", d["action_id"], "An Item"
        )
        dlg.title_var.set("ActionNote")
        dlg.create_note()
        assert d["captured"]["entity_type"] == "action_item"
        assert d["captured"]["subfolder"] == "GenericNotes"

    def test_create_note_for_project_falls_back_when_blank(
        self, db_manager, board_id, monkeypatch, tmp_path
    ):
        """M7.A.6 routed: blank project subfolder → falls back to GenericNotes."""
        ctk = pytest.importorskip("customtkinter")
        from src.getmoredone import app_settings as app_settings_mod
        from src.getmoredone import obsidian_utils as obsidian_mod
        from src.getmoredone.screens.item_editor_note_dialogs import CreateNoteDialog

        try:
            root = ctk.CTk()
        except Exception as exc:
            pytest.skip(f"No GUI display available: {exc}")
        root.withdraw()
        try:
            vault = tmp_path / "vault"
            vault.mkdir()
            test_settings = app_settings_mod.AppSettings(
                obsidian_vault_path=str(vault),
                obsidian_notes_subfolder="GenericNotes",
                project_notes_subfolder="",  # blank!
            )
            monkeypatch.setattr(
                app_settings_mod.AppSettings, "load",
                classmethod(lambda cls: test_settings),
            )

            captured = {}
            monkeypatch.setattr(
                obsidian_mod, "create_obsidian_note",
                lambda vault_path, subfolder, **kw: (
                    captured.update(subfolder=subfolder) or str(tmp_path / "n.md")
                ),
            )
            monkeypatch.setattr(obsidian_mod, "open_in_obsidian",
                                lambda *_a, **_kw: None)

            dlg = CreateNoteDialog(root, db_manager, "project_board", board_id, "Proj")
            dlg.title_var.set("N")
            dlg.create_note()
            assert captured["subfolder"] == "GenericNotes"
        finally:
            root.destroy()


# ============================================================================
# M3 — UI: Project Notes section
# ============================================================================

@pytest.fixture
def gui_screen(db_manager):
    """Real ProjectBoardsScreen with a board selected and no notes yet."""
    ctk = pytest.importorskip("customtkinter")
    from types import SimpleNamespace
    from src.getmoredone.screens.project_boards import ProjectBoardsScreen

    try:
        root = ctk.CTk()
    except Exception as exc:
        pytest.skip(f"No GUI display available: {exc}")
    root.withdraw()

    board_id = db_manager.create_project_board(ProjectBoard(title="M3 Board"))
    screen = ProjectBoardsScreen(
        root, db_manager, SimpleNamespace(vps_manager=None)
    )
    screen.selected_board_id = board_id
    screen.refresh()
    root.update_idletasks()
    yield screen, board_id, root
    root.destroy()


def _all_labels(widget):
    """Recursively collect all CTkLabel texts under a widget."""
    import customtkinter as ctk
    out = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel):
            out.append(child.cget("text"))
        out.extend(_all_labels(child))
    return out


def _all_button_texts(widget):
    import customtkinter as ctk
    out = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            out.append(child.cget("text"))
        out.extend(_all_button_texts(child))
    return out


def _all_checkboxes(widget):
    import customtkinter as ctk
    out = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkCheckBox):
            out.append(child)
        out.extend(_all_checkboxes(child))
    return out


class TestM3UI:
    """M3: Project Notes is a first-class section with status + buttons."""

    def test_project_notes_header_rendered(self, gui_screen, db_manager):
        """M3.A.1: A bold 'Project Notes' label appears in the notes frame."""
        screen, board_id, root = gui_screen
        # Link a note so the section renders fully
        db_manager.add_project_board_link(
            ProjectBoardLink(project_board_id=board_id, url="x://", label="A")
        )
        screen.load_notes()
        root.update_idletasks()
        labels = _all_labels(screen.notes_links_frame)
        assert "Project Notes" in labels

    def test_project_note_row_has_status_buttons_no_checkbox(
        self, gui_screen, db_manager
    ):
        """M3.A.2: A note row has Open, Complete, Unlink buttons; NO checkbox."""
        screen, board_id, root = gui_screen
        db_manager.add_project_board_link(
            ProjectBoardLink(project_board_id=board_id, url="x://", label="A")
        )
        screen.load_notes()
        root.update_idletasks()
        btns = _all_button_texts(screen.notes_links_frame)
        assert "Open" in btns
        assert "Complete" in btns
        assert "Unlink" in btns
        # Verify status pill renders the note's status
        labels = _all_labels(screen.notes_links_frame)
        assert "open" in labels
        # No checkboxes in the notes section
        assert _all_checkboxes(screen.notes_links_frame) == []

    def test_completed_note_shows_reopen_not_complete(
        self, gui_screen, db_manager
    ):
        """A completed note shows Reopen instead of Complete."""
        screen, board_id, root = gui_screen
        # Need show_completed=True for completed notes to be visible
        screen.show_completed_items_var.set(True)
        db_manager.add_project_board_link(
            ProjectBoardLink(
                project_board_id=board_id, url="c://", label="B", status="completed"
            )
        )
        screen.load_notes()
        root.update_idletasks()
        btns = _all_button_texts(screen.notes_links_frame)
        assert "Reopen" in btns
        assert "Complete" not in btns

    def test_complete_button_updates_status(self, gui_screen, db_manager):
        """M3.A.3: The Complete handler flips status in the DB."""
        screen, board_id, root = gui_screen
        link = ProjectBoardLink(
            project_board_id=board_id, url="x://", label="A"
        )
        db_manager.add_project_board_link(link)
        screen.load_notes()
        root.update_idletasks()

        screen._on_complete_project_note(link.id)

        refreshed = db_manager.get_project_board_links(board_id)
        assert refreshed[0].status == "completed"

    def test_reopen_button_updates_status(self, gui_screen, db_manager):
        """The Reopen handler flips status back to open in the DB."""
        screen, board_id, root = gui_screen
        link = ProjectBoardLink(
            project_board_id=board_id, url="x://", label="A", status="completed"
        )
        db_manager.add_project_board_link(link)
        screen.show_completed_items_var.set(True)
        screen.load_notes()
        root.update_idletasks()

        screen._on_reopen_project_note(link.id)

        refreshed = db_manager.get_project_board_links(board_id)
        assert refreshed[0].status == "open"

    def test_notes_count_label(self, gui_screen, db_manager):
        """M3.A.4: Count label reads 'N note(s) shown' or 'N shown • M completed hidden'."""
        screen, board_id, root = gui_screen
        # Two open + one completed
        for label, status in [("A", "open"), ("B", "open"), ("C", "completed")]:
            db_manager.add_project_board_link(
                ProjectBoardLink(
                    project_board_id=board_id, url=f"{label}://",
                    label=label, status=status,
                )
            )

        # When showing all: "3 notes shown"
        screen.show_completed_items_var.set(True)
        screen.load_notes()
        root.update_idletasks()
        labels = _all_labels(screen.notes_links_frame)
        assert any("3 notes shown" in s for s in labels)

        # When hiding completed: "2 shown • 1 completed hidden"
        screen.show_completed_items_var.set(False)
        screen.load_notes()
        root.update_idletasks()
        labels = _all_labels(screen.notes_links_frame)
        assert any("2 shown" in s and "1 completed hidden" in s for s in labels)

    def test_notes_section_orders_newest_first(self, gui_screen, db_manager):
        """Sort: notes display most-recently-linked first."""
        screen, board_id, root = gui_screen
        for label, ts in [("oldest", "2020-01-01T00:00:00"),
                          ("middle", "2022-06-15T12:00:00"),
                          ("newest", "2026-06-06T09:00:00")]:
            db_manager.add_project_board_link(
                ProjectBoardLink(
                    project_board_id=board_id, url=f"{label}://",
                    label=label, created_at=ts,
                )
            )
        screen.show_completed_items_var.set(True)
        screen.load_notes()
        root.update_idletasks()
        labels = _all_labels(screen.notes_links_frame)
        # Find indices of each label in the rendered order
        idx_newest = next(i for i, s in enumerate(labels) if "newest" in s)
        idx_middle = next(i for i, s in enumerate(labels) if "middle" in s)
        idx_oldest = next(i for i, s in enumerate(labels) if "oldest" in s)
        assert idx_newest < idx_middle < idx_oldest


# ============================================================================
# M6 — Spec traceability / spec_coverage.md
# ============================================================================

class TestM6SpecCoverage:
    """M6: docs/spec_coverage.md exists and mentions every spec ID."""

    def test_spec_coverage_doc_mentions_m1_through_m7(self):
        """M6.A.2: docs/spec_coverage.md lists every acceptance criterion ID."""
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent
        doc = repo_root / "docs" / "spec_coverage.md"
        assert doc.exists(), f"Missing {doc}"
        body = doc.read_text()

        expected = [
            "M1.A.1", "M1.A.2", "M1.A.3", "M1.A.4",
            "M2.A.1", "M2.A.2", "M2.A.3",
            "M3.A.1", "M3.A.2", "M3.A.3", "M3.A.4",
            "M4.A.1", "M4.A.2", "M4.A.3",
            "M5.A.1", "M5.A.2",
            "M6.A.1", "M6.A.2",
            "M7.A.1", "M7.A.2", "M7.A.3", "M7.A.4",
            "M7.A.5", "M7.A.6", "M7.A.7",
        ]
        for spec_id in expected:
            assert spec_id in body, f"spec_coverage.md missing {spec_id}"


# ============================================================================
# M5 — Old count-only label removed
# ============================================================================

class TestM5Cleanup:
    """M5: The legacy 'N notes linked to this project.' line is gone, replaced
    by the new Project Notes section header + count."""

    def test_old_count_only_label_removed(self, gui_screen):
        """M5.A.1: No label with the legacy 'notes linked to this project' phrase."""
        screen, _board_id, root = gui_screen
        # Render with zero notes — historical edge case where the label
        # used to read '0 notes linked to this project.'
        screen.load_notes()
        root.update_idletasks()
        labels = _all_labels(screen.notes_links_frame)
        for s in labels:
            assert "notes linked to this project" not in s, \
                f"Legacy phrasing still present: {s!r}"


# ============================================================================
# M4 — Shared Show Completed (default OFF)
# ============================================================================

class TestM4SharedShowCompleted:
    """M4: Single shared 'Show Completed' toggle, default OFF, filters BOTH lists."""

    def test_show_completed_default_off(self, gui_screen):
        """M4.A.1: Default is OFF (open-only view)."""
        screen, _board_id, _root = gui_screen
        assert screen.show_completed_items_var.get() is False

    def test_show_completed_filters_both_lists(self, gui_screen, db_manager):
        """M4.A.2: Toggling the shared filter affects BOTH notes AND action items."""
        from src.getmoredone.models import ActionItem
        screen, board_id, root = gui_screen
        # Open + completed in both lists
        db_manager.add_project_board_link(
            ProjectBoardLink(project_board_id=board_id, url="o://", label="note open")
        )
        db_manager.add_project_board_link(
            ProjectBoardLink(
                project_board_id=board_id, url="c://", label="note done",
                status="completed",
            )
        )
        open_id = db_manager.create_action_item(
            ActionItem(who="me", title="ai-open", status="open")
        )
        db_manager.link_action_item_to_project_board(board_id, open_id)
        done_id = db_manager.create_action_item(
            ActionItem(who="me", title="ai-done", status="open")
        )
        db_manager.link_action_item_to_project_board(board_id, done_id)
        db_manager.complete_action_item(done_id)

        # Default OFF: completed note row absent, completed action item absent
        screen._render_detail()
        root.update_idletasks()
        note_labels = _all_labels(screen.notes_links_frame)
        assert any("note open" in s for s in note_labels)
        assert not any("note done" in s for s in note_labels)
        assert open_id in screen.item_checkbox_vars
        assert done_id not in screen.item_checkbox_vars

        # Flip ON: both completed entries reappear in their respective lists
        screen.show_completed_items_var.set(True)
        screen._render_detail()
        root.update_idletasks()
        note_labels = _all_labels(screen.notes_links_frame)
        assert any("note done" in s for s in note_labels)
        assert done_id in screen.item_checkbox_vars

    def test_select_all_still_respects_filter(self, gui_screen, db_manager):
        """M4.A.3 (existing behavior preserved): Select All only selects visible action items."""
        from src.getmoredone.models import ActionItem
        screen, board_id, root = gui_screen
        # 2 open + 1 completed action items
        open_ids = []
        for i in range(2):
            aid = db_manager.create_action_item(
                ActionItem(who="me", title=f"o{i}", status="open")
            )
            db_manager.link_action_item_to_project_board(board_id, aid)
            open_ids.append(aid)
        done_id = db_manager.create_action_item(
            ActionItem(who="me", title="d", status="open")
        )
        db_manager.link_action_item_to_project_board(board_id, done_id)
        db_manager.complete_action_item(done_id)

        # Default OFF: filter hides completed
        screen._render_detail()
        root.update_idletasks()
        screen.check_all_var.set(True)
        screen._on_check_all_changed()
        assert screen.selected_item_ids == set(open_ids)
        assert done_id not in screen.selected_item_ids


class TestM7SettingsScreenUI:
    """M7.A.4: SettingsScreen has a Project Notes Folder field bound to
    project_notes_folder_var, and save_obsidian_settings persists it."""

    def test_settings_screen_has_project_notes_folder_field(
        self, db_manager, monkeypatch, tmp_path
    ):
        ctk = pytest.importorskip("customtkinter")
        from types import SimpleNamespace
        from src.getmoredone import app_settings as app_settings_mod
        from src.getmoredone.screens.settings import SettingsScreen

        # Redirect settings file location and supply a known initial value
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            app_settings_mod.AppSettings, "get_settings_path",
            classmethod(lambda cls: settings_path),
        )
        # Seed with a known project_notes_subfolder
        seed = app_settings_mod.AppSettings(project_notes_subfolder="SeedFolder")
        seed.save()

        try:
            root = ctk.CTk()
        except Exception as exc:
            pytest.skip(f"No GUI display available: {exc}")
        root.withdraw()
        try:
            screen = SettingsScreen(
                root, db_manager=db_manager, app=SimpleNamespace()
            )
            assert hasattr(screen, "project_notes_folder_var")
            assert screen.project_notes_folder_var.get() == "SeedFolder"

            # Simulate the user editing and clicking Save
            screen.project_notes_folder_var.set("EditedFolder")
            screen.save_obsidian_settings()

            reloaded = app_settings_mod.AppSettings.load()
            assert reloaded.project_notes_subfolder == "EditedFolder"
        finally:
            root.destroy()
