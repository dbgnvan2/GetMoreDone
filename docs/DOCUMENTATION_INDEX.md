# GetMoreDone Documentation Index

## Overview

Complete index of all documentation files for the GetMoreDone task management application.

## Primary Documentation

### README.md (27KB)

Main project documentation including:

- Features overview
- Quick start guide
- Installation instructions
- Recent improvements (VPS, Timer, Contacts, etc.)
- **NEW: Testing section** with test commands and coverage

### GetMoreDone_MasterSpec_SQLite_v1.md (19KB)

Complete specification including:

- System architecture
- Database schema
- Feature requirements
- Design decisions
- Business logic

### NOTES.md (2.3KB)

Recent changes log:

- VPS Segment Management (2026-01-24)
- VPS Bug Fixes (2026-01-24)
- Item Editor improvements (2026-01-23)
- Timer window improvements (2026-01-23)

### BACKLOG.md (4.1KB)

Feature backlog and task tracking:

- Completed features with dates
- Pending enhancements
- Known issues

## VPS (Visionary Planning System) Documentation

### docs/VPS_UPDATES_2026-01-24.md (8.5KB) **NEW**

Comprehensive change log for January 24, 2026 updates:

- Critical bug fixes (CTkMessageBox, year validation, multi-select)
- New segment management features
- Enhanced deletion protection
- Complete testing breakdown
- Migration notes
- Verification checklist

### docs/VPS_TESTING_SUMMARY.md (5.1KB) **NEW**

Test documentation for VPS:

- 21 total tests (14 integration + 7 standalone)
- Test coverage breakdown
- Test results summary (100% pass rate)
- Commands to run tests
- Code coverage metrics
- Future testing considerations

### docs/DOCUMENTATION_UPDATE_SUMMARY.md (5.1KB) **NEW**

Summary of documentation and test updates:

- Documentation files updated
- Test updates and fixes
- Verification checklist
- Complete test results

## Feature-Specific Documentation

### docs/action-timer-requirements.md (19KB)

Action Timer module requirements:

- Timer window specifications
- Music playback features
- Workflow diagrams
- User stories
- Technical requirements

### docs/google-calendar-setup.md (8.7KB)

Google Calendar integration guide:

- OAuth 2.0 setup instructions
- credentials.json configuration
- Authorization flow
- Troubleshooting common issues
- API quota information

## Troubleshooting Guides

### docs/EMAIL-AUTH-TROUBLESHOOTING.md (11KB)

Email authentication troubleshooting:

- Common OAuth errors
- Token refresh issues
- Client ID mismatches
- Step-by-step fixes

### docs/CLIENT_ID_MISMATCH_FIX.md (7.6KB)

Fixing client ID mismatch errors:

- Root cause analysis
- Token file cleanup
- Re-authorization steps
- Verification procedures

### AUDIO_TROUBLESHOOTING.md (2.0KB)

Audio playback issues:

- Missing pygame errors
- Audio file format issues
- Volume control problems
- Music folder configuration

### CLEAR_BROWSER_CACHE.md (5.7KB)

Browser cache clearing guide:

- Chrome instructions
- Firefox instructions
- Safari instructions
- Why clearing cache helps

### QUICK_FIX_ZOMBIE_TOKEN.md (2.0KB)

Quick fix for stuck tokens:

- Delete token.json
- Re-authorize
- Verify functionality

### fix_oauth_app_name.md (3.1KB)

OAuth application name configuration:

- Update Google Cloud Console
- Refresh credentials
- Test authorization

## Test Scripts

### test_vps_segments.py

Standalone test script for VPS segment management:

- 7 structure and functionality tests
- Import validation
- Method existence checks
- Enhanced deletion protection verification
- **Status**: ✅ All tests passing

### tests/test_vps_integration.py

Integration tests for VPS:

- 36 total tests across 6 test classes
- Bug fix tests (5 tests)
- Segment management tests (9 tests)
- Record creation/update/deletion tests
- **Status**: ✅ All tests passing (0.96s)

### Other Test Files

- `tests/test_database.py` - Database operations
- `tests/test_contact_integration.py` - Contact management
- `tests/test_date_adjustment.py` - Date validation
- `tests/test_item_editor.py` - Item editor functionality
- `tests/test_note_search.py` - Obsidian integration
- `tests/test_obsidian_integration.py` - Note linking
- `tests/test_timer.py` - Timer functionality
- `tests/test_today_screen.py` - Today screen
- `tests/test_upcoming_items.py` - Upcoming view
- `tests/test_validation.py` - Data validation

## Utility Scripts

### convert_music_to_mp3.py

Convert audio files to MP3 format:

- Supports M4A, AAC, WAV, OGG
- Batch conversion
- Quality settings

### create_demo_data.py

Create sample data for testing:

- Action items
- Contacts
- VPS records

### diagnose_calendar.py

Diagnose Google Calendar issues

### diagnose_client_id.py

Check OAuth client ID configuration

### debug_auth_loading.py

Debug authentication loading issues

### test_audio.py

Test audio playback functionality

### test_auth.py

Test OAuth authentication

### test_obsidian_dialogs.py

Test Obsidian integration dialogs

### test_vps_init.py

Test VPS initialization

## Shell Scripts

### start.sh (Linux/Mac)

One-command startup script:

- Creates virtual environment
- Installs dependencies
- Launches application

### start.bat (Windows)

Windows startup script

### fix_client_id_mismatch.sh

Automated client ID fix

### fix_wrong_project.sh

Fix wrong Google Cloud project

### fix_zombie_token.sh

Automated token cleanup

### verify_auth.sh

Verify authentication setup

## Documentation Organization

### By Category

**Getting Started**

- README.md
- GetMoreDone_MasterSpec_SQLite_v1.md

**VPS Documentation**

- docs/VPS_UPDATES_2026-01-24.md
- docs/VPS_TESTING_SUMMARY.md
- docs/DOCUMENTATION_UPDATE_SUMMARY.md

**Feature Guides**

- docs/action-timer-requirements.md
- docs/google-calendar-setup.md

**Troubleshooting**

- docs/EMAIL-AUTH-TROUBLESHOOTING.md
- docs/CLIENT_ID_MISMATCH_FIX.md
- AUDIO_TROUBLESHOOTING.md
- CLEAR_BROWSER_CACHE.md
- QUICK_FIX_ZOMBIE_TOKEN.md
- fix_oauth_app_name.md

**Development**

- NOTES.md (recent changes)
- BACKLOG.md (task tracking)
- tests/\* (test files)

### By Size

Large (>10KB):

- README.md (27KB)
- GetMoreDone_MasterSpec_SQLite_v1.md (19KB)
- docs/action-timer-requirements.md (19KB)
- docs/EMAIL-AUTH-TROUBLESHOOTING.md (11KB)

Medium (5-10KB):

- docs/google-calendar-setup.md (8.7KB)
- docs/VPS_UPDATES_2026-01-24.md (8.5KB)
- docs/CLIENT_ID_MISMATCH_FIX.md (7.6KB)
- CLEAR_BROWSER_CACHE.md (5.7KB)

Small (<5KB):

- docs/VPS_TESTING_SUMMARY.md (5.1KB)
- docs/DOCUMENTATION_UPDATE_SUMMARY.md (5.1KB)
- BACKLOG.md (4.1KB)
- fix_oauth_app_name.md (3.1KB)
- NOTES.md (2.3KB)
- AUDIO_TROUBLESHOOTING.md (2.0KB)
- QUICK_FIX_ZOMBIE_TOKEN.md (2.0KB)

## Recent Updates (2026-01-24)

**NEW Documentation**

1. docs/VPS_UPDATES_2026-01-24.md - Comprehensive VPS change log
2. docs/VPS_TESTING_SUMMARY.md - Complete test documentation
3. docs/DOCUMENTATION_UPDATE_SUMMARY.md - Documentation update summary

**UPDATED Documentation**

1. README.md - Added Testing section
2. NOTES.md - Already included all recent changes
3. BACKLOG.md - Marked features complete

## Quick Access

### I need to...

**Learn about the project** → README.md

**See recent changes** → NOTES.md

**Fix authentication issues** → docs/EMAIL-AUTH-TROUBLESHOOTING.md

**Set up Google Calendar** → docs/google-calendar-setup.md

**Understand VPS updates** → docs/VPS_UPDATES_2026-01-24.md

**Run tests** → docs/VPS_TESTING_SUMMARY.md or README.md (Testing section)

**Fix audio issues** → AUDIO_TROUBLESHOOTING.md

**Check feature backlog** → BACKLOG.md

**Understand the system** → GetMoreDone_MasterSpec_SQLite_v1.md

**Clear browser cache** → CLEAR_BROWSER_CACHE.md

## Documentation Standards

All documentation follows these standards:

- Markdown format (.md)
- Clear section headings
- Code blocks with syntax highlighting
- Tables for structured data
- Emoji for visual clarity ✅ ⚠️ ❌
- Links to related documents
- Last updated dates

## Maintenance

Documentation is updated:

- After each feature implementation
- When bugs are fixed
- When tests are added
- When user issues are resolved
- During major releases

**Current Status**: ✅ All documentation up to date as of 2026-01-24
