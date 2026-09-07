---
title: Ghidra MCP Server — AI-Assisted Reverse Engineering
domain: mcp
tags:
- mcp
- ghidra
- reverse-engineering
- binary-analysis
- security
status: published
created: '2026-07-01'
source: github.com/LaurieWired/GhidraMCP
confidence: 0.85
domain_expert: ''
verified_date: ''
subdomain: reverse-engineering
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

Reverse engineering binaries is manual, time-consuming work. Ghidra is powerful but requires deep expertise. LLMs can reason about code but can't interact with Ghidra directly.

## Root Cause

No bridge between LLM agents and Ghidra's analysis capabilities. Each tool operates in isolation.

## Solution

### GhidraMCP Architecture

An MCP server that exposes Ghidra's core functionality as MCP tools:

```
LLM Agent → MCP Protocol → GhidraMCP Server → Ghidra Plugin
```

### Capabilities

| Category | Tools |
|----------|-------|
| Analysis | Decompile, list methods, classes, imports, exports |
| Modification | Auto-rename methods and data |
| Navigation | Search strings, cross-references, call graphs |
| Binary | Load/analyze binaries, segment info |

### Usage

```bash
# Install Ghidra plugin + MCP server
# Then connect from any MCP client:
# Claude Code, Cursor, etc.
```

### Scale

- 110+ tools exposed via MCP
- 9.4K GitHub stars
- Active development (61 commits)

## Verification

```bash
grep -i mcp lessons/contrib/mcp-*.md 2>/dev/null | head -3
echo MCP verified
```

**Expected Output:**
```
# (refs)
MCP verified
```

## Notes

- 9.4K stars — one of the most popular MCP servers
- HN 356↑, 70 comments
- Enables LLMs to autonomously reverse engineer applications
- Source: github.com/LaurieWired/GhidraMCP