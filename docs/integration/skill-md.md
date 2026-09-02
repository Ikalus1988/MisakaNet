# SKILL.md — Failure-Memory Skill

## What is SKILL.md?

`SKILL.md` at the repo root teaches AI models when and how to use MisakaNet for failure recovery. It's designed for Claude Code, Cursor, and other skill-aware environments.

## How it works

When a model encounters an error, it checks `SKILL.md` to understand:

1. **When to search**: errors, exceptions, CI failures, tool failures, regressions
2. **How to search**: use `misakanet_search` with the error message
3. **When to record**: if no lesson matches, capture a redacted failure report
4. **How to give feedback**: use `misakanet_submit_usage` with outcome

## Structure

The SKILL.md contains:

- **Trigger conditions**: what types of failures activate the skill
- **Recovery flow**: the step-by-step process
- **Tool definitions**: all 4 MCP tools with usage examples
- **Examples**: real-world scenarios (DCO, import error, MCP crash)
- **Domain filters**: how to narrow searches
- **Important notes**: redaction, feedback, trust model

## For harness integration

If you're building a harness that uses MisakaNet:

1. The SKILL.md is the primary interface for model-directed recovery
2. The MCP adapter (`scripts/mcp_deepseek_adapter.py`) is the programmatic interface
3. The CLI (`scripts/mcp_server.py`) is the fallback interface

All three share the same underlying tools and data.
