# DeepSeekHarness local runtime field test — 2026-08-15

Issue: #1048
Run date: 2026-08-16T10:16:46.0487879+08:00
Repo: C:\Users\hp\MisakaNet
Git SHA: $full ($sha)
Version: 2.17.0
Environment: Microsoft Windows 11 专业版 10.0.26200 build 26200; Python 3.11.9

## Scope

This report verifies the MisakaNet DeepSeekHarness recovery adapter in a local Windows MCP stdio runtime. It does **not** claim official DeepSeekHarness certification, does not require API keys, and does not test a remote MCP endpoint.

## DSH MCP config snippet

`json
{
  "mcpServers": {
    "misakanet-recovery": {
      "command": "python",
      "args": ["C:/Users/hp/MisakaNet/scripts/mcp_deepseek_adapter.py"],
      "cwd": "C:/Users/hp/MisakaNet"
    }
  }
}
`

## CLI verification

`powershell
python scripts/misakanet_cli.py doctor
python scripts/misakanet_cli.py smoke
python scripts/misakanet_cli.py validate
`

Result summary:

- doctor: exit 0; overall healthy; lessons.json count 289; lessons dir count 418; search engine m25.
- smoke: exit 0; overall pass; search returned 3 results from sag-lite; get_lesson returned lessons/core/dco-auto-fix-workflow.md with content length 3832.
- alidate: exit 0; overall pass; MCP server exposes 4 tools; DeepSeek adapter exposes all 6 deepseek.recovery.* tools.

## MCP stdio runtime verification

Runtime command:

`powershell
python scripts/mcp_deepseek_adapter.py
`

Initialization returned:

`json
{"serverInfo":{"name":"misakanet-deepseek-adapter","version":"1.0.0"},"protocolVersion":"2025-06-18"}
`

	ools/list returned all 6 adapter tools:

- deepseek.recovery.search
- deepseek.recovery.get_lesson
- deepseek.recovery.submit_feedback
- deepseek.recovery.status
- deepseek.recovery.doctor
- deepseek.recovery.smoke

### Search round trip

Request:

`json
{"name":"deepseek.recovery.search","arguments":{"query":"DCO","top":3}}
`

Observed result:

- source: sag-lite
- results: 3
- first match: DCO Auto-Fix Workflow — /fix-dco Command Design & Implementation
- first path: lessons/core/dco-auto-fix-workflow.md

### Get lesson round trip

Request:

`json
{"name":"deepseek.recovery.get_lesson","arguments":{"path":"lessons/core/dco-auto-fix-workflow.md"}}
`

Observed result:

- path: lessons/core/dco-auto-fix-workflow.md
- content length: 3832
- voice: connect-success

### Remaining adapter tool calls

- deepseek.recovery.submit_feedback: returned status: logged for dco-auto-fix-workflow.
- deepseek.recovery.status: returned plugin version 1.0.0, MCP server version 2.17.0, active engine sag-lite, free reads remaining 5.
- deepseek.recovery.doctor: returned overall healthy.
- deepseek.recovery.smoke: returned overall pass; search ok; get_lesson ok; content length 3832.

## Fix applied during field test

Initial runtime testing found the adapter smoke path queried DCO sign-off, which can trip the SAG-Lite SQLite keyword edge case (
o such column: off). The smoke implementation now uses the adapter-level guarded search path and a simpler DCO smoke query, then reuses that search result for the get_lesson step.

Regression coverage added:

`powershell
python -m pytest tests/test_mcp_deepseek_adapter.py tests/test_search_edge_cases.py -q
# 27 passed
`

## Final verification commands

`powershell
python -m py_compile scripts/mcp_deepseek_adapter.py
python -m pytest tests/test_mcp_deepseek_adapter.py tests/test_search_edge_cases.py -q
python scripts/misakanet_cli.py doctor
python scripts/misakanet_cli.py smoke
python scripts/misakanet_cli.py validate
python scripts/lesson_lint.py --lessons-dir lessons --fail-on high
`

Final result: all commands passed.
