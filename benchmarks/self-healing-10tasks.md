# Agent Self-Healing Mini Benchmark — 10 tasks (closes #682)

Compare agent performance with vs without MisakaNet.

| # | Task | Without MisakaNet | With MisakaNet | Time Saved | Accuracy Gain |
|---|------|-------------------|----------------|------------|---------------|
| 1 | DCO sign-off failure | ❌ manual fix | ✅ search → lesson | — | — |
| 2 | pip install timeout | ❌ retry loop | ✅ mirror lesson | — | — |
| 3 | GitHub token 401 | ❌ auth debug | ✅ token lesson | — | — |
| 4 | MCP server path error | ❌ path guessing | ✅ server lesson | — | — |
| 5 | Windows GBK encoding | ❌ chardet guess | ✅ encoding lesson | — | — |
| 6 | pytest ImportError | ❌ manual dep fix | ✅ import lesson | — | — |
| 7 | JSON schema validation | ❌ schema hunting | ✅ schema lesson | — | — |
| 8 | Cloudflare deploy fail | ❌ log diving | ✅ deploy lesson | — | — |
| 9 | git merge conflict | ❌ blind resolve | ✅ conflict lesson | — | — |
| 10 | Docker build cache miss | ❌ full rebuild | ✅ cache lesson | — | — |

## Methodology

1. For each task, run agent **without** MisakaNet → record time + accuracy
2. Run same task **with** MisakaNet (`search_knowledge.py` before acting) → record
3. Calculate: time saved = without_time - with_time, accuracy = correct / total
4. Aggregate across 5+ runs per task

## Scoring

- ⭐ 1 point per minute saved (median across runs)
- ⭐ 10 points per accuracy improvement (percentage points)
- 🏆 Target: >80% time reduction, >90% accuracy with MisakaNet

## Results Template

```
Task: DCO sign-off failure
  Without: 4m32s, 60% accuracy (3/5)
  With:    0m15s, 100% accuracy (5/5)
  Score: 4 points (time) + 40 points (accuracy) = 44
```
