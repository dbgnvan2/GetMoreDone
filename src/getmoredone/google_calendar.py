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
    from tzlocal import get_localzone
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False


# If modifying these scopes, delete the token.pickle file.
SCOPES = ['https://www.googleapis.com/auth/calendar']


class GoogleCalendarManager:
    """Manages Google Calendar API interactions."""

    def __init__(self, credentials_file: Optional[str] = None, token_file: Optional[str] = None, force_reauth: bool = False):
        """
        Initialize Google Calendar manager.

        Args:
            credentials_file: Path to OAuth credentials JSON file
            token_file: Path to store/load token pickle file
            force_reauth: If True, delete existing token and force re-authentication
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

        # Force re-authentication if requested (deletes zombie tokens)
        if force_reauth and os.path.exists(self.token_file):
            print(f"🗑️  Deleting old token (force re-authentication): {self.token_file}")
            os.remove(self.token_file)

        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Calendar API."""
        creds = None

        # Load existing token
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'rb') as token:
                    creds = pickle.load(token)
                print("Loaded existing token from:", self.token_file)
            except Exception as e:
                print(f"Warning: Failed to load token file: {e}")
                print("Will re-authenticate...")
                creds = None

        # If no valid credentials, let user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    print("Refreshing expired credentials...")
                    creds.refresh(Request())
                    print("Successfully refreshed credentials!")
                except Exception as e:
                    print(f"Failed to refresh credentials: {e}")
                    print("Will need to re-authenticate...")
                    creds = None

            if not creds:
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

                print("\n" + "="*60)
                print("GOOGLE CALENDAR AUTHENTICATION REQUIRED")
                print("="*60)
                print("\nAttempting to open browser for authentication...")
                print("If browser doesn't open, you'll see a URL to visit manually.\n")

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)

                # Try local server method first (opens browser)
                try:
                    # Force consent prompt to avoid browser OAuth cache issues
                    # This ensures we use the correct client_id even if browser has cached old session
                    creds = flow.run_local_server(
                        port=0,
                        open_browser=True,
                        success_message='Authentication successful! You can close this window.',
                        prompt='consent'  # Force re-consent to avoid cached OAuth sessions
                    )
                    print("\n✅ Authentication successful via browser!")

                except Exception as e:
                    print(f"\n⚠️  Browser authentication failed: {e}")
                    print("\nFalling back to manual authentication...")
                    print("\nPlease follow these steps:")
                    print("1. Visit the URL shown below in a browser")
                    print("2. Sign in with your Google account")
                    print("3. Click 'Allow' to grant calendar access")
                    print("4. Copy the authorization code shown")
                    print("5. Paste the code below when prompted\n")

                    try:
                        # Get the authorization URL
                        auth_url, _ = flow.authorization_url(prompt='consent')
                        print(f"Visit this URL:\n{auth_url}\n")

                        # Prompt for code
                        code = input("Enter the authorization code: ").strip()

                        # Exchange code for credentials
                        flow.fetch_token(code=code)
                        creds = flow.credentials
                        print("\n✅ Authentication successful via manual code entry!")

                    except KeyboardInterrupt:
                        raise RuntimeError("\nAuthentication cancelled by user.")
                    except Exception as manual_error:
                        raise RuntimeError(
                            f"Manual authentication failed.\n"
                            f"Browser error: {e}\n"
                            f"Manual auth error: {manual_error}\n\n"
                            f"Troubleshooting:\n"
                            f"1. Check that credentials.json is valid\n"
                            f"2. Ensure Google Calendar API is enabled in Google Cloud Console\n"
                            f"3. Verify OAuth consent screen is configured\n"
                            f"4. Make sure you copied the full authorization code\n"
                            f"5. Try running this on a machine with a web browser\n"
                            f"6. Check network/firewall settings"
                        )

            # Save the credentials for next run
            try:
                with open(self.token_file, 'wb') as token:
                    pickle.dump(creds, token)
                # Set secure permissions
                os.chmod(self.token_file, 0o600)
                print(f"✅ Token saved to: {self.token_file}\n")
            except Exception as e:
                print(f"⚠️  Warning: Failed to save token: {e}")
                print("You may need to re-authenticate next time.\n")

        self.service = build('calendar', 'v3', credentials=creds)
        print("✅ Google Calendar service initialized successfully!")

    def _get_local_timezone(self) -> str:
        """
        Get the local timezone name in IANA format.

        Returns:
            IANA timezone name (e.g., 'America/Los_Angeles')
            Falls back to 'UTC' if detection fails
        """
        try:
            tz = get_localzone()
            return str(tz)
        except Exception:
            # Fallback to UTC if we can't detect local timezone
            print("⚠️  Warning: Could not detect local timezone, using UTC")
            return 'UTC'

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

        # Get local timezone
        local_tz = self._get_local_timezone()

        event = {
            'summary': summary,
            'description': description or '',
            'location': location or '',
            'start': {
                'dateTime': start_datetime.isoformat(),
                'timeZone': local_tz,
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': local_tz,
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
                local_tz = self._get_local_timezone()
                event['start'] = {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': local_tz,
                }
                event['end'] = {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': local_tz,
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

    @staticmethod
    def check_token_validity(token_file: Optional[str] = None) -> dict:
        """
        Check if token file exists and get basic info about it.

        Returns:
            dict with keys: exists, valid, client_id, error
        """
        if not token_file:
            token_file = str(Path.home() / ".getmoredone" / "token.pickle")

        result = {
            'exists': False,
            'valid': None,
            'client_id': None,
            'error': None
        }

        if not os.path.exists(token_file):
            return result

        result['exists'] = True

        try:
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
                result['valid'] = creds.valid if hasattr(creds, 'valid') else None
                result['client_id'] = creds.client_id if hasattr(creds, 'client_id') else None
        except Exception as e:
            result['error'] = str(e)

        return result
