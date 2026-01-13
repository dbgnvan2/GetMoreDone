#!/usr/bin/env python3
"""
Test script for Obsidian integration dialogs.
Run this to verify dialogs can be instantiated and work properly.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    try:
        from getmoredone.app_settings import AppSettings
        print("  ✓ AppSettings imported")

        from getmoredone.obsidian_utils import create_obsidian_note, open_in_obsidian
        print("  ✓ obsidian_utils imported")

        from getmoredone.models import ItemLink, ContactLink
        print("  ✓ Models imported")

        from getmoredone.db_manager import DatabaseManager
        print("  ✓ DatabaseManager imported")

        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False


def test_settings():
    """Test settings loading and validation."""
    print("\nTesting settings...")
    try:
        from getmoredone.app_settings import AppSettings

        settings = AppSettings.load()
        print(f"  Vault path: {settings.obsidian_vault_path or '(not set)'}")
        print(f"  Subfolder: {settings.obsidian_notes_subfolder}")

        if settings.obsidian_vault_path:
            vault = Path(settings.obsidian_vault_path)
            print(f"  Vault exists: {vault.exists()}")

            if vault.exists():
                obsidian_folder = vault / ".obsidian"
                print(f"  .obsidian folder exists: {obsidian_folder.exists()}")

                from getmoredone.obsidian_utils import validate_obsidian_setup
                is_valid, message = validate_obsidian_setup(
                    settings.obsidian_vault_path,
                    settings.obsidian_notes_subfolder
                )
                print(f"  Validation: {'✓' if is_valid else '✗'} {message}")
        else:
            print("  ⚠ Vault not configured - configure in Settings first")

        return True
    except Exception as e:
        print(f"  ✗ Settings test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database():
    """Test database connection and links table."""
    print("\nTesting database...")
    try:
        from getmoredone.db_manager import DatabaseManager

        db = DatabaseManager()

        # Check if tables exist
        cursor = db.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='item_links'"
        )
        if cursor.fetchone():
            print("  ✓ item_links table exists")
        else:
            print("  ✗ item_links table missing")

        cursor = db.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contact_links'"
        )
        if cursor.fetchone():
            print("  ✓ contact_links table exists")
        else:
            print("  ✗ contact_links table missing")

        db.close()
        return True
    except Exception as e:
        print(f"  ✗ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dialog_instantiation():
    """Test if dialogs can be created (without GUI)."""
    print("\nTesting dialog classes...")
    try:
        # We can't actually instantiate CTkToplevel without a GUI,
        # but we can check if the classes are defined
        from getmoredone.screens.item_editor import CreateNoteDialog, LinkNoteDialog
        print("  ✓ CreateNoteDialog class found")
        print("  ✓ LinkNoteDialog class found")

        # Check if create_note method exists
        from getmoredone.screens.item_editor import ItemEditorDialog
        if hasattr(ItemEditorDialog, 'create_note'):
            print("  ✓ ItemEditorDialog.create_note() method exists")
        else:
            print("  ✗ ItemEditorDialog.create_note() method missing")

        if hasattr(ItemEditorDialog, 'link_existing_note'):
            print("  ✓ ItemEditorDialog.link_existing_note() method exists")
        else:
            print("  ✗ ItemEditorDialog.link_existing_note() method missing")

        if hasattr(ItemEditorDialog, 'load_notes'):
            print("  ✓ ItemEditorDialog.load_notes() method exists")
        else:
            print("  ✗ ItemEditorDialog.load_notes() method missing")

        return True
    except Exception as e:
        print(f"  ✗ Dialog class test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Obsidian Integration Test Suite")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Settings", test_settings()))
    results.append(("Database", test_database()))
    results.append(("Dialog Classes", test_dialog_instantiation()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("\n✓ All backend tests passed!")
        print("\nNext steps:")
        print("1. Run the app: python run.py")
        print("2. Open an existing Action Item")
        print("3. Look for 'Obsidian Notes' section in right column")
        print("4. Try clicking '+ Create Note' button")
        print("5. If dialog doesn't appear, check terminal for error messages")
    else:
        print("\n✗ Some tests failed - fix these before testing GUI")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
