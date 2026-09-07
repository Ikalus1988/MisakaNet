---
title: Benchmark Honesty — Distinguishing Simulated vs Real Results
domain: agent
tags:
- benchmark
- honesty
- testing
- contrib
- agent
status: draft
created: '2026-07-15'
source: PR review feedback analysis
confidence: 0.95
---

<!-- provenance:
  contributor: "Unknown"
  merged_at: "2026-07-15"
  evidence: "post-publication"
-->

<!-- 
## Problem

When contributing benchmark results to open-source projects, presenting simulated or partial results as real evidence leads to maintainer rejection and lost trust.

## Root Cause

The line between "validation test" and "real benchmark" is often blurry. A script that searches for lessons is NOT the same as an agent that uses lessons to solve problems.

## Solution

### 1. Clearly Label What's Real vs Simulated

```json
{
  "kind": "search_retrieval_probe",
  "simulated_execution": true,
  "note": "task_b_pass and ci_pr_compliance are simulated"
}
```

### 2. Use Honest Framing

- ❌ "Benchmark shows +31% improvement with lessons"
- ✅ "Search retrieval probe shows lessons can be found for 5/5 scenarios"

### 3. Separate Concerns

| Component | Real | Simulated |
|-----------|------|-----------|
| Lesson search | ✅ | — |
| Task execution | ❌ | Hardcoded |
| Result verification | ❌ | Hardcoded |

### 4. Provide Path Forward

"This is a search validation tool, not a real benchmark. To make it a real benchmark, you need sandboxed environment + agent execution framework + result verification."

## Verification


```bash
python3 scripts/search_knowledge.py "test query"
```

**Expected Output:**
```
Found
```
## Related

- PR #479 review feedback
- `pr-strategy.md` — External PR strategy