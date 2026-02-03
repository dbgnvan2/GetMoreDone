# Email/Calendar Authentication Troubleshooting Guide

## Overview

GetMoreDone uses **Google Calendar API with OAuth 2.0** for calendar integration. There is no direct "email login" - authentication is handled through Google's secure OAuth flow.

## ✅ What Has Been Fixed

1. **Google Calendar dependencies installed**
   - All required packages (`google-auth`, `google-auth-oauthlib`, etc.) are now installed

2. **Improved authentication flow**
   - Better error handling and logging
   - Automatic fallback to manual authentication if browser doesn't open
   - Detailed troubleshooting messages

3. **Fixed permissions**
   - `~/.getmoredone/` directory secured (700 permissions)
   - `credentials.json` secured (600 permissions)
   - `token.pickle` will be created with secure permissions (600)

4. **Enhanced error messages**
   - Clear step-by-step instructions
   - Detailed error diagnostics
   - Multiple authentication methods

## 🔧 Current Setup Status

### ✅ Completed
- Google Calendar dependencies installed
- credentials.json exists at `~/.getmoredone/credentials.json`
- Secure permissions configured

### ⚠️ Needs Attention
- **token.pickle is missing** - You need to complete first-time authentication

## 🚀 How to Authenticate (First Time)

### Method 1: Browser Authentication (Recommended)

1. **Launch GetMoreDone**
   ```bash
   cd /home/user/GetMoreDone
   python3 -m getmoredone
   ```

2. **Trigger authentication**
   - Open any action item in the Item Editor
   - Click the **"📅 Calendar"** button
   - Fill in event details
   - Click **"Create Calendar Event"**

3. **Complete OAuth flow**
   - Your browser should open automatically
   - Sign in with your Google account
   - Click **"Allow"** to grant calendar access
   - Browser will show: "Authentication successful! You can close this window."
   - Return to GetMoreDone

4. **Verify success**
   - Check that `~/.getmoredone/token.pickle` was created:
     ```bash
     ls -la ~/.getmoredone/token.pickle
     ```
   - The calendar event should be created successfully

### Method 2: Manual Authentication (If Browser Doesn't Open)

If the browser doesn't open automatically, the app will display:

1. **A URL to visit manually**
   ```
   Visit this URL:
   https://accounts.google.com/o/oauth2/auth?...
   ```

2. **Steps to complete authentication:**
   - Copy the URL
   - Open it in any web browser (on any device)
   - Sign in with your Google account
   - Click "Allow" to grant calendar access
   - Copy the authorization code shown
   - Paste the code back into the GetMoreDone terminal when prompted
   - Press Enter

3. **Verify success**
   - You should see: "✅ Authentication successful via manual code entry!"
   - token.pickle will be created automatically

## 🐛 Common Issues and Solutions

### Issue 1: 🧟 ZOMBIE TOKEN PROBLEM (Most Common!)

**Symptoms:**
- Google login screen shows a **different project name** than your credentials.json
- Example: credentials.json says "getmoredone" but login shows "bowen1rag" or another old project
- Error message: "There is a verification error with [old-project-name]"
- Authentication fails even though credentials.json is correct

**Cause:**
Your Python script is using an **old token.pickle file** from a previous/different project instead of your current credentials.json. This is called a "Zombie Token."

**How it Happens:**
Most Google OAuth scripts follow this logic:
1. Check if token.pickle exists
2. If YES → Use that token (ignores credentials.json!)
3. If NO → Load credentials.json and start new login

If you ever:
- Tested a different Google API project in the same directory
- Renamed your project in Google Cloud Console
- Copied credentials.json from a different project
- Moved files from another machine

...you may have a zombie token that doesn't match your current credentials.

**Solution (Quick Fix):**

```bash
# Delete the zombie token
rm ~/.getmoredone/token.pickle

# Test authentication again
python3 test_auth.py
```

**Solution (Using Test Script):**

The test script now automatically detects zombie tokens:

```bash
python3 test_auth.py
```

If a zombie token is detected, you'll see:

```
🧟 ZOMBIE TOKEN DETECTED!
Your token.pickle is from a DIFFERENT project than credentials.json!

Credentials project: getmoredone
Credentials client:  592866309318-3uth2a6j8ajkh...
Token client:        123456789012-oldprojectid...

Do you want to delete the old token and re-authenticate? (y/N):
```

Type `y` and press Enter to automatically delete the zombie token and re-authenticate with the correct credentials.

**Verification:**

After deleting the zombie token and re-authenticating:
1. Check the Google login screen shows the CORRECT project name
2. Complete authentication
3. Verify new token.pickle matches your credentials:
   ```bash
   python3 test_auth.py
   ```
4. You should see "✅ Successfully authenticated with Google Calendar API!"

**Prevention:**

To avoid zombie tokens in the future:
- Always delete token.pickle when switching projects
- Keep credentials.json and token.pickle together
- Don't copy token files between projects
- Use the `force_reauth=True` parameter if implementing custom code

---

### Issue 2: "Browser authentication failed: could not locate runnable browser"

**Cause:** No web browser available in the environment

**Solution:** Use manual authentication (Method 2 above)
- The app will automatically fall back to manual mode
- Follow the URL and code entry instructions

### Issue 3: "Google Calendar credentials not found"

**Cause:** credentials.json is missing or in wrong location

**Solution:**
```bash
# Check if file exists
ls -la ~/.getmoredone/credentials.json

# If missing, download from Google Cloud Console
# See: /home/user/GetMoreDone/docs/google-calendar-setup.md
```

### Issue 4: "Failed to create calendar event: 403"

**Cause:** Google Calendar API not enabled or OAuth app not approved

**Solution:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Go to **"APIs & Services" > "Library"**
4. Search for "Google Calendar API" and ensure it's **Enabled**
5. Go to **"APIs & Services" > "OAuth consent screen"**
6. If app is in "Testing" mode, ensure your email is in "Test users"

### Issue 5: "Invalid credentials" or "Token expired"

**Cause:** Token is corrupted or credentials changed

**Solution:**
```bash
# Remove old token and re-authenticate
rm ~/.getmoredone/token.pickle

# Launch app and complete authentication again
python3 -m getmoredone
```

### Issue 6: "Permission denied" when saving token

**Cause:** Directory permissions issue

**Solution:**
```bash
# Fix permissions
chmod 700 ~/.getmoredone
chmod 600 ~/.getmoredone/credentials.json

# If token.pickle exists
chmod 600 ~/.getmoredone/token.pickle
```

### Issue 7: Authentication works but calendar event not created

**Cause:** API error or rate limiting

**Solution:**
1. Check terminal output for specific error messages
2. Verify you have write access to your Google Calendar
3. Try creating a test event directly in Google Calendar
4. Wait a few minutes if rate limited
5. Check Google Cloud Console quotas

## 📋 Verification Checklist

Run these commands to verify your setup:

```bash
# 1. Check dependencies
pip show google-auth google-auth-oauthlib google-api-python-client

# 2. Check credentials file
ls -la ~/.getmoredone/credentials.json
cat ~/.getmoredone/credentials.json | python3 -c "import json,sys; print('Valid JSON' if json.load(sys.stdin) else 'Invalid')"

# 3. Check token file (after authentication)
ls -la ~/.getmoredone/token.pickle

# 4. Check permissions
ls -la ~/.getmoredone/

# Expected output:
# drwx------ (700) for directory
# -rw------- (600) for credentials.json
# -rw------- (600) for token.pickle
```

## 🔍 Testing Authentication

Use this test script to verify authentication without launching the full app:

```bash
cd /home/user/GetMoreDone
python3 test_auth.py
```

This will:
- Check for credentials.json
- Check for token.pickle
- Attempt authentication
- List your calendars if successful

## 🛠️ Advanced Troubleshooting

### Enable Debug Logging

Add this to see more detailed OAuth flow information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Manually Inspect Credentials

```bash
# View credentials.json structure (be careful - contains secrets!)
python3 -c "import json; print(json.dumps(json.load(open('/root/.getmoredone/credentials.json')), indent=2))"
```

### Check Network Connectivity

```bash
# Test connection to Google APIs
curl -I https://www.googleapis.com/calendar/v3/users/me/calendarList

# Test OAuth endpoint
curl -I https://accounts.google.com/o/oauth2/auth
```

### Revoke and Re-authorize

If all else fails:

1. **Revoke app access**
   - Go to: https://myaccount.google.com/permissions
   - Find "GetMoreDone" and click "Remove Access"

2. **Delete local credentials**
   ```bash
   rm ~/.getmoredone/token.pickle
   ```

3. **Re-authenticate**
   - Launch GetMoreDone
   - Complete OAuth flow again

## 📞 Getting Help

If you're still experiencing issues:

1. **Collect diagnostic information:**
   ```bash
   # Python version
   python3 --version

   # Installed packages
   pip list | grep google

   # File permissions
   ls -la ~/.getmoredone/

   # Recent error messages from terminal output
   ```

2. **Check the project documentation:**
   - Main setup guide: `/home/user/GetMoreDone/docs/google-calendar-setup.md`
   - README: `/home/user/GetMoreDone/README.md`

3. **Common questions:**
   - **Q: Do I need a Google Workspace account?**
     A: No, a regular free Gmail account works fine

   - **Q: Can I use a different email provider?**
     A: No, GetMoreDone currently only supports Google Calendar

   - **Q: Is my data secure?**
     A: Yes, credentials are stored locally and never sent to third parties. OAuth tokens are encrypted by Google.

   - **Q: Why does authentication expire?**
     A: If your app is in "Testing" mode in Google Cloud Console, tokens may expire after 7 days. Publish your app or refresh the token.

## 📌 Quick Reference

| File | Purpose | Location |
|------|---------|----------|
| credentials.json | OAuth client secrets | ~/.getmoredone/credentials.json |
| token.pickle | Authorization token (auto-created) | ~/.getmoredone/token.pickle |
| google_calendar.py | Authentication code | /home/user/GetMoreDone/src/getmoredone/google_calendar.py |
| test_auth.py | Test script | /home/user/GetMoreDone/test_auth.py |

## ✨ What's New

**Recent Improvements (Latest):**

1. **Automatic fallback authentication** - If browser doesn't open, manual URL/code entry is automatic
2. **Better error messages** - Clear diagnostics with actionable solutions
3. **Progress indicators** - Visual feedback during authentication (✅, ⚠️, ❌)
4. **Secure token storage** - Automatic 600 permissions on token.pickle
5. **Token refresh** - Expired tokens are automatically refreshed when possible
6. **Comprehensive logging** - Detailed output helps diagnose issues

---

**Last Updated:** 2026-01-16
**GetMoreDone Version:** Latest (claude/setup-getmoredone-env-BjJcS branch)
