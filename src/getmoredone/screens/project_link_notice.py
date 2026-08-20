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


# What happens to the item's Annual Plan Element. "replaced" only when the
# target board actually has one to put there — filing under a project with no
# plan element clears it, and saying "replaces" there is simply false.
APE_UNCHANGED, APE_CLEARED, APE_REPLACED = None, "cleared", "replaced"


def describe_single_relink(count: int, target_title: Optional[str],
                           ape_outcome: Optional[str] = APE_UNCHANGED) -> str:
    """What the user is about to lose by filing one item under one project.

    ``count`` is how many projects the item currently sits on. One is the
    ordinary case from the Projects screen (moving an item between two boards);
    more than one only happens on rows that predate exclusive filing.
    ``target_title`` is None when the project is being cleared instead.

    ``ape_outcome`` says what this write does to the item's Annual Plan
    Element: nothing, clears it, or replaces it with the board's. The sentence
    used to promise a loss unconditionally, so an item with no plan element was
    warned about losing one (sweep pass 3); it then covered only the clearing
    direction, so filing swapped one with no mention at all (cold sweep); and a
    single boolean then called filing under a plan-element-less project a
    "replace" when it is a clear.
    """
    # Clearing the project can only ever clear the plan element — there is no
    # board to take one from. Deriving the clause from the direction as well as
    # the outcome means a caller cannot produce "clearing … replaces it", which
    # an exhaustive walk of these branches showed the outcome flag alone could.
    if ape_outcome == APE_UNCHANGED:
        ape_clause = ""
    elif target_title and ape_outcome == APE_REPLACED:
        ape_clause = ", and replaces its Annual Plan Element with the project's"
    else:
        ape_clause = ", and clears the item's Annual Plan Element"
    if count == 0:
        # No link at all — the only thing at stake is the Annual Plan Element,
        # so if this write will not move it there is nothing to ask about.
        # The branch used to assert the loss unconditionally, which defeated
        # the caller's ``ape_known`` guard and told the user their plan element
        # was going when the write would not touch it (sweep pass 8).
        if ape_outcome == APE_UNCHANGED:
            # Unreachable through ``confirm_exclusive_relink``, which no longer
            # classifies an item as losing a plan element it will keep. Kept
            # truthful rather than removed, because "no caller produces this"
            # is what the next caller changes.
            return "This item is about to be re-filed.\n\nContinue?"
        if target_title:
            # Filing replaces it with the board's — unless the board has none,
            # in which case it clears it, and "replaces" is a false promise
            # about the one thing this dialog exists to disclose.
            outcome = ("replaces that with the project's"
                       if ape_outcome == APE_REPLACED else "clears it")
            # (target_title is set here, so APE_REPLACED really is a replace.)
            return (
                "This item has its own Annual Plan Element.\n\n"
                f"Filing it under “{target_title}” {outcome}. Continue?"
            )
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
                f"Filing it under “{target_title}” removes that link"
                f"{ape_clause}. Continue?"
            )
        return f"{filed}\n\nClearing the project removes that link{ape_clause}. Continue?"

    others = count - 1
    plural = "project" if others == 1 else "projects"
    if target_title:
        return (
            f"This item is filed under {count} projects.\n\n"
            f"Filing it under “{target_title}” removes it from the other "
            f"{others} {plural}{ape_clause}. Continue?"
        )
    return (
        f"This item is filed under {count} projects.\n\n"
        f"Clearing the project removes all of them{ape_clause}. Continue?"
    )


def describe_bulk_relink(item_count: int, target_title: Optional[str],
                         verb: str = "selected",
                         ape_outcome: Optional[str] = APE_UNCHANGED,
                         ape_only_count: int = 0) -> str:
    """What a batch link is about to unfile.

    ``item_count`` counts the items that would lose a *link*;
    ``ape_only_count`` those whose only loss is their Annual Plan Element. Both
    are needed, because a batch can consist entirely of the second kind — three
    loose items each carrying their own plan element, filed under a project
    with a different one. Counting only the first produced "**0** selected
    items are already filed under another project" while three plan elements
    were replaced, with no mention of them: both halves of the sentence false
    at once, and the same defect the single-item path had fixed one commit
    earlier (P5).

    ``verb`` is how the user produced the batch: the Projects dialog has a
    selection, the Scheduler has a drag, and telling someone who just dragged
    three items about "3 selected items" describes an action they did not take.
    """
    total = item_count + ape_only_count
    if not total:
        # Nothing at stake produces no sentence, the way describe_bulk_clear
        # already behaves — rather than "0 selected items are ...".
        return ""

    # Two buckets, named separately — the same shape describe_bulk_clear uses.
    # Printing the *total* against "already filed under another project" was
    # false for the items filed under nothing; printing only ``item_count`` was
    # false about the size of the loss. Each count now sits against the clause
    # it is true of (P19).
    noun = "item" if total == 1 else "items"
    target = "\u201c%s\u201d" % target_title if target_title else "this project"
    parts = []
    if item_count:
        parts.append("%d already filed under another project" % item_count)
    if ape_only_count:
        parts.append("%d carrying %s" % (
            ape_only_count,
            "an Annual Plan Element of its own" if ape_only_count == 1
            else "Annual Plan Elements of their own"))

    if ape_outcome == APE_UNCHANGED:
        ape_phrase = ""
    elif target_title and ape_outcome == APE_REPLACED:
        ape_phrase = ("replaces its Annual Plan Element with the project's"
                      if total == 1
                      else "replaces each item's Annual Plan Element with the project's")
    else:
        ape_phrase = ("clears its Annual Plan Element" if total == 1
                      else "clears each item's Annual Plan Element")

    does = []
    if item_count:
        does.append("removes the existing links")
    if ape_phrase:
        does.append(ape_phrase)

    return (
        "%d %s %s: %s.\n\n"
        "An Action Item belongs to exactly one Project, so filing under "
        "%s %s. Continue?" % (total, verb, noun, ", ".join(parts),
                              target, " and ".join(does))
    )


def describe_bulk_clear(filed_count: int, ape_only_count: int, ape_total: int,
                        batch_size: Optional[int] = None,
                        verb: str = "dragged") -> str:
    """What dropping a batch onto "No Project" destroys.

    Two different losses, counted separately. The sentence used to say "N
    dragged items are filed under a project" using the *total* number affected,
    which was false whenever part of the batch had only an Annual Plan Element
    to lose — and the single-item test never reached this branch to notice
    (sweep pass 3, P19).
    """
    total = filed_count + ape_only_count
    if not total:
        return ""

    # ``ape_total`` is how many of the affected items lose an Annual Plan
    # Element, and it is required rather than defaulted: it is NOT the same
    # number as ``ape_only_count``. ``clear_item_project_links`` nulls the APE
    # of every item it touches, and an item filed under an APE-bearing board
    # has one. Defaulting it to the ape-only bucket made this sentence promise
    # less than the write performs — an under-warning before a destructive
    # action (sweep pass 5, P2/P5) — so there is no default to fall into.
    #
    # The noun is pluralised from the size of the *batch*, not from the number
    # affected: "1 of the dragged item" is what the affected count produces
    # when two items are dragged and one of them has something to lose.
    noun = "item" if (batch_size or total) == 1 else "items"
    parts = []
    losses = []
    if filed_count:
        parts.append(f"{filed_count} filed under a project")
        losses.append("the project link")
    if ape_only_count:
        # "an Annual Plan Elements" — the article has to go with the plural.
        parts.append(f"{ape_only_count} with an Annual Plan Element"
                     if ape_only_count == 1
                     else f"{ape_only_count} with Annual Plan Elements")
    if ape_total:
        losses.append("the Annual Plan Element")
    # "of the dragged items", not "dragged items": this is the number that
    # loses something, not the size of the drag (sweep pass 4).
    return (
        f"{total} of the {verb} {noun}: " + ", ".join(parts) + ".\n\n"
        f"Removing the project clears {' and '.join(losses)}. Continue?"
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
                    target_board_id: Optional[str], ape_known: bool = True):
    """Split the affected items by *what* they would lose.

    Returns ``(with_links, ape_only)``. The two are counted separately because
    the sentence shown to the user names them separately — collapsing them into
    one number made the bulk-clear dialog claim items were "filed under a
    project" when their only loss was an Annual Plan Element (sweep pass 3).

    "Losing something" covers both directions, not just clearing. Filing an
    item under a project *overwrites* its Annual Plan Element with the board's
    (``link_item_to_project_exclusive`` step 3), so an item carrying its own
    APE — routine, the editor's Annual Plan field sets one directly — has that
    replaced. Reading only the links meant exactly that item was classified as
    losing nothing and its plan element was destroyed with no dialog: the same
    class this module closed for clearing and left open for filing (P5).
    """
    with_links, ape_only = [], []
    target_ape = None
    if target_board_id is not None:
        board = db_manager.get_project_board(target_board_id)
        target_ape = board.annual_plan_element_id if board else None

    for item_id in item_ids:
        others = [
            board_id
            for board_id in db_manager.get_project_board_ids_for_item(item_id)
            if board_id != target_board_id
        ]
        if _is_weekly_tactic(db_manager, item_id) and target_board_id is not None:
            # Filing is refused for a tactic, so there is nothing to warn about
            # and nothing to consent to.
            continue
        if others:
            with_links.append(item_id)
        elif ape_known and _ape_would_change(db_manager, item_id, target_ape):
            ape_only.append(item_id)
    return with_links, ape_only


def _bulk_ape_outcome(db_manager, item_ids, target_ape: Optional[str]) -> Optional[str]:
    """The outcome shared by a batch, or nothing if no item's APE moves."""
    outcomes = {_ape_outcome(db_manager, i, target_ape) for i in item_ids}
    outcomes.discard(APE_UNCHANGED)
    if not outcomes:
        return APE_UNCHANGED
    # A mixed batch is described by the destructive half.
    return APE_CLEARED if APE_CLEARED in outcomes else APE_REPLACED


def _ape_would_change(db_manager, item_id: str, target_ape: Optional[str]) -> bool:
    """Would this write replace or remove the item's Annual Plan Element?"""
    return _ape_outcome(db_manager, item_id, target_ape) is not APE_UNCHANGED


def ape_outcome_for_change(db_manager, item_id: Optional[str],
                           target_board_id: Optional[str]) -> Optional[str]:
    """What filing under (or clearing) ``target_board_id`` does to the item's APE.

    The single implementation of the rule, including the unreadable-board case:
    ``link_item_to_project_exclusive`` guards its APE write with ``if board:``,
    so a board row that cannot be read means the plan element is not touched
    and the dialog must not say it is.
    """
    if not item_id:
        return APE_UNCHANGED
    target_ape = None
    if target_board_id is not None:
        board = db_manager.get_project_board(target_board_id)
        if board is None:
            return APE_UNCHANGED
        target_ape = board.annual_plan_element_id
    return _ape_outcome(db_manager, item_id, target_ape)


def _ape_outcome(db_manager, item_id: str, target_ape: Optional[str]) -> Optional[str]:
    """What this write does to the item's Annual Plan Element.

    A Weekly Tactic keeps its plan element whatever happens (PL6, enforced in
    ``db_manager_project_boards``): filing one is refused outright and clearing
    leaves the APE alone. The writer learned that rule and the describer did
    not, so dragging a tactic onto "No Project" showed "Removing the project
    also clears it" over a write that changed nothing — an affirmative
    confirmation in front of a silent no-op (P19: the two layers disagreed
    about the same rule).
    """
    if _is_weekly_tactic(db_manager, item_id):
        return APE_UNCHANGED
    item = db_manager.get_action_item(item_id)
    current = getattr(item, "annual_plan_element_id", None) if item else None
    if not current or current == target_ape:
        return APE_UNCHANGED
    return APE_REPLACED if target_ape else APE_CLEARED


def _is_weekly_tactic(db_manager, item_id: str) -> bool:
    checker = getattr(db_manager, "is_weekly_tactic", None)
    if checker is None:          # a stub without the predicate
        return False
    return bool(checker(item_id))


def has_annual_plan_element(db_manager, item_id: Optional[str]) -> bool:
    """Does this item have an Annual Plan Element that a clear would destroy?"""
    if not item_id:
        return False
    item = db_manager.get_action_item(item_id)
    return bool(item and item.annual_plan_element_id)


def confirm_exclusive_relink(parent, db_manager, item_ids: Iterable[str],
                             target_board_id: Optional[str],
                             verb: str = "selected") -> bool:
    """Ask before an exclusive link (or a clear) deletes links.

    Returns True when nothing would be lost, so the ordinary case — an item
    with no project yet — is never interrupted. One question per batch.
    """
    item_ids = list(item_ids)

    # Branch on whether this is a clear, not on whether the board title
    # resolved: an unreadable board is still a filing, and falling through to
    # the clearing wording told the user their Annual Plan Element was about to
    # go when it was not (S2-8).
    clearing = target_board_id is None
    title = None
    target_ape = None
    # An unreadable board row means the write will not touch the item's Annual
    # Plan Element at all — ``link_item_to_project_exclusive`` guards that step
    # with ``if board:``. That has to be decided *before* the items are
    # classified, or an item whose only "loss" is a plan element the write will
    # not touch still triggers a dialog, with nothing true left to say in it.
    ape_known = clearing
    if not clearing:
        board = db_manager.get_project_board(target_board_id)
        # ``or``, not a None check: a board saved with an empty title made
        # ``title`` falsy, and every branch below reads a falsy title as "this
        # is a clear" — so filing under it would have been described as
        # clearing the project (P14: an empty value read as a different state).
        title = (board.title if board else "") or "the selected project"
        target_ape = board.annual_plan_element_id if board else None
        ape_known = board is not None

    with_links, ape_only = classify_losses(
        db_manager, item_ids, target_board_id, ape_known=ape_known)
    if not with_links and not ape_only:
        return True

    if len(item_ids) == 1:
        only = (with_links + ape_only)[0]
        count = len(db_manager.get_project_board_ids_for_item(only))
        question = describe_single_relink(
            count, title,
            ape_outcome=(_ape_outcome(db_manager, only, target_ape)
                         if ape_known else APE_UNCHANGED))
    elif clearing:
        question = describe_bulk_clear(
            len(with_links), len(ape_only),
            ape_total=sum(1 for item_id in with_links + ape_only
                          if has_annual_plan_element(db_manager, item_id)),
            batch_size=len(item_ids), verb=verb,
        )
    else:
        question = describe_bulk_relink(
            len(with_links), title, verb=verb,
            ape_only_count=len(ape_only),
            ape_outcome=(_bulk_ape_outcome(
                db_manager, with_links + ape_only, target_ape)
                if ape_known else APE_UNCHANGED))
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
