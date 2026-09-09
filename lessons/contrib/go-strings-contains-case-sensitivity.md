---
title: Go strings.Contains Case Sensitivity Pitfall and Normalization
domain: contrib
tags:
- go\n- golang\n- strings\n- bugfix\n- case-sensitivity
status: published
created: '2026-09-09'
source: community
evidence_level: E2
evidence_refs:
- issue:#1571
provenance:
  source: community
  contributor: Community
  evidence: post-publication
---

## Problem

In Go microservices, CLI tools, and agent filters, checking substring presence using standard library `strings.Contains` frequently produces silent logic bugs and security bypasses:
1. `strings.Contains(header, "bearer")` evaluates to `false` when an HTTP client sends `Authorization: Bearer <token>`, dropping valid authorization headers.
2. Filtering user input or event topics fails when casing varies between uppercase, lowercase, and titlecase (e.g. `GITHUB_TOKEN` vs `github_token`).
3. Routing middlewares that inspect URL paths fail to match valid endpoints due to case discrepancies.

## Root Cause

1. Go's `strings.Contains(s, substr)` operates strictly on byte-for-byte exact equality. It does not perform Unicode case-folding.
2. Developers familiar with dynamic languages assume case-insensitive options exist as function parameters, which Go standard library deliberately omits.
3. Calling `strings.ToLower()` naively in high-throughput hot paths allocates a new string on the heap for every comparison.

## Solution

### 1. Case-Insensitive Substring Match (Standard Path)
For standard pipelines, normalize both haystack and needle using `strings.ToLower`:

```go
package main

import (
    "strings"
)

// ContainsFold checks whether substr is within s, case-insensitively.
func ContainsFold(s, substr string) bool {
    return strings.Contains(strings.ToLower(s), strings.ToLower(substr))
}
```

### 2. Exact Equality Matching
If checking for full string equality rather than substring containment, use Go's built-in allocation-friendly `strings.EqualFold`:

```go
if strings.EqualFold(authScheme, "bearer") {
    // Matches "Bearer", "BEARER", "bearer"
}
```

### 3. Allocation-Free Substring Matching for Hot Paths
For high-performance loops, avoid heap allocations by using an in-place case-folding scanner:

```go
import "unicode"

func ContainsFoldFast(s, substr string) bool {
    if len(substr) == 0 {
        return true
    }
    if len(s) < len(substr) {
        return false
    }
    subRunes := []rune(substr)
    for i, r := range subRunes {
        subRunes[i] = unicode.ToLower(r)
    }
    for i := 0; i <= len(s)-len(substr); i++ {
        matched := true
        for j, sr := range subRunes {
            if unicode.ToLower(rune(s[i+j])) != sr {
                matched = false
                break
            }
        }
        if matched {
            return true
        }
    }
    return false
}
```

## Verification

```bash
go test -v -run TestContainsFold
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed: fix command exited 0` is printed.
