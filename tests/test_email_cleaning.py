"""
Tests for cleaning imported email bodies (excess lines + footer removal).

Covers the real Google "brand account invitation" body from the reported
screenshot, blank-line collapsing, separator stripping, and adversarial cases
where a footer phrase must NOT truncate genuine content (P7).
"""

import logging

from src.getmoredone.email_cleaning import clean_email_body, _load_rules, _DEFAULT_RULES


# The body as extracted from the reported email (unsubscribe footer + rulers).
GOOGLE_INVITE_BODY = """Dave B Galloway GM


You received an invitation

Joan Jurkowski invited you to share ownership of Bowen Theory Academy.

Accept invitation

https://myaccount.google.com/brandaccounts/100235540829682470495/accept?dnm=false&emr=15506013911920014813


------------------------------------------------------------

Unsubscribe from these emails:
https://myaccount.google.com/organization-preferences/unsubscribe?tk=AbcFtOBR-417-abc
"""


def test_footer_and_rulers_removed_from_real_email():
    out = clean_email_body(GOOGLE_INVITE_BODY)

    # Message content is preserved.
    assert "You received an invitation" in out
    assert "Joan Jurkowski invited you to share ownership" in out
    assert "Accept invitation" in out
    assert "myaccount.google.com/brandaccounts/100235540829682470495/accept" in out

    # Footer + separators are gone.
    assert "Unsubscribe" not in out
    assert "unsubscribe" not in out.lower()
    assert "-----" not in out
    assert "organization-preferences" not in out

    # The kept text ends on the accept URL, not trailing blanks/rulers.
    assert out.rstrip() == out
    assert out.splitlines()[-1].startswith("https://myaccount.google.com/brandaccounts")


def test_excess_blank_lines_collapsed():
    text = "Line one\n\n\n\n\nLine two\n\n\n\nLine three"
    out = clean_email_body(text)
    assert out == "Line one\n\nLine two\n\nLine three"


def test_leading_and_trailing_blank_lines_trimmed():
    text = "\n\n\nHello\n\n\n"
    assert clean_email_body(text) == "Hello"


def test_standalone_separator_lines_removed():
    text = "Top\n------------\nBottom"
    out = clean_email_body(text)
    assert "---" not in out
    assert "Top" in out and "Bottom" in out


def test_copyright_footer_removed():
    text = "Real message here.\n\n© 2026 Acme Corp\n123 Main St"
    out = clean_email_body(text)
    assert "Real message here." in out
    assert "Acme Corp" not in out
    assert "123 Main St" not in out


def test_content_mentioning_unsubscribe_on_first_line_is_kept():
    # Adversarial (P7): a footer phrase as the very first/only real content must
    # NOT gut the message — there is no preceding content to anchor a footer.
    text = "Please help me unsubscribe John from the mailing list before Friday."
    out = clean_email_body(text)
    assert "unsubscribe John from the mailing list" in out


def test_body_without_footer_is_returned_intact():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    assert clean_email_body(text) == text


def test_empty_and_none_inputs():
    assert clean_email_body("") == ""
    assert clean_email_body(None) == ""
    assert clean_email_body("   \n\n  \n") == ""


def test_malformed_rules_file_falls_back_and_warns(tmp_path, caplog):
    # P2/P16: a missing/malformed rules file must fall back to defaults AND log,
    # so the degradation isn't silent.
    bad = tmp_path / "broken.json"
    bad.write_text("{ not valid json,,, }", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        rules = _load_rules(bad)
    assert rules == _DEFAULT_RULES
    assert any("unreadable" in rec.message for rec in caplog.records)

    missing = tmp_path / "does_not_exist.json"
    assert _load_rules(missing) == _DEFAULT_RULES
