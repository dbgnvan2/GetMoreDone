"""Gmail → GetMoreDone importer.

This watches a Gmail label (e.g. "GMD") and creates GetMoreDone Action Items
in the local SQLite DB.

Design goals:
- No Spark API dependency (Spark is just your mail client)
- Gmail label is the trigger
- After import, remove trigger label and apply a "moved" label (e.g. "GMD/moved")

Auth:
- Uses Google OAuth via Installed App flow.
- Token/credentials live in the existing GetMoreDone credential directory.

"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Iterable

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from .db_manager import DatabaseManager
from .email_cleaning import clean_email_body
from .models import ActionItem, ItemLink
from .paths import app_data_dir_path, legacy_dot_dir


SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_logger() -> logging.Logger:
    """Get the Gmail importer logger, configured with timestamps."""
    logger = logging.getLogger("getmoredone.gmail_importer")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    
    # We log to stdout/stderr which are redirected by launchd to /tmp logs.
    # By using a formatter here, we get timestamps in those files.
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


@dataclass
class GmailImportConfig:
    gmail_user_id: str = "me"  # "me" == authenticated user
    trigger_label_name: str = "GMD"
    moved_label_name: str = "GMD/moved"

    who_value: str = "Email"
    group_value: str = "EMAIL"

    # Dates
    start_offset_days: int = 0
    due_offset_days: int = 1

    # Body handling
    max_body_chars: int = 40000  # keep DB reasonable

    # Credentials
    credentials_json: str = str(legacy_dot_dir() / "credentials.json")
    token_json: str = str(legacy_dot_dir() / "gmail_token.json")


def _load_creds(cfg: GmailImportConfig) -> Credentials:
    token_path = legacy_dot_dir() / "gmail_token.json"
    token_path.parent.mkdir(parents=True, exist_ok=True)

    creds: Optional[Credentials] = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                get_logger().warning(f"Could not refresh token: {e}. Re-authenticating...")
                flow = InstalledAppFlow.from_client_secrets_file(cfg.credentials_json, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cfg.credentials_json, SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def _header(headers: list[dict], name: str) -> Optional[str]:
    name_l = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_l:
            return h.get("value")
    return None


def _decode_b64url(data: str) -> str:
    # Gmail uses URL-safe base64 without padding
    data += "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")


def _extract_plain_text(payload: dict) -> str:
    """Extract a best-effort plain-text body from a Gmail message payload."""

    def walk(part: dict) -> Iterable[dict]:
        yield part
        for p in part.get("parts", []) or []:
            yield from walk(p)

    # Prefer text/plain parts
    for part in walk(payload):
        if part.get("mimeType") == "text/plain":
            body = part.get("body", {})
            data = body.get("data")
            if data:
                return _decode_b64url(data)

    # Fallback: try text/html and strip tags crudely
    for part in walk(payload):
        if part.get("mimeType") == "text/html":
            body = part.get("body", {})
            data = body.get("data")
            if data:
                html = _decode_b64url(data)
                # very rough html->text
                html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
                html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.I)
                text = re.sub(r"<[^>]+>", "", html)
                return re.sub(r"\n{3,}", "\n\n", text).strip()

    return ""


def _gmail_thread_url(thread_id: str) -> str:
    # Works for most users; Gmail will route to correct UI.
    return f"https://mail.google.com/mail/u/0/#all/{thread_id}"


def _get_or_create_label_id(service, user_id: str, label_name: str) -> str:
    labels = service.users().labels().list(userId=user_id).execute().get("labels", [])
    for lab in labels:
        if lab.get("name") == label_name:
            return lab["id"]

    created = service.users().labels().create(
        userId=user_id,
        body={
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()
    return created["id"]


def import_labeled_emails(db_path: Optional[str] = None, cfg: Optional[GmailImportConfig] = None, dry_run: bool = False) -> int:
    """Import messages currently in cfg.trigger_label_name.

    Returns number of imported messages.
    """
    cfg = cfg or GmailImportConfig()
    logger = get_logger()

    try:
        creds = _load_creds(cfg)
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        user_id = cfg.gmail_user_id
        trigger_label_id = _get_or_create_label_id(service, user_id, cfg.trigger_label_name)
        moved_label_id = _get_or_create_label_id(service, user_id, cfg.moved_label_name)

        # List message IDs under trigger label
        resp = service.users().messages().list(userId=user_id, labelIds=[trigger_label_id]).execute()
        messages = resp.get("messages", []) or []

        imported = 0
        if not messages:
            return 0

        dbm = DatabaseManager(db_path=db_path)
        try:
            for m in messages:
                msg_id = m["id"]
                full = service.users().messages().get(userId=user_id, id=msg_id, format="full").execute()
                payload = full.get("payload", {})
                headers = payload.get("headers", []) or []

                subject = _header(headers, "Subject") or "(no subject)"
                from_h = _header(headers, "From") or ""
                date_h = _header(headers, "Date") or ""

                logger.info(f"Importing email: {subject} from {from_h}")

                # Strip separators, footer boilerplate and excess blank lines
                # before the body lands in the Action Item description.
                body_text = clean_email_body(_extract_plain_text(payload))
                if cfg.max_body_chars and len(body_text) > cfg.max_body_chars:
                    body_text = body_text[: cfg.max_body_chars] + "\n\n[TRUNCATED]"

                today = date.today()
                start_date = (today + timedelta(days=cfg.start_offset_days)).isoformat()
                due_date = (today + timedelta(days=cfg.due_offset_days)).isoformat()

                desc_parts = [
                    f"From: {from_h}",
                    f"Date: {date_h}",
                    "",
                    body_text.strip(),
                ]
                description = "\n".join(desc_parts).strip()

                item = ActionItem(
                    who=cfg.who_value,
                    title=subject,
                    description=description,
                    start_date=start_date,
                    due_date=due_date,
                    group=cfg.group_value,
                )

                if dry_run:
                    # Don't touch DB or Gmail labels
                    logger.info(f"[DRY RUN] Would create item for: {subject}")
                    imported += 1
                    continue

                item_id = dbm.create_action_item(item, apply_defaults=True)

                # Link back to Gmail thread
                thread_id = full.get("threadId")
                if thread_id:
                    link = ItemLink(
                        item_id=item_id,
                        url=_gmail_thread_url(thread_id),
                        label="Email (Gmail)",
                        link_type="url",
                    )
                    dbm.add_item_link(link)

                # Move: remove trigger label, add moved label
                service.users().messages().modify(
                    userId=user_id,
                    id=msg_id,
                    body={"addLabelIds": [moved_label_id], "removeLabelIds": [trigger_label_id]},
                ).execute()

                imported += 1

        finally:
            dbm.close()

        return imported

    except Exception as e:
        logger.exception(f"Error during Gmail import: {e}")
        raise
