"""WT-M6.C — Project Boards exposes the new start and end dates.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6c
"""

from pathlib import Path
from types import SimpleNamespace

from src.getmoredone.models import ProjectBoard
from src.getmoredone.screens.project_boards import ProjectBoardEditorDialog
from tests.weekly_tactic_fixtures import make_vps, seed_ape


def test_wt_m6c1_project_dates_reach_db_layer(tmp_path):
    """Entering dates and saving must reach the board update call (P25).

    Driven through the dialog's own ``save``, so a field that renders but is
    never read fails here rather than looking fine.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = ProjectBoard(title="Existing", annual_plan_element_id=ape_id)
        manager.create_project_board(board)

        stub = SimpleNamespace(
            board=manager.get_project_board(board.id),
            title_var=SimpleNamespace(get=lambda: "Existing"),
            ape_var=SimpleNamespace(get=lambda: "label"),
            ape_label_to_id={"label": ape_id},
            priority_var=SimpleNamespace(get=lambda: ""),
            status_var=SimpleNamespace(get=lambda: "active"),
            next_step_var=SimpleNamespace(get=lambda: ""),
            notes_box=SimpleNamespace(get=lambda *a: ""),
            start_date_var=SimpleNamespace(get=lambda: "2026-03-01"),
            end_date_var=SimpleNamespace(get=lambda: "2026-09-30"),
            _extract_factor_value=lambda _v: None,
            result=None,
            destroy=lambda: None,
        )
        ProjectBoardEditorDialog.save(stub)

        assert stub.result is not None, "the dialog produced no board"
        assert stub.result.start_date == "2026-03-01"
        assert stub.result.end_date == "2026-09-30"

        manager.update_project_board(stub.result)
        stored = manager.get_project_board(board.id)
        assert stored.start_date == "2026-03-01"
        assert stored.end_date == "2026-09-30"
    finally:
        vps.close()


def test_wt_m6c1_blank_dates_clear_rather_than_store_empty_strings(tmp_path):
    """Clearing a field stores NULL, not ''."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = ProjectBoard(title="Dated", annual_plan_element_id=ape_id,
                             start_date="2026-03-01", end_date="2026-09-30")
        manager.create_project_board(board)

        stub = SimpleNamespace(
            board=manager.get_project_board(board.id),
            title_var=SimpleNamespace(get=lambda: "Dated"),
            ape_var=SimpleNamespace(get=lambda: "label"),
            ape_label_to_id={"label": ape_id},
            priority_var=SimpleNamespace(get=lambda: ""),
            status_var=SimpleNamespace(get=lambda: "active"),
            next_step_var=SimpleNamespace(get=lambda: ""),
            notes_box=SimpleNamespace(get=lambda *a: ""),
            start_date_var=SimpleNamespace(get=lambda: "  "),
            end_date_var=SimpleNamespace(get=lambda: ""),
            _extract_factor_value=lambda _v: None,
            result=None,
            destroy=lambda: None,
        )
        ProjectBoardEditorDialog.save(stub)
        manager.update_project_board(stub.result)

        stored = manager.get_project_board(board.id)
        assert stored.start_date is None
        assert stored.end_date is None
    finally:
        vps.close()


def test_wt_m6c1_the_editor_builds_both_date_fields():
    """The controls exist alongside the wiring, not instead of it."""
    source = (Path(__file__).resolve().parents[1] / "src" / "getmoredone"
              / "screens" / "project_boards.py").read_text(encoding="utf-8")
    build = source.split("def _build(self):")[1].split("\n    def ")[0]
    assert "self.start_date_var" in build
    assert "self.end_date_var" in build
