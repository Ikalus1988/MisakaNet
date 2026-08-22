---
{
  "title": "Data Quality Fix: Always Keep Three Layers (DB + ETL + Query)",
  "domain": "data-engineering",
  "tags": [
    "data-quality",
    "etl",
    "sql",
    "normalization",
    "defense-in-depth"
  ],
  "status": "published",
  "evidence_level": "E2",
  "created": "2026-08-06",
  "updated": "2026-08-06",
  "source": "manual",
  "verified_date": "2026-08-06",
  "author": "Liona Can",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

# Data Quality Fix: Always Keep Three Layers (DB + ETL + Query)

## Problem

ETL pipeline derives identifiers from source filenames (e.g., `robot_name` from Excel sheet names). Filenames are inherently inconsistent — the same physical robot appears as `FE135R01`, `FE66135R01`, `UB&FE135R01`, and `FE_处理后数据135R01` depending on which file it came from.

A single-point fix (e.g., only fixing the database) leaves the system vulnerable to regression when new data arrives through the same broken ETL.

## Root Cause

No normalization layer exists between raw filename parsing and database insertion. The ETL trusts filenames as-is, and downstream queries assume identifiers are consistent.

The failure pattern:
1. ETL inserts inconsistent names → database has duplicates
2. Query `GROUP BY robot_name` → inflated counts (11 robots instead of 1)
3. Dashboard shows wrong numbers → user loses trust

## Solution

Apply fixes at three layers, in order of permanence:

### Layer 1: ETL (prevent recurrence)

Add a normalization function that runs at insert time:

```python
# common.py — single source of truth
ROBOT_NAME_PREFIXES = [
    ('TGO_FEN_处理后数据', 'TGO'),
    ('FEN&TGO', 'TGO'),
    ('TGO&FEN', 'TGO'),
    ('TGO FEN', 'TGO'),
    ('FE_处理后数据', 'FE'),
    ('UB&FE', 'FE'),
    ('FE66', 'FE'),
]

def normalize_robot_name(name):
    for prefix, replacement in ROBOT_NAME_PREFIXES:
        if name.startswith(prefix):
            return replacement + name[len(prefix):]
    return name
```

In the ETL script:
```python
from common import normalize_robot_name

def process_record(rec):
    robot_name = normalize_robot_name(rec['robot_name'])
    # ... insert into DB
```

### Layer 2: Database (fix historical data)

Run a one-time migration script that normalizes existing data:

```python
# fix_robot_names.py — uses the SAME normalize function as ETL
from common import normalize_robot_name

for old_name in dirty_names:
    new_name = normalize_robot_name(old_name)
    if old_name != new_name:
        conn.execute("UPDATE table SET robot_name=? WHERE robot_name=?",
                     (new_name, old_name))
```

### Layer 3: Query (safety net)

Keep a `CASE WHEN` in SQL as a defense-in-depth fallback:

```sql
CASE WHEN t.line IN ('FEN&TGO', 'FE66', 'FE_处理后数据') THEN 'FE'
     ELSE t.line END as normalized_line
```

This catches any edge case that slips through Layers 1 and 2.

## Verification

```sql
-- Before fix: 11 "different" robots (all the same physical robot)
SELECT robot_name, COUNT(*) FROM robot_timestamps
WHERE line='FE' GROUP BY robot_name;
-- FE135R01: 635, FE66135R01: 63, UB&FE135R01: 49, ...

-- After fix: 1 robot with merged data
SELECT robot_name, COUNT(*) FROM robot_timestamps
WHERE line='FE' GROUP BY robot_name;
-- FE135R01: 1194
```

## Notes

- **The normalization function MUST be shared** between ETL, migration script, and any other code that touches identifiers. If you copy-paste the prefix list, it will diverge.
- **Prefix matching must be ordered by length (longest first)** to avoid short-prefix false matches (e.g., `FE` matching before `FE66`).
- **SELECT queries are not affected** by this issue — only `GROUP BY` and `JOIN` on the inconsistent column produce wrong results.
- **This pattern applies to any ETL that derives identifiers from filenames**, not just robot names. Common cases: station names, line names, product codes.
- The `CASE WHEN` in Layer 3 can be removed once Layer 1 is proven stable across multiple ETL runs.
