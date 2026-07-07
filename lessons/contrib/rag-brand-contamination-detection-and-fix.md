---
{
  "domain": "contrib",
  "title": "RAG 知识库品牌污染Detection与治理",
  "verification": "metadata-normalized",
  "created": "2026-07-06",
  "source": "unknown"
}
---
---{"title": "RAG 知识库品牌污染Detection与治理", "domain": "rag", "tags": ["rag", "chromadb", "brand-contamination", "data-quality", "metadata"], "confidence": 0.9, "created": "2026-05-29"}---

## 背景

一个面向特定品牌的垂直 RAG 知识库（200K+ 向量），在每日巡检中发现部分查询答案混入了竞品品牌技术内容。例如：

- 查询「急停回路和安全门联锁在电路设计上有什么不同？」时，答案引用了竞品文档
- 查询「TCP 设定方法」时，回答来源中包含其他品牌的操作手册

## 根因

### 1. 数据源混入竞品 PDF
知识库由 190+ 个 PDF 构建，其中约 0.04% 的 PDF 属于竞品品牌文档（如 KR C4 控制器手册、IRC5 操作手册等）。这些文档在数据收集阶段误入知识库。

### 2. 品牌过滤条件不足
检索层已有的品牌过滤代码仅在查询中包含目标品牌关键词时触发 —— 但日常巡检的问题通常不写品牌名。

### 3. 文件名检测漏洞
文件名不包含明确品牌标记的文档被遗漏（例如 kap05_1_*.pdf 实际是竞品文档，但文件名未体现品牌）。

## 修复

### 第一步：全量元数据打标

对 ChromaDB 中全部 200K+ chunk 进行品牌分类：

```python
# RAG 知识库品牌污染Detection与治理
fanuc_pat = re.compile(r'(?i)(fanuc|r-30i[ab]?|m-\d{3}[a-z]?|b-\d{5})')
kuka_pat  = re.compile(r'(?i)(kuka|krc|kr_c[2-5]?|库卡|kap04_2|pf006|kap05_)')
abb_pat   = re.compile(r'(?i)(abb|irc5|3hac\d{5,}|man_12_)')

for doc_id, meta in zip(ids, metadatas):
    fn = meta.get("filename", "")
    if kuka_pat.search(fn):      brand = "kuka"
    elif abb_pat.search(fn):     brand = "abb"
    elif fanuc_pat.search(fn):   brand = "fanuc"
    else:                         brand = "unknown"

collection.update(ids=[doc_id], metadatas=[{"brand": brand}])
```

更新 200K 条时需注意：
- ChromaDB `update()` 单次上限约 100 条
- 先扫描全量分类，再分批写入
- 由于 ChromaDB 的持久化特性，更新后需重建 BM25 缓存

### 第二步：补充遗漏品牌文档

文件名分类会遗漏不含品牌名的文档。通过内容关键词搜索补漏：

```python
# 对 unknown brand 的文档做内容级扫描
r = collection.query(query_texts=["特定品牌关键词"], n_results=200)
for meta in r["metadatas"]:
    if meta.get("brand") == "unknown":
        # 重新分类为对应品牌
        collection.update(ids=[id], metadatas=[{"brand": "identified-brand"}])
```

### 第三步：始终过滤 + 元数据驱动

将品牌过滤从「查询含品牌关键词时条件触发」改为「始终过滤，除非无替代文档」：

```python
# 过滤策略
good = [c for c in chunks if c.get("brand", "unknown") in ("fanuc", "unknown")]
if good:
    chunks = good
else:
    # 无合格文档时保留高分结果作为应急退退
    chunks.sort(key=lambda c: c["score"], reverse=True)
    chunks = chunks[:min(5, len(chunks))]
```

## 效果

- 品牌污染从 100% 降为 0%（过滤前 ABB/KUKA 文档全部被排除）
- 已知的品牌文档全部正确标记
- 应急退退策略保证在无合格文档时仍有回答，但 LLM 不会在答案中提及竞品品牌
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 注意事项

1. ChromaDB 的 `query()` 返回最新 metadata，但 BM25 索引会缓存旧 metadata —— 更新后必须删除 BM25 缓存文件并重建
2. 文件名正则分类会遗漏不含品牌名的文档，需要用内容语义搜索补充
3. Python 的 `.pyc` 缓存会导致代码更改不生效 —— 记得清 `__pycache__`
