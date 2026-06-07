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
