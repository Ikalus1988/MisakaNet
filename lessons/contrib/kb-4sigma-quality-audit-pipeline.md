---
{"title": "知识库 4σ 质量审计流水线", "domain": "rag", "subdomain": "quality", "source": "bootstrap", "status": "draft", "tags": ["project:self-grow-wiki", "severity:medium", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## Problem

RAG 知识库在持续导入文档后出现数据污染、Version混乱、来源不一致等Problem，
影响检索质量。

## 根因

1. 多次导入同一文档的不同Version（旧Version未移除）
2. OCR 导入引入乱码数据
3. 同一知识点在多个文档中有不同表述
4. 缺乏系统性的质量Check流程

## Fix

建立 4σ 质量审计流水线：
1. 污染清洗：Delete非文档内容（乱码、空块、纯数字块）
2. Version去重：按File名+导入时间识别重复
3. 来源校正：统一文档Path、File名、源 URL
4. 质量评分：按完整性/清洁度/Version一致性打分

实现为 daily_audit.py，cron 每日 6:00 AutomaticRun。
报告存 ~/audit_reports/audit_YYYY-MM-DD.json。

## 验证

审计报告连续 7 天无新增污染，知识库评分稳定在 95% 以上。

## 场景

持续增长的 RAG 知识库（>150 份文档，>20 万向量），RequireAutomatic化质量保障。
