# MisakaNet MCP Server

## Summary of Changes for Issue #2967

This PR fixes the issue where the MCP client silently registers zero tools when the server returns tool schemas containing JSON Schema keywords outside the DSH-allowed subset (e.g. `minProperties`).

The root cause was that the tools/list response was passed through to the client without schema normalization. DeepSeek Harness enforces a strict subset of JSON Schema keywords, and any disallowed keyword causes the tool to be rejected silently.

**Changes:**

1. Added `normalizeToolSchema()` function in `src/tools.ts` that recursively strips disallowed JSON Schema keywords from tool schemas, preserving only the DSH-approved subset (`type`, `oneOf`, `properties`, `required`, `additionalProperties`, `items`, `enum`, `const`) plus description/title annotations.

2. Updated `listTools` handler in `src/server.ts` to apply schema normalization before returning tools to the client.

3. Updated integration test in `tests/integration/mcp-server.test.ts` to verify that tools with disallowed keywords like `minProperties` are properly normalized and returned.

This fix ensures that tool schemas are correctly processed regardless of extra keywords present in the server response, preventing the "no tools registered" silent failure.

Closes #2967
/attempt
/claim #2967
<<<END_PR_DESCRIPTION>>>
</think>
