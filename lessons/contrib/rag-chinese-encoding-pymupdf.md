---{"title": "RAG 检索中文乱码 — pymupdf4llm Default编码Issue", "domain": "rag", "source": "bootstrap", "status": "published", "confidence": "0.7", "created": "2026-04-01"}---


## Background

构建 FANUC 知识库 RAG 时，检索中文报警码出现乱码。

## 根因

`pymupdf4llm` 提取 PDF 时Default编码未指定 utf-8，含中文特殊字符的页面被截断。

## Fix

在 `extract()` 调用中显式指定 `encoding="utf-8"`：

```python
# RAG 检索中文乱码 — pymupdf4llm Default编码Issue
text = pymupdf4llm.extract(doc)

# 正确
text = pymupdf4llm.extract(doc, encoding="utf-8")
```

## 验证

重新导入含中文报警码的 PDF（如 SRVO-023），检索返回正确中文描述。

## 关键点

- BGE-small CUDA 编码，query ~0.3s
- hybrid 检索方案：向量 top20 候选 + BM25 rerank，余弦相似度+关键词命中率综合排序
