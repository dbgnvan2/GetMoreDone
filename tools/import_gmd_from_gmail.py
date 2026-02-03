#!/usr/bin/env python3
"""Import emails from Gmail label GMD into GetMoreDone.

Usage:
  python tools/import_gmd_from_gmail.py
  python tools/import_gmd_from_gmail.py --dry-run

Notes:
- Requires ~/.getmoredone/credentials.json (OAuth client)
- First run will open a browser for authorization and store token at ~/.getmoredone/gmail_token.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root without installing as a package
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from getmoredone.gmail_importer import GmailImportConfig, import_labeled_emails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", help="Optional path to getmoredone.db")
    ap.add_argument("--label", default="GMD", help="Trigger label name")
    ap.add_argument("--moved", default="GMD/moved", help="Moved/processed label name")
    args = ap.parse_args()

    cfg = GmailImportConfig(
        trigger_label_name=args.label,
        moved_label_name=args.moved,
        who_value="Email",
        group_value="EMAIL",
        start_offset_days=0,
        due_offset_days=1,
    )

    n = import_labeled_emails(db_path=args.db, cfg=cfg, dry_run=args.dry_run)
    print(f"Imported {n} email(s) from label {cfg.trigger_label_name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
