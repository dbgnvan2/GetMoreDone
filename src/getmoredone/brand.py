"""The daVIPA colour system, as named constants.

Purpose: give the brand palette one home, so a colour used anywhere can be
         traced to the document it was measured from.
Spec:    daVIPA-colour-system.pdf (v1.0, 20 August 2026)
Tests:   tests/test_brand_palette.py

Every value here was measured from the crimson app icon and is copied from
that document unchanged. Nothing was picked by eye, and nothing should be
adjusted here without re-deriving it there — the document is the source, this
module is the transcription.

**These constants do not repaint the app.** They are the palette plus the
``davipa`` theme built from it, which a user selects in Settings. The existing
semantic tokens in ``theme.py`` still drive the UI; the brand document is
explicit that it is "an extraction, not a decision", and which accent leads on
a given screen is design judgement rather than a substitution.

Reserve ``CRIMSON`` for the mark and for genuine emphasis: it is the only
colour in the system that reads as a signal rather than a surface. Green stays
reserved for "complete / done" and is deliberately absent from the palette.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Core palette — eight measured colours
# --------------------------------------------------------------------------

#: The circle and square strokes. Carries the mark. PRIMARY.
CRIMSON = "#DE1B24"
#: Upper-left of the icon tile. Large surfaces, headers, filled panels. SECONDARY.
INDIGO = "#2E1C8F"
#: Mid-right of the tile. Bridges indigo and magenta; secondary surfaces, hover.
VIOLET = "#813389"
#: Arrow tail. The cool end of the arrow gradient. ACCENT.
MAGENTA = "#D051C1"
#: Arrow midpoint. Nearest neighbour to Crimson — keep the two apart. ACCENT.
CORAL = "#F55161"
#: Arrow tip and the tile's upper-right glow. Highlights, warm emphasis. ACCENT.
AMBER = "#FD924A"
#: The canvas the tile sits on. Default dark background. NEUTRAL.
MIDNIGHT = "#171447"
#: Lower-left of the tile, the darkest measured value. Dark-mode base. NEUTRAL.
DEEP_INK = "#101342"

#: Text and icons on the dark grounds.
ON_DARK = "#FFFFFF"

# --------------------------------------------------------------------------
# Tint and shade ramps — eleven steps, the base colour at its own lightness
# --------------------------------------------------------------------------

RAMPS = {
    "crimson": {
        50: "#FFF4F2", 100: "#FFE5E1", 200: "#FFC7BD", 300: "#FFA090",
        400: "#FF7260", 500: "#F43E37", 600: "#DE1B24", 700: "#B20016",
        800: "#86000E", 900: "#5D0000", 950: "#350B00",
    },
    "indigo": {
        50: "#F9F5FF", 100: "#F0E7FF", 200: "#DFCCFF", 300: "#C7AAFF",
        400: "#AD8BF9", 500: "#9170E0", 600: "#7859CA", 700: "#5E42B4",
        800: "#40299C", 900: "#2E1C8F", 950: "#000365",
    },
    "violet": {
        50: "#FFF3FF", 100: "#FFE2FF", 200: "#FCC1FF", 300: "#E99FED",
        400: "#CE83D3", 500: "#B368B9", 600: "#9C4FA2", 700: "#813389",
        800: "#691E71", 900: "#4E0157", 950: "#330039",
    },
    "magenta": {
        50: "#FFF3FC", 100: "#FFE3F9", 200: "#FFC1F4", 300: "#FF93EF",
        400: "#EA6FDA", 500: "#D051C1", 600: "#B339A6", 700: "#97208C",
        800: "#78006E", 900: "#52004B", 950: "#360031",
    },
    "coral": {
        50: "#FFF4F4", 100: "#FFE5E4", 200: "#FFC7C5", 300: "#FF9E9E",
        400: "#FF6F77", 500: "#F55161", 600: "#CB3046", 700: "#AD1233",
        800: "#850023", 900: "#5C0015", 950: "#3D0005",
    },
    "amber": {
        50: "#FFF4EF", 100: "#FFE6D8", 200: "#FFC9A9", 300: "#FD924A",
        400: "#EA833E", 500: "#C96A28", 600: "#AC5515", 700: "#8F4000",
        800: "#6B2F00", 900: "#461F00", 950: "#2A1400",
    },
    "midnight": {
        50: "#F8F5FF", 100: "#EEE8FF", 200: "#DACDFF", 300: "#BEB1E5",
        400: "#A396CB", 500: "#897CB2", 600: "#71659B", 700: "#5A4F85",
        800: "#42386D", 900: "#292256", 950: "#171447",
    },
    "deep_ink": {
        50: "#F7F5FF", 100: "#EDE8FF", 200: "#D7CEFE", 300: "#BCB3E3",
        400: "#A098C9", 500: "#867DAF", 600: "#6E6799", 700: "#575183",
        800: "#3F3A6B", 900: "#262454", 950: "#101342",
    },
}

# --------------------------------------------------------------------------
# Gradients — the icon has no flat brand surfaces beyond the strokes
# --------------------------------------------------------------------------

#: Arrow, tail to tip. Nine sampled points; these are the endpoints and midpoint.
#: Do not rebuild by eye — a two-stop approximation misses the coral midpoint.
ARROW_GRADIENT = (MAGENTA, CORAL, AMBER)

#: The icon tile, bottom-left to top-right across four positions.
TILE_GRADIENT = (DEEP_INK, INDIGO, "#813798", "#FD915B")

#: The canvas behind the tile, corner to corner.
GROUND_GRADIENT = ("#100F47", "#291E68")
