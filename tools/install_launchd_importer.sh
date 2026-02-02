#!/usr/bin/env bash
set -euo pipefail

# Installs launchd plists for Gmail→GetMoreDone importer.
# Creates:
#   ~/Library/LaunchAgents/com.getmoredone.gmailimport.dev.plist
#   ~/Library/LaunchAgents/com.getmoredone.gmailimport.prod.plist
#
# Usage:
#   ./tools/install_launchd_importer.sh
#
# Then load one (recommended: only one at a time):
#   launchctl load -w ~/Library/LaunchAgents/com.getmoredone.gmailimport.prod.plist
#

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_ROOT/venv/bin/python"
SCRIPT="$REPO_ROOT/tools/import_gmd_from_gmail.py"
DEV_DB="$REPO_ROOT/data/getmoredone.db"

LA_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LA_DIR"

write_plist() {
  local label="$1"
  local plist_path="$2"
  local db_path="$3"  # empty means prod default

  if [[ -n "$db_path" ]]; then
    cat > "$plist_path" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${PY}</string>
    <string>${SCRIPT}</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>GETMOREDONE_DB</key>
    <string>${db_path}</string>
  </dict>

  <key>StartInterval</key>
  <integer>60</integer>

  <key>RunAtLoad</key>
  <true/>

  <key>StandardOutPath</key>
  <string>/tmp/getmoredone-gmailimport-${label}.out.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/getmoredone-gmailimport-${label}.err.log</string>
</dict>
</plist>
EOF
  else
    cat > "$plist_path" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${PY}</string>
    <string>${SCRIPT}</string>
  </array>

  <key>StartInterval</key>
  <integer>60</integer>

  <key>RunAtLoad</key>
  <true/>

  <key>StandardOutPath</key>
  <string>/tmp/getmoredone-gmailimport-${label}.out.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/getmoredone-gmailimport-${label}.err.log</string>
</dict>
</plist>
EOF
  fi
}

DEV_PLIST="$LA_DIR/com.getmoredone.gmailimport.dev.plist"
PROD_PLIST="$LA_DIR/com.getmoredone.gmailimport.prod.plist"

write_plist "com.getmoredone.gmailimport.dev" "$DEV_PLIST" "$DEV_DB"
write_plist "com.getmoredone.gmailimport.prod" "$PROD_PLIST" ""

echo "Wrote: $DEV_PLIST"
echo "Wrote: $PROD_PLIST"
echo
echo "Next: load ONE of them (not both):"
echo "  launchctl load -w $PROD_PLIST"
echo "or"
echo "  launchctl load -w $DEV_PLIST"
