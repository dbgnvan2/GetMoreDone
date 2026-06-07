"""Tests for the project-tile note chooser (📄 icon → Create / Link dialog).

Spec:    docs/implementation_plan_2026-06-06.md (paper-icon-enhancement)
GUI tests skip cleanly when customtkinter / a display is unavailable.
Run under the project venv:
    ./venv/bin/python -m pytest tests/test_project_note_chooser.py -v
"""
import pytest


@pytest.fixture
def db_manager(tmp_path):
    """Temp DB for the screen fixture."""
    from src.getmoredone.db_manager import DatabaseManager

    db_path = str(tmp_path / "chooser_test.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


@pytest.fixture
def gui_screen_and_board(db_manager):
    """Real ProjectBoardsScreen with one board selected."""
    ctk = pytest.importorskip("customtkinter")
    from types import SimpleNamespace
    from src.getmoredone.models import ProjectBoard
    from src.getmoredone.screens.project_boards import ProjectBoardsScreen

    try:
        root = ctk.CTk()
    except Exception as exc:
        pytest.skip(f"No GUI display available: {exc}")
    root.withdraw()

    board = ProjectBoard(title="Chooser Test Board")
    board_id = db_manager.create_project_board(board)
    screen = ProjectBoardsScreen(
        root, db_manager, SimpleNamespace(vps_manager=None)
    )
    screen.selected_board_id = board_id
    screen.refresh()
    root.update_idletasks()
    yield screen, board_id, root
    root.destroy()


class TestNoteActionChooserDialog:
    """Dialog itself — buttons set the correct result."""

    def test_choice_is_create(self, gui_screen_and_board):
        """Clicking 'Create New' sets result to CHOICE_CREATE."""
        screen, _, root = gui_screen_and_board
        from src.getmoredone.screens.project_boards import NoteActionChooserDialog

        chooser = NoteActionChooserDialog(screen, "Board")
        root.update_idletasks()
        chooser._choose_create()
        assert chooser.result == NoteActionChooserDialog.CHOICE_CREATE

    def test_choice_is_link(self, gui_screen_and_board):
        """Clicking 'Link Existing' sets result to CHOICE_LINK."""
        screen, _, root = gui_screen_and_board
        from src.getmoredone.screens.project_boards import NoteActionChooserDialog

        chooser = NoteActionChooserDialog(screen, "Board")
        root.update_idletasks()
        chooser._choose_link()
        assert chooser.result == NoteActionChooserDialog.CHOICE_LINK

    def test_cancel_returns_none(self, gui_screen_and_board):
        """Cancel button (or window close) leaves result as None."""
        screen, _, root = gui_screen_and_board
        from src.getmoredone.screens.project_boards import NoteActionChooserDialog

        chooser = NoteActionChooserDialog(screen, "Board")
        root.update_idletasks()
        chooser.cancel()
        assert chooser.result is None


class TestAddNoteToProjectHandler:
    """Handler — dispatches to create_note / link_note based on chooser result."""

    def test_handler_dispatches_to_create_note(self, gui_screen_and_board, monkeypatch):
        """When chooser returns CHOICE_CREATE, screen.create_note is called."""
        screen, board_id, _root = gui_screen_and_board
        from src.getmoredone.screens import project_boards as pb

        # Stub the chooser to return CREATE immediately
        class StubChooser:
            CHOICE_CREATE = pb.NoteActionChooserDialog.CHOICE_CREATE
            CHOICE_LINK = pb.NoteActionChooserDialog.CHOICE_LINK
            result = pb.NoteActionChooserDialog.CHOICE_CREATE

            def __init__(self, *_a, **_kw):
                pass

        monkeypatch.setattr(pb, "NoteActionChooserDialog", StubChooser)
        monkeypatch.setattr(screen, "wait_window", lambda *_a: None)

        calls = {"create": 0, "link": 0}
        monkeypatch.setattr(screen, "create_note", lambda bid: calls.__setitem__("create", calls["create"] + 1))
        monkeypatch.setattr(screen, "link_note", lambda bid: calls.__setitem__("link", calls["link"] + 1))

        screen.add_note_to_project(board_id)
        assert calls == {"create": 1, "link": 0}

    def test_handler_dispatches_to_link_note(self, gui_screen_and_board, monkeypatch):
        """When chooser returns CHOICE_LINK, screen.link_note is called."""
        screen, board_id, _root = gui_screen_and_board
        from src.getmoredone.screens import project_boards as pb

        class StubChooser:
            CHOICE_CREATE = pb.NoteActionChooserDialog.CHOICE_CREATE
            CHOICE_LINK = pb.NoteActionChooserDialog.CHOICE_LINK
            result = pb.NoteActionChooserDialog.CHOICE_LINK

            def __init__(self, *_a, **_kw):
                pass

        monkeypatch.setattr(pb, "NoteActionChooserDialog", StubChooser)
        monkeypatch.setattr(screen, "wait_window", lambda *_a: None)

        calls = {"create": 0, "link": 0}
        monkeypatch.setattr(screen, "create_note", lambda bid: calls.__setitem__("create", calls["create"] + 1))
        monkeypatch.setattr(screen, "link_note", lambda bid: calls.__setitem__("link", calls["link"] + 1))

        screen.add_note_to_project(board_id)
        assert calls == {"create": 0, "link": 1}

    def test_handler_does_nothing_on_cancel(self, gui_screen_and_board, monkeypatch):
        """When the chooser is cancelled (result None), no dispatch happens."""
        screen, board_id, _root = gui_screen_and_board
        from src.getmoredone.screens import project_boards as pb

        class StubChooser:
            CHOICE_CREATE = pb.NoteActionChooserDialog.CHOICE_CREATE
            CHOICE_LINK = pb.NoteActionChooserDialog.CHOICE_LINK
            result = None

            def __init__(self, *_a, **_kw):
                pass

        monkeypatch.setattr(pb, "NoteActionChooserDialog", StubChooser)
        monkeypatch.setattr(screen, "wait_window", lambda *_a: None)

        calls = {"create": 0, "link": 0}
        monkeypatch.setattr(screen, "create_note", lambda bid: calls.__setitem__("create", calls["create"] + 1))
        monkeypatch.setattr(screen, "link_note", lambda bid: calls.__setitem__("link", calls["link"] + 1))

        screen.add_note_to_project(board_id)
        assert calls == {"create": 0, "link": 0}

    def test_handler_noop_for_unknown_board(self, gui_screen_and_board, monkeypatch):
        """Unknown board_id → handler short-circuits without showing the chooser."""
        screen, _, _root = gui_screen_and_board
        from src.getmoredone.screens import project_boards as pb

        opened = {"count": 0}

        class StubChooser:
            CHOICE_CREATE = pb.NoteActionChooserDialog.CHOICE_CREATE
            CHOICE_LINK = pb.NoteActionChooserDialog.CHOICE_LINK
            result = None

            def __init__(self, *_a, **_kw):
                opened["count"] += 1

        monkeypatch.setattr(pb, "NoteActionChooserDialog", StubChooser)
        monkeypatch.setattr(screen, "wait_window", lambda *_a: None)

        screen.add_note_to_project("not-a-real-id")
        assert opened["count"] == 0
