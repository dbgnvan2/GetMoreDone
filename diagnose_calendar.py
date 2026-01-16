#!/usr/bin/env python
"""
Diagnostic script to identify why Google Calendar integration isn't working.
Run this on your local machine in the GetMoreDone directory.
"""

import sys
import os

print("=" * 70)
print("GOOGLE CALENDAR INTEGRATION DIAGNOSTIC")
print("=" * 70)
print()

# 1. Python environment
print("1. PYTHON ENVIRONMENT")
print("-" * 70)
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print()

# 2. Check virtual environment
print("2. VIRTUAL ENVIRONMENT")
print("-" * 70)
venv = os.environ.get('VIRTUAL_ENV', None)
if venv:
    print(f"✓ Running in venv: {venv}")
else:
    print("✗ NOT in a virtual environment (using system Python)")
print()

# 3. Try importing each library individually
print("3. LIBRARY IMPORTS (testing each one)")
print("-" * 70)

libraries = [
    ('google.auth.transport.requests', 'Request'),
    ('google.oauth2.credentials', 'Credentials'),
    ('google_auth_oauthlib.flow', 'InstalledAppFlow'),
    ('googleapiclient.discovery', 'build'),
    ('googleapiclient.errors', 'HttpError'),
    ('tzlocal', 'get_localzone'),
]

all_ok = True
for module_name, import_name in libraries:
    try:
        module = __import__(module_name, fromlist=[import_name])
        getattr(module, import_name)
        print(f"✓ {module_name}.{import_name}")
    except ImportError as e:
        print(f"✗ {module_name}.{import_name} - MISSING!")
        print(f"  Error: {e}")
        all_ok = False
    except Exception as e:
        print(f"✗ {module_name}.{import_name} - ERROR!")
        print(f"  Error: {e}")
        all_ok = False

print()

# 4. Check the actual google_calendar module
print("4. GOOGLE_CALENDAR MODULE STATUS")
print("-" * 70)
try:
    from src.getmoredone.google_calendar import GoogleCalendarManager, GOOGLE_CALENDAR_AVAILABLE
    print(f"✓ Module import successful")
    print(f"  GOOGLE_CALENDAR_AVAILABLE = {GOOGLE_CALENDAR_AVAILABLE}")
    print(f"  is_available() = {GoogleCalendarManager.is_available()}")
    print(f"  has_credentials() = {GoogleCalendarManager.has_credentials()}")
except Exception as e:
    print(f"✗ Module import FAILED!")
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()

print()

# 5. Summary and recommendations
print("5. DIAGNOSIS & RECOMMENDATIONS")
print("-" * 70)

if all_ok:
    try:
        from src.getmoredone.google_calendar import GOOGLE_CALENDAR_AVAILABLE
        if GOOGLE_CALENDAR_AVAILABLE:
            print("✅ ALL LIBRARIES INSTALLED CORRECTLY!")
            print()
            print("Next steps:")
            print("1. Clear Python cache:")
            print("   find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null")
            print("   find . -name '*.pyc' -delete 2>/dev/null")
            print()
            print("2. Restart your GetMoreDone app")
            print()
            print("If error persists, the app might be using a different Python.")
        else:
            print("⚠️  Libraries installed but GOOGLE_CALENDAR_AVAILABLE is False")
            print("This means the module was imported when libraries were missing.")
            print()
            print("Solution:")
            print("1. Clear cache: find . -name '__pycache__' -delete -o -name '*.pyc' -delete")
            print("2. Restart the app")
    except:
        pass
else:
    print("❌ MISSING LIBRARIES DETECTED!")
    print()
    print("Solution:")
    if venv:
        print("1. Make sure your venv is activated")
        print("2. Run: pip install -r requirements.txt")
    else:
        print("You're not using a venv. Install missing libraries:")
        print("  pip install tzlocal>=5.0.0")
    print()
    print("3. Then restart the app")

print()
print("=" * 70)
