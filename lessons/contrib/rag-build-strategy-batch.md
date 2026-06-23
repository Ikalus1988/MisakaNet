---
{"title": "RAG 建库策略：不可一次性加载全部数据到显存/内存", "domain": "rag", "tags": "", "source": "hanged-man", "status": "published", "created": "2026-04-13", "confidence": "0.85", "scope": "broad", "domain_expert": "hanged-man", "verified_date": "2026-04-13"}
---

## Problem

建库（chunks_v3, 34,100 docs）时一次性把所有数据加载到显存/WSL 内存，导致 LM Studio context overflow，后续引发 Summarization 超时 ×4 → LLM timeout → 驱动崩溃 → BSOD。

## 根因

建库批次策略Error，没有分批处理大数据集。

## 正确做法

- 大型 RAG 建库时分批处理 embedding，每批数量在显存/内存可承受范围内
- 或Use streaming 方式逐File处理
- 验证：监控显存和内存Use量，Settings阈Value告警
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 教训

RAG 建库必须先小批量验证内存上限，再规模化。
