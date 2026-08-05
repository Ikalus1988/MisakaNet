---
name: "feat: Add 'explain' mode to search results"
about: Good first issue — small feature with clear scope
labels: ["good first issue", "enhancement", "Ring-3"]
assignees: ''
---

## Task

Enhance the search engine to show "why this lesson was recommended" explanations alongside results.

## Context

When a user searches for an error, they get a list of lessons with scores. But they don't know *why* each lesson was recommended. Adding an `--explain` flag that shows the matching factors (domain match, title match, BM25 score, boost factors) would improve trust and usability.

## Current State

The `--explain` flag already exists in `search_knowledge.py` (line ~280) but the implementation is minimal — it only shows the raw score. We need a proper explanation.

## Acceptance Criteria

1. When `--explain` is passed, each search result shows:
   - BM25 base score
   - Metadata bonus breakdown (domain match, title match, status weight)
   - Boost factors applied (core/verified/recent/draft)
   - Final weighted score formula

2. Output format example:
   ```
   [1] GitHub Actions Code Injection (score: 0.87)
       BM25: 0.52 | domain(security): +0.30 | title(exact): +0.50 | boost(core): +0.15
   ```

3. Add a test in `tests/test_search_edge_cases.py` that verifies explain output

## Skills Required

- Python 3.10+
- Understanding of the scoring formula in `misakanet/search/engine.py` lines 130-180

## Estimated Time

3-5 hours

## How to Claim

Comment `/claim` on this issue. You have 8 hours to open a WIP PR.
