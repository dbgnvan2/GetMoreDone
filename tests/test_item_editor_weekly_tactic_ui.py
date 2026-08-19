"""WT-M6.A — the Edit Action -> Org tab shows the real Weekly Tactic.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6a

The combo this replaces read the legacy ``week_actions`` table, which is empty
on every database, so it could never show anything (WT-F7).
"""

from pathlib import Path
from types import SimpleNamespace

from src.getmoredone.screens.item_editor import ItemEditorDialog
from tests.weekly_tactic_fixtures import (
    make_daily_item,
    make_vps,
    make_week_item,
    seed_ape,
)

EDITOR_SOURCE = (
    Path(__file__).resolve().parents[1] / "src" / "getmoredone" / "screens" / "item_editor.py"
)


def _editor_stub(manager, item, vps=None):
    """Enough of the dialog to drive the Org-tab methods without a display."""
    labels = []
    return SimpleNamespace(
        NO_TACTIC_TEXT=ItemEditorDialog.NO_TACTIC_TEXT,
        db_manager=manager,
        vps_manager=vps,
        item=item,
        item_id=item.id if item else None,
        weekly_tactic_label=SimpleNamespace(
            configure=lambda **kw: labels.append(kw.get("text"))),
        _labels=labels,
    ), labels


def test_wt_m6a1_org_tab_never_queries_legacy_table(tmp_path):
    """Intercepting the legacy week_actions readers records zero calls."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        calls = []
        for name in ("get_week_actions", "get_week_actions_in_range",
                     "get_week_action_months"):
            original = getattr(vps, name)
            setattr(vps, name, (lambda n: (lambda *a, **k: (calls.append(n), [])[1]))(name))

        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id)
        item = make_daily_item(vps, "Task")
        stored = manager.get_action_item(item.id)
        stored.weekly_tactic_id = tactic.id
        manager.update_action_item(stored)

        stub, _ = _editor_stub(manager, manager.get_action_item(item.id), vps)
        ItemEditorDialog.refresh_weekly_tactic_display(stub)
        ItemEditorDialog.load_week_actions(stub)

        assert calls == [], f"the Org tab still reads the legacy table: {calls}"
    finally:
        vps.close()


def test_wt_m6a1_the_legacy_loader_is_a_no_op():
    """load_week_actions is kept as a public no-op, not left querying."""
    source = EDITOR_SOURCE.read_text(encoding="utf-8")
    body = source.split("def load_week_actions(self):")[1].split("\n    def ")[0]
    assert "get_week_actions" not in body
    assert "week_action_combo" not in body


def test_wt_m6a2_org_tab_shows_current_tactic_or_none(tmp_path):
    """The linked tactic's title, or an explicit "(none)"."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = make_daily_item(vps, "Task", start="2026-02-25", due="2026-02-25")

        # Unlinked first.
        stub, labels = _editor_stub(manager, manager.get_action_item(item.id), vps)
        ItemEditorDialog.refresh_weekly_tactic_display(stub)
        assert labels[-1] == "(none)"

        stored = manager.get_action_item(item.id)
        stored.weekly_tactic_id = tactic.id
        manager.update_action_item(stored)

        stub, labels = _editor_stub(manager, manager.get_action_item(item.id), vps)
        ItemEditorDialog.refresh_weekly_tactic_display(stub)
        shown = labels[-1]
        assert tactic.title in shown
        assert "2026-02-23" in shown and "2026-03-01" in shown
    finally:
        vps.close()


def test_wt_m6a2_stale_stamp_is_surfaced(tmp_path):
    """WT-M3.A.4 — a stamp whose tactic was deleted is shown, not hidden."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = make_daily_item(vps, "Task", start="2026-02-25", due="2026-02-25")
        stored = manager.get_action_item(item.id)
        stored.weekly_tactic_id = tactic.id
        manager.update_action_item(stored)

        manager.delete_action_item(tactic.id)

        stub, labels = _editor_stub(manager, manager.get_action_item(item.id), vps)
        ItemEditorDialog.refresh_weekly_tactic_display(stub)
        assert "(none)" in labels[-1]
        assert "2026-02-23" in labels[-1], "the orphaned stamp must be visible"
    finally:
        vps.close()


def test_wt_m6a3_manual_stamp_edit_reaches_db_layer(tmp_path):
    """The stamp widget's value must arrive at update_action_item (P25).

    A control that renders but is never passed through is decoration.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id, start="2026-02-23", due="2026-03-01")
        item = make_daily_item(vps, "Task", start="2026-02-25", due="2026-02-25")
        stored = manager.get_action_item(item.id)
        stored.weekly_tactic_id = tactic.id
        manager.update_action_item(stored)

        captured = {}
        original = manager.update_action_item

        def _intercept(target, *args, **kwargs):
            captured["weekly_tactic_start_date"] = target.weekly_tactic_start_date
            return original(target, *args, **kwargs)

        manager.update_action_item = _intercept
        try:
            edited = manager.get_action_item(item.id)
            edited.weekly_tactic_start_date = "2026-01-05"   # the widget's value
            manager.update_action_item(edited)
        finally:
            manager.update_action_item = original

        assert captured["weekly_tactic_start_date"] == "2026-01-05"
        assert manager.get_action_item(item.id).weekly_tactic_start_date == "2026-01-05"
    finally:
        vps.close()


def test_wt_m6a3_the_save_path_reads_the_stamp_widget():
    """And the editor's own save reads that widget, not something else."""
    source = EDITOR_SOURCE.read_text(encoding="utf-8")
    save_body = source.split("def save_item(")[1].split("\n    def ")[0]
    assert "self.weekly_tactic_start_var.get()" in save_body, (
        "the Org tab's stamp field is never read on save"
    )
    assert "item.weekly_tactic_start_date" in save_body


def test_wt_m6a4_picker_can_reach_any_week(tmp_path):
    """WT-F14 — any week must be reachable, not only anchor -21/+7 days."""
    from src.getmoredone.screens.item_editor_weekly_tactic_dialog import SetWeeklyTacticDialog

    source = EDITOR_SOURCE.read_text(encoding="utf-8")
    assert "_get_week_window_range" in source

    # The picker offers month and all-weeks filters, so a tactic outside the
    # rolling window is selectable. WT-F14 described the Org-tab combo, which
    # WT-M6.A has now removed entirely.
    for name in ("_set_month_range", "_set_all_weeks_range", "_set_specific_week_range"):
        assert hasattr(SetWeeklyTacticDialog, name), f"{name} is the escape from the window"

    vps = make_vps(tmp_path)
    try:
        ape_id = seed_ape(vps)
        far = make_week_item(vps, ape_id, start="2027-06-07", due="2027-06-13",
                             title="Far future")
        bounds = vps.get_weekly_action_item_bounds()
        assert bounds is not None
        assert bounds[1] >= "2027-06-07", (
            "the all-weeks range must include a tactic far outside the rolling window"
        )
        months = {(row["year"], row["month"]) for row in vps.get_weekly_action_item_months()}
        assert (2027, 6) in months, "the month filter must offer that tactic's month"
    finally:
        vps.close()
