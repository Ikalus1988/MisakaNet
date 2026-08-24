---
{
  "title": "RAG 检索六层静默退化：BM25 失败 + 截断 + 分数混合导致有效 chunk 被丢弃",
  "domain": "rag",
  "tags": ["rag", "retrieval", "bm25", "truncation", "chinese", "fanuc"],
  "status": "published",
  "evidence_level": "E2",
  "source": "closed-pr-1044",
  "created": "2026-08-18",
  "updated": "",
  "verified_date": "",
  "domain_expert": ""
}

provenance:
  source: "unknown"
  contributor: "Ikalus1988"
  merged_at: "2026-08-18"
  evidence: "post-publication"
---

## Problem

RAG 知识库包含完整的 FANUC M-900iB/330L 规格表，但 agent 回答"M-900iB/330L 不存在"。六个独立层级各自丢弃了有效 chunk — 无单一修复足够。

## Root Cause

六层静默退化：

1. **BM25 依赖失败** — BM25 索引未构建或损坏，回退到纯关键词匹配
2. **Warmup-no-retry** — 预热失败后不重试，直接返回空结果
3. **Variant tokenization** — `$contains` 分词变体导致查询不匹配
4. **Multi-layer truncation** — 多层截断（query → retrieval → context）累积丢失有效信息
5. **Score-scale mismatch** — RRF 分数与语义分数混合时尺度不一致
6. **Chinese tokenization in overlap-guard** — 中文分词在 overlap guard 中失效

## Solution

**6 步修复：**

1. **验证 BM25 索引完整性**
   ```bash
   python3 scripts/misakanet_cli.py doctor
   ```

2. **添加 warmup 重试逻辑**
   - 首次失败后等待 5s 重试
   - 重试失败后回退到 BM25-only

3. **修复 `$contains` tokenization**
   - 统一查询预处理：先分词，再匹配
   - 避免特殊字符干扰分词

4. **减少截断层数**
   - 在 retrieval 阶段就截断，避免 context 阶段重复截断
   - 设置合理 top-k（如 top=10 而非 top=50）

5. **统一分数尺度**
   - RRF 和语义分数分别归一化到 [0,1]
   - 再加权合并

6. **修复中文 overlap guard**
   - 使用 jieba 分词替代简单空格分割
   - 确保中文查询在 overlap guard 中正确匹配

## Verification

```bash
# 1. 验证检索结果包含目标规格
python3 scripts/search_knowledge.py "M-900iB/330L 速度"

# 2. 验证生产路径端到端
python3 scripts/misakanet_cli.py smoke

# 3. 验证六层修复
python3 -c "
from scripts.search_engine import search
results = search('M-900iB/330L')
assert len(results) > 0, 'No results found'
assert any('M-900iB' in r.get('title','') for r in results), 'Target not in top results'
"
```

## Key Points

- RAG 检索失败往往是多层复合问题，不是单一修复
- 生产路径验证比单元测试更重要
- 中文分词在 RAG 管道中需要特别注意
- "验证于生产接口" 规则：在最终输出层验证，不只是中间层

## Related Lessons

- fanuc-r-2000ic-retrieval-fix: keyword forced recall
- rag-alarm-code-mandatory-recall: alarm-code keyword recall
