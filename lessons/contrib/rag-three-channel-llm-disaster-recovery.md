---
{"title": "RAG 三通道 LLM 容灾方案", "domain": "rag", "subdomain": "llm", "source": "bootstrap", "status": "draft", "tags": ["project:self-grow-wiki", "node:hermes_wsl", "scope:broad"], "confidence": "0.85", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## Problem

RAG 知识库对外服务（Gradio Web UI / 微信机器人）时，单路 LLM API 可能因网络、配额、服务端故障而不可用，导致整个服务不可用。

## 根因

依赖单一 LLM 通道是单点故障。API 限流、网络波动、服务端升级都会导致查询失败。在工业文档场景下，用户期望容错而非"服务不可用"。

## Fix

实现三通道Automatic容灾，按优先级降级：
```
Channel 1 (主)   InternalModel-Flash     api.internal-gateway.local    ~1.5s  内部网络
Channel 2 (备)   Qwen 云端      通义千问 API            ~3s    公网
Channel 3 (兜底) Qwen2.5:3b      localhost:11434         ~50s   Ollama 本地
```

核心逻辑：
- 先试主通道，超时或非 200 时Automatic切备
- 备通道失败时切兜底（本地模型，无网络依赖）
- 所有通道失效时返回纯检索结果（不生成答案）

## 验证

Manual断掉 Windows 梯子（主通道不可用），RAG 仍能Via本地 Ollama 返回答案。
连续 7 天监控无服务中断。

## 场景

任何Require对外提供稳定的 LLM 问答服务的生产环境。
