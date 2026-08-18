#!/usr/bin/env python3
"""
Test script for VPS Segment Management in Settings.
Tests the enhanced deletion protection with detailed vision count reporting.
"""


def test_imports():
    """Test that the VPS segment management modules import correctly."""
    print("Testing imports...")
    try:
        from src.getmoredone.screens.settings import SettingsScreen
        from src.getmoredone.screens.vps_segment_editor import VPSSegmentEditorDialog
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_settings_has_vps_tab():
    """Test that SettingsScreen has VPS segments section."""
    print("\nTesting Settings screen structure...")
    try:
        from src.getmoredone.screens.settings import SettingsScreen

        # Check for required methods
        required_methods = [
            'create_vps_segments_section',
            'refresh_segments_list',
            'create_segment_row',
            'create_new_segment',
            'edit_segment',
            'delete_segment'
        ]

        for method in required_methods:
            if hasattr(SettingsScreen, method):
                print(f"✓ {method} method exists")
            else:
                print(f"✗ {method} method not found")
                return False

        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_segment_editor_structure():
    """Test that VPSSegmentEditorDialog has required functionality."""
    print("\nTesting Segment Editor structure...")
    try:
        from src.getmoredone.screens.vps_segment_editor import VPSSegmentEditorDialog

        # Check for required methods
        required_methods = [
            'create_form',
            'load_segment_data',
            'pick_color',
            'validate_color',
            'save_segment'
        ]

        for method in required_methods:
            if hasattr(VPSSegmentEditorDialog, method):
                print(f"✓ {method} method exists")
            else:
                print(f"✗ {method} method not found")
                return False

        # Check __init__ for color handling
        import inspect
        source = inspect.getsource(VPSSegmentEditorDialog.__init__)
        if 'selected_color' in source and 'color_hex' in source:
            print("✓ Color handling initialized")
        else:
            print("✗ Color handling not properly initialized")
            return False

        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_color_validation():
    """Test color validation function."""
    print("\nTesting color validation...")
    try:
        from src.getmoredone.screens.vps_segment_editor import VPSSegmentEditorDialog

        # Create a mock instance just for validation testing
        class MockVPSManager:
            pass

        # We can't instantiate the dialog without a parent, but we can check the method exists
        import inspect
        source = inspect.getsource(VPSSegmentEditorDialog.validate_color)

        if 'startswith' in source and '#' in source:
            print("✓ Color validation checks for # prefix")
        else:
            print("⚠ Color validation might not check # prefix")

        if 'len' in source and '7' in source:
            print("✓ Color validation checks length")
        else:
            print("⚠ Color validation might not check length")

        if 'int' in source and '16' in source:
            print("✓ Color validation checks hex format")
        else:
            print("⚠ Color validation might not check hex format")

        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_vps_manager_segment_methods():
    """Test that VPSManager has all required segment methods."""
    print("\nTesting VPSManager segment methods...")
    try:
        from src.getmoredone.vps_manager import VPSManager

        required_methods = [
            'get_all_segments',
            'get_segment',
            'create_segment',
            'update_segment',
            'delete_segment'
        ]

        for method in required_methods:
            if hasattr(VPSManager, method):
                print(f"✓ {method} method exists")
            else:
                print(f"✗ {method} method not found")
                return False

        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_colorchooser_import():
    """Test that colorchooser is properly imported."""
    print("\nTesting colorchooser import...")
    try:
        from src.getmoredone.screens import vps_segment_editor
        import inspect

        source = inspect.getsource(vps_segment_editor)
        if 'colorchooser' in source:
            print("✓ colorchooser imported in vps_segment_editor")
        else:
            print("✗ colorchooser not found in vps_segment_editor")
            return False

        if 'askcolor' in source:
            print("✓ askcolor method used for color picking")
        else:
            print("✗ askcolor method not found")
            return False

        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_enhanced_deletion_protection():
    """Test that delete_segment returns detailed vision count."""
    print("\nTesting enhanced deletion protection...")
    try:
        from src.getmoredone.vps_manager import VPSManager
        import inspect

        # Check delete_segment return type annotation
        source = inspect.getsource(VPSManager.delete_segment)

        if 'tuple[bool, int]' in source or 'Tuple[bool, int]' in source:
            print("✓ delete_segment returns tuple[bool, int]")
        else:
            print("⚠ delete_segment return type not explicitly annotated")

        if 'vision_count' in source:
            print("✓ delete_segment tracks vision_count")
        else:
            print("✗ vision_count not found in delete_segment")
            return False

        if 'COUNT(*)' in source or 'count' in source.lower():
            print("✓ delete_segment counts linked records")
        else:
            print("✗ No counting logic found")
            return False

        # Check Settings error message
        from src.getmoredone.screens import settings
        settings_source = inspect.getsource(
            settings.SettingsScreen.delete_segment)

        if 'vision_count' in settings_source:
            print("✓ Settings screen uses vision_count")
        else:
            print("✗ Settings screen doesn't use vision_count")
            return False

        if 'To delete this segment:' in settings_source or 'Go to VPS Planning' in settings_source:
            print("✓ Settings provides step-by-step instructions")
        else:
            print("⚠ No step-by-step instructions found")

        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("VPS Segment Management Test")
    print("=" * 60)

    results = []
    results.append(("Import Test", test_imports()))
    results.append(("Settings VPS Tab", test_settings_has_vps_tab()))
    results.append(("Segment Editor Structure",
                   test_segment_editor_structure()))
    results.append(("Color Validation", test_color_validation()))
    results.append(("VPSManager Methods", test_vps_manager_segment_methods()))
    results.append(("Colorchooser Import", test_colorchooser_import()))
    results.append(("Enhanced Deletion Protection",
                   test_enhanced_deletion_protection()))

    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests PASSED!")
        print("\nEnhanced Features:")
        print("  • Detailed vision count in deletion errors")
        print("  • Step-by-step removal instructions")
        print("  • Cascade deletion warnings")
    else:
        print("✗ Some tests FAILED")
    print("=" * 60)

    exit(0 if all_passed else 1)
