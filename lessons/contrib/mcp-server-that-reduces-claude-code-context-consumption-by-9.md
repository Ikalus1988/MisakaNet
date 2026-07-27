---
{
  "title": "Reducing Claude Code Context Consumption with Context Mode MCP Server",
  "domain": "ai-tools",
  "tags": ["mcp", "claude", "context-window", "optimization", "tool-output-compression"],
  "language": "en",
  "status": "published",
  "source": "https://mksg.lu/blog/context-mode",
  "created": "2026-07-27",
  "confidence": "0.85"
}
---

## Problem

When using Claude Code with 81+ active MCP tools, tool output dumps raw uncompressed data directly into the 200K context window. A single Playwright snapshot consumes 56 KB, a list of 20 GitHub issues consumes 59 KB, and an access log with 500 requests consumes 45 KB. After 30 minutes of typical development work, 40% of the context window is depleted by raw tool outputs, forcing the session to slow down or restart.

## Root Cause

MCP tool definitions and outputs both consume context tokens. While tool definitions on input can be compressed with Code Mode techniques, the raw output side was unaddressed. Each tool call returns unprocessed data (JSON responses, log files, test outputs, API responses) that enters the conversation context unchanged. With multiple tool calls per minute during agent-assisted development, context accumulates rapidly and becomes the bottleneck rather than reasoning capability.

## Solution

Install Context Mode, an MCP server that intercepts tool outputs and compresses them before they enter context. The server uses two mechanisms:

1. **Sandbox Execution Model**: Each tool call runs in an isolated subprocess that captures only stdout to context—raw data files never enter the conversation.

2. **Knowledge Base Compression**: For document-heavy operations, use SQLite FTS5 (Full-Text Search 5) with BM25 ranking instead of dumping raw content.

### Installation Steps

**Option 1: Via Plugin Marketplace (Recommended)**

```bash
/plugin marketplace add mksglu/claude-context-mode
/plugin install context-mode@claude-context-mode
```

Then restart Claude Code.

**Option 2: Via MCP Direct**

```bash
claude mcp add context-mode -- npx -y context-context-mode
```

Then restart Claude Code.

### Integration (No Code Changes Required)

Context Mode includes a PreToolUse hook that automatically routes tool outputs through the sandbox. No changes to your workflow needed—it operates transparently.

### Example: Indexing and Searching Documentation

```python
# The index tool chunks markdown by headings and stores in SQLite FTS5
# When you call search(), it returns exact code blocks with hierarchy

# Internally uses Porter stemming so "running", "runs", "ran" match
# BM25 ranking scores by term frequency and document length
# Result: exact content returned, not summaries or approximations
```

### Example: Processing Raw Data

```bash
# Before Context Mode:
# Run access log analysis → 45 KB of raw JSON in context
# Run test suite → raw XML output → 78 KB in context

# After Context Mode:
# Access log (500 requests): 45 KB → 155 B (only summary stdout)
# Test suite XML: processed in sandbox → only failure summary to context
```

Authenticated CLIs (`gh`, `aws`, `gcloud`, `kubectl`, `docker`) work through credential passthrough—the subprocess inherits environment variables and config paths without exposing them to the conversation context.

## Verification

Run these commands in Claude Code to verify compression is working:

```bash
# Check that Context Mode is installed
claude mcp list | grep context-mode
# Expected: context-mode should appear in the list
```

```bash
# Monitor a Playwright snapshot operation
# Before: Raw HTML snapshot (56 KB) enters context
# After: Only CSS-selector summary (299 B) in context
# Verify by checking token count before/after in Claude Code interface
```

```bash
# Test with GitHub issues search
gh issue list --limit 20 | head -c 59000
# This normally dumps 59 KB
# With Context Mode active, only 1.1 KB enters context
# Verify by observing context token growth is 55x smaller
```

```bash
# Monitor session duration improvement
# Track how long you can work before context degradation
# Expected improvement: 30 minutes → 3+ hours on same 200K token budget
# Check context remaining after 45 minutes: should be ~99% instead of 60%
```

## Notes

This compression technique generalizes to any AI agent system with tool outputs:

- **LLM API calls with external integrations**: The sandbox isolation pattern applies to any system where tool responses enter a fixed context window. GPT-4 with Code Interpreter, Claude with API calls, or Anthropic's own agent deployments all benefit.

- **Multi-turn retrieval workflows**: Any RAG system using full document chunks can adopt the FTS5 + BM25 approach to return exact sections instead of summarized results, reducing hallucination while cutting tokens.

- **Log analysis and monitoring**: The pattern of processing large text streams (logs, metrics, traces) in subprocess sandboxes and returning only aggregated output is applicable to observability agent architectures.

- **Batch tool operations**: Subagents learn to use `batch_execute` as primary tool, and Bash subagents are upgraded to `general-purpose` mode to access MCP tools, enabling more efficient coordination of multiple tool calls.

## References

- **Source**: https://mksg.lu/blog/context-mode
- **GitHub Repository**: https://github.com/mksglu/claude-context-mode
- **License**: MIT
- **Related Work**: Cloudflare's Code Mode (tool definition compression at 99.9%) inspired the output-side compression approach