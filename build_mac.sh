#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Use repo venv if present; otherwise fall back to system python.
PY="./venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

$PY -m pip install -r requirements.txt
$PY -m pip install pyinstaller

# Invoke PyInstaller through $PY. Calling ./venv/bin/pyinstaller directly meant
# the python3 fallback above could never work — the venv it referenced was the
# very thing we had just established was absent.
# Guarded by tests/test_packaging_resources.py::test_rm1c_build_scripts_do_not_hardcode_venv_pyinstaller
$PY -m PyInstaller --noconfirm --clean GetMoreDone.spec

# Prove the bundle actually starts before calling the build a success.
# A temp DB keeps the build from touching the developer's real database.
SELFTEST_DB="$(mktemp -t gmd-selftest)"
trap 'rm -f "$SELFTEST_DB"' EXIT
GETMOREDONE_DB="$SELFTEST_DB" ./dist/GetMoreDone.app/Contents/MacOS/GetMoreDone --selftest

echo "Built: dist/GetMoreDone.app"
