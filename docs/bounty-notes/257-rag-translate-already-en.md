# Issue #257 — RAG batch already English

**Date:** 2026-07-21  
**Reporter:** uncledad96-glitch

## Finding

All 10 paths listed in #257 already have **English titles and English bodies**, with frontmatter `language: "en"` (or equivalent) on most files:

1. `lessons/contrib/rag-alarm-code-mandatory-recall.md` — EN
2. `lessons/contrib/rag-brand-filter-three-pitfalls.md` — EN
3. `lessons/contrib/rag-build-strategy-batch.md` — EN
4. `lessons/contrib/rag-chinese-encoding-pymupdf.md` — EN
5. `lessons/contrib/rag-chunk-params-800-100.md` — EN
6. `lessons/contrib/rag-cross-encoder-cpu-bottleneck.md` — EN
7. `lessons/contrib/rag-kb-quality-flywheel-self-loop.md` — EN
8. `lessons/contrib/rag-three-channel-llm-disaster-recovery.md` — EN
9. `lessons/contrib/bge-embedding-fallback-crash.md` — EN
10. `lessons/contrib/kb-4sigma-quality-audit-pipeline.md` — EN

Sample verification (CJK count vs ASCII): each file is overwhelmingly Latin script; problem/solution sections are full English prose (not machine-garbled CN leftovers).

## Recommendation

- Close #257 as **already satisfied** (or retarget to a true CN-only RAG list if telemetry still shows CN-only paths).
- No duplicate EN copies under `lessons/en/` to avoid near-duplicate inflation.

## Method

```bash
for f in rag-alarm-code-mandatory-recall ...; do
  find lessons -name "$f.md"
  # inspect frontmatter language + body
done
```
