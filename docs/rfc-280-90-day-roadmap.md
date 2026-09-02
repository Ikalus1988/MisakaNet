# RFC: MisakaNet 90-Day Roadmap Evaluation

**Author:** [zsxh1990](https://github.com/zsxh1990)
**Date:** 2026-07-29
**Issue:** [#280](https://github.com/Ikalus1988/MisakaNet/issues/280)

## Executive Summary

MisakaNet has 363 lessons, 55 scripts, an MCP server, a quality scorer, and 20+ PRs merged in the last week. The project is at an inflection point: it has proven the core concept (git-backed failure memory) and attracted real contributor activity. The next 90 days should focus on **making lessons discoverable by agents at the moment of failure** — everything else is secondary.

**Recommendation:** Double down on Vision 1 (experience reuse substrate) with targeted investments in Vision 2 (MCP gateway). Defer Vision 3 (testing platform) to Q4.

## Current State (as of 2026-07-29)

| Metric | Value |
|--------|-------|
| Total lessons | 363 (core + contrib) |
| Scripts | 55 (search, scoring, MCP, triage, etc.) |
| Open PRs | 18 |
| Merges (last 7d) | 20 |
| Contributors | 10+ active |
| MCP server | Functional (stdio transport) |
| Quality gate | 75/100 threshold, enforced in CI |
| Search | BM25 + FTS5, OKF export |

**What is working:**
- Lesson quality scoring pipeline (100-point rubric)
- Fork-and-PR contribution workflow
- Heartbeat-driven lesson harvesting (2-3 lessons per session, targeting 8)
- MCP server for Claude Code / Cursor integration

**What is not working:**
- Search recall: BM25 misses semantically relevant lessons
- Lesson discovery at the moment of failure: agents do not know to search MisakaNet
- Contributor retention: most contributors submit one PR and disappear
- No feedback loop: no data on which lessons are actually useful to agents

## Vision 1: Experience Reuse Substrate (Recommended Primary Focus)

### What it is
MisakaNet as the **git-backed, agent-readable layer** that stores and serves failure lessons. The core value proposition: when an agent hits an error, it can search MisakaNet and find "someone else hit this exact error, here is the fix."

### Why this wins
- It is what MisakaNet already does well. The infrastructure (lessons, search, quality scoring) is in place.
- It aligns with the natural workflow: agent fails → searches → finds fix → applies. No extra integration needed.
- The competition is Stack Overflow (human-written, not agent-optimized) and internal wikis (not shared). MisakaNet occupies a unique niche: **agent-first failure memory**.

### 90-day plan

**Days 1-30: Fix search recall**
- Implement hybrid search: BM25 for exact match + vector embeddings for semantic similarity
- Add lesson-to-lesson linking: when a new lesson is submitted, auto-detect related existing lessons
- Goal: search recall@10 > 80% on the existing 363 lessons

**Days 31-60: Build the feedback loop**
- Track which lessons are retrieved and whether the agent's follow-up action succeeds
- Use retrieval → success/failure as a training signal for search ranking
- Goal: 1000+ retrieval events with outcome data

**Days 61-90: Harden the contribution pipeline**
- Automate the heartbeat lesson pipeline (cron job, not manual sessions)
- Add auto-merge for lessons that pass quality gate + fact-check + no duplicate
- Goal: 8 lessons per day (up from 2-3 per session)

### Risks
- **Search quality ceiling.** BM25 alone cannot solve semantic search. Embedding-based search requires hosting a vector DB or using an external service. This adds operational complexity.
- **Fabrication in automation.** The fact-check layer rejects 25-47% of LLM-extracted lessons. Scaling to 8/day requires improving extraction quality, not just running more searches.

## Vision 2: Lightweight MCP Gateway (Recommended Secondary)

### What it is
MisakaNet as a **thin MCP server** that agents can connect to for lesson search, retrieval, and contribution. Not a heavy platform — just a tool that any MCP client can call.

### Why this matters
- MCP is the emerging standard for agent-tool integration. Claude Code, Cursor, Continue.dev, and others all support it.
- A MisakaNet MCP server means agents can search lessons **without leaving their workflow**. No web UI, no CLI switch — just a tool call.
- This is the "last mile" for Vision 1: even with perfect search, agents need a way to access it.

### 90-day plan

**Days 1-30: Stabilize the existing MCP server**
- Add resources endpoint (lesson metadata, tags, domains)
- Add proper error handling and rate limiting
- Publish to PyPI for `pip install misakanet-mcp`

**Days 31-60: Expand client support**
- VS Code extension (partial: exists as PR #627)
- Cursor rules integration (exists as PR #628)
- Continue.dev adapter

**Days 61-90: Agent-native contribution**
- Add MCP tools for submitting lessons (not just searching)
- Agent can write a lesson as a tool call, which goes through quality gate
- Goal: 10% of new lessons submitted via MCP

### Risks
- **MCP adoption is still early.** Most developers do not use MCP clients yet. Investment in MCP may not pay off for 6-12 months.
- **Server hosting.** The current MCP server runs locally (stdio transport). A remote server requires hosting, auth, and rate limiting — significant operational overhead.

## Vision 3: Agent Capability Testing Platform (Defer to Q4)

### What it is
Using MisakaNet lessons as **test cases** for agent capabilities: can the agent search, retrieve, and apply a failure lesson to fix a real bug?

### Why defer
- This is a research project, not a product. It requires building a benchmark harness, defining metrics, and running evaluations — 90 days is tight.
- MisakaNet's current value is as a knowledge base, not a testing platform. Premature pivot risks diluting the core offering.
- The testing platform is a **consumer** of lessons, not a producer. It benefits from a larger, higher-quality lesson corpus — which is Vision 1's job.

### When to revisit
- When the lesson corpus reaches 1000+ (currently 363)
- When search recall is >90% (currently unknown)
- When there are 3+ MCP clients actively using MisakaNet

### What to do now
- Track the data needed for future benchmarking: retrieval events, agent actions, success/failure outcomes
- This is free — it comes from Vision 1's feedback loop

## Vision 4: Other Directions

### Federated MisakaNet (multiple instances, shared protocol)
- Interesting long-term, but premature. The single-instance MisakaNet needs to prove product-market fit first.
- The failure-memory protocol (Shared Knowledge Protocol) architecture supports this in theory, but no one has tested it.

### Enterprise / Internal deployment
- Companies could run their own MisakaNet instance for internal failure lessons.
- This is a revenue opportunity, but requires auth, permissions, and admin features — a separate product.
- Defer until community MisakaNet is stable.

### MisakaNet as a standard
- OKF (Open Knowledge Format) for lessons, interop with other knowledge bases.
- The OKF export exists (PR #630). Adoption depends on other projects choosing to use it.
- Low effort to maintain, high potential if adopted.

## Prioritized 90-Day Roadmap

| Priority | Days | Milestone | Success Metric |
|----------|------|-----------|----------------|
| P0 | 1-30 | Hybrid search (BM25 + embeddings) | recall@10 > 80% |
| P0 | 1-30 | MCP server stabilization + PyPI | `pip install misakanet-mcp` works |
| P1 | 31-60 | Feedback loop (retrieval → outcome) | 1000+ events with outcome data |
| P1 | 31-60 | VS Code + Cursor extensions | 2+ clients in production |
| P2 | 61-90 | Automated heartbeat pipeline | 8 lessons/day, >75 quality |
| P2 | 61-90 | Agent-native lesson submission via MCP | 10% of new lessons via MCP |

## Decision

**Go with Vision 1 + Vision 2.** Defer Vision 3 to Q4. Track data for Vision 3 via Vision 1's feedback loop (zero incremental cost).

The 90-day goal: **make MisakaNet the place agents look when they fail.** Everything else follows from that.
