#!/usr/bin/env python3
"""
Simple run script for GetMoreDone application.

Usage:
    python run.py              Launch the app.
    python run.py --selftest   Headless startup check; exits 0 when the build is
                               sound. Used by CI against the packaged binary.
                               See docs/spec_2026-08-18_downloadable_release.md#r-m1b
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        # Imported here so the selftest never pulls in the main window module.
        from getmoredone.selftest import run_selftest

        return run_selftest()

    from getmoredone.app import main as app_main

    app_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
