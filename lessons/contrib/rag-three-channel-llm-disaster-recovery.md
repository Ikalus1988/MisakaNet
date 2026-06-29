---
domain: "contrib"
title: "rag three channel llm disaster recovery"
verification: "metadata-normalized"
{"title": "RAG 三通道 LLM 容灾方案", "domain": "rag", "subdomain": "llm", "source": "bootstrap", "status": "draft", "tags": ["project:self-grow-wiki", "node:hermes_wsl", "scope:broad"], "confidence": "0.85", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## Problem

When serving a RAG knowledge base externally (Gradio Web UI / WeChat bot), a single LLM API path may become unavailable due to network issues, quota limits, or server-side failures, causing the whole service to become unavailable.

## Root Cause

Depending on one LLM channel creates a single point of failure. API rate limits, network fluctuations, and server upgrades can all make queries fail. In industrial-document scenarios, users expect fault tolerance rather than "service unavailable".

## Fix

Implement three-channel automatic disaster recovery, degrading by priority:
```
Channel 1 (primary)  InternalModel-Flash  api.internal-gateway.local  ~1.5s  internal network
Channel 2 (backup)   Qwen cloud           Tongyi Qianwen API          ~3s    public internet
Channel 3 (fallback) Qwen2.5:3b           localhost:11434             ~50s   local Ollama
```

Core logic:
- Try the primary channel first, and automatically switch to backup on timeout or non-200 responses
- If the backup channel fails, switch to the fallback channel (local model, no network dependency)
- If all channels fail, return pure retrieval results without generating an answer

## Verification

After manually disconnecting the Windows proxy (primary channel unavailable), RAG could still return answers through local Ollama.
Monitoring for 7 consecutive days showed no service interruption.

## Scenario

Any production environment that needs to provide stable external LLM Q&A service.
