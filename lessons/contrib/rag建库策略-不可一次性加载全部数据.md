---
{"title": "RAG 建库策略：不可一次性加载全部数据到显存/内存", "domain": "rag", "source": "hanged-man", "status": "published", "tags": [], "created": "2026-04-13", "updated": "2026-04-13", "confidence": 0.85, "scope": "broad"}
---


## 问题

建库（chunks_v3, 34,100 docs）时一次性把所有数据加载到显存/WSL 内存，导致 LM Studio context overflow，后续引发 Summarization 超时 ×4 → LLM timeout → 驱动崩溃 → BSOD。

## 根因

建库批次策略错误，没有分批处理大数据集。

## 正确做法

- 大型 RAG 建库时分批处理 embedding，每批数量在显存/内存可承受范围内
- 或使用 streaming 方式逐文件处理
- 验证：监控显存和内存使用量，设置阈值告警

## 教训

RAG 建库必须先小批量验证内存上限，再规模化。
