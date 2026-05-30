---
{"title": "RAG 品牌过滤三坑：条件触发、文件正则、BM25 缓存", "domain": "rag", "tags": ["rag", "brand-filter", "architecture", "chromadb", "bm25", "pitfall"], "confidence": 0.88, "created": "2026-05-29"}
---

## 背景

一个 FANUC 机器人 RAG 知识库在做质量巡检时发现品牌过滤策略存在三层设计缺陷，导致竞品文档持续混入检索结果。

## 三个坑

### 坑一：条件触发的品牌过滤

**现象：** 品牌过滤仅当查询中包含目标品牌关键词（如 "FANUC"）时触发。

**为什么是个坑：**
- 日常巡检题目通常不写品牌名，如「焊枪工具和抓手工具在 TCP 设定方法上有什么区别？」
- 前端用户提问也很少主动加品牌关键词
- 结果是巡检全部绕过过滤，竞品文档畅通无阻

**正确做法：**
- 品牌过滤应始终启用（always-on），非目标品牌文档在检索层直接排除
- 如果全部结果被排除，作为应急保留 top-k 高分结果（但给 LLM 标注来源警告）

### 坑二：文件名正则替代元数据

**现象：** 品牌过滤使用正则匹配文件名，而不是元数据字段。

```python
# 坑：文件名正则——脆弱、遗漏、漏检
_fanuc_pat = re.compile(r'(?i)fanuc|B-\d{5}|R-30i[AB]|M-\d{3}|A-\d{5}')
filtered = [c for c in chunks if _fanuc_pat.search(c["filename"])]
```

**为什么是个坑：**
- 文件名不合品牌命名规范的文档被遗漏（如 kap05_1_*.pdf 实际是 KUKA 文档）
- 每次查询都要做正则搜索，浪费 CPU
- 添加新品牌/新模式需要改代码
- 文件名和文档实际内容可能不一致

**正确做法：**
- 在入库时通过元数据字段标记品牌（`brand: "fanuc" | "kuka" | "abb" | "unknown"`）
- 过滤时直接读元数据字段，O(1) 判断，无需正则
- 品牌检测逻辑集中在一次全量扫描，不分散到每次查询

### 坑三：BM25 缓存与元数据不一致

**现象：** ChromaDB 元数据已更新，但检索仍返回旧数据。

**为什么是个坑：**
- RAG 系统使用 BM25 索引加速关键词检索
- BM25 索引从 ChromaDB 构建时会复制一份 metadata 到内存（通过 pickle 持久化到 `bm25_index.pkl`）
- ChromaDB `update()` 更新元数据后，BM25 缓存中的 metadata 仍是旧的
- 导致 `_build_chunk_v2()` 中的 `meta.get("brand", "unknown")` 永远返回 `"unknown"`

```python
# BM25 search 返回的 meta 来自缓存，不是实时 ChromaDB
def search(self, query, n_results, where_filter=None):
    tokens = list(jieba.cut(query))
    scores = self.bm25.get_scores(tokens)
    # scores[i] 对应 self.metas[i] —— 缓存中的旧数据！
    return [(self.docs[i], self.metas[i], scores[i]) for i in top_indices]
```

**正确做法：**
- 修改 ChromaDB 元数据后必须删除 BM25 缓存文件并重建索引
- 或在 `_build_chunk_v2()` 中添加兜底：如果 meta 没有 brand 字段，从 ChromaDB 实时查询
- 缓存文件通常较大（500MB+），重建需 2-5 分钟

## 总结

| 坑 | 现象 | 修复 |
|---|---|---|
| 条件触发 | 查询无品牌名时过滤跳过 | always-on 始终过滤 |
| 文件名正则 | 命名不规范的文档漏检 | 入库时元数据打标 |
| BM25 缓存 | 更新元数据后缓存未刷新 | 显式删除缓存并重建 |

这三个问题同时存在时，品牌过滤基本上是形同虚设，无论 ChromaDB 中标记得多准确。
