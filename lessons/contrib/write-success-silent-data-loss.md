---
title: "Write operations return success but data is missing"
domain: backend
tags: [data-loss, go, bigquery, silent-failure, verification]
status: published
created: '2026-09-15'
updated: '2026-09-16'
source: "intake #1618 + #1619 — BigQuery telemetry silent failure + Firestore Go omitempty fields not written"
evidence_level: E3
summary_plain: "API返回成功但数据未写入，因为错误被静默吞掉——需要写后读验证。"
trigger: "write success but data missing / 200 OK but no data"
verify: "写入后立即读回并比对内容，匹配则通过；检查批量API的partial failure iterator"
provenance:
  source: "intake"
  issue: "#1619"
---

## Problem

API returns 200 OK, logs show "write successful", but the data doesn't appear in the destination store. In MCP memory-service: memory operations return success but memories are lost on next read.

## Root Cause

**Three-layer silent swallowing:**

1. **Go `omitempty`** — error fields with `nil` value are serialized out of the JSON response, so the client sees no error field and assumes success
2. **BigQuery batch insert** — `Put()` returns nil even when some rows fail; individual row errors are only available via `errors()` iterator, which nobody calls
3. **No read-after-write** — the write path returns success based on "no exception thrown" rather than "data confirmed readable"

```
Client → Write request → Backend → BigQuery Put() → nil (no error)
                                                       ↓
                                              Some rows silently dropped
                                                       ↓
                                              Client gets 200 OK
```

## Solution

1. **Read-after-write verification** — after writing, immediately read back and compare:

```go
// Write
if err := store.Put(ctx, memory); err != nil {
    return fmt.Errorf("write failed: %w", err)
}

// Verify
stored, err := store.Get(ctx, memory.ID)
if err != nil || stored == nil {
    return fmt.Errorf("write succeeded but read-back failed: %w", err)
}
```

2. **Check batch error iterator** for BigQuery:

```go
err := inserter.Put(ctx, rows)
if err != nil {
    // Even if Put returns nil, check for partial failures
    for _, e := range err.(bigquery.PutMultiError) {
        log.Printf("row %d failed: %v", e.RowIndex, e.Error())
    }
}
```

3. **Explicit success fields** — don't rely on absence of error:

```json
{"status": "ok", "written": 1, "verified": true}
```

## Verification

```bash
# 1. Write a test memory
RESPONSE=$(curl -s -X POST http://localhost:8000/memory \
  -H "Content-Type: application/json" \
  -d '{"content": "test verification", "type": "fact"}')
MEMORY_ID=$(echo "$RESPONSE" | jq -r '.id')
echo "Write response: $RESPONSE"

# 2. Immediately read it back
READBACK=$(curl -s http://localhost:8000/memory/$MEMORY_ID)
echo "Read-back: $READBACK"

# 3. Verify content matches
echo "$READBACK" | jq -e '.content == "test verification"' && echo "VERIFIED" || echo "DATA LOSS DETECTED"

# 4. Check Go response includes explicit success field
echo "$RESPONSE" | jq -e '.status == "ok"' && echo "Explicit success" || echo "Implicit success (risky)"
```

## Prevention

- Never trust "no exception" as success — verify state after mutation
- For batch writes: always check partial failure APIs (BigQuery, DynamoDB, etc.)
- Add smoke tests: write → read → assert in CI
- Log write confirmation with record count and destination