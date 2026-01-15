"""
Google Calendar integration for creating meeting events.
"""

import os
import pickle
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False


# If modifying these scopes, delete the token.pickle file.
SCOPES = ['https://www.googleapis.com/auth/calendar']


class GoogleCalendarManager:
    """Manages Google Calendar API interactions."""

    def __init__(self, credentials_file: Optional[str] = None, token_file: Optional[str] = None):
        """
        Initialize Google Calendar manager.

        Args:
            credentials_file: Path to OAuth credentials JSON file
            token_file: Path to store/load token pickle file
        """
        if not GOOGLE_CALENDAR_AVAILABLE:
            raise ImportError(
                "Google Calendar libraries not installed. "
                "Run: pip install google-auth google-auth-oauthlib "
                "google-auth-httplib2 google-api-python-client"
            )

        # Default paths
        self.data_dir = Path.home() / ".getmoredone"
        self.data_dir.mkdir(exist_ok=True)

        self.credentials_file = credentials_file or str(self.data_dir / "credentials.json")
        self.token_file = token_file or str(self.data_dir / "token.pickle")

        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Calendar API."""
        creds = None

        # Load existing token
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

        # If no valid credentials, let user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"Google Calendar credentials not found at: {self.credentials_file}\n"
                        "Please download OAuth credentials from Google Cloud Console:\n"
                        "1. Go to https://console.cloud.google.com/\n"
                        "2. Create project or select existing\n"
                        "3. Enable Google Calendar API\n"
                        "4. Create OAuth 2.0 credentials (Desktop app)\n"
                        "5. Download JSON and save as credentials.json\n"
                        f"6. Place at: {self.credentials_file}"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)

        self.service = build('calendar', 'v3', credentials=creds)

    def create_event(
        self,
        summary: str,
        start_datetime: datetime,
        duration_minutes: int = 60,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Create a Google Calendar event.

        Args:
            summary: Event title
            start_datetime: When the event starts
            duration_minutes: Event duration in minutes
            description: Event description/notes
            location: Event location
            attendees: List of email addresses

        Returns:
            Dict with event details including 'htmlLink' for the calendar URL

        Raises:
            HttpError: If the API request fails
        """
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)

        event = {
            'summary': summary,
            'description': description or '',
            'location': location or '',
            'start': {
                'dateTime': start_datetime.isoformat(),
                'timeZone': 'America/New_York',  # TODO: Make configurable
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': 'America/New_York',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }

        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        try:
            event_result = self.service.events().insert(
                calendarId='primary',
                body=event,
                sendUpdates='none'  # Don't send email notifications
            ).execute()

            return event_result

        except HttpError as error:
            raise RuntimeError(f"Failed to create calendar event: {error}")

    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start_datetime: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing calendar event."""
        try:
            # Get existing event
            event = self.service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()

            # Update fields
            if summary:
                event['summary'] = summary
            if description is not None:
                event['description'] = description
            if start_datetime and duration_minutes:
                end_datetime = start_datetime + timedelta(minutes=duration_minutes)
                event['start'] = {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'America/New_York',
                }
                event['end'] = {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'America/New_York',
                }

            updated_event = self.service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=event
            ).execute()

            return updated_event

        except HttpError as error:
            raise RuntimeError(f"Failed to update calendar event: {error}")

    def delete_event(self, event_id: str):
        """Delete a calendar event."""
        try:
            self.service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
        except HttpError as error:
            raise RuntimeError(f"Failed to delete calendar event: {error}")

    @staticmethod
    def is_available() -> bool:
        """Check if Google Calendar integration is available."""
        return GOOGLE_CALENDAR_AVAILABLE

    @staticmethod
    def has_credentials(credentials_file: Optional[str] = None) -> bool:
        """Check if credentials file exists."""
        if credentials_file:
            return os.path.exists(credentials_file)

        default_path = Path.home() / ".getmoredone" / "credentials.json"
        return default_path.exists()
