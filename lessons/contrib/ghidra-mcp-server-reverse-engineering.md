{"title": "Ghidra MCP Server — AI-Assisted Reverse Engineering", "domain": "mcp", "subdomain": "reverse-engineering", "tags": ["mcp", "ghidra", "reverse-engineering", "binary-analysis", "security"], "source": "github.com/LaurieWired/GhidraMCP", "status": "published", "confidence": "0.85", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


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

1. Install GhidraMCP plugin in Ghidra
2. Start MCP server
3. Ask Claude: "Analyze this binary and list the main functions"
4. Verify Claude can decompile and rename functions

## Notes

- 9.4K stars — one of the most popular MCP servers
- HN 356↑, 70 comments
- Enables LLMs to autonomously reverse engineer applications
- Source: github.com/LaurieWired/GhidraMCP
