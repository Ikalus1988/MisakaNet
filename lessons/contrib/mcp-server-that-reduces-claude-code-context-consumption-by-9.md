---
{
  "title": "Reducing Claude Code Context Consumption with Context Mode MCP Server",
  "domain": "AI/LLM",
  "tags": ["MCP", "Claude Code", "context-window", "token-optimization", "tool-output-compression"],
  "language": "en",
  "status": "published",
  "source": "https://mksg.lu/blog/context-mode",
  "created": "2026-07-27",
  "confidence": "0.85"
}
---

## Problem

When using Claude Code with 81+ MCP tools enabled, the 200K token context window fills rapidly. A single Playwright snapshot consumes 56 KB, a GitHub issue list query returns 59 KB, and accessing log files or documentation each add 45 KB. After 30 minutes of typical agentic work, 40% of the context window is consumed by raw tool outputs (not even including the initial 72% consumed by tool definitions), forcing sessions to end or degrade significantly. For example, a 315 KB collection of real-world tool outputs (Playwright snapshots, GitHub issues, access logs, CSV analytics) consumed the majority of available context in a standard 3-hour session.

## Root Cause

Every MCP tool call in Claude Code returns raw, uncompressed data directly into the conversation context. The tool output pipeline lacks filtering or summarization: Playwright snapshots dump full DOM trees, `gh issue list` returns complete JSON responses, access logs include every request entry, and CSV files load entirely. While tool definitions themselves can be compressed 99.9% (as Cloudflare demonstrated with Code Mode), no mechanism existed to compress the output side—the raw data returned from tool executions. This asymmetry means the context window fills from tool outputs even if tool definitions are optimized.

## Solution

Context Mode is an MCP server that intercepts tool outputs and processes them through a sandbox before adding them to context. Implement it in three steps:

1. **Install Context Mode via Claude Code plugin marketplace:**
```bash
/plugin marketplace add mksglu/claude-context-mode
/plugin install context-mode@claude-context-mode
```
Or install as MCP-only:
```bash
claude mcp add context-mode -- npx -y context-mode
```

2. **Restart Claude Code.** The PreToolUse hook automatically routes all tool outputs through the sandbox without changing your workflow.

3. **Understand the sandbox execution model:**
   - Each `execute` call spawns an isolated subprocess with its own process boundary
   - Scripts cannot access each other's memory or state
   - Only stdout enters the conversation context; raw data (logs, API responses, snapshots) stays in the sandbox
   - Ten language runtimes supported: JavaScript, TypeScript, Python, Shell, Ruby, Go, Rust, PHP, Perl, R
   - Bun is auto-detected for 3-5x faster JS/TS execution

4. **For knowledge base queries, use the indexed search tool:**
   - The `index` tool chunks markdown by headings while preserving code blocks
   - Content is stored in SQLite FTS5 (Full-Text Search 5) with BM25 ranking
   - Porter stemming applied at index time (e.g., "running", "runs", "ran" match the same stem)
   - The `search` tool returns exact code blocks with heading hierarchy—not summaries
   - Use `fetch_and_index` to index URLs: it fetches, converts HTML to markdown, chunks, and indexes without raw page content entering context

5. **For authenticated CLI tools, credential passthrough handles auth:**
   - Tools like `gh`, `aws`, `gcloud`, `kubectl`, `docker` work through environment variable and config path inheritance
   - Credentials never appear in conversation context
   - Subprocess inherits credentials securely

Example workflow: instead of a Playwright snapshot (56 KB) entering context raw, the sandbox executes a script that extracts only the relevant DOM elements, returning 299 B to context.

## Verification

Validate the compression ratio by monitoring context consumption before and after:

```bash
# Before Context Mode: run a typical agentic session and observe context filled at ~40% after 30 minutes
# After Context Mode: run equivalent session and verify context remaining after 45 minutes

# Test case 1: Playwright snapshot compression
# Input: 56 KB Playwright snapshot
# Expected output: ~299 B (0.5% of original)

# Test case 2: GitHub issues query
# Input: 20 GitHub issues (59 KB)
# Expected output: ~1.1 KB (1.9% of original)

# Test case 3: Access log processing
# Input: 500-request access log (45 KB)
# Expected output: ~155 B (0.3% of original)

# Test case 4: CSV analytics
# Input: 500-row CSV (85 KB)
# Expected output: ~222 B (0.3% of original)

# Aggregate session test
# Input: 315 KB of mixed real-world outputs
# Expected output: 5.4 KB (1.7% of original)
# Expected session duration: ~3 hours vs ~30 minutes without Context Mode
# Expected context remaining after 45 minutes: 99% vs 60% without optimization
```

Verify the knowledge base indexing:

```python
# Example: index markdown documentation and search for relevant sections
# After running index tool on documentation
search_result = context_mode.search("async error handling")
# Returns: exact code blocks with heading hierarchy, not summaries
# Example output: [{"heading": "Error Handling > Async Patterns", "code": "..."}]
```

## Notes

This compression pattern generalizes beyond Claude Code:

- **Any AI agentic system with tool interactions** suffers from context bloat when tools return raw data. The sandbox filtering approach applies to any LLM-agent architecture.
- **Knowledge base retrieval** in RAG systems can use the same FTS5 + BM25 + Porter stemming pattern to return precise chunks instead of approximate summaries.
- **Multi-turn conversations with external tools** (e.g., autonomous coding assistants, research agents) benefit from output filtering to extend usable session duration.
- **Credential-sensitive tools** in any LLM context require similar passthrough mechanisms to prevent secrets from entering context.
- The 98% reduction in token consumption directly extends session time by ~6x: same 200K tokens, used more carefully through filtering rather than compression.

## References

- **Source:** https://mksg.lu/blog/context-mode
- **Repository:** github.com/mksglu/claude-context-mode (MIT license)
- **Author:** Mert Köseoğlu, Senior Software Engineer
- **Related:** Cloudflare's Code Mode blog post (tool definition compression, analogous principle applied to input side)
- **HN Discussion:** 570 points on Hacker News