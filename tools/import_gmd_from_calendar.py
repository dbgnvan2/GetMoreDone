#!/usr/bin/env python3
"""Import Google Calendar events into GetMoreDone as open Action Items.

Usage:
  python tools/import_gmd_from_calendar.py
  python tools/import_gmd_from_calendar.py --days 30
  python tools/import_gmd_from_calendar.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root without installing as a package
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from getmoredone.calendar_importer import CalendarImportConfig, import_upcoming_calendar_events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Preview imports without writing to DB")
    ap.add_argument("--db", help="Optional path to getmoredone.db")
    ap.add_argument("--days", type=int, default=14, help="Import events in next N days (default: 14)")
    ap.add_argument("--calendar-id", default="primary", help="Google Calendar ID (default: primary)")
    ap.add_argument("--who", default="Calendar", help="Who value for imported items")
    ap.add_argument("--group", default="CALENDAR", help="Group value for imported items")
    ap.add_argument("--no-all-day", action="store_true", help="Skip all-day events")
    args = ap.parse_args()

    cfg = CalendarImportConfig(
        calendar_id=args.calendar_id,
        days_ahead=max(1, args.days),
        who_value=args.who or "Calendar",
        group_value=args.group or "CALENDAR",
        include_all_day=not args.no_all_day,
    )

    stats = import_upcoming_calendar_events(db_path=args.db, cfg=cfg, dry_run=args.dry_run)

    print(
        "Calendar import complete: "
        f"seen={stats['events_seen']}, "
        f"created={stats['created']}, "
        f"updated_existing={stats.get('updated_existing', 0)}, "
        f"skipped_existing={stats['skipped_existing']}, "
        f"skipped_all_day={stats['skipped_all_day']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
