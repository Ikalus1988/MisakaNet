---
{
  "title": "Reducing Claude Code Context Consumption with Context Mode MCP Server",
  "domain": "ai-agents",
  "tags": ["mcp", "claude", "context-window", "tool-output-compression", "sandbox"],
  "language": "en",
  "status": "published",
  "source": "https://mksg.lu/blog/context-mode",
  "created": "2026-07-27",
  "confidence": "0.85"
}
---

## Problem

When using Claude Code with 81+ MCP tools active, tool outputs rapidly consume the 200K context window. A single Playwright snapshot dumps 56 KB into context. Running `gh issue list` costs 59 KB. A 500-line access log consumes 45 KB. After 30 minutes of typical development work, 40% of the context window is exhausted by raw tool output data that Claude only needs summarized, not in full detail. This forces developers to start new sessions prematurely, losing conversation history and requiring re-context.

## Root Cause

MCP (Model Context Protocol) tool definitions already consume 143K tokens (72%) of the context window before the first user message. Each subsequent tool call returns raw, unprocessed output directly into the conversation context: raw log files, full API responses, complete Playwright page snapshots, full GitHub issue listings. These outputs never get filtered or compressed—they arrive unmodified, treating context as an infinite resource when in fact it's a scarce, expensive constraint. The sandwich effect (tool definitions on input + raw output on output) creates a compounding context drain.

## Solution

Deploy Context Mode, an MCP server that intercepts tool outputs and processes them through an isolated sandbox before returning compressed results to Claude.

1. **Install Context Mode via Claude Code Plugin Marketplace** (recommended for auto-routing):
```bash
/plugin marketplace add mksglu/claude-context-mode
/plugin install context-mode@claude-context-mode
```

   Or install as standalone MCP server:
```bash
claude mcp add context-mode -- npx -y context-mode
```

2. **Restart Claude Code** to activate the PreToolUse hook that automatically routes tool outputs through the sandbox.

3. **Configure authenticated CLI credential passthrough** for tools like `gh`, `aws`, `gcloud`, `kubectl`, `docker`:
```bash
# Environment variables and config paths are inherited by subprocess automatically
# No credentials are exposed to the conversation context
export GITHUB_TOKEN="your-token"
export AWS_PROFILE="your-profile"
```

4. **Index external documentation** using the `fetch_and_index` tool to convert HTML to markdown, chunk by headings, and store in SQLite FTS5:
```python
# The raw page HTML never enters context
# Only exact code blocks with heading hierarchy are returned on search
response = await mcp_client.call_tool("fetch_and_index", {
    "url": "https://api.example.com/docs",
    "knowledge_base": "api_docs"
})
```

5. **Execute code in isolated sandboxes** using one of 10 language runtimes:
```javascript
// JavaScript/TypeScript execution (auto-detects Bun for 3-5x speed)
// Subprocess runs code, captures stdout only
// Raw data never leaves the sandbox
const result = await mcp_client.call_tool("execute", {
    "language": "javascript",
    "code": "console.log(JSON.stringify(largeDataset.map(x => x.summary)))"
});
```

6. **Subagents automatically adopt batch operations** through the PreToolUse hook and learn to use `batch_execute` as primary tool, reducing call count by 94% (e.g., repo research from 37 calls to 5 calls).

## Verification

Run these commands in a Claude Code session to measure context consumption before and after:

1. **Measure Playwright snapshot compression**:
```bash
# Before Context Mode: 56 KB
# After Context Mode: 299 B
playwright_page=$(npx playwright eval "
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('https://example.com');
  console.log(await page.content());
")
echo "Raw size: $(echo $playwright_page | wc -c) bytes"
```

2. **Measure GitHub issues list compression**:
```bash
# Before: 59 KB
# After: 1.1 KB
gh issue list --limit 20 --json title,body,author,state | wc -c
```

   Expected output after Context Mode processes it: ~1.1 KB instead of 59 KB.

3. **Measure access log compression**:
```bash
# Before: 45 KB
# After: 155 B
tail -500 /var/log/access.log | wc -c
```

   Expected output after Context Mode processes it: ~155 B instead of 45 KB.

4. **Verify session duration improvement**:
```bash
# Before Context Mode: sessions degrade after ~30 minutes
# After Context Mode: measure context remaining after 45 minutes of active work
# Expected: 99% remaining instead of 60%

# Check token usage in Claude Code session metrics
```

5. **Validate knowledge base search returns exact content**:
```bash
curl -X POST http://localhost:3000/tools/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication", "knowledge_base": "api_docs"}'

# Expected output: exact code blocks with heading hierarchy, not summaries
# Example: {"results": [{"heading": "## API Authentication", "code_block": "const auth = ..."}]}
```

## Notes

This pattern generalizes beyond Claude Code. Any AI agent system using tool-based interactions (ReAct, LangChain agents, AutoGPT) faces the same context-compression problem. The principle: process tool outputs through a sandbox to extract only decision-relevant information before returning to the agent. SQLite FTS5 with BM25 ranking and Porter stemming applies to any knowledge base retrieval task where raw documents are too large (medical records, legal contracts, research papers). Credential passthrough via environment variable inheritance works for any authenticated CLI tool. The 98% compression ratio (315 KB → 5.4 KB) is reproducible across log files, API responses, and structured data (CSV, JSON) because the work is always: filter to essentials, extract actionable summaries, discard raw noise.

## References

- **Source**: https://mksg.lu/blog/context-mode
- **Repository**: https://github.com/mksglu/claude-context-mode (MIT licensed)
- **Related**: Cloudflare Code Mode blog post (tool definition compression)
- **Hacker News**: 570 points (validates widespread context-window pain)
- **Author**: Mert Köseoğlu, MCP Directory & Hub maintainer