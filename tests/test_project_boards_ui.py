from src.getmoredone.screens.project_boards import ProjectBoardsScreen

from tests.source_asserts import assigns_self_attribute


def test_project_board_edit_icon_is_upright_pencil():
    # Fallback still exists
    assert ProjectBoardsScreen.ICON_EDIT == "✐"


def test_project_board_edit_icon_image_is_loaded():
    """The card falls back to a text glyph when no image loaded.

    The body of this test was `pass`. It constructed a screen and asserted
    nothing, so it reported green whether the icon logic worked, was deleted,
    or had never existed.

    Building the real screen needs a full Tk stack, so this asserts the
    contract the card actually depends on: `edit_icon_image` is consulted to
    choose between the image and the `ICON_EDIT` glyph, so it must exist as an
    attribute on any constructed screen — including when the image fails to
    load, where it must be falsy rather than absent.
    """
    screen = ProjectBoardsScreen.__new__(ProjectBoardsScreen)

    # Not yet initialised: the card's `text=""  if self.edit_icon_image else ...`
    # would raise AttributeError, which is exactly what the fallback exists to
    # avoid. __init__ must set it unconditionally.
    assert assigns_self_attribute(ProjectBoardsScreen.__init__, "edit_icon_image"), (
        "ProjectBoardsScreen.__init__ no longer assigns self.edit_icon_image, "
        "so the edit button's image/glyph fallback raises AttributeError"
    )

    # And the text fallback it falls back TO must still exist.
    assert ProjectBoardsScreen.ICON_EDIT, "the text fallback glyph is gone"
    assert not hasattr(screen, "edit_icon_image"), (
        "an uninitialised screen should not already carry the attribute — if "
        "it does, this test is asserting a class attribute, not __init__'s work"
    )


def test_card_release_selects_project_when_not_dragged():
    screen = ProjectBoardsScreen.__new__(ProjectBoardsScreen)
    screen._dragging_board_id = "board-1"
    screen._drag_pointer_start = (100, 100)
    screen._drag_threshold = 8

    selected = []
    screen.select_project = lambda board_id: selected.append(board_id)
    screen._board_id_at_pointer = lambda: None
    screen._reorder_cards = lambda source_id, target_id: (_ for _ in ()).throw(AssertionError("should not reorder"))

    event = type("Event", (), {"x_root": 101, "y_root": 102})()
    screen._on_card_release(event, "board-1")

    assert selected == ["board-1"]


def test_card_release_reorders_when_dragged():
    screen = ProjectBoardsScreen.__new__(ProjectBoardsScreen)
    screen._dragging_board_id = "board-1"
    screen._drag_pointer_start = (100, 100)
    screen._drag_threshold = 8

    reordered = []
    screen.select_project = lambda board_id: (_ for _ in ()).throw(AssertionError("should not select"))
    screen._board_id_at_pointer = lambda: "board-2"
    screen._reorder_cards = lambda source_id, target_id: reordered.append((source_id, target_id))

    event = type("Event", (), {"x_root": 120, "y_root": 100})()
    screen._on_card_release(event, "board-1")

    assert reordered == [("board-1", "board-2")]
