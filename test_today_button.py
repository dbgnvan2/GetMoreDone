#!/usr/bin/env python3
"""Test script to diagnose Today button issue."""

import sys
sys.path.insert(0, 'src')

try:
    print("1. Testing import of TodayScreen...")
    from getmoredone.screens.today import TodayScreen
    print("   ✓ TodayScreen imports successfully")
except Exception as e:
    print(f"   ✗ Failed to import TodayScreen: {e}")
    sys.exit(1)

try:
    print("\n2. Testing import of app...")
    from getmoredone.app import GetMoreDoneApp
    print("   ✓ GetMoreDoneApp imports successfully")
except Exception as e:
    print(f"   ✗ Failed to import GetMoreDoneApp: {e}")
    sys.exit(1)

try:
    print("\n3. Checking if show_today method exists...")
    if hasattr(GetMoreDoneApp, 'show_today'):
        print("   ✓ show_today method exists")
    else:
        print("   ✗ show_today method NOT found!")
        sys.exit(1)
except Exception as e:
    print(f"   ✗ Error checking method: {e}")
    sys.exit(1)

try:
    print("\n4. Checking TodayScreen __init__ signature...")
    import inspect
    sig = inspect.signature(TodayScreen.__init__)
    print(f"   TodayScreen.__init__{sig}")
    params = list(sig.parameters.keys())
    print(f"   Parameters: {params}")
    if len(params) == 3:  # self, parent, db_manager
        print("   ✓ Signature looks correct")
    else:
        print(f"   ? Unexpected parameter count: {len(params)}")
except Exception as e:
    print(f"   ✗ Error checking signature: {e}")

print("\n5. Checking button configuration in source code...")
with open('src/getmoredone/app.py', 'r') as f:
    content = f.read()
    if 'command=self.show_today' in content:
        print("   ✓ Button wired to self.show_today")
    else:
        print("   ✗ Button NOT properly wired!")

    if 'def show_today(self):' in content:
        print("   ✓ show_today method defined")
    else:
        print("   ✗ show_today method NOT defined!")

print("\nAll basic checks passed. The button should work.")
print("\nIf the button still doesn't work when you click it:")
print("1. Make sure you restarted the application after the code update")
print("2. Check the terminal for any error messages")
print("3. Try clicking another button to see if navigation works at all")
