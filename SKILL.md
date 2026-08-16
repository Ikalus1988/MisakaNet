# misakanet-failure-memory

> Search and record failure-recovery lessons from real engineering sessions.

## When to use this skill

Use MisakaNet when you encounter:

- **Errors**: `ModuleNotFoundError`, `ConnectionRefusedError`, `TimeoutError`
- **Exceptions**: uncaught exceptions, unhandled rejections, segfaults
- **CI failures**: DCO sign-off, lint errors, test failures, build failures
- **Tool failures**: MCP server crashes, API timeouts, auth errors
- **Regression**: something that worked before now fails
- **Preflight checks**: high-risk operations (RAG index builds, GPU/WSL heavy jobs, bulk imports)

Do NOT use MisakaNet for:

- Normal code completion or refactoring
- Questions about how to use a library (use documentation instead)
- Feature requests or design discussions
- Anything that isn't a failure, error, or high-risk execution boundary

## Recovery flow

```
1. Before high-risk tasks: run preflight check
   Hit an error during execution
   ↓
2. Search MisakaNet for matching lessons
   ↓
3. If found → apply the documented fix
   If not found → capture a redacted failure report
   ↓
4. Submit feedback (solved / partial / not-helpful)
```

## Tools

### Preflight risk evaluation

```
misakanet_preflight(intent="build RAG index from 218 PDFs", context="WSL, GPU 8GB VRAM")
```

Evaluates intent against failure patterns and returns risk level, matched lessons, and safety guard checklists before execution.

### Search for lessons

```
misakanet_search(query="error message or keyword", top=5)
```

Returns ranked lessons with path, title, score, and domain.

### Get a specific lesson

```
misakanet_get_lesson(path="lessons/core/some-lesson.md")
```

Returns the full lesson content in markdown.

### Submit feedback

```
misakanet_submit_usage(lesson_id="some-lesson", outcome="solved")
```

Records that a lesson helped. Outcomes: `solved`, `partial`, `not-helpful`.

### Check status

```
misakanet_usage_status()
```

Shows remaining quota and credits.

## Examples

### Example 1: Preflight check before RAG build

```
Intent: "build RAG index from 218 PDFs"
Context: "WSL, GPU 8GB VRAM"

Action: misakanet_preflight(intent="build RAG index from 218 PDFs", context="WSL, GPU 8GB VRAM")
Result: Risk "critical", guards suggest batch_size <= 8, 3-5 doc sampling, and checkpointing.
Action taken: Run probe first with 3 docs, verify VRAM, then scale up safely.
```

### Example 2: DCO sign-off failure

```
Error: Expected "Signed-off-by: Your Name <your@email.com>"

Action: misakanet_search(query="DCO sign-off failed")
Result: Found lesson "dco-signoff-missing"
Fix: git commit --signoff
Outcome: misakanet_submit_usage(lesson_id="dco-signoff-missing", outcome="solved")
```

### Example 3: Python import error

```
Error: ModuleNotFoundError: No module named 'requests'

Action: misakanet_search(query="ModuleNotFoundError requests")
Result: Found lesson "python-import-error-fix"
Fix: pip install requests
Outcome: misakanet_submit_usage(lesson_id="python-import-error-fix", outcome="solved")
```

### Example 4: MCP server crash

```
Error: MCP server crashed during startup: JSONDecodeError

Action: misakanet_search(query="MCP server crash JSON")
Result: Found lesson "mcp-server-json-error"
Fix: Validate JSON input format
Outcome: misakanet_submit_usage(lesson_id="mcp-server-json-error", outcome="solved")
```

## Domain filters

You can narrow searches by domain:

- `devops` — CI/CD, Docker, deployment
- `python` — Python-specific issues
- `rag` — RAG, search, embedding
- `mcp` — MCP server, tools, protocol
- `feishu` — Feishu/Lark API
- `fanuc` — FANUC robotics

Example: `misakanet_search(query="timeout", domain="python")`

## Important notes

- **Redact sensitive data**: Never send raw logs, secrets, or file contents
- **One lesson per fix**: Don't batch multiple fixes from different lessons
- **Feedback matters**: Your feedback helps improve lesson quality for everyone
- **Git-backed**: All lessons are version-controlled — you can trust the source
