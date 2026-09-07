# Error-Signature Index (failure_patterns) Design Summary

## 1. Problem Statement & Root Cause

The MisakaNet lesson corpus historically achieved a benchmark hit rate of 0.489 when queried with raw error strings.

### Root Cause
1. **Vocabulary Mismatch**: Lessons are written in narrative prose (problem explanation, root cause analysis, architecture rationale), whereas CI agents and automated tools query using raw runtime strings (exception traces, HTTP status lines, stack frames, compiler logs).
2. **Noise Dilution**: Raw error logs contain volatile session variables (commit hashes, ephemeral file paths, line numbers, timestamps, usernames). In standard BM25 and bag-of-words token overlap, these terms dilute query scores or trigger false positives against unrelated documents containing generic tokens (such as "commit", "read", "at").
3. **Threshold Sensitivity**: Intake-bot precheck uses a strict Jaccard token overlap threshold against lesson prose. Because error messages contain few prose keywords, valid lessons frequently score below the 0.30 threshold and are incorrectly flagged as missing lessons.

---

## 2. Architecture & Design

Phase A establishes a structured error-signature index (`failure_patterns`) and integrates signature matching into `misakanet.search.engine` and `scripts.intake_bot`.

```
Raw Error String / Query
           │
           ▼
┌──────────────────────────────────────┐
│  Error Signature Normalizer         │
│  - Strip volatile variables          │
│  - Parameterize paths/hashes/lines   │
│  - Extract high-entropy key tokens   │
└──────────────────┬───────────────────┘
                   │
         Normalized Signature
                   │
                   ▼
┌──────────────────────────────────────┐
│  Failure Patterns Index Matcher      │
│  - Template exact/containment match  │
│  - Regular expression match          │
│  - Distinctive token set overlap     │
└──────────────────┬───────────────────┘
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
┌───────────────────────┐   ┌───────────────────────┐
│ misakanet.search      │   │ intake-bot precheck   │
│ - Score boost (+1.5)  │   │ - Immediate top-1 hit │
│ - Match reason tag    │   │ - Bypass prose decay  │
│ - High confidence tag │   │ - Skip duplicate PRs  │
└───────────────────────┘   └───────────────────────┘
```

---

## 3. Error Normalization Grammar

The normalizer replaces volatile execution artifacts with standardized semantic placeholders:

| Pattern Type | Raw Pattern Example | Normalized Semantic Placeholder |
|---|---|---|
| Git SHAs / Hex | `8f9b1c2`, `0x7ffee3b4` | `<SHA>`, `<HEX>` |
| File Paths | `/app/service.py`, `C:\workspace\repo` | `<PATH>` |
| Line & Column Numbers | `:123`, `line 45:10` | `line <NUM>`, `:<NUM>` |
| Timestamps / Dates | `2026-09-07T11:20:00Z` | `<TIMESTAMP>` |
| IP Addresses | `192.168.1.100` | `<IP>` |
| URLs | `https://github.com/org/repo` | `<URL>` |
| Emails | `user@example.com` | `<EMAIL>` |
| Port Numbers | `:3000`, `:8080` | `:<PORT>` |

---

## 4. Storage Model

Phase A utilizes a sidecar index (`data/failure_patterns.json`) as the primary storage layer, with transparent fallback to frontmatter `failure_patterns` when present.

### Schema per Lesson Entry
```json
{
  "id": "dco-auto-fix-workflow",
  "title": "DCO Auto-Fix Workflow",
  "domain": "devops",
  "templates": [
    "Commit sha: <SHA>, Author: <USER>, Committer: <USER>; Expected \"Signed-off-by: <USER> <<EMAIL>>\", but got \"\"",
    "Expected \"Signed-off-by: <USER> <<EMAIL>>\", but got \"\""
  ],
  "regexes": [
    "Commit sha:.*Author:.*Committer:.*Expected [\"']Signed-off-by:",
    "Expected [\"']Signed-off-by:"
  ],
  "key_tokens": [
    "author",
    "committer",
    "dco",
    "signed-off-by"
  ],
  "source": "extracted"
}
```

### Advantages of Sidecar Index
1. **Zero Churn on Markdown Corpus**: 360+ lesson files remain clean without mass git commits modifying frontmatter.
2. **Fast In-Memory Lookup**: Single JSON file loaded into memory in <5ms.
3. **Pipeline Extensibility**: Future write-time tooling (Phase B) can inspect and enrich individual records or attach manual frontmatter overrides.

---

## 5. Search Engine Fusion Strategy

In `misakanet.search.engine`:
1. **Pattern Score Calculation**: Queries are evaluated against `failure_patterns`.
   - Exact template or regex match: score 1.0.
   - Normalized substring containment: score 0.9.
   - Distinctive key token overlap (>= 2 key error tokens and >= 0.6 token containment): score 0.75 - 0.85.
2. **Ranking Integration**:
   ```python
   score = (
       bm25_weight * bm25_norm
       + metadata_weight * metadata_bonus
       + baseline_weight * baseline
       + boost
       + (1.5 * pattern_score)
   )
   ```
3. **Metadata & Explainability**:
   - `match_reason` includes `failure_pattern '<matched_signature>'`.
   - `why_matched` adds `failure_pattern` field.
   - Confidence classifier automatically classifies pattern-matched hits as `high`.

---

## 6. Intake-Bot Precheck Fusion Strategy

In `scripts.intake_bot`:
1. Incoming error text is evaluated against the failure pattern index before running token overlap.
2. If a pattern matches with score >= 0.70, precheck immediately returns the matched lesson with high similarity (`sim >= 0.85`).
3. If no pattern matches, precheck falls back to the existing fuzzy prose token overlap.

---

## 7. Phase A Acceptance Criteria & Verification

- [x] Extraction engine processes all 364 canonical lessons.
- [x] Sidecar index generated at `data/failure_patterns.json`.
- [x] Search engine and intake-bot integrated with pattern matching.
- [x] 10 spot-check error-to-lesson pairs evaluated:
  - Required: >= 80% (8/10) top-1 accuracy.
  - Target: 100% (10/10) top-1 accuracy.
- [x] Benchmark hit-rate delta measured and reported.
