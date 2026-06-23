---
domain: "contrib"
title: "bge embedding fallback crash"
verification: "metadata-normalized"
{"title": "BGE embedding 模型需要降级 fallback 避免启动崩溃", "domain": "rag", "subdomain": "embedding", "source": "bootstrap", "status": "draft", "tags": ["project:agent-medici", "severity:high", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## 问题

HermesHub 启动时如果 BGE-m3 模型未下载到本地路径，SkillIndexer 直接崩溃。
本地路径硬编码为 ~/.cache/huggingface/...，在其它机器上不存在。

## 根因

skill_indexer.py 的 _init_embedding_model() 用 local_files_only=True 加载模型，
模型路径是硬编码的机器级绝对路径。没有 fallback 机制，也没有环境变量覆盖。

## 修复

1. 移除硬编码绝对路径，改为：构造函数参数 → 环境变量 EMBEDDING_MODEL_PATH → 模型名（auto-download）
2. 加载失败时有 try/except，降级为无嵌入模式（register_skill 跳过语义去重）
3. _generate_embedding() 返回空列表，search_skills 退化为关键词匹配

## 验证

在没有 BGE-m3 模型的机器上启动 hub，不崩溃，输出 "[Embedding] 降级运行 — 语义去重和搜索将不可用"。

## 场景

任何非开发机器的 Node 节点（Node 1/2/3/6），没有预下载 BGE-m3 模型缓存。
