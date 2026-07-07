---
title: MCP Context Mode — 98% Context Window Reduction for Claude Code
domain: mcp
subdomain: optimization
tags:
- mcp
- claude-code
- context-window
- optimization
- token-efficiency
source: mksg.lu/blog/context-mode
status: published
confidence: '0.9'
created: '2026-07-01'
verified_date: ''
domain_expert: ''
---


## Problem

Every MCP tool call in Claude Code dumps raw data into the 200K context window. A Playwright snapshot costs 56 KB. Twenty GitHub issues cost 59 KB. One access log — 45 KB. After 30 minutes, 40% of context is consumed by tool outputs alone.

With 81+ tools active, 143K tokens (72%) are consumed by tool definitions before the first message.

## Root Cause

MCP's design has a tension: every tool interaction fills the context window from both sides — definitions on the way in, raw output on the way out. Tool outputs are unoptimized, returning full data when summaries would suffice.

## Solution

### Context Mode Architecture

An MCP server that sits between Claude Code and tool outputs, compressing responses:

```
Claude Code → MCP Context Mode → Actual MCP Server
              ↓
         315 KB → 5.4 KB (98% reduction)
```

### Compression Strategies

| Strategy | Example |
|----------|---------|
| **Summarize** | Full page snapshot → key elements only |
| **Filter** | 20 GitHub issues → only titles + labels |
| **Truncate** | 45 KB log → error lines only |
| **Structure** | Raw HTML → semantic JSON |

### Results

| Tool | Raw Output | After Context Mode | Reduction |
|------|-----------|-------------------|-----------|
| Playwright snapshot | 56 KB | ~1 KB | 98% |
| gh issue list (20) | 59 KB | ~1 KB | 98% |
| Access log | 45 KB | ~0.5 KB | 99% |

## Verification

1. Run `gh issue list` without Context Mode — note token usage
2. Enable Context Mode MCP server
3. Run same command — token usage should drop by ~98%
4. Verify Claude still understands the output

## Notes

- Cloudflare showed tool definitions can be compressed 99.9% with Code Mode
- Context Mode addresses the other direction: tool output compression
- HN 570↑, 107 comments — high community interest
- Source: https://mksg.lu/blog/context-mode (2026-02-26)
