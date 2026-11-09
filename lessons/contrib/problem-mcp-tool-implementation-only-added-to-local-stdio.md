---
title: "MCP 工具只加到本地 stdio 面、没加托管端点：远程调用找不到该工具"
domain: "mcp"
tags:
  - "problem"
  - "mcp"
  - "tool"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-2559"
summary_plain: "MCP tool implementation only added to local stdio surface, not to hosted worker endpoint."
trigger: "Problem MCP tool implementation only added to local stdio surface, not to hosted. MCP tool implementation only added to local stdio surface, not to hosted…"
verify: "```bash python3 -m pytest tests/test_mcp_tool_count_ssot.py tests/test_mcp_doc_surface.py -v # All tests pass, documented count matches registered count ```"
provenance:
  issue: "#2559"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

MCP tool implementation only added to local stdio surface, not to hosted worker endpoint. Maintainer flags as `needs-scope-fix` because ~65% of users reach the hosted endpoint.

## Root Cause

When adding a new MCP tool to MisakaNet, there are two surfaces: local stdio (`scripts/mcp_server.py`, 10 tools) and hosted worker (`workers/register-proxy-sw.js`, 8 tools). The handler dict in `protocol.py` (local) and the `toolName` if-chain + `MCP_TOOLS` array + `openTools` array in `register-proxy-sw.js` (worker) must all be updated. Forgetting the worker side means the tool is unreachable for most users.

Additionally, if the handler depends on local files (e.g. JSONL logs in `data/`), those files may not exist on main — the tool silently returns empty/pending results.

## Fix

1. Add tool definition to worker's `MCP_TOOLS` array (with description, inputSchema, annotations, outputSchema)
2. Add handler block in the worker's `toolName` if-chain (with rate-limiting for anonymous access)
3. Add tool name to `openTools` array if it should be anonymous-accessible
4. For the local handler: proxy to the hosted worker API endpoint instead of reading local files
5. Update AGENTS.md tool table (heading count + new row), docs/mcp.md surface table, and test assertions
6. Run `tests/test_mcp_tool_count_ssot.py` and `tests/test_mcp_doc_surface.py` to verify all three copies agree

## Verification

```bash
python3 -m pytest tests/test_mcp_tool_count_ssot.py tests/test_mcp_doc_surface.py -v
# All tests pass, documented count matches registered count
```
