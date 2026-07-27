---
{"title": "Context Mode: Reducing Claude Code Context Consumption by 98%", "domain": "AI/MCP", "tags": ["MCP", "Claude Code", "context-optimization", "token-efficiency"], "language": "en", "status": "published", "source": "https://mksg.lu/blog/context-mode", "created": "2026-07-27", "confidence": "0.85"}
---

## Problem

Every MCP tool call in Claude Code dumps raw data into the 200K context window, rapidly consuming tokens. A Playwright snapshot costs 56 KB, twenty GitHub issues cost 59 KB, and one access log costs 45 KB. With 81+ tools active, 143K tokens (72%) are consumed before the first message, and after 30 minutes, 40% of the context window is gone.

## Root Cause

MCP has a fundamental tension: every tool interaction fills the context window from both sides — tool definitions on the way in, and raw output on the way out. Tool outputs (log files, API responses, snapshots) enter the conversation context directly without compression or filtering.

## Solution

Context Mode is an MCP server that sits between Claude Code and tool outputs:

1. Each `execute` call spawns an isolated subprocess with its own process boundary
2. Scripts cannot access each other's memory or state
3. The subprocess runs the code, captures stdout, and only that stdout enters the conversation context
4. The raw data — log files, API responses, snapshots — never leaves the sandbox
5. For knowledge bases, the `index` tool chunks markdown content by headings while keeping code blocks intact, then stores them in SQLite FTS5
6. Search uses BM25 ranking (a probabilistic relevance algorithm that scores documents based on term frequency, inverse document frequency, and document length normalization)
7. Porter stemming is applied at index time so terms with the same stem match
8. The `search` tool returns exact code blocks with their heading hierarchy — not summaries
9. `fetch_and_index` extends this to URLs: fetch, convert HTML to markdown, chunk, index; the raw page never enters context
10. Install via Plugin Marketplace with `/plugin marketplace add mksglu/claude-context-mode` and `/plugin install context-mode@claude-context-mode`, or MCP-only with `claude mcp add context-mode -- npx -y context-mode`
11. Restart Claude Code

## Verification

Validated across 11 real-world scenarios — test triage, TypeScript error diagnosis, git diff review, dependency audit, API response processing, CSV analytics. Compression results:

- Playwright snapshot: 56 KB → 299 B
- GitHub issues (20): 59 KB → 1.1 KB
- Access log (500 requests): 45 KB → 155 B
- Analytics CSV (500 rows): 85 KB → 222 B
- Git log (153 commits): 11.6 KB → 107 B
- Repo research (subagent): 986 KB → 62 KB (5 calls vs 37)

Over a full session: 315 KB of raw output becomes 5.4 KB. Session time before slowdown goes from ~30 minutes to ~3 hours. Context remaining after 45 minutes: 99% instead of 60%.

## Notes

Context Mode achieves 98% reduction in token consumption by processing tool outputs through an isolated sandbox before they enter the conversation context. Ten language runtimes are available: JavaScript, TypeScript, Python, Shell, Ruby, Go, Rust, PHP, Perl, R, with Bun auto-detected for 3-5x faster JS/TS execution. Authenticated CLIs (gh, aws, gcloud, kubectl, docker) work through credential passthrough. The solution doesn't change user workflows; a PreToolUse hook automatically routes tool outputs through the sandbox. Subagents learn to use `batch_execute` as their primary tool, and Bash subagents are upgraded to `general-purpose` to access MCP tools.

## References

- Source: https://mksg.lu/blog/context-mode
- GitHub: https://github.com/mksglu/claude-context-mode
- Author: Mert Köseoğlu