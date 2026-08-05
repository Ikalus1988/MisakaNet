---
name: "feat: Build search quality benchmark (prove MisakaNet works)"
about: Good first issue — quantifies value, drives trust
labels: ["good first issue", "enhancement", "growth", "Ring-3"]
assignees: ''
---

## Why This Matters

MisakaNet claims "one agent hits a bug, all agents skip that failure path." But there's no **proof** that search actually returns relevant lessons. A benchmark turns marketing claims into verifiable data.

## Task

Build a benchmark that measures search quality against known queries.

## Acceptance Criteria

1. Create `scripts/bench_search.py` that:
   - Defines 20 test queries (realistic agent errors, e.g., "database locked", "npm install ENOMEM", "GitHub Actions code injection", "Playwright libnss3 missing")
   - Each query has expected relevant lesson(s) (manually curated)
   - Runs `search_knowledge.py` for each query
   - Measures: Precision@1, Precision@3, MRR (Mean Reciprocal Rank)
   - Outputs a JSON report to `bench_results/search_quality.json`

2. Create `tests/test_search_bench.py` that:
   - Runs the benchmark and asserts MRR > 0.5 (search is better than random)
   - Fails if any query returns 0 results (search should always find something)

3. Add to CI as a non-blocking metric (report only, don't gate merges on it yet)

## Why This Is a Good First Issue

- No architectural decisions — it's a measurement tool
- Clear success criteria (MRR > 0.5)
- Directly proves MisakaNet's value proposition
- Results become marketing data ("our search has 0.7 MRR across 20 real-world queries")

## How to Claim

Comment `/claim`. 8-hour window.
