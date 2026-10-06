---
domain: "rag"
title: "FANUC RAG Knowledge-Base Build SOP: Anti-BSOD / Anti-Full-Loss"
status: "draft"
verification: "metadata-normalized"
confidence: "0.95"
created: "2026-08-16"
updated: "2026-08-16"
verified_date: "2026-08-16"
domain_expert: ""
tags: ["rag", "kb-build", "chromadb", "memory", "bsod", "checkpoint", "batch", "sop"]
source: >-
  2026-08-16 FANUC Manual 13.0 CM rebuild incident (BSOD) + 2026-04 lessons (rag-build-strategy-batch, chroma-rebuild-no-checkpoint-cn)
---

# FANUC RAG Knowledge-Base Build SOP: Anti-BSOD / Anti-Full-Loss

## Problem

2026-08-16: after receiving approval to rebuild the KB with the new FANUC Manual 13.0 CM (218 PDFs, 2.6GB), the build was started directly — without first reading the existing MisakaNet build lessons. Result: WSL memory/driver overload → **BSOD / system restart**. Same failure modes were already documented in 2026-04: `rag-build-strategy-batch` (all data loaded into VRAM/WSL memory at once → driver crash → BSOD) and `chroma-rebuild-no-checkpoint-cn` (all 34,100 embeddings computed before writing → process death = total data loss).

Root cause of the incident: (1) build lessons not consulted before starting; (2) full dataset processed at once without memory budget; (3) no checkpointing.

## Root Cause

1. **Lesson lookup skipped.** Knowledge-base builds are exactly the long-running, crash-prone tasks MisakaNet lessons exist for. Starting a 30min+ build without grepping lessons (`build/chroma/ingest/rebuild/batch/memory`) turns past incidents into future repeats.
2. **Whole-dataset loading.** Extract + embed + write all at once blows past WSL memory and CUDA limits; driver crash → BSOD.
3. **No checkpoint.** If the process dies, everything embedded but not yet written is lost.

## Solution (SOP — follow in order)

### Step 1 — Consult lessons first (mandatory)

Before any KB build / re-ingest / full Phase-1 rerun, grep MisakaNet lessons for `build|chroma|ingest|rebuild|batch|memory`, read every hit, and copy its rules into the execution plan (todo list). This step is the first todo item, not optional.

### Step 2 — Small-sample validation

Run the pipeline on 5–10 PDFs first (dry-run / mini batch). Measure peak memory:

```bash
/usr/bin/time -v python3 scripts/import/import_batch.py /tmp/sample_pdfs --dry-run 2>&1 | grep -E "Maximum resident|Elapsed"
```

### Step 3 — Memory budget before scaling

Estimate: `dataset_size × peak_factor + existing_collection + embedding_model(vram)`. WSL on this box: ~23Gi RAM, C: only ~19Gi free, D: ~247Gi free. If the estimate exceeds limits, lower concurrency or split into stages — do not scale up blind.

### Step 4 — Small batches + checkpoint

Embed a batch, write a batch (≤5000/batch), print progress per batch. Never embed everything then write once:

```python
for i in range(0, len(chunks), 5000):
    batch = chunks[i:i+5000]
    embeddings = model.encode([c["text"] for c in batch])
    collection.add(ids=[c["id"] for c in batch],
                   embeddings=embeddings.tolist(),
                   documents=[c["text"] for c in batch])
    print(f"[Checkpoint] written {i+len(batch)}/{len(chunks)}", flush=True)
```

### Step 5 — Run in background, never in an interactive session

```bash
nohup python3 scripts/import/import_batch.py /mnt/d/Downloads/extracted_fanuc13 2>&1 | tee /tmp/kb_build.log &
```

Keep the log with `tee` (stdout is buffered otherwise). Poll the log; do not occupy the foreground session.

### Step 6 — Post-restart / post-build health check

After any crash/reboot, verify before continuing: ChromaDB count matches expectation, spot-check a critical chunk (e.g. `M-900iB/330L`), BM25 cache exists, both repos' git status clean. (2026-08-16 data survived at 198,116 chunks — luck, not design.)

## Verification

```bash
python3 -c "import chromadb; c=chromadb.PersistentClient('/home/eric_jia/rag_chromadb'); print(c.get_collection('wiki_docs').count())"
# retrieval smoke test
python3 -m pytest tests/test_retrieval_regression.py -q
# peak memory recorded in build log < WSL limit
```

## Notes

- **"Not consulted" is the primary failure.** The lessons existed and matched the task exactly; skipping the lookup was the root cause, not the memory limit itself.
- Related lessons: `rag-build-strategy-batch` (BSOD), `chroma-rebuild-no-checkpoint-cn` (checkpoint + background), `wsl-ntfs-sqlite-update-100x-slower` (SQLite on NTFS).
- Any long-running production task (build, rerun, ingest) gets Steps 1 and 5 as non-negotiable.
