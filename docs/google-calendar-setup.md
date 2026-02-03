# Google Calendar Integration Setup

GetMoreDone can create Google Calendar events directly from action items, making it easy to schedule meetings and block time for tasks.

## Features

- 📅 Create calendar events from action items
- 🔗 Automatic linking of calendar events to tasks
- ⏰ Set start time, duration, location, and attendees
- 🌍 **Automatic timezone detection** - uses your local timezone
- 📝 Pre-fill event with action item details
- 🔄 Events appear as links in the item editor
- ✅ **Meeting tracking** - automatically marks items as meetings with scheduled time

## Configuration Directory

GetMoreDone stores Google Calendar credentials and authentication tokens in:
```
~/.getmoredone/
```

This is your **home directory**, not the project directory. This approach:
- ✅ Keeps credentials secure (less likely to commit to git)
- ✅ Persists across project clones/deletions
- ✅ Shares credentials across multiple GetMoreDone projects
- ✅ Follows standard patterns (like ~/.ssh, ~/.aws)

**Files stored:**
- `credentials.json` - OAuth client credentials (you provide this)
- `token.pickle` - Your authentication token (auto-generated on first login)

Both files are sensitive and should be kept private.

## Prerequisites

1. Python packages (already in requirements.txt):
   - google-auth
   - google-auth-oauthlib
   - google-auth-httplib2
   - google-api-python-client
   - tzlocal (for automatic timezone detection)

2. Google Cloud Project with Calendar API enabled
3. OAuth 2.0 credentials

## Setup Instructions

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. In the project, go to **"APIs & Services" > "Library"**
4. Search for **"Google Calendar API"**
5. Click **"Enable"**

### Step 2: Create OAuth 2.0 Credentials

1. Go to **"APIs & Services" > "Credentials"**
2. Click **"+ CREATE CREDENTIALS"** > **"OAuth client ID"**
3. If prompted, configure the OAuth consent screen:
   - Choose **"Internal"** (for organization) or **"External"** (for personal use)
   - Fill in required fields:
     - App name: "GetMoreDone"
     - User support email: your email
     - Developer contact: your email
   - Click **"Save and Continue"**
   - On Scopes, click **"Add or Remove Scopes"**
   - Search for "Google Calendar API" and select: `.../auth/calendar`
   - Click **"Save and Continue"**
   - On Test users (if External), add your email
   - Click **"Save and Continue"**

4. Back on Credentials page:
   - Click **"+ CREATE CREDENTIALS"** > **"OAuth client ID"**
   - Application type: **"Desktop app"**
   - Name: "GetMoreDone Desktop"
   - Click **"Create"**

5. Download the credentials:
   - Click the download icon next to your OAuth 2.0 Client ID
   - This downloads a JSON file (usually named like `client_secret_XXXXX.json`)

### Step 3: Install Credentials

1. Rename the downloaded file to `credentials.json`
2. Place it in the GetMoreDone config directory:
   ```bash
   mkdir -p ~/.getmoredone
   mv ~/Downloads/client_secret_*.json ~/.getmoredone/credentials.json
   ```

3. Set correct permissions:
   ```bash
   chmod 600 ~/.getmoredone/credentials.json
   ```

### Step 4: First-Time Authorization

1. Launch GetMoreDone
2. Open any action item
3. Click the **"📅 Calendar"** button
4. Fill in event details
5. Click **"Create Calendar Event"**
6. Your browser will open asking you to authorize the app
7. Sign in with your Google account
8. Click **"Allow"** to grant calendar access
9. The browser will show "The authentication flow has completed"
10. Close the browser tab and return to GetMoreDone

A `token.pickle` file will be created in `~/.getmoredone/` to save your authorization for future use.

## Usage

### Creating a Calendar Event

1. **Open an action item** in the Item Editor
2. Click the **"📅 Calendar"** button (purple, on the button bar)
3. Fill in the event details:
   - **Event Title**: Defaults to action item title
   - **Date**: Use quick buttons (Today, +1) or enter YYYY-MM-DD
   - **Start Time**: Hour (1-12), Minute (0-59), AM/PM (uses your local timezone)
   - **Duration**: In minutes (default: 60)
   - **Description**: Optional (defaults to action item description)
   - **Location**: Optional
   - **Attendees**: Optional, comma-separated emails
4. Click **"Create Calendar Event"**
5. The event is created and automatically:
   - A link appears in the item's Links section
   - **"Is Meeting"** checkbox is checked
   - **"Meeting Time"** field displays the scheduled time

### Viewing Calendar Events

- Calendar links appear in the **Links & Notes** tab of the item editor
- Labeled as "Calendar: [Event Title]"
- Click the link to open the event in Google Calendar (browser)

### Managing Events

- **Edit**: Click the calendar link to open in Google Calendar, edit there
- **Delete**: Delete from Google Calendar directly
- **Remove Link**: Click the 🗑️ button next to the link in GetMoreDone

## Troubleshooting

### "Google Calendar libraries not installed"

**Solution**: Install dependencies:
```bash
pip install -r requirements.txt
```

**If using a virtual environment (venv)**, make sure to activate it first:
```bash
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Then install
pip install -r requirements.txt
```

**Or use the startup script** (recommended):
```bash
./start.sh  # Linux/Mac
start.bat   # Windows
```

### "Google Calendar credentials not found"

**Solution**: Make sure `credentials.json` is at `~/.getmoredone/credentials.json`

### "Invalid date format"

**Solution**: Use YYYY-MM-DD format (e.g., 2026-01-15)

### "Invalid time"

**Solution**: Hour must be 1-12, Minute must be 0-59

### "Failed to create calendar event: 403"

**Solution**:
1. Verify Google Calendar API is enabled in Google Cloud Console
2. Check OAuth consent screen status
3. Make sure your email is in test users (if External app)
4. Try deleting `~/.getmoredone/token.pickle` and re-authorizing

### "Authentication flow has completed" but event not created

**Solution**:
1. Check terminal output for errors
2. Verify `token.pickle` was created at `~/.getmoredone/token.pickle`
3. Try the calendar creation again

### Authorization browser doesn't open

**Solution**:
1. Look for a URL in the terminal output
2. Copy and paste it into your browser manually
3. Complete authorization and return to app

### Calendar event appears at wrong time

**This should not happen anymore** - GetMoreDone now auto-detects your timezone.

If you still see incorrect times:
1. Verify your system timezone is set correctly
2. Restart GetMoreDone to pick up timezone changes
3. Check if `tzlocal` is installed: `pip show tzlocal`
4. If issue persists, check the terminal for timezone detection warnings

## Security Notes

- **credentials.json**: Contains OAuth client credentials, keep private
- **token.pickle**: Contains your authorization token, keep private
- Both files are stored in `~/.getmoredone/` (user's home directory)
- Never commit these files to version control
- The `.gitignore` already excludes these files

## Timezone Handling

**Automatic Detection:**
GetMoreDone automatically detects and uses your **local timezone** when creating calendar events. No configuration needed!

- Uses the `tzlocal` library to detect your system's timezone
- Events are created in your local timezone automatically
- No more timezone confusion or manual configuration
- Falls back to UTC if timezone detection fails (rare)

**Example:**
- If you're in California (Pacific Time), events use `America/Los_Angeles`
- If you're in London, events use `Europe/London`
- If you're in Tokyo, events use `Asia/Tokyo`

This ensures calendar events appear at the correct time in Google Calendar, regardless of where you are.

## Privacy

- GetMoreDone only accesses your primary Google Calendar
- It only creates/reads events you explicitly create through the app
- No data is sent to external servers (direct Google API connection)
- Authorization tokens are stored locally on your machine

## Technical Details

- **API**: Google Calendar API v3
- **Authentication**: OAuth 2.0 (Desktop app flow)
- **Scopes**: `https://www.googleapis.com/auth/calendar`
- **Storage**: SQLite (links, meeting data), Local files (credentials/tokens)
- **Link Type**: `google_calendar` (stored in `item_links` table)
- **Timezone**: Auto-detected using `tzlocal` library
- **Meeting Tracking**:
  - `is_meeting` flag in `action_items` table (INTEGER, 0 or 1)
  - `meeting_start_time` in `action_items` table (TEXT, ISO datetime format)

## Uninstalling

To remove Google Calendar integration:

```bash
# Remove credentials and tokens
rm ~/.getmoredone/credentials.json
rm ~/.getmoredone/token.pickle

# Revoke app access (optional)
# Go to: https://myaccount.google.com/permissions
# Find "GetMoreDone" and click "Remove Access"
```
