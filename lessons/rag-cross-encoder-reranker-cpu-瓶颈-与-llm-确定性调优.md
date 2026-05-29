---
title: RAG Cross-Encoder Reranker CPU 瓶颈与 LLM 确定性调优
domain: rag
subdomain: performance
source: bootstrap
status: published
tags: ["project:self-grow-wiki", "node:hermes_wsl", "scope:broad", "severity:high"]
confidence: 0.9
created: 2026-05-28
---

## 问题

RAG 知识库回答速度太慢（冷启动 113s，热查询 44s），且相同问题在不同场景下得到不同回答。

## 根因

### 速度瓶颈

- **Cross-encoder reranker 是唯一瓶颈**。`BAAI/bge-reranker-v2-m3`（568M 参数）在 CPU 上对 25 条候选逐对推理，每次查询耗时 25-60s。
- 其他阶段（向量检索、BM25、实体精确搜索、LLM 生成）加起来不到 2s。
- 冷启动 113s 中的 60s 花在 reranker，热查询 44s 中的 42.7s 也花在 reranker。
- 第一次查询的 40s+ "隐性开销" 实际就是 reranker，不是 ChromaDB 的问题。加 [TIMING] 日志才定位到。

### 回答不一致

- `temperature=0.3` 仍然有采样随机性。
- 未传 `seed` 参数 → LLM 每次调用随机种子不同，相同 prompt + 相同 context 输出不同。
- 群聊场景下 `share_session_in_channel=true` 导致多个用户共享同一 session，上下文污染。

## 修复

### 速度优化：直接关闭 cross-encoder reranker

```python
# rag_core.py
# 方案 A：改配置变量
_RERANK_TOP_K = 0

# 方案 B：_get_reranker() 直接返回 None
def _get_reranker():
    return None
```

**理由**：已有 RRF 融合（向量 + BM25）+ 实体精确搜索 + topic_tag_boost，排序信号已足够。Cross-encoder rerank 边际收益极低。

**效果**：热查询 44s → ~1.2s。冷启动 34s（首次加载 embedding + BM25），不影响后续。

### 回答一致性：调 LLM 参数

```python
# rag_core.py DEFAULT_TEMPERATURE
DEFAULT_TEMPERATURE = 0       # 从 0.3 改为 0，消除采样随机性

# LLM 调用 kwargs 补全
kwargs = dict(
    model=ch["model_id"],
    messages=messages,
    temperature=0,      # 确定性
    seed=42,            # 固定随机种子，可复现
    top_p=1,            # 关闭 nucleus sampling
    max_tokens=4096,
    stream=True,
)
```

### Fallback：群聊 session 隔离

```toml
# cc-connect config 或对应 bot 配置
[projects.platforms.options]
share_session_in_channel = false  # 每个用户独立 session
```

## 验证

1. 热查询速度：44s → ~1.2s（AP 调用测两次）
2. 回答一致性：相同 query 连续问两次，输出完全相同
3. 排序质量抽查：禁用 reranker 后回答未降级

## 经验

1. **先加 [TIMING] 日志再优化**。Hermes 一开始推测 40s 是 ChromaDB 开销，实际日志定位到 reranker。没有数据支持的优化是瞎猜。
2. **Cross-encoder reranker 不要放在 CPU 上用**。568M 参数的模型在 GPU 上可能百毫秒，CPU 上就是半分钟到一分钟。如果必须用，换成 `bge-reranker-v2-minicpm-layerwise`（~100M 参数）加 GPU 推理。
3. **temperature > 0 必须配合 seed 参数**。即使 temperature=0，如果不设 seed，某些 API 实现仍然可能因为随机种子不同产生微小差异。temperature=0 + seed=42 + top_p=1 三件套才能保证确定性。
4. **群聊共享 session 是回答案不一致的隐藏原因**。排查"相同 prompt 不同结果"时，不仅要看模型参数，还要看 session key 的作用域。
