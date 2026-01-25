#!/usr/bin/env python3
"""
Test script to verify VPS bug fixes.
"""


def test_imports():
    """Test that the VPS modules import correctly."""
    print("Testing imports...")
    try:
        from src.getmoredone.screens.vps_editors import TLVisionEditorDialog
        from src.getmoredone.screens.vps_planning import VPSPlanningScreen
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_messagebox_import():
    """Test that messagebox is properly imported."""
    print("\nTesting messagebox import...")
    try:
        from src.getmoredone.screens import vps_editors
        if hasattr(vps_editors, 'messagebox'):
            print("✓ messagebox is imported in vps_editors")
            return True
        else:
            print("✗ messagebox not found in vps_editors")
            return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_vision_editor_structure():
    """Test that TLVisionEditorDialog has the correct structure."""
    print("\nTesting VisionEditorDialog structure...")
    try:
        from src.getmoredone.screens.vps_editors import TLVisionEditorDialog

        # Check if save_vision method exists
        if hasattr(TLVisionEditorDialog, 'save_vision'):
            print("✓ save_vision method exists")
        else:
            print("✗ save_vision method not found")
            return False

        # Read the source to check for CTkMessageBox (should not exist)
        import inspect
        source = inspect.getsource(TLVisionEditorDialog.save_vision)
        if 'CTkMessageBox' in source:
            print("✗ CTkMessageBox still referenced in save_vision")
            return False
        else:
            print("✓ No CTkMessageBox references found")

        if 'messagebox.showerror' in source or 'messagebox.showinfo' in source:
            print("✓ Using tkinter messagebox instead")
        else:
            print("⚠ Warning: No messagebox calls found")

        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_planning_screen_structure():
    """Test that VPSPlanningScreen has segment selection feature."""
    print("\nTesting VPSPlanningScreen segment selection...")
    try:
        from src.getmoredone.screens.vps_planning import VPSPlanningScreen

        # Check for required methods
        required_methods = [
            'show_segment_filter_dialog', 'update_segment_filter']
        for method in required_methods:
            if hasattr(VPSPlanningScreen, method):
                print(f"✓ {method} method exists")
            else:
                print(f"✗ {method} method not found")
                return False

        # Check __init__ for selected_segments
        import inspect
        source = inspect.getsource(VPSPlanningScreen.__init__)
        if 'selected_segments' in source:
            print("✓ selected_segments tracking added")
        else:
            print("✗ selected_segments not found in __init__")
            return False

        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("VPS Bug Fixes Verification")
    print("=" * 60)

    results = []
    results.append(("Import Test", test_imports()))
    results.append(("Messagebox Import", test_messagebox_import()))
    results.append(("Vision Editor Structure", test_vision_editor_structure()))
    results.append(("Planning Screen Structure",
                   test_planning_screen_structure()))

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
    else:
        print("✗ Some tests FAILED")
    print("=" * 60)

    exit(0 if all_passed else 1)
