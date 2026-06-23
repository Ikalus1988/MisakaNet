---
domain: "archive"
title: "Edoc Rag"
verification: "metadata-normalized"
source: "skill-pipeline"
status: "draft"
created: "2026-05-09"
---

## 背景

（此 lesson 从 skill `edoc-rag` 自动提取，待补全）

## 根因

（待补充）

## 修复


# FANUC Robot Knowledge Base RAG

## Phase 0: 知识检索（硬性门禁）

> RAG 查询是高频操作，查询结果直接影响答案质量。开始查询前，先确认 lessons/ 中是否有已知检索问题或已修复的故障。

### Step 0.1: 搜索 lessons

```bash
cd ~/Agent-Medici
python3 search_knowledge.py "rag\|FANUC\|检索\|chromadb\|BM25" --lessons
```

**Output gate：** 输出匹配 lessons 数量 + top-3 文件的实际摘要。如果返回空则输出 `"search_knowledge.py 空结果"`。

### Step 0.2: 输出检索结论

```
📋 检索结论
  - 可复用的 lessons: [标题列表]
  - 已知检索问题与本查询的关联: [具体说明]
  - 核心风险（不检索可能踩的坑）: [一句话]
```

**Output gate：** 必须输出此结论块。不输出 = 不允许进入查询阶段。

## 快速调用

```bash
# 有参数：单次查询（供 gateway subprocess 调用）
~/.hermes/hermes-agent/.venv/bin/python3 ~/.hermes/scripts/rag_answer.py "SRVO-001 急停报警"
# 输出：格式化字符串，含来源、耗时、答案（供飞书展示）

# JSON 模式（gateway 用 --json，精准拿结构化数据）
~/.hermes/hermes-agent/.venv/bin/python3 ~/.hermes/scripts/rag_answer.py --json "SRVO-001 急停报警"
# 输出：单行 JSON {"query","answer","sources":[{"rank","source","page","chars","bm25","kw_hit"}],"elapsed","error"}

# 无参数：5-query 交互测试循环
python3 ~/.hermes/scripts/rag_answer.py
```

## BM25 后台构建（2026-04-20 更新）

- `warmup()` 先加载 BGE-m3 → 立即标记 `ready=True`，向量检索 ~5s 可用
- BM25 在独立 daemon 线程构建，不阻塞首次查询
- `hybrid_search()` 首次触发时最多等待 30s（timeout 兜底）
- 缓存路径：`~/.hermes/scripts/bm25_index.pkl`

## Tag Filter 覆盖情况

- **数据源**：`~/.hermes/scripts/tag_results.jsonl`（127 条，2026-04-15）
- **已知问题**：67/127 PDF 的 `robot_model: Unknown`，tag 过滤对这些查询失效
- **当前行为**：无匹配关键词时返回 `[]`（不过滤），不影响检索结果

## 使用场景

| 向量库 | 路径 | Chunks | 模型 | 状态 |
|--------|------|--------|------|------|
| **edoc_v10_m3** | `/mnt/d/Eric/知识库/chroma_db_v4` | 34,100 | BGE-m3 1024维 | ✅ 生产主力 |
| edoc_v10_zh | `/mnt/d/Eric/知识库/chroma_db_v3` | 14,889 | BGE-large-zh 1024维 | 备用 |

- **检索脚本**：`~/.hermes/scripts/rag_answer.py`
- **BM25 索引**：`~/.hermes/scripts/bm25_index.pkl`（首次查询自动重建，coll.count=34100≠cache.N时触发）
- **Query Embedding 缓存**：`~/.hermes/scripts/q_embeddings.npz`

## 关键路径（2026-04-16 确认）

| 资源 | 路径 |
|------|------|
| 向量库 | `/mnt/d/Eric/知识库/chroma_db_v4`（NOT `~/.hermes/chroma_db_v4`） |
| Collection 名 | `edoc_v10_m3`（34,100 chunks） |
| BM25 索引 | `~/.hermes/scripts/bm25_index.pkl`（34100 docs） |
| BGE-m3 模型 | `~/.hermes/models/bge-m3` |

## 关键参数

- `coll.query(..., n_results=20)` — 向量 Top-20 候选
- BM25 rerank：取 top-20 向量候选后用关键词命中重排
- **合并策略**：每个 source 保留 min dist chunk，最终按 final_score 排序
- **Metadata 过滤**：通过 `_get_tag_filter` 从 `tag_results.jsonl` 实现

## ⚠️ 常见故障：hybrid_search 返回空

**症状**：所有查询返回"无法完成检索"或空列表。

**根因 1：Python .pyc 缓存**（最常见）
```bash
# 每次修改 rag_answer.py 后必须清理
rm -f ~/.hermes/scripts/__pycache__/rag_answer.cpython-*.pyc
```

**根因 2：CHROMA_PATH 错误**
```python
# ❌ 错误（hermes venv 中路径不存在）
CHROMA_PATH = os.path.expanduser("~/chroma_db_v4")

# ✅ 正确
CHROMA_PATH = "/mnt/d/Eric/知识库/chroma_db_v4"
```

**根因 3：Collection 名写错**
```python
# ❌ 旧版 edoc_v10（7015 docs）
coll = client.get_collection()

# ✅ edoc_v10_m3（34100 docs）
coll = client.get_collection("edoc_v10_m3")
```

**根因 4：hybrid_search 缩进断裂**
- `_get_tag_filter` 必须嵌套在 `hybrid_search` 函数内部（8 空格缩进）
- `hybrid_search` 函数体（4 空格缩进）包含关键词提取 → 向量检索 → RRF 合并
- 验证：`python3 -c "im

## 验证

（待补充）
