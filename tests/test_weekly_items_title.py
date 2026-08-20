"""BP6 — a related Action Item is titled what the user typed.

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#bp6

The Weekly Items screen used to compose ``<tactic context> - <title>``. No
screen has offered a Context field for some time, and ``lineage_for_item``
resolves an item's segment/subsegment/category from its Annual Plan Element
first and its parent second — the title prefix is only the third choice, and
these rows carry both of the first two. So the prefix changed what got stored
without changing anything the app reads.

The lineage assertions matter more than the title one: the title change is only
safe because lineage never depended on it, and that is what these tests pin.
"""

from types import SimpleNamespace

import pytest

from src.getmoredone.screens.item_lineage import lineage_for_item
from src.getmoredone.screens.weekly_items import WeeklyItemsScreen
from tests.weekly_tactic_fixtures import make_vps, make_week_item, seed_ape


def _screen_stub(vps, weekly_row, typed):
    """Enough of WeeklyItemsScreen to drive the create method without a display."""
    status = []
    stub = SimpleNamespace(
        vps_manager=vps,
        app=SimpleNamespace(db_manager=vps.db_manager),
        selected_weekly_item=weekly_row,
        status_label=SimpleNamespace(configure=lambda **kw: status.append(kw.get("text"))),
    )
    stub._status = status
    stub._typed = typed
    return stub


def _create(stub, monkeypatch):
    """Run the real method with the input dialog answering ``stub._typed``."""
    import src.getmoredone.screens.weekly_items as wi

    monkeypatch.setattr(
        wi.ctk, "CTkInputDialog",
        lambda *a, **kw: SimpleNamespace(get_input=lambda: stub._typed))
    WeeklyItemsScreen.create_action_item_for_selected_weekly(stub)
    items = stub.app.db_manager.get_all_items(status_filter="open")
    return [item for item in items if item.item_type == "daily"]


def _weekly_row(tactic, ape_id, title):
    return {
        "id": tactic.id,
        "title": title,
        "who": "Self",
        "start_date": tactic.start_date,
        "category": None,
        "annual_plan_element_id": ape_id,
    }


@pytest.mark.parametrize("weekly_title", [
    # The canonical shape: no context is found in it today either.
    "PW|LS|Blog - W34",
    # The legacy shape — a body after the week number. This is the one that
    # used to produce "PW|LS|Blog - W34 - Draft the outline".
    "PW|LS|Blog - W34 - Publish the March post",
])
def test_bp6_the_title_is_what_the_user_typed(tmp_path, monkeypatch, weekly_title):
    vps = make_vps(tmp_path)
    try:
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id)
        stub = _screen_stub(vps, _weekly_row(tactic, ape_id, weekly_title),
                            "Draft the outline")

        created = _create(stub, monkeypatch)

        assert len(created) == 1
        assert created[0].title == "Draft the outline", (
            "the tactic's context is being prefixed onto the user's words again")
    finally:
        vps.close()


def test_bp6_lineage_still_resolves_without_the_prefix(tmp_path, monkeypatch):
    """The prefix was a lineage fallback; the APE is what actually answers."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id)
        stub = _screen_stub(
            vps, _weekly_row(tactic, ape_id, "PW|LS|Blog - W34 - Publish the March post"),
            "Draft the outline")

        created = _create(stub, monkeypatch)
        item = created[0]

        segment, subsegment, category = lineage_for_item(item, manager, {}, {}, {})
        assert segment and subsegment and category, (
            f"the unprefixed item has no lineage at all: {(segment, subsegment, category)}")
        assert subsegment == "Living Systems"
        assert category == "Blog"
    finally:
        vps.close()


def test_bp6_lineage_survives_even_with_the_annual_plan_element_missing(tmp_path, monkeypatch):
    """The second fallback — the parent tactic — still answers on its own.

    Without this, "the APE covers it" would be a single point of failure the
    prefix used to back up.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id)
        stub = _screen_stub(
            vps, _weekly_row(tactic, ape_id, "PW|LS|Blog - W34 - Publish the March post"),
            "Draft the outline")

        item = _create(stub, monkeypatch)[0]
        item.annual_plan_element_id = None

        segment, subsegment, category = lineage_for_item(item, manager, {}, {}, {})
        assert (segment, subsegment, category) != ("", "", ""), (
            "with no APE the item falls through to the parent tactic, and did not")
        assert category == "Blog"
    finally:
        vps.close()


def test_bp6_the_description_still_names_the_tactic(tmp_path, monkeypatch):
    """Dropping the prefix must not drop the only human trace of where it came from."""
    vps = make_vps(tmp_path)
    try:
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id)
        weekly_title = "PW|LS|Blog - W34 - Publish the March post"
        stub = _screen_stub(vps, _weekly_row(tactic, ape_id, weekly_title),
                            "Draft the outline")

        item = _create(stub, monkeypatch)[0]

        assert weekly_title in (item.description or "")
        assert item.parent_id == tactic.id
    finally:
        vps.close()
