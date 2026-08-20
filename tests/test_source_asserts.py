"""The AST helpers must be able to say no — and must not say yes to prose.

Purpose: prove tests/source_asserts.py is not a no-op that passes on anything.
Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md
Tests:   this file

Every converted assertion in the suite reads ``assert calls_attribute(...)``.
A helper that always returned True would make all of them vacuous, and one that
always returned False would fail loudly (so it is the True direction that
matters). Both directions are asserted below.

The positive cases are deliberately hostile: a docstring naming the call, a
string literal containing it, a variable of the same name, and a read where a
write is required. Each is exactly what the substring checks these helpers
replaced would have accepted.
"""

from __future__ import annotations

import pytest

from tests.source_asserts import (
    assigns_self_attribute,
    calls_any_attribute,
    calls_attribute,
    iterates_mapping,
    references_name,
)


# --- subjects -------------------------------------------------------------
# Module-level so inspect.getsource sees a real function, and indented inside
# a class where the helpers must dedent before parsing.

class _Subject:
    def calls_it(self):
        messagebox.showerror("Title", "Body")

    def only_mentions_it(self):
        """We used to call messagebox.showerror here."""
        note = "messagebox.showerror"
        return note

    def calls_a_different_method(self):
        messagebox.showinfo("Title", "Body")

    def assigns_the_attribute(self):
        self.selected_segments = []

    def only_reads_the_attribute(self):
        return self.selected_segments

    def mentions_the_attribute_in_prose(self):
        """Sets selected_segments, honestly."""
        return "selected_segments"

    def uses_the_class(self):
        return CTkMessageBox(self)

    def uses_the_class_by_attribute(self):
        return ctk.CTkMessageBox(self)

    def only_names_it_in_a_string(self):
        """CTkMessageBox must never come back."""
        return "CTkMessageBox"

    def iterates_the_mapping(self):
        for key, value in counts.items():
            print(key, value)

    def sums_the_mapping(self):
        return sum(counts.values())

    def treats_it_as_a_scalar(self):
        return counts + 1

    def augments_the_attribute(self):
        self.selected_segments += ["x"]


# --- calls_attribute ------------------------------------------------------

def test_calls_attribute_finds_a_real_call():
    assert calls_attribute(_Subject.calls_it, "messagebox", "showerror")


def test_calls_attribute_ignores_a_docstring_and_a_string_literal():
    """The substring check this replaced accepted both."""
    assert not calls_attribute(_Subject.only_mentions_it, "messagebox", "showerror")


def test_calls_attribute_distinguishes_methods():
    assert not calls_attribute(_Subject.calls_a_different_method, "messagebox", "showerror")


def test_calls_any_attribute_accepts_either_method():
    assert calls_any_attribute(
        _Subject.calls_a_different_method, "messagebox", ("showerror", "showinfo")
    )
    assert not calls_any_attribute(
        _Subject.only_mentions_it, "messagebox", ("showerror", "showinfo")
    )


# --- references_name ------------------------------------------------------

def test_references_name_finds_both_call_routes():
    assert references_name(_Subject.uses_the_class, "CTkMessageBox")
    assert references_name(_Subject.uses_the_class_by_attribute, "CTkMessageBox")


def test_references_name_ignores_strings_and_docstrings():
    """This is the one asserted NEGATIVELY in the suite, so a helper that
    always returned True would make that assertion impossible to satisfy —
    but one that always returned False would make it vacuous."""
    assert not references_name(_Subject.only_names_it_in_a_string, "CTkMessageBox")


# --- assigns_self_attribute -----------------------------------------------

def test_assigns_self_attribute_requires_a_write():
    assert assigns_self_attribute(_Subject.assigns_the_attribute, "selected_segments")
    assert assigns_self_attribute(_Subject.augments_the_attribute, "selected_segments")


def test_assigns_self_attribute_rejects_a_read_or_a_mention():
    """`"selected_segments" in source` accepted all three of these."""
    assert not assigns_self_attribute(_Subject.only_reads_the_attribute, "selected_segments")
    assert not assigns_self_attribute(
        _Subject.mentions_the_attribute_in_prose, "selected_segments"
    )


# --- iterates_mapping -----------------------------------------------------

def test_iterates_mapping_accepts_items_and_values():
    assert iterates_mapping(_Subject.iterates_the_mapping, "counts")
    assert iterates_mapping(_Subject.sums_the_mapping, "counts")


def test_iterates_mapping_rejects_scalar_use():
    """The regression it guards: delete_segment going back to a scalar."""
    assert not iterates_mapping(_Subject.treats_it_as_a_scalar, "counts")


# --- the helpers must work on real, indented methods ----------------------

def test_the_helpers_parse_a_real_method_from_the_app():
    """Adversarial: these run against source dedented out of a class body.

    A helper that raised IndentationError on a real method would take every
    converted assertion down with it — loudly, but only once someone ran it.
    """
    from src.getmoredone.screens.vps_editors import TLVisionEditorDialog

    assert calls_any_attribute(
        TLVisionEditorDialog.save_vision, "messagebox", ("showerror", "showinfo")
    ), "the helper cannot see a call it should see in real app source"


def test_the_helpers_reject_a_name_absent_from_real_source():
    """The other direction, on the same real method."""
    from src.getmoredone.screens.vps_editors import TLVisionEditorDialog

    assert not references_name(TLVisionEditorDialog.save_vision, "ThisNameIsNotThere")
