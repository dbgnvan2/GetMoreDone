# Fix: OAuth Consent Screen Shows Wrong App Name

## Problem

- Your Google Cloud project: **getmoredone**
- But OAuth screen shows: **bowen1rag**
- You can't find "bowen1rag" project

## Root Cause

The OAuth consent screen **app name** is set to "bowen1rag". This is separate from the project ID.

## Solution: Change the App Name

### Step 1: Go to OAuth Consent Screen

Visit: https://console.cloud.google.com/apis/credentials/consent?project=getmoredone

### Step 2: Click "EDIT APP"

At the top of the OAuth consent screen page, click the **"EDIT APP"** button.

### Step 3: Change the App Name

1. In the **"App name"** field, you'll see: `bowen1rag`
2. Change it to: `GetMoreDone`
3. Scroll down and click **"SAVE AND CONTINUE"**
4. Click through the remaining screens (Scopes, Test users, Summary)
5. Click **"BACK TO DASHBOARD"**

### Step 4: Add Test User (If Not Already Added)

1. On the OAuth consent screen page, scroll to **"Test users"**
2. Click **"+ ADD USERS"**
3. Enter: `davebgalloway@gmail.com`
4. Click **"SAVE"**

### Step 5: Delete Old Token and Re-authenticate

```bash
# Delete the old token
rm ~/.getmoredone/token.pickle

# Test authentication
cd /home/user/GetMoreDone
python3 test_auth.py
```

### Step 6: Verify

When you authenticate now, the Google screen should show **"GetMoreDone"** instead of "bowen1rag".

---

## Alternative: Create Completely New OAuth Client

If changing the app name doesn't work, create a fresh OAuth client:

### 1. Delete Current Credentials

```bash
# Backup current credentials
mv ~/.getmoredone/credentials.json ~/.getmoredone/credentials.json.backup

# Delete any tokens
rm ~/.getmoredone/token.pickle 2>/dev/null
```

### 2. Create New OAuth Client in Google Cloud Console

1. Go to: https://console.cloud.google.com/apis/credentials?project=getmoredone
2. Click **"+ CREATE CREDENTIALS"** > **"OAuth client ID"**
3. Application type: **Desktop app**
4. Name: **GetMoreDone Desktop New**
5. Click **"CREATE"**

### 3. Download New Credentials

1. Find your newly created OAuth 2.0 Client ID in the list
2. Click the download icon (⬇️) on the right
3. This downloads a file like `client_secret_XXXXX.json`

### 4. Install New Credentials

```bash
# Move to GetMoreDone config directory
mv ~/Downloads/client_secret_*.json ~/.getmoredone/credentials.json

# Set permissions
chmod 600 ~/.getmoredone/credentials.json
```

### 5. Verify the New Credentials

```bash
python3 -c "import json; data = json.load(open('/root/.getmoredone/credentials.json')); print('Project:', data['installed']['project_id'])"
```

Should show: `Project: getmoredone`

### 6. Test Authentication

```bash
cd /home/user/GetMoreDone
python3 test_auth.py
```

The OAuth screen should now show the correct app name!

---

## Quick Command Summary

```bash
# Option 1: Just change app name in console, then:
rm ~/.getmoredone/token.pickle
python3 test_auth.py

# Option 2: Create new credentials, then:
mv ~/.getmoredone/credentials.json ~/.getmoredone/credentials.json.backup
# (download new credentials from console)
mv ~/Downloads/client_secret_*.json ~/.getmoredone/credentials.json
chmod 600 ~/.getmoredone/credentials.json
python3 test_auth.py
```
