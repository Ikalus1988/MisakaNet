# MisakaNet 90-Day Strategic Direction

> **Date:** 2026-07-02
> **Version:** v2.8.0
> **Author:** Strategic Review
> **Status:** RFC — open for community feedback

---

## One-Sentence Positioning

**MisakaNet = Agent Failure Memory Network**
Use real failure experience to test and improve Agent recovery capabilities.

---

## Current State (Evidence-Based)

| Metric | Value | Source |
|--------|-------|--------|
| Published lessons | 200+ | `lessons/` directory |
| Core lessons | 11 | `lessons/core/` |
| Quality score avg | 0.261 | `data/quality_scores.json` |
| Stars | 123+ | GitHub |
| Forks | 39+ | GitHub |
| Merged PRs (external) | 10+ | GitHub |
| Integrations | 3 active | Continue.dev, Claude Code, Shell |
| Python version | 3.10+ | `pyproject.toml` |
| Dependencies (core) | 0 | `misakanet-core` |

### Existing Assets

1. **Experience Reuse Substrate**
   - Git-backed lessons with JSON frontmatter
   - BM25 search with RRF fusion
   - Quality scoring infrastructure
   - OKF-compatible export (`scripts/export_okf.py`)

2. **Lightweight MCP Gateway**
   - Thin MCP server (`scripts/mcp_server.py`)
   - 3 tools: search, get_lesson, submit_usage
   - Claude Code / Continue.dev integration ready

3. **SAG-Lite Search**
   - SQLite FTS5 index (`scripts/build_sag_index.py`)
   - Offline-capable, zero external dependencies
   - OKF JSONL as input format

4. **Helpful/Reuse Feedback**
   - Frontend helpful button (#276)
   - KV-based vote storage
   - Dedup via localStorage

---

## Strategic Direction Evaluation

### Direction 1: Experience Reuse Substrate (Core)

**Verdict: DOUBLE DOWN — this is the moat.**

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Impact | 9/10 | Unique value prop — no other tool does cross-agent failure sharing |
| Effort | 3/10 | Already built, just needs polish |
| Risk | 2/10 | Zero-dependency, git-native = no infra risk |
| Fit | 10/10 | Core to mission, protected baseline |

**What to do:**
- Keep `search_knowledge.py` as the zero-dependency CLI path
- Improve lesson quality (target: avg 0.6 by day 90)
- Add domain-specific cookbooks (RAG, DevOps, Security)
- Build lesson reference graph (`[[lesson-id]]` links)

**What NOT to do:**
- Don't add vector database as required dependency
- Don't abandon git-native storage for a SaaS backend
- Don't prioritize search speed over offline capability

### Direction 2: Lightweight MCP Gateway (Adapter)

**Verdict: KEEP AS ADAPTER — don't make it the core product.**

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Impact | 7/10 | Enables integration with AI tools |
| Effort | 4/10 | Already built, needs maintenance |
| Risk | 5/10 | MCP protocol may evolve, tool ecosystem fragmented |
| Fit | 7/10 | Good access layer, but not the value prop |

**What to do:**
- Maintain MCP server as thin adapter
- Add Cursor, Aider, VS Code integrations
- Keep MCP tools minimal (search, get, submit)
- Document setup for each AI tool

**What NOT to do:**
- Don't build a heavy MCP platform
- Don't add authentication/authorization to MCP
- Don't make MCP the primary interface (CLI is primary)

### Direction 3: Agent Capability Testing Platform (Niche)

**Verdict: NARROW TO FAILURE RECOVERY — don't become a generic benchmark.**

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Impact | 6/10 | Valuable for agent developers |
| Effort | 7/10 | Requires task design, evaluation harness |
| Risk | 6/10 | Generic LLM benchmark space is crowded |
| Fit | 5/10 | Tangential to core mission |

**What to do:**
- Focus on "failure recovery" tasks only
- Use real lessons as test cases
- Measure: search relevance, fix quality, contribution quality
- Integrate with bench-core for task injection

**What NOT to do:**
- Don't build a generic LLM leaderboard
- Don't compete with MMLU/HumanEval/etc.
- Don't add SaaS infrastructure for benchmarking

### Direction 4: Other Directions (Opportunistic)

| Direction | Priority | Rationale |
|-----------|----------|-----------|
| Contributor reputation | P2 | Nice-to-have, not core value |
| Helpful/reuse feedback loop | P1 | Already started (#276), complete the loop |
| Domain-specific cookbooks | P1 | High value for specific user groups |
| Field reports | P2 | Good for credibility, low effort |
| Tool integration ecosystem | P2 | Grow via integrations, not core feature |

---

## Decision Matrix

| Direction | Impact | Effort | Risk | Fit | Priority |
|-----------|--------|--------|------|-----|----------|
| Experience reuse substrate | 9 | 3 | 2 | 10 | **P0 — Core** |
| MCP gateway | 7 | 4 | 5 | 7 | **P1 — Adapter** |
| Agent testing (narrow) | 6 | 7 | 6 | 5 | **P2 — Niche** |
| Helpful feedback loop | 7 | 3 | 2 | 8 | **P1 — Complete** |
| Domain cookbooks | 8 | 5 | 3 | 9 | **P1 — Growth** |

---

## 30/60/90-Day Roadmap

### Days 1–30: Foundation Hardening

| Task | Priority | Deliverable |
|------|----------|-------------|
| Complete OKF/SAG-Lite integration | P0 | `data/okf/lessons.jsonl` + `data/sag.db` |
| Verify MCP server in production | P0 | Test with Claude Code + Continue.dev |
| Helpful feedback loop closure | P1 | `data/reactions.json` → search ranking boost |
| Merge #277 (real lesson) | P1 | One real-world lesson merged |
| Quality score gate: avg → 0.4 | P1 | CI enforcement |

### Days 31–60: Content & Growth

| Task | Priority | Deliverable |
|------|----------|-------------|
| Domain cookbooks (RAG, DevOps) | P1 | `docs/cookbooks/rag.md`, `docs/cookbooks/devops.md` |
| Lesson reference graph | P2 | CI scans `[[lesson-id]]` links |
| Cursor integration | P2 | Setup guide + MCP config |
| Blog post: "Agent Failure Memory" | P2 | V2EX + X publication |
| Quality score gate: avg → 0.5 | P1 | CI enforcement |

### Days 61–90: Ecosystem & Polish

| Task | Priority | Deliverable |
|------|----------|-------------|
| Agent failure recovery tasks (bench-core) | P2 | 10 task definitions |
| VS Code integration | P2 | Extension or MCP setup |
| Quality score gate: avg → 0.6 | P1 | CI enforcement |
| v2.9.0 release | P1 | Tag + release notes |
| Strategic review | P1 | Update this document |

---

## What to Double Down On

1. **Zero-dependency CLI path** — `search_knowledge.py` must always work offline
2. **Lesson quality** — avg score from 0.26 → 0.6 by day 90
3. **OKF format** — make it the standard for lesson interoperability
4. **Helpful feedback** — close the loop: vote → ranking → better search
5. **Domain cookbooks** — targeted value for specific user groups

## What NOT to Build Yet

1. ❌ Full vector database migration (ChromaDB stays optional)
2. ❌ Generic LLM leaderboard (focus on failure recovery only)
3. ❌ Heavy SaaS platform (git-native is the moat)
4. ❌ Authentication/authorization for MCP (keep it simple)
5. ❌ Blockchain/token incentives (GOVERNANCE.md prohibits this)
6. ❌ Mobile app (CLI + web is sufficient)
7. ❌ Real-time collaboration (git workflow is sufficient)

---

## Suggested Next 5 Issues

1. **[P1] Domain Cookbook: RAG Failure Patterns**
   - Extract RAG-related lessons into a structured cookbook
   - Add search boost for cookbook matches
   - Deliverable: `docs/cookbooks/rag.md`

2. **[P1] Helpful Feedback → Search Ranking**
   - Use `data/reactions.json` to boost highly-voted lessons
   - Add `helpful_count` to lesson metadata
   - Deliverable: Updated `search_knowledge.py` ranking formula

3. **[P2] Cursor Integration Guide**
   - MCP server setup for Cursor
   - Test with Cursor's MCP client
   - Deliverable: `docs/integrations/cursor/README.md`

4. **[P2] Lesson Reference Graph**
   - CI scans for `[[lesson-id]]` links
   - Build `data/reference_graph.json`
   - Deliverable: Related lessons section in search results

5. **[P2] Agent Failure Recovery Tasks (bench-core)**
   - Define 10 failure recovery scenarios
   - Use real lessons as expected solutions
   - Deliverable: `bench/tasks/failure_recovery/`

---

## Release Criteria for v2.9.0

- [ ] Lesson quality avg ≥ 0.5
- [ ] OKF/SAG-Lite fully integrated
- [ ] MCP server tested with 3+ AI tools
- [ ] Helpful feedback loop closed
- [ ] At least 1 domain cookbook published
- [ ] At least 1 new integration (Cursor or VS Code)
- [ ] All CI gates passing
- [ ] CHANGELOG updated

---

## Appendix: Strategic Framing

MisakaNet should NOT become "another RAG app".

**Preferred framing:**
- OKF-compatible lessons as the knowledge format
- SAG-Lite as the search layer
- MCP as the agent access layer
- Real failure recovery as the evaluation loop

**Anti-patterns to avoid:**
- ❌ "We need a vector database" → Use SAG-Lite (SQLite FTS5)
- ❌ "We need a web UI" → CLI is primary, web is optional
- ❌ "We need authentication" → Git-native = trust the repo
- ❌ "We need real-time sync" → Git pull is sufficient
- ❌ "We need to compete with Mem0/Letta" → Different game: failure memory, not preference memory

---

*This document is a living strategy. Update quarterly based on community feedback and repo metrics.*
