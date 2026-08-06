# Search Badcase Report — 2026-07-13

## Baseline

- Lessons: 205
- Regression queries: 10
- Search engine: BM25 + RRF (misakanet-core)

## Regression Query Results

| Query | Expected Lesson | Found? | Top Result | Notes |
|-------|----------------|--------|------------|-------|
| DCO | dco-auto-fix-workflow | ✅ | dco-auto-fix-workflow | Exact match |
| GitHub token | github-api-pr-issue-management | ✅ | github-api-pr-issue-management | Exact match |
| pip timeout | pip-install-timeout-ssl | ✅ | pip-install-timeout-ssl | Exact match |
| database locked | agent-state-database-lock-issues-cleanup-protocol | ✅ | agent-state-database-lock-issues-cleanup-protocol | Exact match |
| feishu | feishu-block-api-false-success | ✅ | feishu-block-batch-limit | Domain match (top 3 all feishu) |
| FANUC | fanuc-io-marker-m-instruction | ✅ | fanuc-io-marker-m-instruction | Exact match |
| PROFINET | fanuc-profinet-32bit-real-value-transfer | ✅ | fanuc-profinet-32bit-real-value-transfer | Exact match |
| secret scan | codeql-alert-dismissal-false-positive | ✅ | codeql-alert-dismissal-false-positive | Exact match |
| Windows Unicode | python-gbk-encoding-error | ✅ | python-gbk-encoding-error | Exact match |
| WSL permission | wsl-permission-ntfs-fix | ✅ | wsl-permission-ntfs-fix | Exact match |

## Summary

- **10/10 queries returned expected lessons** ✅
- No no-result failures
- No misleading top results
- Domain-specific queries (feishu, FANUC) correctly prioritize domain lessons

## Known Gaps

- Chinese queries (e.g., "数据库锁定") may not match English lesson titles
- Compound queries (e.g., "pip install timeout SSL") may rank differently
- No semantic search baseline (BM25 keyword-only)

## Risk Tags

| Tag | Count | Description |
|-----|-------|-------------|
| no_result | 0 | Queries returning zero results |
| low_confidence | 0 | Results with score < 0.3 |
| duplicate | 0 | Multiple lessons covering same topic |
| stale_count | 0 | Lesson count mismatches |

## Next Steps

- Run this report before each release
- Add Chinese query variants
- Track no-result queries from blind tests (#429)
- Consider adding domain-specific synonyms (#313)
