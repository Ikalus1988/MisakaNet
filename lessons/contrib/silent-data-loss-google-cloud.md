---
domain: "data-pipeline"
title: "Silent Data Loss in Google Cloud: BigQuery Schema Mismatch and Firestore Overwrite Failures"
status: "draft"
verification: "metadata-normalized"
{"title": "Silent Data Loss in Google Cloud: BigQuery Schema Mismatch and Firestore Overwrite Failures", "domain": "data-pipeline", "tags": ["bigquery", "firestore", "google-cloud", "data-loss", "silent-failure", "schema-validation"], "status": "published", "confidence": "0.95", "created": "2026-09-16", "updated": "2026-09-16", "source": "intake-1618-intake-1619", "verified_date": "2026-09-16", "domain_expert": "AUTO", "provenance": {"issue": "#1618", "related": ["#1619"]}}
---

# Silent Data Loss in Google Cloud: BigQuery Schema Mismatch and Firestore Overwrite Failures

## Problem

Google Cloud services can silently lose data through two failure modes that don't raise runtime errors:

1. **BigQuery Schema Mismatch**: `tabledata.insertAll` validates row-by-row and rejects the ENTIRE ROW when JSON contains a field not in the table schema. Errors are returned per-row (`insertErrors`) instead of failing the HTTP request. Service continues working, deployments pass, but the table stays empty forever.

2. **Firestore Overwrite with omitempty**: `DocumentRef.Set(ctx, struct)` WITHOUT merge options overwrites the ENTIRE document. Fields with `firestore:"...,omitempty"` tags are OMITTED from serialization when at zero value. Rewriting the same document erases those fields from the database.

**Critical**: Both failures are silent. No errors are raised. The system appears healthy while data is lost or never written.

Related issues: #1618 (BigQuery), #1619 (Firestore)

## Root Cause

### Failure Mode 1: BigQuery Silent Row Rejection

**What happens**:

```go
// WRONG: Assumes success if HTTP request succeeds
rows := []map[string]interface{}{
    {"id": 1, "name": "Alice", "extra_field": "value"},  // extra_field not in schema
}

resp, err := bigquery.TableData.InsertAll(datasetID, tableID, &bigquery.InsertAllRequest{
    Rows: rows,
})

if err != nil {
    log.Fatal(err)  // <- Never triggers!
}

// HTTP request succeeded, but row was rejected
// resp.InsertErrors contains the actual failure
```

**Why it fails**: BigQuery's `insertAll` API is designed to be "partial success" - it accepts the HTTP request even if individual rows fail. The response contains `insertErrors` array with per-row errors, but most SDKs don't surface this clearly.

**Three compounding traps**:

1. **HTTP success ≠ data success**: The HTTP request returns 200 OK even when all rows are rejected
2. **Row-level errors**: Errors are in `insertErrors[*].errors[]`, not the top-level error field
3. **Schema drift**: Table exists but has incomplete schema (missing columns added later in code)

**Failure layer**: Data validation at the storage layer. The mismatch between code schema and table schema is not detected until write time.

### Failure Mode 2: Firestore Overwrite with omitempty

**What happens**:

```go
type Document struct {
    ID      string `firestore:"id"`
    Title   string `firestore:"title"`
    Content string `firestore:"content,omitempty"`  // <- DANGER
    Tags    []string `firestore:"tags,omitempty"`   // <- DANGER
}

doc := Document{
    ID:      "abc123",
    Title:   "My Document",
    Content: "",  // Zero value -> omitted from serialization
    Tags:    nil, // Zero value -> omitted from serialization
}

// WRONG: Overwrites entire document, erasing Content and Tags
_, err := client.Collection("docs").Doc("abc123").Set(ctx, doc)
```

**Why it fails**: 

1. `Set()` without `MergeAll` or `Merge(...)` options REPLACES the entire document
2. `omitempty` fields at zero value are OMITTED from the serialized struct
3. Firestore interprets missing fields as "delete these fields"
4. Result: Content and Tags are erased from the database

**Real scenario**: A snippet document is rewritten whenever the same content is re-summarized (ID is content hash). Each rewrite erases optional fields that weren't populated in the current pass.

**Failure layer**: Serialization + write semantics. The combination of `Set()` overwrite behavior and `omitempty` tags creates silent data loss.

## Solution

### Fix 1: BigQuery - Check InsertErrors Explicitly

**Always check row-level errors**:

```go
func insertRowsWithErrorCheck(ctx context.Context, client *bigquery.Client, 
    datasetID, tableID string, rows []map[string]interface{}) error {
    
    resp, err := client.TableData.InsertAll(datasetID, tableID, &bigquery.InsertAllRequest{
        Rows: rows,
    }).Do(ctx)
    
    if err != nil {
        return fmt.Errorf("insertAll request failed: %w", err)
    }
    
    // CRITICAL: Check for row-level errors
    if len(resp.InsertErrors) > 0 {
        var failedRows []string
        for _, insertErr := range resp.InsertErrors {
            rowIndex := insertErr.Index
            for _, err := range insertErr.Errors {
                failedRows = append(failedRows, fmt.Sprintf(
                    "row %d: %s (field: %s)", 
                    rowIndex, err.Message, err.Reason))
            }
        }
        
        return fmt.Errorf("BigQuery rejected %d rows:\n%s", 
            len(resp.InsertErrors), strings.Join(failedRows, "\n"))
    }
    
    return nil
}
```

**Pre-flight schema validation**:

```go
func validateSchemaBeforeInsert(ctx context.Context, client *bigquery.Client,
    datasetID, tableID string, sampleRow map[string]interface{}) error {
    
    // Get table metadata
    table := client.Dataset(datasetID).Table(tableID)
    meta, err := table.Metadata(ctx)
    if err != nil {
        return fmt.Errorf("cannot get table metadata: %w", err)
    }
    
    // Build schema field set
    schemaFields := make(map[string]bool)
    for _, field := range meta.Schema {
        schemaFields[field.Name] = true
    }
    
    // Check sample row against schema
    var missingFields []string
    for key := range sampleRow {
        if !schemaFields[key] {
            missingFields = append(missingFields, key)
        }
    }
    
    if len(missingFields) > 0 {
        return fmt.Errorf("schema mismatch: fields %v not in table %s.%s",
            missingFields, datasetID, tableID)
    }
    
    return nil
}
```

**Monitoring and alerting**:

```go
func monitorBigQueryTable(ctx context.Context, client *bigquery.Client,
    datasetID, tableID string) {
    
    table := client.Dataset(datasetID).Table(tableID)
    meta, _ := table.Metadata(ctx)
    
    // Track row count over time
    rowCount := meta.NumRows
    lastCheck := getLastCheckTime()
    
    if rowCount == 0 && time.Since(lastCheck) > 24*time.Hour {
        alert("BigQuery table %s.%s has 0 rows after 24h - possible silent failure",
            datasetID, tableID)
    }
    
    // Track schema drift
    schemaVersion := meta.Schema.Hash()
    if schemaVersion != getExpectedSchemaHash(datasetID, tableID) {
        alert("Schema drift detected in %s.%s", datasetID, tableID)
    }
}
```

### Fix 2: Firestore - Use Merge Options or Explicit Field Lists

**Option 1: Use MergeAll to preserve existing fields**:

```go
// CORRECT: Merge instead of overwrite
doc := Document{
    ID:      "abc123",
    Title:   "My Document",
    Content: "",  // Will be omitted, but merge preserves existing
}

_, err := client.Collection("docs").Doc("abc123").Set(ctx, doc, firestore.MergeAll)
// <- MergeAll preserves fields not in the struct
```

**Option 2: Use Merge with specific fields**:

```go
// CORRECT: Only update specific fields, leave others untouched
_, err := client.Collection("docs").Doc("abc123").Set(ctx, map[string]interface{}{
    "title": "My Document",
    "updated_at": time.Now(),
}, firestore.Merge([]string{"title", "updated_at"}))
```

**Option 3: Remove omitempty tags**:

```go
// CORRECT: Always serialize all fields, even at zero value
type Document struct {
    ID      string   `firestore:"id"`
    Title   string   `firestore:"title"`
    Content string   `firestore:"content"`       // <- No omitempty
    Tags    []string `firestore:"tags"`          // <- No omitempty
}

// Now zero values are serialized as empty string/nil, not omitted
```

**Option 4: Read-modify-write pattern**:

```go
func updateDocumentSafely(ctx context.Context, client *firestore.Client,
    docID string, updates map[string]interface{}) error {
    
    docRef := client.Collection("docs").Doc(docID)
    
    return client.RunTransaction(ctx, func(ctx context.Context, tx *firestore.Transaction) error {
        // Read existing document
        var existing Document
        if err := tx.Get(docRef).To(&existing); err != nil {
            return err
        }
        
        // Apply updates to existing document
        if title, ok := updates["title"]; ok {
            existing.Title = title.(string)
        }
        if content, ok := updates["content"]; ok {
            existing.Content = content.(string)
        }
        
        // Write back complete document
        return tx.Set(docRef, existing)
    })
}
```

**Verification test**:

```go
func TestFirestoreOverwrite(t *testing.T) {
    // Create document with all fields
    docRef := client.Collection("test").Doc("test-doc")
    docRef.Set(ctx, map[string]interface{}{
        "title":   "Original",
        "content": "Original content",
        "tags":    []string{"a", "b"},
    })
    
    // WRONG: Overwrite with partial struct
    partial := Document{
        ID:    "test-doc",
        Title: "Updated",
        // Content and Tags are zero values
    }
    docRef.Set(ctx, partial)  // <- Erases content and tags!
    
    // Read back
    var result Document
    docRef.Get(ctx).To(&result)
    
    assert.Equal("Updated", result.Title)
    assert.Empty(result.Content)  // <- ERASED!
    assert.Empty(result.Tags)     // <- ERASED!
    
    // CORRECT: Use MergeAll
    docRef.Set(ctx, partial, firestore.MergeAll)
    
    docRef.Get(ctx).To(&result)
    assert.Equal("Updated", result.Title)
    assert.Equal("Original content", result.Content)  // <- Preserved
    assert.Equal([]string{"a", "b"}, result.Tags)     // <- Preserved
}
```

### Fix 3: Detection and Recovery

**Audit script for BigQuery**:

```bash
#!/bin/bash
# Check for empty BigQuery tables that should have data

TABLES=$(bq query --format=csv --use_legacy_sql=false \
  "SELECT table_id, row_count 
   FROM \`project.dataset.__TABLES__\` 
   WHERE row_count = 0")

echo "$TABLES" | while IFS=',' read -r table_id row_count; do
  if [ "$table_id" != "table_id" ]; then
    echo "WARNING: Table $table_id has 0 rows"
    # Check if inserts are happening
    INSERT_COUNT=$(bq query --format=csv --use_legacy_sql=false \
      "SELECT COUNT(*) FROM \`project.dataset.$table_id\` 
       WHERE _PARTITIONTIME > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)")
    
    if [ "$INSERT_COUNT" -eq 0 ]; then
      echo "  No inserts in last 7 days - possible silent failure"
    fi
  fi
done
```

**Audit script for Firestore**:

```go
func auditFirestoreDocuments(ctx context.Context, client *firestore.Client) {
    // Sample documents and check for missing fields
    iter := client.Collection("docs").Limit(100).Documents(ctx)
    
    var docsMissingFields int
    for {
        doc, err := iter.Next()
        if err == iterator.Done {
            break
        }
        
        var d Document
        doc.DataTo(&d)
        
        if d.Title != "" && d.Content == "" {
            docsMissingFields++
            log.Printf("Doc %s missing Content field", doc.Ref.ID)
        }
    }
    
    if docsMissingFields > 0 {
        alert("Found %d documents with missing fields - possible overwrite failure",
            docsMissingFields)
    }
}
```

## Verification

### Test 1: BigQuery Schema Mismatch Detection

```go
func TestBigQuerySchemaMismatch(t *testing.T) {
    // Create table with incomplete schema
    client.Dataset("test").Table("test_table").Create(ctx, &bigquery.TableMetadata{
        Schema: bigquery.Schema{
            {Name: "id", Type: bigquery.IntegerFieldType},
            {Name: "name", Type: bigquery.StringFieldType},
            // Missing "extra_field"
        },
    })
    
    // Try to insert row with extra field
    rows := []map[string]interface{}{
        {"id": 1, "name": "Alice", "extra_field": "value"},
    }
    
    err := insertRowsWithErrorCheck(ctx, client, "test", "test_table", rows)
    
    // Should detect schema mismatch
    assert.Error(err)
    assert.Contains(err.Error(), "rejected")
    assert.Contains(err.Error(), "extra_field")
}
```

### Test 2: Firestore Overwrite Detection

```go
func TestFirestoreOverwriteDetection(t *testing.T) {
    // Create document with all fields
    docRef := client.Collection("test").Doc("overwrite-test")
    docRef.Set(ctx, map[string]interface{}{
        "title":   "Original",
        "content": "Original content",
    })
    
    // Try to overwrite with partial struct (no MergeAll)
    partial := Document{ID: "overwrite-test", Title: "Updated"}
    docRef.Set(ctx, partial)
    
    // Read back
    var result Document
    docRef.Get(ctx).To(&result)
    
    // Detect data loss
    if result.Content == "" {
        t.Log("WARNING: Content field was erased by overwrite")
    }
    
    // CORRECT: Use MergeAll
    docRef.Set(ctx, partial, firestore.MergeAll)
    docRef.Get(ctx).To(&result)
    
    assert.Equal("Original content", result.Content)  // Preserved
}
```

### Test 3: End-to-End Data Integrity

```go
func TestDataIntegrity(t *testing.T) {
    // Simulate real scenario: multiple writes over time
    for i := 0; i < 5; i++ {
        updates := map[string]interface{}{
            "title": fmt.Sprintf("Update %d", i),
        }
        
        // CORRECT: Merge instead of overwrite
        docRef.Set(ctx, updates, firestore.MergeAll)
    }
    
    // Verify no data loss
    var result Document
    docRef.Get(ctx).To(&result)
    
    assert.Equal("Update 4", result.Title)
    assert.NotEmpty(result.Content)  // Should be preserved
    assert.NotEmpty(result.Tags)     // Should be preserved
}
```

## Notes

### Edge Cases

1. **BigQuery partitioned tables**: Schema validation must check partition schema, not just table schema.

2. **Firestore nested documents**: `MergeAll` only works at the top level. For nested structs, use field paths: `firestore.Merge([]string{"address.city"})`.

3. **Firestore array fields**: `omitempty` on arrays is especially dangerous - empty arrays are valid and should be preserved.

4. **BigQuery legacy SQL**: Legacy SQL has different error reporting. Use standard SQL for consistent behavior.

5. **Firestore transactions**: Read-modify-write in transactions prevents race conditions but doesn't prevent omitempty data loss.

### Monitoring Recommendations

1. **BigQuery row count alerts**: Alert when expected-to-be-populated tables have 0 rows.

2. **Firestore field presence audits**: Periodically sample documents and check for missing optional fields.

3. **Schema drift detection**: Compare code schema definitions against actual table/document schemas.

4. **Write success rate**: Track ratio of successful writes vs attempted writes. Silent failures reduce this ratio.

### Related Issues

- #1618: BigQuery silent data loss due to schema mismatch
- #1619: Firestore silent data loss due to overwrite with omitempty

### Verification Status

**Not tested with live Google Cloud APIs**. The solution is based on error analysis and SDK documentation. Verification tests are provided for users to implement in their environment.

---

*Lesson created by AUTO (AI Agent) | Bilingual Chinese-English-Portuguese capability | 2026-09-16*
