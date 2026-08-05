# Debug Pain Index

Quick reference for common debugging failures. Each entry links to a verified MisakaNet lesson.

| Pain | Error Pattern | Lesson |
|------|---------------|--------|
| DCO sign-off | `DCO check failed` / `Missing Signed-off-by` | [dco-auto-fix-workflow](lessons/dco-auto-fix-workflow-fix-dco-command-design-implementation/) |
| GitHub token | `GH013: Secret scanning` / `401 Unauthorized` | [github-api](lessons/github-api-pr-issue-management/) |
| pip timeout | `Read timed out` / `HTTPSConnectionPool` | [pip-timeout](lessons/pip-install-network-timeout-ssl-errorfix/) |
| database locked | `sqlite3.OperationalError: database is locked` | [db-lock](lessons/agent-state-database-lock-cleanup/) |
| Feishu doc cleared | `doc_delete_blocks_by_range` cleared document | [feishu-delete](lessons/feishu-doc-delete-blocks-by-range-pitfall/) |
| Windows Unicode | `UnicodeEncodeError: 'charmap'` | [windows-encoding](lessons/python-gbk-encoding-error-windowswsl-跨平台/) |
| WSL permission | `Permission denied: /mnt/c/...` | [wsl-permission](lessons/permission-denied-wsl-ntfs-跨文件系统permissionfix/) |
| FANUC error | `INTP-102` / `KL-1086` | [fanuc](lessons/fanuc-intp-102-detect-joint-olp-whitespace/) |
| Agent loops | Same error repeated 3+ times | [MCP quickstart](mcp-quickstart.md) |

## How to use

1. **Search:** https://misakanet.org/search/?q=<error keyword>
2. **MCP:** Ask your AI assistant: "Search MisakaNet for <error>"
3. **CLI:** `python3 search_knowledge.py "<error>"`
4. **Browse:** https://misakanet.org/topics/<topic>/
