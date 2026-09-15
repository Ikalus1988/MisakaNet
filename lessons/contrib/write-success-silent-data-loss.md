---
title: "Write succeeds but data missing: silent serialization and error-swallowing failures"
domain: database
tags:
  - firestore
  - bigquery
  - serialization
  - omitempty
  - silent-failure
  - debugging
status: published
created: 2026-08-21
language: en
confidence: 0.9
verified_date: 2026-08-21
provenance:
  source: "intake"
  issue: "#1618"
  contributor: "Community"
  merged_at: "2026-08-21"
  evidence: "reproduction"
---

## Problem

Write operations return success (HTTP 200, no error) but data doesn't appear in database. No errors in logs.

**Symptoms:**
- BigQuery telemetry silently drops rows — no errors logged
- Firestore Go client: `DocumentRef.Set()` returns nil error but fields missing
- API returns `200 OK` with correct response body
- Data simply not there when queried

**Minimal reproduction (Go + Firestore):**
```go
type User struct {
    Name  string `json:"name"`
    Email string `json:"email,omitempty"`
}

user := User{Name: "Alice"}  // Email is zero value
_, err := client.Collection("users").Doc("alice").Set(ctx, user)
// err is nil, but "email" field is missing in Firestore
```

## Root Cause

Two distinct failure modes:

**Mode A: `omitempty` serialization (Go/Firestore)**
- Go's `json:"omitempty"` omits zero-value fields during JSON serialization
- Firestore SDK uses JSON serialization internally
- Zero-value fields (empty string, 0, false, nil) silently omitted
- No error — just missing data

**Mode B: Error swallowing in batch/async writes**
- BigQuery streaming insert returns success for batch
- Individual row failures logged to internal sink, not caller
- Retry logic swallows errors, logs "retrying" but never "failed"
- Caller sees success, data never lands

**Mode C: Silent schema mismatch**
- Write succeeds with wrong field name (e.g., `userId` vs `user_id`)
- Database accepts it (flexible schema)
- Query uses correct field name → returns nothing

## Solution

**For `omitempty` issue:**
```go
// Option 1: Use pointer types (nil = omit, empty = include)
type User struct {
    Name  string  `json:"name"`
    Email *string `json:"email"`  // nil omits, "" includes
}

// Option 2: Use Firestore-specific tags
type User struct {
    Name  string `firestore:"name"`
    Email string `firestore:"email"`  // No omitempty
}

// Option 3: Explicit map (always includes all fields)
data := map[string]interface{}{
    "name":  user.Name,
    "email": user.Email,  // Always included, even if empty
}
```

**For BigQuery silent drops:**
```python
# Check response for partial failures
errors = client.insert_rows_json(table, rows)
if errors:
    print(f"Failed rows: {errors}")
    # errors contains per-row failure details
    
# Better: use insert_rows_json with retry
from google.cloud.bigquery import Retry
errors = client.insert_rows_json(table, rows, retry=Retry(deadline=60))
```

**For schema mismatch:**
```python
# Verify write by reading back immediately
doc_ref.set(data)
doc = doc_ref.get()
if not doc.exists:
    raise RuntimeError("Write succeeded but document missing")
    
# Compare fields
written = doc.to_dict()
for key in data:
    if key not in written:
        print(f"WARNING: field '{key}' not persisted")
```

## Prevention

1. **Read-after-write verification**: Write then immediately read back, compare
2. **Field count assertion**: Check document has expected number of fields
3. **Log raw payload**: Log what you're sending, not just "success"
4. **Disable omitempty for writes**: Use separate write/read structs

## Verification

```go
// Test that all fields persist
user := User{Name: "Alice", Email: ""}
_, err := ref.Set(ctx, user)
if err != nil {
    t.Fatal(err)
}

doc, _ := ref.Get(ctx)
data := doc.Data()
if _, ok := data["email"]; !ok {
    t.Error("email field missing after write")
}
```

## References

- [Go JSON omitempty behavior](https://pkg.go.dev/encoding/json#Marshal)
- [Firestore Go client docs](https://cloud.google.com/docs/reference/libraries/go-client/firestore)
- [BigQuery streaming insert error handling](https://cloud.google.com/bigquery/docs/streaming-data-into-bigquery)
