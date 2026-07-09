"""Tests for the reusable column-resize controller (screens/column_resize.py).

Covers the pure width/clamp/persistence logic without a Tk window; the divider
drag and live re-clamp are exercised interactively in the running app.
"""

from src.getmoredone.screens.column_resize import (
    ColumnResizer,
    ColumnSpec,
    chars_for_width,
)


class FakeSettings:
    """Minimal stand-in for AppSettings (attribute bag + save() counter)."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.saved = 0

    def save(self):
        self.saved += 1


def _resizer(settings, prefix="drag_schedule", specs=None, **kw):
    specs = specs or [ColumnSpec("title", grid_col=1, default_width=220, min_width=120)]
    return ColumnResizer(owner=None, settings=settings, prefix=prefix, specs=specs, **kw)


# --- chars_for_width -------------------------------------------------------

def test_chars_for_width_monotonic_and_min_one():
    assert chars_for_width(0) == 1          # never below 1
    assert chars_for_width(120) == 15
    assert chars_for_width(900) == 112
    # wider column -> strictly more characters
    assert chars_for_width(900) > chars_for_width(400) > chars_for_width(120)


def test_wide_title_is_not_truncated_to_a_handful():
    """Regression for the Scheduler bug: a 900px Title column showed ~20 chars.

    The clamp must follow the actual width, so a wide column yields many chars
    and a narrow column yields few.
    """
    settings = FakeSettings(drag_schedule_col_widths={"title": 900})
    r = _resizer(settings)
    assert r.chars("title") >= 100        # was hard-capped at 20 before the fix

    settings_narrow = FakeSettings(drag_schedule_col_widths={"title": 120})
    r2 = _resizer(settings_narrow)
    assert r2.chars("title") <= 20


# --- width load / legacy fallback / clamp ----------------------------------

def test_legacy_title_scalar_is_honoured_when_dict_missing():
    settings = FakeSettings(drag_schedule_title_col_width=300)  # no *_col_widths
    r = _resizer(settings)
    assert r.width("title") == 300


def test_dict_width_takes_precedence_over_legacy_scalar():
    settings = FakeSettings(
        drag_schedule_col_widths={"title": 410},
        drag_schedule_title_col_width=300,
    )
    r = _resizer(settings)
    assert r.width("title") == 410


def test_width_is_clamped_to_spec_bounds_on_load():
    spec = ColumnSpec("title", grid_col=1, default_width=220, min_width=120, max_width=800)
    lo = _resizer(FakeSettings(drag_schedule_col_widths={"title": 50}), specs=[spec])
    hi = _resizer(FakeSettings(drag_schedule_col_widths={"title": 5000}), specs=[spec])
    assert lo.width("title") == 120
    assert hi.width("title") == 800


def test_default_width_when_no_setting():
    r = _resizer(FakeSettings())
    assert r.width("title") == 220


# --- chars reserve ---------------------------------------------------------

def test_chars_reserve_subtracts():
    r = _resizer(FakeSettings(drag_schedule_col_widths={"title": 240}))
    assert r.chars("title") == 30
    assert r.chars("title", reserve=4) == 26


# --- persistence -----------------------------------------------------------

def test_persist_round_trips_over_dirty_state():
    # Dirty prior-run state: an unrelated column width already stored (P8).
    settings = FakeSettings(drag_schedule_col_widths={"title": 150, "segment": 999})
    r = _resizer(settings)
    assert r.width("title") == 150

    r._widths["title"] = 400
    r._persist()

    assert settings.saved == 1
    # New width written, unrelated stored key preserved.
    assert settings.drag_schedule_col_widths["title"] == 400
    assert settings.drag_schedule_col_widths["segment"] == 999

    # A fresh resizer reads back the persisted width.
    assert _resizer(settings).width("title") == 400
