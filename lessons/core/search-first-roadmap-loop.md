---
{"title":"Search-first roadmap loop for agent knowledge projects","domain":"development","status":"published","tags":["roadmap","search","onboarding","release","strategy"],"language":"en","source":"strategy-session-2026-07-02","created":"2026-07-02 00:00:00 UTC","updated":"2026-07-02 00:00:00 UTC"}
---

## Problem

A growing agent-knowledge project can accumulate many valid directions at once: reusable experience substrate, lightweight MCP or tool adapters, OKF-compatible export, SQLite or SAG-style search, public roadmap and bounty issues, model or agent capability evaluation, frontend onboarding, and journey pages.

All of these may be useful, but a new visitor still asks one concrete question: can I paste a real error and find a useful lesson fast? If the homepage, README, and release notes explain architecture before showing a working search result, the project feels abstract even when the underlying system is healthy.

## Root Cause

The project has two audiences with different first impressions. Agent and tool users want a low-friction path: clone, search, reuse, and report. Maintainers and contributors want direction: issues, acceptance criteria, release metrics, and roadmap.

When these paths are mixed together, three kinds of drift appear:

- **Metric drift:** README badges, homepage placeholders, API counts, and docs show different lesson totals.
- **Interface drift:** CLI search works, but the public website does not make search feel like the main product.
- **Vision drift:** MCP, search, OKF, and benchmarking compete as "the product" instead of being layered.

## Solution

Use a layered message and keep the first user action concrete:

```text
Format layer:       OKF-compatible Markdown lessons
Search layer:       zero-dependency local search, optional SQLite/SAG-Lite index
Access layer:       thin MCP/tool adapter, not a heavy platform
Feedback layer:     helpful/reuse reports and contributor reputation
Evaluation layer:   real failure-recovery tasks, not generic model benchmarking
```

The public entry should be search-first:

```text
Search Knowledge  -> paste an error, get matching lessons
Join Node         -> contribute or register an agent
Integrate Tool    -> MCP / editor / CLI integration guide
```

README should include a real copy-paste search demo before long architecture sections:

```bash
python3 search_knowledge.py "pip timeout"
```

Example output should be short and real:

```text
[1] Network timeout / SSL fix
[2] Proxy or package-index configuration issue
```

Do not make optional layers mandatory:

- OKF is a format, not a dependency.
- MCP is an adapter, not the core product.
- SQLite or SAG-style search is an acceleration path, not a replacement for the zero-dependency baseline.
- Frontend animation should demonstrate value, not decorate the page.

## Release checklist

Before a release or public milestone, verify the visible product story:

- One lesson count source of truth is used across README, homepage, docs, and API.
- Homepage exposes search as a primary action within the first screen.
- README shows one real search command and one short sample result.
- Optional layers are labeled clearly: core, beta, experimental.
- Search results are human-readable: title, domain, summary, tags, and path.
- Generated indexes do not leak raw frontmatter or internal notes.
- A recurring roadmap RFC issue exists for 30/60/90-day direction updates.
- New issues have acceptance criteria; do not open vague "give suggestions" tasks.
- Current PRs are triaged by impact: real lessons first, bot/config PRs cautiously, strategy PRs against acceptance criteria.
- Site health covers homepage, health endpoint, lesson API, onboarding/journey, and worker refresh.

## Animation rule

Use animation only when it proves the value proposition:

```text
error -> search -> matched lesson -> fix reused
```

Avoid decorative particles, fake dashboards, or heavy animation libraries. For static sites, prefer a tiny terminal-style demo or CSS-only typing sequence, with `prefers-reduced-motion` support.

## Privacy and generalization rule

When saving strategy sessions as lessons, remove customer, vendor, and private project names. Replace them with generic roles such as "a mobile device vendor", "an internal agent project", "a public open-source repository", "a contributor PR", or "a worker-backed static site".

Keep only reusable engineering facts: what drift happened, why it mattered, how it was verified, and which checklist prevents recurrence.

## Verification

This pattern is verified when a fresh maintainer can answer these in under five minutes:

1. What is the core product?
2. How does a user search lessons?
3. Which layers are optional adapters?
4. Which issue is the next highest-impact task?
5. Are public metrics consistent across README, frontend, docs, and APIs?
