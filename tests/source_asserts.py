"""AST helpers for the few checks that must inspect source.

Purpose: make an unavoidable source-text check unable to match prose.
Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md
Tests:   tests/test_source_asserts.py

A behavioural assertion is always preferred — call the thing, check the result
or the rows it wrote. Some checks cannot be: proving a UI method still reports
errors needs a fully built CustomTkinter screen with entry widgets populated,
which is a heavier and more brittle test than the one it replaces.

Where a source check is genuinely the only option, it must not be a substring
match. That is the shape that produced a guard dead for months:
``test_enhanced_deletion_protection`` greped ``delete_segment``'s source for
``vision_count``, a name removed when the return shape changed, and reported
green throughout. The same shape passes on a *comment* that happens to contain
the word, and fails on a rename that changed nothing that matters.

These helpers parse instead. ``calls_attribute(fn, "messagebox", "showerror")``
is true only for a real call; a docstring saying "we call messagebox.showerror"
does not satisfy it, and neither does a variable of that name.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Callable


def _tree(func: Callable) -> ast.AST:
    """Parse a function's own source, dedented so a method parses standalone."""
    return ast.parse(textwrap.dedent(inspect.getsource(func)))


def calls_attribute(func: Callable, obj: str, attr: str) -> bool:
    """Does ``func`` contain a real call to ``obj.attr(...)``?

    Matches the call, not the text: a docstring mentioning it, or a string
    literal containing it, does not count.
    """
    for node in ast.walk(_tree(func)):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if (
            isinstance(target, ast.Attribute)
            and target.attr == attr
            and isinstance(target.value, ast.Name)
            and target.value.id == obj
        ):
            return True
    return False


def calls_any_attribute(func: Callable, obj: str, attrs: tuple[str, ...]) -> bool:
    """``calls_attribute`` for a set of acceptable method names."""
    return any(calls_attribute(func, obj, attr) for attr in attrs)


def references_name(func: Callable, name: str) -> bool:
    """Is ``name`` used as a real identifier in ``func`` — not in a string?

    Covers a bare name (``CTkMessageBox(...)``) and an attribute access
    (``ctk.CTkMessageBox``), which is how the same class arrives by two routes.
    """
    for node in ast.walk(_tree(func)):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
    return False


def assigns_self_attribute(func: Callable, attr: str) -> bool:
    """Does ``func`` assign ``self.<attr>``?

    ``"selected_segments" in source`` was true of a comment, a docstring, or a
    method that merely *read* the attribute. This is true only of a write, which
    is what "the filter has something to write to" actually requires.
    """
    def _is_self_attr(target: ast.AST) -> bool:
        return (
            isinstance(target, ast.Attribute)
            and target.attr == attr
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        )

    for node in ast.walk(_tree(func)):
        if isinstance(node, ast.Assign):
            if any(_is_self_attr(t) for t in node.targets):
                return True
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if _is_self_attr(node.target):
                return True
        elif isinstance(node, (ast.For, ast.comprehension)):
            if _is_self_attr(getattr(node, "target", None)):
                return True
    return False


def calls_method_on_name(func: Callable, name: str, method: str) -> bool:
    """Does ``func`` call ``<name>.<method>(...)`` on a local or parameter?

    Distinct from ``calls_attribute`` only in intent — kept separate so a
    caller's assertion reads as what it means.
    """
    return calls_attribute(func, name, method)


def iterates_mapping(func: Callable, name: str) -> bool:
    """Does ``func`` call ``<name>.items()`` or ``<name>.values()``?

    The Settings screen's contract with ``delete_segment`` is that the second
    return value is a mapping. Asserting the *call* rather than the substring
    means a comment explaining the mapping does not satisfy it.
    """
    return calls_any_attribute(func, name, ("items", "values"))
