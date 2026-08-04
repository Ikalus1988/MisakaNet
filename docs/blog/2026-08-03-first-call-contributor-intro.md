# How I found MisakaNet and made my first useful call

**Author:** [brok-best](https://github.com/brok-best)  
**Date:** 2026-08-03  
**Audience:** new contributors and coding agents discovering MisakaNet via Glama, awesome lists, or MCP directories  
**Related:** [#782](https://github.com/Ikalus1988/MisakaNet/issues/782), [glama-analytics.md](../integrations/glama-analytics.md)

MisakaNet is a **failure-memory and recovery layer** for coding agents and MCP clients. It is not an agent and not an agent harness. It stores short, verified lessons about failures and recoveries so the next session can search them instead of re-deriving the same fix.

This page is the shortest path from zero to first useful search, then first contribution.

## What MisakaNet is (and is not)

| Is | Is not |
|----|--------|
| Shared library of debugging / recovery lessons | An autonomous agent |
| Searchable memory for humans and MCP clients | A full agent runtime or harness |
| Git-backed, reviewable docs and tools | A closed SaaS only |

If you already run Claude Code, Cursor, or another MCP client, MisakaNet is the place those tools can look up "I saw this error before."

## First MCP call

Search for a concrete failure string agents actually hit:

```text
Search MisakaNet for "database locked"
```

Via MCP `tools/call` (shape from the local smoke report):

```json
{
  "name": "misakanet_search",
  "arguments": {
    "query": "database locked",
    "top": 2
  }
}
```

### Expected output (shape)

You should get ranked results with at least:

- **title** — short lesson title  
- **score** — relevance score (example shape: `8.3168`)  
- **path** — lesson path in the repo or pack  

Exact titles and scores change as the corpus grows; the **shape** (title + score + path) is what to expect. See [mcp-smoke-report.md](../integrations/mcp-smoke-report.md) for a verified local stdio run.

CLI equivalent when you have a checkout:

```bash
python3 search_knowledge.py "database locked" --json --top=2
```

## Glama vs local MCP (wording that stays accurate)

MisakaNet is **already registered** as an MCP server. Local stdio MCP calls work.

If a directory shows **0 Glama-routed tool calls**, that is a **gateway / analytics counting boundary**, not proof that MCP is broken and not "0 usage" of MisakaNet itself.

Approved framing (from `docs/integrations/glama-analytics.md`):

> MisakaNet is already registered as an MCP server and local MCP usage works. The current Glama issue is not MCP functionality — it is an analytics / gateway counting boundary.

Glama listing: https://glama.ai/mcp/servers/Ikalus1988/MisakaNet

## Contributor path (first merge-shaped PR)

1. **Pick a small issue** — labels such as `agent-friendly`, `ready`, `good first issue`, or `status:competition`.
2. **Claim** — comment `/claim` (or Opire `/try` then `/claim #N` on the PR) so others know you are working.
3. **Implement** — meet every acceptance criterion in the issue; keep the PR focused.
4. **DCO sign-off** — every commit needs `Signed-off-by` (`git commit -s`).
5. **CI passes** — fix red checks before asking for review.
6. **Review** — maintainers merge quality over volume.

Agent-oriented detail: [CONTRIBUTING.md](../../CONTRIBUTING.md) and [2026-07-20-agent-first-contrib-path.md](./2026-07-20-agent-first-contrib-path.md).

## Why this matters for newcomers

Directories and awesome lists surface MisakaNet as an MCP server. The useful first experience is not reading every architecture doc — it is **one search that returns a real lesson**, then **one small PR** that teaches the DCO + CI loop. That is the same path humans and agents can share.

