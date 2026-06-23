---
domain: "contrib"
title: "rag alarm code mandatory recall"
verification: "metadata-normalized"
{"title": "RAG 报警代码检索需要关键词强制召回", "domain": "rag", "subdomain": "fanuc", "source": "bootstrap", "status": "draft", "tags": ["project:self-grow-wiki", "severity:high", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## 问题

查询 "SRVO-023 机器人报警" 时 RAG 返回了不相关结果，没有返回正确的 FANUC 报警文档。

## 根因

ChromaDB 纯语义检索对短代码（SRVO-023、M-900 等）区分能力弱。数字字符串的嵌入向量
容易与不相关文档混淆。x"2000" 在语义上同时匹配 FANUC 和 KUKA 文档。

## 修复

在 rag_core.py 的 retrieve() 函数中加入关键词强制召回：
1. 报警代码模式：/[A-Z]+-\d+/ 匹配到则从文档标题/标签中强制召回含该代码的文档
2. 机器人型号：型号名（如 M-900、R-30iB）做字符串匹配，混合到检索结果中

## 验证

查询 "SRVO-023" 返回正确的 FANUC 报警文档列表，且排序靠前。查询 "FANUC R-2000iC 最大速度"
不再返回 KUKA Series 2000 数据。

## 场景

FANUC 机器人知识库 RAG，含大量报警代码和型号名称的工业文档。
