"""One wording for "filing this item here unfiles it from somewhere else".

Purpose: BP1/BP2 — an Action Item belongs to exactly one Project. Three
         surfaces file items (the item editor, the Scheduler's drag-drop, and
         the Projects screen's "link existing items" dialog) and they must all
         say the same thing before deleting links the user did not choose to
         delete (P2 — never silently drop).
Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp1
Tests:   tests/test_project_multi_link.py

The messages live here rather than in a dialog class so a test can read the
exact sentence the user is shown without building a window.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Iterable, List, Optional


def describe_single_relink(count: int, target_title: Optional[str],
                           clears_ape: bool = False) -> str:
    """What the user is about to lose by filing one item under one project.

    ``count`` is how many projects the item currently sits on. One is the
    ordinary case from the Projects screen (moving an item between two boards);
    more than one only happens on rows that predate exclusive filing.
    ``target_title`` is None when the project is being cleared instead.

    ``clears_ape`` says whether this item actually has an Annual Plan Element
    to lose. The sentence used to promise it unconditionally, so an item with
    no APE was warned about losing one (sweep pass 3).
    """
    ape_clause = (", and also clears the item's Annual Plan Element"
                  if clears_ape else "")
    if count == 0:
        # No link at all — the only thing at stake is the Annual Plan Element,
        # which clear_item_project_links also nulls (S2-2). Saying "filed under
        # another project" here would be simply untrue.
        return (
            "This item has an Annual Plan Element.\n\n"
            "Removing the project also clears it. Continue?"
        )

    if count == 1:
        # "filed under 1 projects ... removes it from the other 0" is what the
        # plural form produces here, and it reads as though nothing is at stake.
        filed = "This item is already filed under another project."
        if target_title:
            return (
                f"{filed}\n\n"
                f"Filing it under “{target_title}” removes that link. Continue?"
            )
        return f"{filed}\n\nClearing the project removes that link{ape_clause}. Continue?"

    others = count - 1
    plural = "project" if others == 1 else "projects"
    if target_title:
        return (
            f"This item is filed under {count} projects.\n\n"
            f"Filing it under “{target_title}” removes it from the other "
            f"{others} {plural}. Continue?"
        )
    return (
        f"This item is filed under {count} projects.\n\n"
        f"Clearing the project removes all of them{ape_clause}. Continue?"
    )


def describe_bulk_relink(item_count: int, target_title: Optional[str]) -> str:
    """What a batch link is about to unfile.

    ``item_count`` counts only the items that would actually lose a link, so
    the number the user reads is the number of items affected — not the size
    of the selection.
    """
    noun = "item is" if item_count == 1 else "items are"
    target = f"“{target_title}”" if target_title else "this project"
    return (
        f"{item_count} selected {noun} already filed under another project.\n\n"
        f"An Action Item belongs to exactly one Project, so filing under "
        f"{target} removes the existing links. Continue?"
    )


def describe_bulk_clear(filed_count: int, ape_only_count: int = 0) -> str:
    """What dropping a batch onto "No Project" destroys.

    Two different losses, counted separately. The sentence used to say "N
    dragged items are filed under a project" using the *total* number affected,
    which was false whenever part of the batch had only an Annual Plan Element
    to lose — and the single-item test never reached this branch to notice
    (sweep pass 3, P19).
    """
    total = filed_count + ape_only_count
    noun = "item" if total == 1 else "items"
    parts = []
    if filed_count:
        parts.append(f"{filed_count} filed under a project")
    if ape_only_count:
        plural = "" if ape_only_count == 1 else "s"
        parts.append(f"{ape_only_count} with an Annual Plan Element{plural}")
    return (
        f"{total} dragged {noun}: " + ", ".join(parts) + ".\n\n"
        "Removing the project clears the project link and the Annual Plan "
        "Element. Continue?"
    )


def items_losing_links(db_manager, item_ids: Iterable[str],
                       target_board_id: Optional[str]) -> List[str]:
    """Which of ``item_ids`` would lose something to this write.

    Purpose: sweep F1 — the Projects dialog asked before deleting links and the
             Scheduler's drag-drop did not, so the same destructive write was
             guarded on one surface and silent on the other (P5).
    Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp1
    Tests:   tests/test_project_multi_link.py::test_f1_dragging_onto_a_project_asks_before_unfiling

    Clearing (``target_board_id is None``) destroys more than the link:
    ``clear_item_project_links`` also nulls the item's Annual Plan Element. An
    item with an APE and no board row — routine, since the editor's Annual Plan
    field sets one directly — therefore counts as losing something even though
    it has no link to drop. Sweep pass 2 (S2-2): reading only the links meant
    exactly that item had its APE deleted with no question asked.
    """
    with_links, ape_only = classify_losses(db_manager, item_ids, target_board_id)
    return with_links + ape_only


def classify_losses(db_manager, item_ids: Iterable[str],
                    target_board_id: Optional[str]):
    """Split the affected items by *what* they would lose.

    Returns ``(with_links, ape_only)``. The two are counted separately because
    the sentence shown to the user names them separately — collapsing them into
    one number made the bulk-clear dialog claim items were "filed under a
    project" when their only loss was an Annual Plan Element (sweep pass 3).
    """
    with_links, ape_only = [], []
    for item_id in item_ids:
        others = [
            board_id
            for board_id in db_manager.get_project_board_ids_for_item(item_id)
            if board_id != target_board_id
        ]
        if others:
            with_links.append(item_id)
        elif target_board_id is None and _has_annual_plan_element(db_manager, item_id):
            ape_only.append(item_id)
    return with_links, ape_only


def _has_annual_plan_element(db_manager, item_id: str) -> bool:
    item = db_manager.get_action_item(item_id)
    return bool(item and item.annual_plan_element_id)


def confirm_exclusive_relink(parent, db_manager, item_ids: Iterable[str],
                             target_board_id: Optional[str]) -> bool:
    """Ask before an exclusive link (or a clear) deletes links.

    Returns True when nothing would be lost, so the ordinary case — an item
    with no project yet — is never interrupted. One question per batch.
    """
    item_ids = list(item_ids)
    with_links, ape_only = classify_losses(db_manager, item_ids, target_board_id)
    if not with_links and not ape_only:
        return True

    # Branch on whether this is a clear, not on whether the board title
    # resolved: an unreadable board is still a filing, and falling through to
    # the clearing wording told the user their Annual Plan Element was about to
    # go when it was not (S2-8).
    clearing = target_board_id is None
    title = None
    if not clearing:
        board = db_manager.get_project_board(target_board_id)
        title = board.title if board else "the selected project"

    if len(item_ids) == 1:
        only = (with_links + ape_only)[0]
        count = len(db_manager.get_project_board_ids_for_item(only))
        question = describe_single_relink(
            count, title,
            clears_ape=clearing and _has_annual_plan_element(db_manager, only))
    elif clearing:
        question = describe_bulk_clear(len(with_links), len(ape_only))
    else:
        question = describe_bulk_relink(len(with_links), title)
    return messagebox.askyesno("Change Project", question, parent=parent)


MULTI_LINK_NAMES_SHOWN = 5


def describe_outstanding_multi_links(count: int, items=None) -> str:
    """The report on rows that predate exclusive filing.

    Returns an empty string when there is nothing to report, so a caller can
    use the truthiness rather than compare to zero.

    ``items`` are the rows from ``get_items_on_multiple_project_boards``. They
    are named because a bare count is not actionable — sweep F4: the query that
    can say *which* items had no caller, so the user was given a number and no
    way to find what it referred to (P21).
    """
    if count <= 0:
        return ""
    noun = "item is" if count == 1 else "items are"
    text = (
        f"{count} action {noun} filed under more than one project. "
        "Filing is now exclusive, so each one is resolved the next time it is "
        "re-filed — nothing is removed until you choose a project for it."
    )
    if not items:
        return text

    shown = list(items)[:MULTI_LINK_NAMES_SHOWN]
    named = "; ".join(
        f"{row['title']} ({row['board_count']} projects)" for row in shown)
    if count > len(shown):
        named += f"; and {count - len(shown)} more"
    return f"{text}\n{named}"
