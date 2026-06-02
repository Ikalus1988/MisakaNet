### 📌 Context

PR #113 merged the async streaming, RRF multi-query, and SQLite caching upgrade. However, the current implementation still uses a numeric tiebreaker (`score + 0.001 * best_score`) in the RRF ranking, and the async test mocks `to_thread` instead of proving true concurrent execution.

### 🛠️ ACCEPTANCE CRITERIA

1. **CODE LOCATION**: `misakanet/tools/langchain_tool.py` and `tests/test_langchain_tool.py`

2. **RRF TIEBREAKER REFACTOR**: Replace the numeric `score + 0.001 * best_score` hack with a clean multi-level tuple sort key: **`(-rrf_score, best_rank, filename)`**.

3. **TRUE ASYNC CONCURRENCY TEST**: Replace the mocked `test_arun` with a real concurrent test using **`asyncio.gather` + `time.perf_counter`** that runs two slow queries (0.2s each) and asserts total elapsed time < 0.35s to prove non-blocking execution.

4. **COMPATIBILITY**: All 11 existing tests (8 original + 3 new) must pass. Run `pytest tests/` to confirm.
