# 🧟 Quick Fix: Zombie Token Problem

## The Problem

You see the **WRONG project name** in Google's login screen:
- Your `credentials.json` says **"getmoredone"**
- But Google shows **"bowen1rag"** (or another old project name)
- Authentication fails

## Why This Happens

Your `token.pickle` file is from an **old/different** Google Cloud project.

Python's OAuth logic:
1. ✅ Does `token.pickle` exist?
2. ✅ YES → Use that token (ignores credentials.json!)
3. ❌ Auth fails because token is for wrong project

## The Fix (Choose One)

### Method 1: Quick Script (Recommended)
```bash
cd /home/user/GetMoreDone
./fix_zombie_token.sh
```

### Method 2: Test Script with Auto-Detection
```bash
cd /home/user/GetMoreDone
python3 test_auth.py
# It will detect zombie token and offer to delete it
```

### Method 3: Manual
```bash
# Delete the zombie token
rm ~/.getmoredone/token.pickle

# Test authentication
python3 test_auth.py
```

## After Deletion

1. Run authentication test:
   ```bash
   python3 test_auth.py
   ```

2. Complete OAuth flow in browser

3. Verify correct project name appears

4. New `token.pickle` created with CORRECT project

## How to Prevent This

❌ **Don't:**
- Copy `token.pickle` between projects
- Use the same token for different Google projects
- Reuse tokens after changing credentials

✅ **Do:**
- Delete `token.pickle` when switching projects
- Keep credentials.json and token.pickle matched
- Use `force_reauth=True` in custom code when needed

## Verify It's Fixed

After fixing, check these:

```bash
# 1. Check credentials project
python3 -c "import json; print('Credentials project:', json.load(open('$HOME/.getmoredone/credentials.json'))['installed']['project_id'])"

# 2. Test authentication
python3 test_auth.py

# 3. Should see:
# ✅ Successfully authenticated with Google Calendar API!
```

## Still Having Issues?

See full troubleshooting guide:
```bash
cat docs/EMAIL-AUTH-TROUBLESHOOTING.md
```

Or run diagnostic script:
```bash
./verify_auth.sh
```

---

**TL;DR:**
```bash
rm ~/.getmoredone/token.pickle && python3 test_auth.py
```
