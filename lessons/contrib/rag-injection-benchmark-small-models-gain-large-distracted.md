---
title: 'RAG Memory Injection Benchmark: Small Models Gain, Large Models Can Be Distracted'
domain: rag
tags:
- rag
- benchmark
- workers-ai
- context-injection
- failure-memory
- llm
- mcp
- hooks
status: published
created: '2026-09-02'
source: benchmark-compare-2026-09-02
evidence_level: E0
---

## Problem

MisakaNet exposes verified failure-memory lessons via MCP (`misakanet_search`). The open question: does **injecting** a matching lesson into an LLM's context actually improve its fix quality — and for which model sizes? A naive "always inject" approach may help small models but backfire on large ones.

## Root Cause

Two compounding factors surfaced in a `--compare` ablation (plain vs with_lesson) over 4 scenarios × 2 models:

1. **Reference-command extraction bug in the benchmark** (`scripts/benchmark_workers_ai.py`): ASCII flow diagrams inside lessons (e.g. `PR opened → Shadow Branch → DCO check`) were treated as "reference commands". Feeding that prose as the expected answer skewed scores — the 8B model went 100% (plain, it answered correctly) → 50% (with_lesson, it echoed the injected prose instead of the real fix).
2. **Model-size asymmetry**: even after fixing extraction, small models benefit strongly from injected context (they lack world knowledge to recover the fix), while large models can be *distracted* by an injected "reference answer" that conflicts with their own (better) reasoning.

## Fix

1. **Fix extraction**: only bash/sh/shell/zsh fenced blocks and `run:` lines in yaml blocks count as commands; skip multi-line backtick spans containing `->`/`→`; drop prose lines via a `_looks_like_command` heuristic. Fix/Solution sections must include `###` subsections (they hold the real commands).
2. **Measure, don't assume**: run `python3 scripts/benchmark_workers_ai.py --compare` to quantify the injection effect instead of trusting intuition.
3. **Design the injector by model tier**:
   - Small/light models (3B, local): **inject matching lessons aggressively** — big gain.
   - Large models (8B+): inject as **low-priority reference** (or only when the model signals it's stuck), matching Claude-Code-style `PreToolUse` hooks that gate on actual failure, not every turn.

## Verification

```bash
# Fresh run (delete stale output first to avoid resume-cache from empty runs)
python3 scripts/benchmark_workers_ai.py --compare --output docs/benchmarks/benchmark-2026-09-02-compare.json
```

Result (2026-09-02): avg lesson_hit_rate **46% → 58% (+12pp)** with injection;
3B model **+29pp**, 8B model **−4pp**. Answers also got more focused
(1125 → 1014 chars). Scenario detail: "GitHub Actions Script Injection"
benefited most (+33 to +50pp); "Auto-Merge CI" hurt the 8B model (−50pp)
when a prose "reference" was injected.

## Lesson

- **RAG memory injection is a tiered lever**: verify with an ablation per model size before defaulting to "always inject".
- A benchmark returning `len=0 hit=0%` for every run usually means the model call is failing (OAuth/network), not that lessons are bad — check the model call first (see mcporter-cloudflare-oauth-endpoint-scope-wsl-callback).
- Reference-answer extraction must not treat ASCII flow diagrams as commands; otherwise "with lesson" scores are meaningless.
