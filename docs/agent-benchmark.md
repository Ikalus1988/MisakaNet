# Agent Benchmark — One-Command Smoke Tests

Run these three commands to verify MisakaNet is working. No credentials needed for search and validation.

## 1. Search (JSON output)

```bash
PYTHONIOENCODING=utf-8 python3 scripts/misaka_search_json.py "supabase capacity" --top 3
```

**Expected**: JSON array with 3 results, each containing `title`, `domain`, `score`, `path`.

## 2. MCP Server (stdio)

```bash
PYTHONIOENCODING=utf-8 python3 scripts/mcp_server.py
```

**Expected**: Starts stdio MCP server. Send `{"jsonrpc":"2.0","id":1,"method":"tools/list"}` to get tool list including `misakanet_search`.

## 3. Lesson Validator

```bash
PYTHONIOENCODING=utf-8 python3 scripts/validate_lessons.py
```

**Expected**: Reports total lessons checked. Hard failures should be 0. Warnings on legacy frontmatter are acceptable.

## Pass Criteria

| Check | Pass | Fail |
|-------|------|------|
| Search | Returns JSON array with results | Empty or error |
| MCP | `tools/list` includes `misakanet_search` | Missing tool or crash |
| Validator | Hard failures = 0 | Any hard failure |

## Notes

- Search quota: 5 free searches per clone. Contributing a lesson resets quota.
- MCP requires `PYTHONIOENCODING=utf-8` on Windows.
- Validator warnings on legacy frontmatter are expected and do not block.
