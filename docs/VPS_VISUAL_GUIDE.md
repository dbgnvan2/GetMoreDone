# VPS Data Integrity - Visual Guide

## The Question

"If I update a '5-Year Vision' segment, does the system correctly reflect that change in linked 'Yearly' and 'Daily' actions?"

## The Answer: YES ✅ (with one critical caveat)

---

## Part 1: How Segment Updates Work (GOOD ✅)

### Data Structure

```
Life Segment: "Career" (id: seg-12345)
    ↓
TL Vision: "Become Senior Engineer" (segment_id: seg-12345)
    ↓
Annual Vision: "2026 Career Goals" (segment_id: seg-12345)
    ↓
Annual Plan: "Skill Development" (segment_id: seg-12345)
    ↓
Quarter Initiative: "Learn Cloud" (segment_id: seg-12345)
    ↓
Month Tactic: "AWS Certification" (segment_id: seg-12345)
    ↓
Week Action: "Study 5 hours" (segment_id: seg-12345)
```

### What Happens When You Rename "Career" → "Professional Development"

```sql
-- Update executes:
UPDATE segment_descriptions
SET name = 'Professional Development'
WHERE id = 'seg-12345'

-- UI queries join like this:
SELECT v.title, s.name as segment_name
FROM tl_visions v
JOIN segment_descriptions s ON v.segment_description_id = s.id

-- Result: All records instantly show "Professional Development"
```

**Visual:**

```
BEFORE UPDATE:
┌─────────────────────┐
│ Segment: Career     │ seg-12345
└─────────────────────┘
          ↓ (FK)
┌─────────────────────┐
│ TL Vision           │ segment_id: seg-12345
│ Shows: "Career"     │ ← Fetched via JOIN
└─────────────────────┘

AFTER UPDATE:
┌─────────────────────────────────┐
│ Segment: Professional Dev       │ seg-12345
└─────────────────────────────────┘
          ↓ (FK)
┌─────────────────────────────────┐
│ TL Vision                       │ segment_id: seg-12345
│ Shows: "Professional Dev"       │ ← Updated via JOIN
└─────────────────────────────────┘
```

**✅ WORKING CORRECTLY** - Foreign key relationship ensures all records show updated segment name

---

## Part 2: How Deletion Works (PROBLEM 🔴)

### Current Implementation

```python
def delete_segment(segment_id):
    # ONLY checks this table:
    vision_count = COUNT(*) FROM tl_visions
                   WHERE segment_description_id = segment_id

    if vision_count > 0:
        return False, vision_count  # Block deletion

    DELETE FROM segment_descriptions WHERE id = segment_id
    # ^ This triggers CASCADE DELETE in database
```

### The Problem

**Scenario:** User has this data:

```
Segment: "Health" (seg-99999)
├── TL Visions: 0 records
├── Annual Visions: 3 records  ← NOT CHECKED
├── Annual Plans: 5 records    ← NOT CHECKED
├── Quarter Initiatives: 12    ← NOT CHECKED
├── Month Tactics: 20          ← NOT CHECKED
└── Week Actions: 35           ← NOT CHECKED
    Total: 75 records
```

**What Happens:**

```
1. User clicks "Delete Segment: Health"
2. delete_segment() checks: TL Visions = 0 ✓
3. System says: "OK to delete"
4. Database CASCADE deletes all 75 records
5. User sees: "Segment deleted successfully"
6. User doesn't know: Lost 75 records
```

**Visual:**

```
CURRENT BEHAVIOR:
┌────────────────────────────┐
│ Check TL Visions only      │ Found: 0
└────────────────────────────┘
          ↓
    ✓ Allow deletion
          ↓
┌────────────────────────────┐
│ CASCADE DELETE:            │
│ • 3 Annual Visions         │  ← SILENT
│ • 5 Annual Plans          │  ← SILENT
│ • 12 Quarter Initiatives   │  ← SILENT
│ • 20 Month Tactics         │  ← SILENT
│ • 35 Week Actions          │  ← SILENT
└────────────────────────────┘
User sees: "Segment deleted" (doesn't know about 75 records)
```

---

## Part 3: How It SHOULD Work (RECOMMENDED FIX)

### Enhanced Implementation

```python
def delete_segment(segment_id):
    counts = {}

    # Check ALL tables
    for table in ['tl_visions', 'annual_visions', 'annual_plans',
                  'quarter_initiatives', 'month_tactics', 'week_actions']:
        count = COUNT(*) FROM {table} WHERE segment_description_id = segment_id
        if count > 0:
            counts[table] = count

    if counts:
        return False, counts  # Block deletion with full details

    DELETE FROM segment_descriptions WHERE id = segment_id
```

**Visual:**

```
RECOMMENDED BEHAVIOR:
┌────────────────────────────┐
│ Check ALL tables:          │
│ • TL Visions: 0            │
│ • Annual Visions: 3        │ ← FOUND
│ • Annual Plans: 5          │ ← FOUND
│ • Quarter Initiatives: 12  │ ← FOUND
│ • Month Tactics: 20        │ ← FOUND
│ • Week Actions: 35         │ ← FOUND
└────────────────────────────┘
          ↓
    ✗ Block deletion
          ↓
┌────────────────────────────┐
│ Show detailed warning:     │
│                            │
│ Cannot delete "Health"     │
│ because it has:            │
│                            │
│ • 3 Annual Visions         │
│ • 5 Annual Plans           │
│ • 12 Quarter Initiatives   │
│ • 20 Month Tactics         │
│ • 35 Week Actions          │
│                            │
│ Total: 75 records          │
│                            │
│ To delete this segment:    │
│ 1. Go to VPS Planning      │
│ 2. Delete these records    │
│ 3. Return here to delete   │
└────────────────────────────┘
User is informed and protected ✓
```

---

## Test Results

### Test 1: Segment Update Propagation ✅

```
1. Create segment "Original Name"
2. Create TL Vision linked to it
3. Update segment to "Updated Name"
4. Query TL Vision: Shows "Updated Name" ✅

PASS: Updates propagate correctly
```

### Test 2: Cascade Deletion Works ✅

```
1. Create TL Vision → Annual Vision → Annual Plan
2. Delete TL Vision
3. Check children: All deleted ✅

PASS: CASCADE DELETE works at database level
```

### Test 3: Incomplete Deletion Check 🔴

```
1. Create 6 records across 6 tables
2. Call delete_segment()
3. Function reports: "1 linked vision"
4. Actual linked records: 6

FAIL: User sees warning about 1, loses 6
```

---

## Summary Table

| Operation                    | Works Correctly? | Notes                       |
| ---------------------------- | ---------------- | --------------------------- |
| Segment name update          | ✅ YES           | Foreign key JOIN handles it |
| Segment color update         | ✅ YES           | Foreign key JOIN handles it |
| Segment description update   | ✅ YES           | Foreign key JOIN handles it |
| Parent record deletion       | ✅ YES           | CASCADE deletes children    |
| Child record creation        | ✅ YES           | NOT NULL prevents orphans   |
| **Segment deletion warning** | **🔴 NO**        | **Only checks TL Visions**  |

---

## Quick Reference

### ✅ What's Working

- Segment updates propagate instantly
- Foreign keys prevent orphaning
- Database CASCADE protects data integrity
- Creation requires valid parents

### 🔴 What Needs Fixing

- `delete_segment()` only checks 1 of 7 tables
- Users can lose data without adequate warning
- No bulk segment operations
- No undo/archive capability

### 🎯 Priority Fix

Implement comprehensive deletion checking across all VPS tables before allowing segment deletion.

**Estimated time**: 2-4 hours  
**Risk if not fixed**: HIGH - Silent data loss in production

---

## Files Created

1. **VPS_DATA_INTEGRITY_AUDIT.md** - Complete technical analysis (27KB)
2. **VPS_AUDIT_SUMMARY.md** - Executive summary (6KB)
3. **test_vps_data_integrity.py** - Executable test suite (5KB)
4. **VPS_VISUAL_GUIDE.md** - This document (5KB)

**Total documentation**: 43KB, fully covers the issue
