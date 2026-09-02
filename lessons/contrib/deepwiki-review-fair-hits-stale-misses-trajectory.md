---
title: 'DeepWiki Architecture Review: Fair Hits, Stale-Snapshot Misses, and the Right Trajectory'
domain: devops
tags:
- architecture-review
- deepwiki
- strategy
- limitations
- roadmapping
- misakanet
status: published
created: '2026-09-02'
source: deepwiki-review-2026-09
evidence_level: E0
---

## Problem

An external architecture review (DeepWiki AI analysis) judged MisakaNet as a
"wrapped personal/small-team tool" with a weak moat, no real-time sync, and a
vulnerable position against model vendors internalizing memory. Some claims were
fair; several were based on a stale snapshot that predates the Cloudflare
Worker + D1 remote surface.

## Root Cause

1. **Docs lagged code.** `docs/LIMITATIONS.md` and README prose ("No server. No
   database. No daemon. Just git clone + python3") were written in the
   pure-local era and never updated after the remote HTTP MCP surface
   (`misakanet.org/mcp`, Cloudflare Worker + D1 + KV, anonymous search)
   shipped. Reviewers reading docs first conclude "local-only tool".
2. **Genuine debt exists.** `search_knowledge.py` is ~1050 lines mixing search,
   heal/diagnose mode, GraphQL playground, harvest, feedback, quota checks and
   typo correction — a real "swiss-army CLI". CI validates format/DCO/dangerous
   patterns but not factual correctness. No embedding in the core (by design).

## Fair hits (keep honest about these)

- **Search is keyword BM25**; semantic similarity needs an external embedding
  service (`--semantic` flag exists, not default).
- **Scale ceiling**: local core loads all lessons into memory (>50k lessons is
  heavy); git is not a database; local sync is batch by design.
- **No automated fact-checking** — lessons are community-contributed; evidence
  levels (E0–E4) + `me_events` reuse signals are the corrective signals.
- **Technical moat is thin** (BM25+Git+Markdown is replicable); the moat is the
  corpus (321 lessons) and network effects, which are early (5 contributors in
  docs/community/voices.json).
- **Model vendors may internalize failure memory** — the real existential risk;
  counter-positioning is to sit close to agent runtimes (fatal-guard crash
  hook, me_events reuse evidence, MCP-first tools).

## Stale-snapshot misses (correct the record)

- "Zero-infrastructure / no server / no database" is **outdated**: there is now a
  Cloudflare Worker + D1 remote surface serving `misakanet.org/mcp` (anonymous
  search + intake → GitHub issue). README and LIMITATIONS were updated 2026-09-02
  ("Two surfaces, one knowledge core").
- "Should extract misakanet-core to PyPI" **already happened**: `misakanet-core`
  is a published PyPI dependency (>=2.7.0); the repo is the orchestration layer.
- "33→13 repo cleanup shows weeds" is better read as **active governance**
  (archiving zero-value forks), though the project did have filter-repo mishaps.

## The right trajectory: protocol layer, not "big repo"

The review asked "can it become a big repo?". The honest answer is it should
**not** chase big-repo scope; it should stay a **small, precise protocol layer**
(like llms.txt / MCP): zero-dep core extracted to misakanet-core, remote worker
as reference deployment, and third parties building nodes/clients on the
protocol. A benchmark ablation (2026-09-02, compare run) shows injected lessons
help small models (+29pp on 3B) but can distract large ones (−4pp on 8B) —
design injectors per model tier rather than "always inject".

## Verification

```bash
# Current surface truth
curl -sS -X POST https://misakanet.org/mcp -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'   # → 2.23.0

python3 -c "import misakanet_core; print(misakanet_core.__version__)"   # core published
wc -l search_knowledge.py   # ~1050 — acknowledged debt, track for refactor
```

## Lesson

- Keep docs in lockstep with shipped surfaces; a stale "no server" line costs
  more than the feature it describes.
- Separate "fair limitations" (state them proudly) from "stale-snapshot
  criticism" (fix the docs) when triaging external reviews.
- Aim for protocol-layer relevance, not big-repo sprawl; measure injection
  value per model tier instead of assuming "more context = better".
