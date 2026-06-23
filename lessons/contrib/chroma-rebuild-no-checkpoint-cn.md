---
{"title": "Chroma 建库无 Checkpoint — 进程一死全部丢失", "domain": "rag", "source": "bootstrap", "status": "published", "confidence": "0.7", "created": "2026-04-01", "domain_expert": "bootstrap", "verified_date": "2026-04-01"}
---


## Background

Agent 内跑 BGE-large-zh 建库（约30分钟），Gateway 重启后整个Database为空，0条向量入库。

## 根因

旧脚本设计把所有 34,100 条 embedding 算完后才写 Chroma，进程一死 = 从零开始，没有 checkpoint 能力。

```
load chunks → embed ALL 34100 (内存) → write ALL to Chroma
                                    ↑ 这一步还没到就崩了
```

## Fix

改造 `build_edoc_chroma.py` 为小批次写入：

```python
# Chroma 建库无 Checkpoint — 进程一死全部丢失
def embed_and_build(chunks, model, collection, batch_size=5000):
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        embeddings = model.encode([c["text"] for c in batch])
        collection.add(
            ids=[c["id"] for c in batch],
            embeddings=embeddings.tolist(),
            documents=[c["text"] for c in batch]
        )
        print(f"[Checkpoint] Written {i+batch_size}/{len(chunks)}")
```

**Start方式改为后台独立Run**（不在 agent 里跑）：

```bash
cd ~//hf-mirror.com \
~/.hermes/hermes-agent/.venv/bin/python3 ~/.hermes/scripts/build_edoc_chroma.py \
2>&1 | tee /mnt/d/Eric/知识库/chroma_db_v3/build.log &
```

## 验证

```bash
# Check入库数量
python3 -c "import chromadb; c=chromadb.PersistentClient('/path/to/chroma_db'); print(c.get_collection('edoc').count())"
```

## 关键点

- 建库 ~30 分钟的任务必须在独立终端跑，绝不能在飞书 agent 子进程里跑
- stdout 有缓冲，`tee` 才能写到File留下完整记录
