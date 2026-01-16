# Fix: OAuth Client ID Mismatch

## Problem

When attempting to authenticate with Google Calendar, the OAuth URL shows the wrong client_id:

```
❌ WRONG (Bowen1rag project):
client_id=888606952491-5anpt1nbript6ls1l02jmtqds2ufaqfg.apps.googleusercontent.com

✅ CORRECT (getmoredone project):
client_id=592866309318-7r1aor9ln8von3vlbqgrineslrl91e6u.apps.googleusercontent.com
```

## Root Cause

The application loads cached authentication tokens from `~/.getmoredone/token.pickle`. If this token file was created using a different OAuth client (e.g., from the "Bowen1rag" project), it will continue to use that client_id even after you've updated `credentials.json`.

This is what we call a **"Zombie Token"** - a cached token from a different project that refuses to die.

## Solution

### Quick Fix (Recommended)

Run the automated diagnostic and fix script:

```bash
./fix_client_id_mismatch.sh
```

This script will:
1. ✅ Verify `credentials.json` has the correct client_id
2. 🔍 Find all cached token files
3. 🗑️ Offer to delete zombie tokens
4. 🌐 Guide you through clearing browser cache
5. 🧪 Test authentication

### Manual Fix

If you prefer to fix it manually:

#### Step 1: Delete Cached Tokens

```bash
rm -f ~/.getmoredone/token.pickle
rm -f ~/.credentials/*.pickle  # If this directory exists
```

#### Step 2: Verify credentials.json

Check that your `~/.getmoredone/credentials.json` has the correct client_id:

```bash
python3 diagnose_client_id.py
```

Expected output:
```
✅ This is the CORRECT client_id (getmoredone project)
Client ID: 592866309318-7r1aor9ln8von3vlbqgrineslrl91e6u.apps.googleusercontent.com
```

#### Step 3: Clear Browser Cache

The browser may have cached OAuth sessions. Clear them:

1. Open your browser settings
2. Go to: `chrome://settings/cookies` (or equivalent)
3. Search for: `accounts.google.com`
4. Delete **all** cookies for accounts.google.com
5. **Close ALL browser windows**
6. Restart browser

#### Step 4: Re-authenticate

```bash
python3 test_auth.py
```

When the OAuth URL opens, verify it shows the **correct** client_id:
```
client_id=592866309318-7r1aor9ln8von3vlbqgrineslrl91e6u.apps.googleusercontent.com
```

## Why This Happens

### Authentication Flow

1. App checks for existing token: `~/.getmoredone/token.pickle`
2. If found, loads the token (which contains a client_id)
3. If not found, loads credentials from `credentials.json`
4. Creates new OAuth flow with client_id from credentials.json

### The Problem

If step 1 finds an existing token from the wrong project, it will:
- Use the **old client_id** from the cached token
- Ignore your new `credentials.json`
- Show the wrong project name in OAuth consent screen

### URL Analysis

When you see this URL:
```
https://accounts.google.com/o/oauth2/auth?
  client_id=888606952491-5anpt1nbript6ls1l02jmtqds2ufaqfg.apps.googleusercontent.com
  &redirect_uri=http://localhost:61199/
  &scope=https://www.googleapis.com/auth/calendar
```

It tells us:
- `client_id`: Which OAuth client is being used (wrong one!)
- `redirect_uri`: The callback URL (port may vary: 61199, 8080, etc.)
- `scope`: Permissions requested (calendar access)

## Additional Observations from URL

### Port Number Differences

The OAuth redirect_uri shows `http://localhost:61199/` but your `credentials.json` has `http://localhost`. This is **normal** - Google's OAuth library automatically picks an available port and appends it to the localhost redirect URI.

### Scope Differences

- **URL shows**: `scope=https://www.googleapis.com/auth/calendar` ✅
- **Your app requests**: Calendar access ✅

This is correct! Your app is requesting calendar access, not Gmail/email access.

## Verification

After applying the fix, verify everything is correct:

### 1. Check credentials.json

```bash
python3 diagnose_client_id.py
```

Should show:
```
✅ credentials.json has CORRECT client_id
✅ No cached token files found
✅ No issues found!
```

### 2. Check OAuth URL

When you run the app, check the OAuth URL carefully:
```bash
python3 test_auth.py
```

The URL should contain:
```
client_id=592866309318-7r1aor9ln8von3vlbqgrineslrl91e6u.apps.googleusercontent.com
```

### 3. Check OAuth Consent Screen

The consent screen should show:
- **App name**: GetMoreDone (not "Bowen1rag")
- **Project**: getmoredone
- **Permissions**: Google Calendar access

## Troubleshooting

### Still seeing wrong client_id?

1. **Browser cache**: Use incognito/private mode
   ```bash
   # On Linux, you can specify browser:
   BROWSER=/usr/bin/google-chrome python3 test_auth.py
   ```

2. **Multiple credentials files**: Search for all credentials.json files
   ```bash
   find ~/ -name "credentials.json" 2>/dev/null
   ```

3. **Multiple Python environments**: Make sure you're using the right venv
   ```bash
   which python3
   # Should show: /home/user/GetMoreDone/venv/bin/python3
   ```

4. **Hardcoded credentials**: Search the codebase (already checked - none found)
   ```bash
   grep -r "888606952491" .
   ```

### OAuth consent screen shows "Bowen1rag"?

This means the OAuth client is from the wrong project. Check:

1. **credentials.json project_id**:
   ```bash
   jq .installed.project_id ~/.getmoredone/credentials.json
   ```
   Should output: `"getmoredone"`

2. **Download correct credentials**:
   - Go to: https://console.cloud.google.com/
   - Select project: **getmoredone** (NOT Bowen1rag)
   - APIs & Services > Credentials
   - Download OAuth client credentials
   - Save as `~/.getmoredone/credentials.json`

## Prevention

To avoid this issue in the future:

### 1. Force Re-authentication

When switching projects, always force re-auth:

```python
from getmoredone.google_calendar import GoogleCalendarManager

manager = GoogleCalendarManager(force_reauth=True)
```

This automatically deletes the old token.

### 2. Zombie Token Detection

The `test_auth.py` script now has built-in zombie token detection:

```python
python3 test_auth.py
```

It will warn you:
```
🧟 ZOMBIE TOKEN DETECTED!
Your token.pickle is from a DIFFERENT project than credentials.json!

Delete the old token and re-authenticate? (y/N):
```

### 3. Use Diagnostic Tool

Run the diagnostic before authentication:

```bash
python3 diagnose_client_id.py
```

This will catch mismatches before they cause problems.

## Tools Provided

### 1. `diagnose_client_id.py`

Comprehensive diagnostic tool that checks:
- ✅ credentials.json client_id
- ✅ All cached token files
- ✅ Token/credential mismatches
- 📋 Detailed recommendations

```bash
python3 diagnose_client_id.py
```

### 2. `fix_client_id_mismatch.sh`

Interactive fix script that:
- 🔍 Detects the problem
- 🗑️ Deletes zombie tokens
- 🌐 Guides browser cache clearing
- 🧪 Tests authentication

```bash
./fix_client_id_mismatch.sh
```

### 3. `test_auth.py`

Enhanced test script with:
- 🧟 Zombie token detection
- 🔄 Automatic fix option
- 📊 Detailed diagnostics
- ✅ Calendar API verification

```bash
python3 test_auth.py
```

## Related Issues

- [Zombie Token Detection](./ZOMBIE_TOKEN_FIX.md) - General zombie token problems
- [OAuth Consent Screen Fix](./OAUTH_CONSENT_SCREEN_FIX.md) - App name mismatches
- [Google Calendar Authentication](./GOOGLE_CALENDAR_AUTH.md) - Complete auth guide

## Summary

**The problem**: Cached `token.pickle` from "Bowen1rag" project (888606952491...)
**The solution**: Delete cached token, verify correct `credentials.json`, clear browser cache
**The tools**: `diagnose_client_id.py`, `fix_client_id_mismatch.sh`, `test_auth.py`

Your system is now configured correctly with:
- ✅ credentials.json from "getmoredone" project (592866309318...)
- ✅ No cached zombie tokens
- ✅ Proper OAuth client setup

Next time you run the app, it should authenticate with the **correct** client_id!
