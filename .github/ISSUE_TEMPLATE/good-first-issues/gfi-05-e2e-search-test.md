---
name: "test: Add end-to-end test for search_knowledge.py"
about: Good first issue — testing task with clear scope
labels: ["good first issue", "tests", "Ring-3"]
assignees: ''
---

## Task

Write an end-to-end test that exercises `search_knowledge.py main()` with actual lesson files and verifies results.

## Context

Currently there are 16 test files, but **none** test the main search pipeline end-to-end. The `test_search_edge_cases.py` tests tokenizer and BM25 scoring in isolation, but there's no test that:
1. Loads actual lesson files from `lessons/`
2. Runs a search query through `main()`
3. Verifies the results are correct and properly ranked

## Acceptance Criteria

1. Create `tests/test_search_e2e.py` with these test cases:
   - `test_basic_search_returns_results`: Search for a known term (e.g., "database lock") and verify at least 1 result
   - `test_search_ranking_order`: Search for a term with multiple matches and verify core lessons rank higher than contrib
   - `test_domain_filter`: Use `--domain devops` and verify all results have domain "devops"
   - `test_no_results_fallback`: Search for gibberish and verify graceful "no results" output
   - `test_titles_mode`: Use `--titles` and verify output format

2. Each test should use the actual `lessons/` directory (not mocks)

3. Tests should pass with `python -m pytest tests/test_search_e2e.py -v`

## Skills Required

- Python 3.10+
- pytest
- Understanding of `search_knowledge.py` API

## Reference

Look at `tests/test_search_edge_cases.py` for existing patterns. The key is to test through `main()` or the engine's `search()` method with real lesson files.

## Estimated Time

3-5 hours

## How to Claim

Comment `/claim` on this issue. You have 8 hours to open a WIP PR.
