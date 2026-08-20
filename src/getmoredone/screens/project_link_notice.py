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

from typing import Optional


def describe_single_relink(count: int, target_title: Optional[str]) -> str:
    """What the user is about to lose by filing one item under one project.

    ``count`` is how many projects the item currently sits on. One is the
    ordinary case from the Projects screen (moving an item between two boards);
    more than one only happens on rows that predate exclusive filing.
    ``target_title`` is None when the project is being cleared instead.
    """
    if count <= 1:
        # "filed under 1 projects ... removes it from the other 0" is what the
        # plural form produces here, and it reads as though nothing is at stake.
        filed = "This item is already filed under another project."
        if target_title:
            return (
                f"{filed}\n\n"
                f"Filing it under “{target_title}” removes that link. Continue?"
            )
        return f"{filed}\n\nClearing the project removes that link. Continue?"

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
        "Clearing the project removes all of them. Continue?"
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


def describe_outstanding_multi_links(count: int) -> str:
    """The start-up report: rows that predate exclusive filing.

    Returns an empty string when there is nothing to report, so a caller can
    use the truthiness rather than compare to zero.
    """
    if count <= 0:
        return ""
    noun = "item is" if count == 1 else "items are"
    return (
        f"{count} action {noun} filed under more than one project. "
        "Filing is now exclusive, so each one is resolved the next time it is "
        "re-filed — nothing is removed until you choose a project for it."
    )
