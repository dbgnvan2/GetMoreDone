"""The brand palette, and the theme built from it.

Purpose: keep the transcribed palette faithful to the document it was measured
         from, and keep the daVIPA theme using only colours from it.
Spec:    daVIPA-colour-system.pdf (v1.0, 20 August 2026)
Tests:   this file

The palette is a transcription. Its risk is not that the code is wrong but
that a value drifts from the source document and nothing notices — so these
assert the shape the document states about itself, the contrast ratios it
publishes, and that the theme cannot introduce a colour from outside it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.getmoredone import brand, theme
from src.getmoredone.app_settings import AppSettings

THEMES_DIR = Path(__file__).resolve().parents[1] / "themes"
DAVIPA_THEME = THEMES_DIR / "davipa.json"

RAMP_STEPS = (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)


def _relative_luminance(value: str) -> float:
    channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 2.1 contrast, computed here rather than trusted from the document."""
    a, b = _relative_luminance(foreground), _relative_luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


# --------------------------------------------------------------------------
# The palette matches what the document says about itself
# --------------------------------------------------------------------------


def test_the_palette_has_the_shape_the_document_states():
    """"Eight core colours · 88 ramp steps · three gradients", verbatim.

    The document's own cover line, used as a checksum on the transcription: a
    ramp dropped or a step mistyped changes one of these three numbers.
    """
    core = [
        brand.CRIMSON, brand.INDIGO, brand.VIOLET, brand.MAGENTA,
        brand.CORAL, brand.AMBER, brand.MIDNIGHT, brand.DEEP_INK,
    ]
    assert len(core) == 8
    assert len(set(core)) == 8, "two core colours are the same value"
    assert len(brand.RAMPS) == 8, "one colour has no ramp"
    assert sum(len(steps) for steps in brand.RAMPS.values()) == 88
    gradients = [brand.ARROW_GRADIENT, brand.TILE_GRADIENT, brand.GROUND_GRADIENT]
    assert len(gradients) == 3


@pytest.mark.parametrize("name", sorted(brand.RAMPS))
def test_every_ramp_has_the_eleven_documented_steps(name):
    assert tuple(sorted(brand.RAMPS[name])) == RAMP_STEPS


@pytest.mark.parametrize("name,base", [
    ("crimson", brand.CRIMSON), ("indigo", brand.INDIGO),
    ("violet", brand.VIOLET), ("magenta", brand.MAGENTA),
    ("coral", brand.CORAL), ("amber", brand.AMBER),
    ("midnight", brand.MIDNIGHT), ("deep_ink", brand.DEEP_INK),
])
def test_each_ramp_contains_its_own_brand_colour_exactly(name, base):
    """"each ramp contains the real colour rather than an approximation".

    The document's stated method. If a base colour were transcribed wrongly it
    would no longer appear in its own ramp, so this catches a typo in either.
    """
    assert base in brand.RAMPS[name].values(), (
        f"{name}'s ramp does not contain {base} — one of the two is mistyped"
    )


@pytest.mark.parametrize("value", [
    v for ramp in brand.RAMPS.values() for v in ramp.values()
] + [
    brand.CRIMSON, brand.INDIGO, brand.VIOLET, brand.MAGENTA, brand.CORAL,
    brand.AMBER, brand.MIDNIGHT, brand.DEEP_INK, brand.ON_DARK,
])
def test_every_value_is_an_uppercase_six_digit_hex(value):
    assert len(value) == 7 and value[0] == "#"
    assert value[1:] == value[1:].upper()
    int(value[1:], 16)


# --------------------------------------------------------------------------
# The published contrast figures, recomputed
# --------------------------------------------------------------------------


@pytest.mark.parametrize("colour,expected", [
    (brand.CRIMSON, 4.90), (brand.INDIGO, 12.51), (brand.VIOLET, 7.59),
    (brand.MIDNIGHT, 17.11), (brand.DEEP_INK, 17.59),
])
def test_white_on_colour_matches_the_published_ratio(colour, expected):
    """The document's "white on it" column, recomputed from the hex values.

    Agreement to two decimal places is the check that the transcription and
    the measurement describe the same colour.
    """
    assert contrast_ratio(brand.ON_DARK, colour) == pytest.approx(expected, abs=0.01)


def test_amber_is_unsafe_for_white_text_as_the_document_warns():
    """"White text is safe on Crimson, Indigo, Violet and both neutrals, and
    unsafe on Amber." Asserted so the warning cannot quietly stop being true."""
    assert contrast_ratio(brand.ON_DARK, brand.AMBER) < 4.5


# --------------------------------------------------------------------------
# The theme is selectable, and made only of brand colours
# --------------------------------------------------------------------------


def test_the_theme_is_offered_in_the_settings_picker():
    """P25 — a theme file nothing offers is a file, not a theme."""
    assert "davipa" in theme.THEME_NAMES
    assert theme.normalize_theme_name("davipa") == "davipa"
    assert theme.theme_path_for("davipa").exists()


def test_the_theme_has_every_section_the_other_themes_have():
    """A missing widget section falls back to CustomTkinter's default silently."""
    davipa = json.loads(DAVIPA_THEME.read_text())
    reference = json.loads((THEMES_DIR / "purple.json").read_text())

    assert set(davipa) == set(reference), (
        f"section mismatch: {set(reference) ^ set(davipa)}"
    )
    for section, values in reference.items():
        assert set(davipa[section]) == set(values), (
            f"{section} keys differ from the reference theme"
        )


def test_the_theme_introduces_no_colour_from_outside_the_palette():
    """Every hex in the theme is a documented brand value.

    The palette is an extraction from the artwork; a colour that is not in it
    did not come from the mark. Greys inherited from the reference theme are
    named CustomTkinter colours ("gray74"), not hex, so they do not qualify.
    """
    allowed = {v for ramp in brand.RAMPS.values() for v in ramp.values()}
    allowed |= {
        brand.CRIMSON, brand.INDIGO, brand.VIOLET, brand.MAGENTA, brand.CORAL,
        brand.AMBER, brand.MIDNIGHT, brand.DEEP_INK, brand.ON_DARK,
    }
    allowed |= set(brand.ARROW_GRADIENT) | set(brand.TILE_GRADIENT)
    allowed |= set(brand.GROUND_GRADIENT)

    davipa = json.loads(DAVIPA_THEME.read_text())
    strays = {
        f"{section}.{key}={value}"
        for section, values in davipa.items()
        for key, entry in values.items()
        for value in (entry if isinstance(entry, list) else [entry])
        if isinstance(value, str) and value.startswith("#") and value not in allowed
    }
    assert strays == set(), f"colours not in the brand palette: {sorted(strays)}"


@pytest.mark.parametrize("section,text_key,fill_key", [
    ("CTkButton", "text_color", "fg_color"),
    ("CTkButton", "text_color", "hover_color"),
    ("CTkComboBox", "text_color", "fg_color"),
    ("CTkOptionMenu", "text_color", "fg_color"),
    ("CTkSegmentedButton", "text_color", "selected_color"),
    ("CTkEntry", "text_color", "fg_color"),
    ("CTkCheckBox", "checkmark_color", "fg_color"),
])
def test_every_text_on_fill_pairing_clears_aa(section, text_key, fill_key):
    """The document: check any new pairing reaches 4.5:1 and report the number.

    Both appearance modes, since a theme file carries [light, dark] and a
    pairing that passes in one can fail in the other.
    """
    davipa = json.loads(DAVIPA_THEME.read_text())
    text = davipa[section][text_key]
    fill = davipa[section][fill_key]

    for mode, index in (("light", 0), ("dark", 1)):
        ratio = contrast_ratio(text[index], fill[index])
        assert ratio >= 4.5, (
            f"{section}.{text_key} on {fill_key} in {mode} mode is "
            f"{ratio:.2f}:1, below AA's 4.5:1"
        )


# --------------------------------------------------------------------------
# Picking a theme has to actually give you that theme
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", theme.THEME_NAMES)
def test_settings_accepts_every_theme_the_picker_offers(name):
    """One list of theme names, not two.

    app_settings held its own hardcoded copy. Adding a theme put it in the
    Settings picker and wrote it to settings.json — and this rewrote it to
    "apple_grey" on the next load, because the new name was not in the copy.
    Picking daVIPA silently gave you Apple Grey, with nothing logged.
    """
    assert AppSettings._normalize_theme_name(name) == name, (
        f"the Settings picker offers {name!r} but loading it returns "
        f"{AppSettings._normalize_theme_name(name)!r} — two lists have drifted"
    )


def test_settings_still_rejects_a_name_that_is_not_a_theme():
    """The normalisation is not simply gone: junk still falls back."""
    assert AppSettings._normalize_theme_name("not-a-theme") == theme.DEFAULT_THEME_NAME
    assert AppSettings._normalize_theme_name(None) == theme.DEFAULT_THEME_NAME
    assert AppSettings._normalize_theme_name("  DAVIPA  ") == "davipa"


def test_the_window_background_matches_the_theme_that_was_picked(tmp_path, monkeypatch):
    """The root is a widget, so the theme must be applied before it exists.

    CustomTkinter colours each widget as it is CREATED. apply_theme_settings
    ran after super().__init__(), so the main window kept the theme from the
    PREVIOUS launch — one behind whatever the user chose. Every theme was
    affected; it showed as a window background that never matched its own
    sidebar.
    """
    import json

    import customtkinter as ctk

    monkeypatch.setenv("GETMOREDONE_DB", str(tmp_path / "themed.db"))
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({"theme_name": "davipa", "appearance_mode": "dark"})
    )
    monkeypatch.setattr(
        AppSettings, "get_settings_path", classmethod(lambda cls: settings_file)
    )

    from src.getmoredone.app import GetMoreDoneApp

    expected = json.loads(theme.theme_path_for("davipa").read_text())
    app = GetMoreDoneApp()
    try:
        assert app.settings.theme_name == "davipa", (
            "the app did not keep the theme the settings file asked for"
        )
        assert app.cget("fg_color") == expected["CTk"]["fg_color"], (
            f"the window is {app.cget('fg_color')}, not the picked theme's "
            f"{expected['CTk']['fg_color']}"
        )
        assert app.sidebar.cget("fg_color") == expected["CTkFrame"]["fg_color"]
    finally:
        app.destroy()
