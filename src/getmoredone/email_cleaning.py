"""Clean imported email bodies before they land in an Action Item description.

Removes excess blank lines, decorative separator lines, and trailing footer
boilerplate (unsubscribe blocks, "you received this because…", copyright lines,
etc.). The *editorial* vocabulary — which phrases mark a footer, what a separator
line looks like — lives in ``email_cleaning_rules.json`` beside this module
(rule 9: editorial content belongs in config, not source), so it can be tuned
without touching code.

Purpose: strip email chrome so the Action Item description holds just the message.
Spec:    user request 2026-07-17 — "remove excess/extra lines and footer info".
Tests:   tests/test_email_cleaning.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

_RULES_PATH = Path(__file__).parent / "email_cleaning_rules.json"

# Default fallback used only if the rules file is missing/unreadable, so the
# importer never hard-fails on a packaging glitch (P2: surface, don't crash).
_DEFAULT_RULES = {
    "footer_start_phrases": ["unsubscribe"],
    "footer_start_regexes": [],
    "separator_line_regex": r"^\s*[-_=*~•·—–]{4,}\s*$",
    "min_content_lines_before_footer": 1,
    "max_consecutive_blank_lines": 1,
}


def _load_rules() -> dict:
    try:
        with open(_RULES_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return dict(_DEFAULT_RULES)


_RULES = _load_rules()


def clean_email_body(text: Optional[str], rules: Optional[dict] = None) -> str:
    """Return ``text`` with separators, footer boilerplate and excess blank lines removed.

    Args:
        text:  raw plain-text email body (may be ``None``/empty).
        rules: override rule dict (defaults to the bundled JSON); mainly for tests.

    The body up to the first footer marker is preserved verbatim (aside from
    blank-line collapsing); everything from the footer marker onward is dropped.
    A footer marker is only honoured once at least
    ``min_content_lines_before_footer`` real content lines have been seen, so a
    message whose very first line happens to say "unsubscribe" is not gutted.
    """
    if not text:
        return ""

    rules = rules or _RULES

    # Normalise newlines and invisible whitespace often left by HTML→text.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = (text.replace(" ", " ")   # non-breaking space
                .replace("​", "")     # zero-width space
                .replace("‌", "")     # zero-width non-joiner
                .replace("﻿", ""))    # BOM / zero-width no-break space

    footer_phrases = [p.lower() for p in rules.get("footer_start_phrases", [])]
    footer_regexes = [re.compile(p, re.I) for p in rules.get("footer_start_regexes", [])]
    sep_re = re.compile(rules.get("separator_line_regex", _DEFAULT_RULES["separator_line_regex"]))
    min_content = int(rules.get("min_content_lines_before_footer", 1))
    max_blanks = int(rules.get("max_consecutive_blank_lines", 1))

    lines = text.split("\n")

    # 1) Truncate at the first footer marker that appears after real content.
    cut = None
    content_seen = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        is_footer = content_seen >= min_content and (
            any(phrase in low for phrase in footer_phrases)
            or any(rx.search(stripped) for rx in footer_regexes)
        )
        if is_footer:
            cut = i
            break
        content_seen += 1

    if cut is not None:
        lines = lines[:cut]
        # Drop any trailing separator/blank lines the footer left dangling.
        while lines and (not lines[-1].strip() or sep_re.match(lines[-1])):
            lines.pop()

    # 2) Turn decorative separator lines into blanks (collapsed in step 3).
    normalised = ["" if sep_re.match(ln) else ln.rstrip() for ln in lines]

    # 3) Collapse runs of blank lines and trim leading/trailing blanks.
    out: list[str] = []
    blanks = 0
    for line in normalised:
        if line == "":
            blanks += 1
            if blanks <= max_blanks:
                out.append("")
        else:
            blanks = 0
            out.append(line)
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()

    return "\n".join(out)
