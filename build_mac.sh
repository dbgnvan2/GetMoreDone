#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Use repo venv if present; otherwise fall back to system python
PY="./venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

$PY -m pip install -r requirements.txt
$PY -m pip install pyinstaller

./venv/bin/pyinstaller --noconfirm --clean GetMoreDone.spec

echo "Built: dist/GetMoreDone.app"
