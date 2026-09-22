# Field Report: Cursor MCP Smoke Test

**Date:** 2026-09-23
**Agent/Client:** Cursor
**Version:** 0.45.1
**Mode:** Remote (SSE)

## Configuration Used
**Path:** `.cursor/mcp.json`
*(Note: I explicitly ran this configuration myself. Cursor's official docs show similar structures, but this confirms that the `headers` key natively accepts the `Bearer` syntax without breaking the internal JSON parser).*

## Live Query Test
**Query:** "database is locked"
**Cursor Agent Action:** Invoked `misakanet_search_lessons` with arguments `{"query": "database is locked"}`.
**Result Excerpt:** "Found 1 relevant lesson: SQLite WAL mode + timeout fix..."

## Failure Modes Observed
*   **Typo in Key (`header` instead of `headers`):** Cursor **fails silently**. The tools simply do not appear in the interface.
