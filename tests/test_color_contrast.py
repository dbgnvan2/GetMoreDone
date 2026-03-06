import math

from src.getmoredone.color_contrast import (
    contrast_ratio,
    meets_wcag,
    pick_text_color,
    pick_text_color_with_meta,
    relative_luminance,
)


def test_pick_text_color_known_cases():
    assert pick_text_color("#FFFF00") == "#000000"  # bright yellow -> black
    assert pick_text_color("#003366") == "#FFFFFF"  # dark blue -> white


def test_contrast_ratio_published_examples():
    # WCAG canonical black/white
    assert math.isclose(contrast_ratio("#000000", "#FFFFFF"), 21.0, rel_tol=0.0, abs_tol=0.01)
    # Common WebAIM examples
    assert math.isclose(contrast_ratio("#777777", "#FFFFFF"), 4.48, rel_tol=0.0, abs_tol=0.03)
    assert math.isclose(contrast_ratio("#0000FF", "#FFFFFF"), 8.59, rel_tol=0.0, abs_tol=0.03)


def test_meets_wcag_thresholds():
    assert meets_wcag("#767676", "#FFFFFF", large_text=False)
    assert meets_wcag("#767676", "#FFFFFF", large_text=True)
    assert not meets_wcag("#777777", "#FFFFFF", large_text=False)
    assert not meets_wcag("#FF0000", "#FFFFFF", large_text=False)
    assert meets_wcag("#FF0000", "#FFFFFF", large_text=True)


def test_pick_text_color_with_meta_failure_flag_and_determinism():
    first = pick_text_color_with_meta("#7A7A7A", light="#888888", dark="#777777")
    second = pick_text_color_with_meta("#7A7A7A", light="#888888", dark="#777777")

    assert first == second
    assert first.text_color in {"#888888", "#777777"}
    assert isinstance(first.contrast_ratio, float)
    assert first.meets_threshold is False


def test_relative_luminance_known_edges():
    assert math.isclose(relative_luminance("#000000"), 0.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(relative_luminance("#FFFFFF"), 1.0, rel_tol=0.0, abs_tol=1e-9)
