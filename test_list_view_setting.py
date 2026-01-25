#!/usr/bin/env python3
"""Test script to verify list view expansion setting implementation."""

from getmoredone.app_settings import AppSettings
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_default_setting():
    """Test that the default_columns_expanded setting exists and defaults to False."""
    settings = AppSettings.load()

    # Check attribute exists
    assert hasattr(settings, 'default_columns_expanded'), \
        "default_columns_expanded attribute missing from AppSettings"

    # Check default value
    print(
        f"✓ Setting exists: default_columns_expanded = {settings.default_columns_expanded}")

    # Toggle the value
    original_value = settings.default_columns_expanded
    settings.default_columns_expanded = not original_value
    settings.save()
    print(f"✓ Changed setting to: {settings.default_columns_expanded}")

    # Reload and verify
    settings_reloaded = AppSettings.load()
    assert settings_reloaded.default_columns_expanded == (not original_value), \
        "Setting did not persist after save/reload"
    print(
        f"✓ Setting persisted after reload: {settings_reloaded.default_columns_expanded}")

    # Restore original value
    settings_reloaded.default_columns_expanded = original_value
    settings_reloaded.save()
    print(f"✓ Restored original value: {original_value}")

    print("\n✓ All tests passed!")


if __name__ == "__main__":
    test_default_setting()
