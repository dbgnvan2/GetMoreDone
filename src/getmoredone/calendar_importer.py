"""Google Calendar -> GetMoreDone importer.

Creates open Action Items from upcoming Google Calendar events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from .db_manager import DatabaseManager
from .google_calendar import GoogleCalendarManager
from .models import ActionItem, ItemLink


@dataclass
class CalendarImportConfig:
    calendar_id: str = "primary"
    days_ahead: int = 14
    who_value: str = "Calendar"
    group_value: str = "CALENDAR"
    include_all_day: bool = True


def _parse_rfc3339(value: str) -> datetime:
    """Parse RFC3339 datetime string from Google APIs."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _extract_event_timing(event: dict) -> tuple[Optional[str], Optional[str], Optional[str], Optional[int], bool]:
    """
    Returns:
      start_date, due_date, meeting_start_time_iso, planned_minutes, is_all_day
    """
    start = event.get("start", {}) or {}
    end = event.get("end", {}) or {}

    # Timed event
    if "dateTime" in start:
        start_dt = _parse_rfc3339(start["dateTime"])
        start_date = start_dt.date().isoformat()
        due_date = start_date
        meeting_start_time = start_dt.isoformat()

        planned_minutes = None
        if "dateTime" in end:
            end_dt = _parse_rfc3339(end["dateTime"])
            delta_min = int((end_dt - start_dt).total_seconds() // 60)
            planned_minutes = max(0, delta_min)

        return start_date, due_date, meeting_start_time, planned_minutes, False

    # All-day event
    if "date" in start:
        start_date = start["date"]
        due_date = start_date
        return start_date, due_date, None, None, True

    return None, None, None, None, False


def _find_item_id_for_event(conn, event_id: str) -> Optional[str]:
    """Find existing item linked to this calendar event."""
    marker = f"Google Calendar Event: {event_id}"
    row = conn.execute(
        """
        SELECT item_id
        FROM item_links
        WHERE link_type = 'google_calendar' AND label = ?
        LIMIT 1
        """,
        (marker,),
    ).fetchone()
    if row:
        return row["item_id"]
    return None


def import_upcoming_calendar_events(
    db_path: Optional[str] = None,
    cfg: Optional[CalendarImportConfig] = None,
    dry_run: bool = False,
) -> dict:
    """
    Import upcoming calendar events as open action items.

    Returns:
      {
        "events_seen": int,
        "created": int,
        "updated_existing": int,
        "skipped_existing": int,
        "skipped_all_day": int
      }
    """
    cfg = cfg or CalendarImportConfig()

    manager = GoogleCalendarManager()
    service = manager.service

    now_utc = datetime.now(timezone.utc)
    end_utc = now_utc + timedelta(days=max(1, int(cfg.days_ahead)))

    events = []
    page_token = None
    while True:
        resp = service.events().list(
            calendarId=cfg.calendar_id,
            timeMin=now_utc.isoformat().replace("+00:00", "Z"),
            timeMax=end_utc.isoformat().replace("+00:00", "Z"),
            singleEvents=True,
            orderBy="startTime",
            pageToken=page_token,
            showDeleted=False,
        ).execute()
        events.extend(resp.get("items", []) or [])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    stats = {
        "events_seen": 0,
        "created": 0,
        "updated_existing": 0,
        "skipped_existing": 0,
        "skipped_all_day": 0,
    }

    if not events:
        return stats

    dbm = DatabaseManager(db_path=db_path)
    try:
        for event in events:
            stats["events_seen"] += 1

            event_id = event.get("id")
            if not event_id:
                continue

            start_date, due_date, meeting_start_time, planned_minutes, is_all_day = _extract_event_timing(event)
            if not start_date:
                continue

            if is_all_day and not cfg.include_all_day:
                stats["skipped_all_day"] += 1
                continue

            summary = (event.get("summary") or "").strip() or "(No title)"
            description = (event.get("description") or "").strip() or None
            location = (event.get("location") or "").strip()
            if location:
                location_line = f"Location: {location}"
                description = f"{location_line}\n\n{description}" if description else location_line

            existing_item_id = _find_item_id_for_event(dbm.db.conn, event_id)
            if existing_item_id:
                # Sync selected fields for already-imported events.
                existing_item = dbm.get_action_item(existing_item_id)
                if not existing_item:
                    stats["skipped_existing"] += 1
                    continue

                existing_item.planned_minutes = planned_minutes
                existing_item.is_meeting = True
                existing_item.meeting_start_time = meeting_start_time
                existing_item.description = description
                existing_item.start_date = start_date
                existing_item.due_date = due_date

                if dry_run:
                    stats["updated_existing"] += 1
                else:
                    dbm.update_action_item(existing_item)
                    stats["updated_existing"] += 1
                continue

            item = ActionItem(
                who=cfg.who_value,
                title=summary,
                description=description,
                start_date=start_date,
                due_date=due_date,
                group=cfg.group_value,
                planned_minutes=planned_minutes,
                is_meeting=True,
                meeting_start_time=meeting_start_time,
                status="open",
            )

            if dry_run:
                stats["created"] += 1
                continue

            item_id = dbm.create_action_item(item, apply_defaults=True)

            link = ItemLink(
                item_id=item_id,
                url=event.get("htmlLink") or f"https://calendar.google.com/calendar/u/0/r/eventedit/{event_id}",
                label=f"Google Calendar Event: {event_id}",
                link_type="google_calendar",
            )
            dbm.add_item_link(link)
            stats["created"] += 1
    finally:
        dbm.close()

    return stats
