"""The application's name, in one place.

Purpose: make the displayed name a value rather than a literal repeated at
         every surface that shows it.
Spec:    daVIPA_rebrand_prompt.md
Tests:   tests/test_branding.py

Three surfaces render the name to a person — the window title, the sidebar
wordmark and the ``--selftest`` banner — and each held its own copy of the
string. A rename then meant finding all three, which is how a display name
drifts from the one in the packaging.

**Deliberately NOT the same value as the paths.** ``paths.APP_NAME`` is the
identifier for the user-data directory and must not follow a rebrand: changing
it silently moves where the app looks for its database, and every existing
install would look like data loss rather than a rename. The two are separate
constants on purpose, and the test asserts they are allowed to differ.
"""

from __future__ import annotations

#: The name shown to a person. Change this to rebrand the display surface.
#: Always "daVIPA" — capital V I P A, lowercase "da". Never expanded, and the
#: tagline is never appended to it.
APP_DISPLAY_NAME = "daVIPA"

#: The strapline. Shown beneath the wordmark; never part of the name itself.
APP_TAGLINE = "Vision - Planning - Action"


def window_title(mode_tag: str, day_of_week: str, date_str: str) -> str:
    """The main window's title bar.

    Purpose: one formatter, so the title cannot drift from the wordmark.
    Tests:   tests/test_branding.py::test_window_title_uses_the_display_name
    """
    return f"{APP_DISPLAY_NAME} {mode_tag} - {day_of_week}, {date_str}"
