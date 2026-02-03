#!/usr/bin/env python3
"""Update/install launchd plists for the Gmail → GetMoreDone importer.

Reads poll interval from GetMoreDone Settings (settings.json) and writes:
- ~/Library/LaunchAgents/com.getmoredone.gmailimport.dev.plist
- ~/Library/LaunchAgents/com.getmoredone.gmailimport.prod.plist

Optionally reloads launchd jobs.

Usage:
  python tools/update_launchd_importer.py            # write plists only
  python tools/update_launchd_importer.py --reload prod
  python tools/update_launchd_importer.py --reload dev

Notes:
- This script is meant to be called from the app Settings screen.
- It uses the repo venv python to run the importer.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

# Allow running from repo root without installing as a package
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
os.sys.path.insert(0, str(SRC_PATH))

from getmoredone.app_settings import AppSettings


def write_plist(path: Path, label: str, python_exe: Path, script_path: Path, interval: int, db_path: str | None):
    env_block = ""
    if db_path:
        env_block = f"""
  <key>EnvironmentVariables</key>
  <dict>
    <key>GETMOREDONE_DB</key>
    <string>{db_path}</string>
  </dict>
"""

    plist = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
  <key>Label</key>
  <string>{label}</string>

  <key>ProgramArguments</key>
  <array>
    <string>{python_exe}</string>
    <string>{script_path}</string>
  </array>
{env_block}
  <key>StartInterval</key>
  <integer>{interval}</integer>

  <key>RunAtLoad</key>
  <true/>

  <key>StandardOutPath</key>
  <string>/tmp/getmoredone-gmailimport-{label}.out.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/getmoredone-gmailimport-{label}.err.log</string>
</dict>
</plist>
"""

    path.write_text(plist, encoding="utf-8")


def launchctl(cmd: list[str]):
    subprocess.run(["launchctl", *cmd], check=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reload", choices=["none", "prod", "dev", "both"], default="none")
    args = ap.parse_args()

    settings = AppSettings.load()
    interval = int(getattr(settings, "gmail_import_interval_seconds", 300) or 300)
    if interval < 15:
        interval = 15

    la_dir = Path.home() / "Library" / "LaunchAgents"
    la_dir.mkdir(parents=True, exist_ok=True)

    python_exe = REPO_ROOT / "venv" / "bin" / "python"
    script_path = REPO_ROOT / "tools" / "import_gmd_from_gmail.py"
    dev_db = REPO_ROOT / "data" / "getmoredone.db"

    dev_plist = la_dir / "com.getmoredone.gmailimport.dev.plist"
    prod_plist = la_dir / "com.getmoredone.gmailimport.prod.plist"

    write_plist(dev_plist, "com.getmoredone.gmailimport.dev", python_exe, script_path, interval, str(dev_db))
    write_plist(prod_plist, "com.getmoredone.gmailimport.prod", python_exe, script_path, interval, None)

    # Reload if requested
    if args.reload in ("prod", "both"):
        launchctl(["unload", "-w", str(prod_plist)])
        launchctl(["load", "-w", str(prod_plist)])
    if args.reload in ("dev", "both"):
        launchctl(["unload", "-w", str(dev_plist)])
        launchctl(["load", "-w", str(dev_plist)])

    print(f"Wrote launchd plists. Interval={interval}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
