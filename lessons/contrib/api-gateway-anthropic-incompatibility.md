---
{"title": "InternalGateway API 网关不兼容 Anthropic 原生格式", "domain": "devops", "subdomain": "api", "source": "bootstrap", "status": "draft", "tags": ["project:rag", "severity:medium", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## Problem

Hermes Agent Configuration Anthropic provider Use internal-gateway.local API 时失败，
API 返回 400 Error。

## 根因

internal-gateway.local API 端点 (https://api.internal-gateway.local/v1) 只接受 OpenAI 格式
(/v1/chat/completions)，不Support Anthropic 原生格式 (/v1/messages)。
Hermes Configuration了 Anthropic provider 会发送 Anthropic 格式请求。

## Fix

在 Hermes 的 config.yaml 中将 provider Configuration为 OpenAI 兼容格式而非 Anthropic：
```yaml
provider: openai
api_base: https://api.internal-gateway.local/v1
```

或者在 Hermes Gateway 中Configuration代理转换层。

## 验证

Configuration为 OpenAI provider 后，API 调用正常返回，模型响应正确。

## 场景

Use公司内网大模型网关（InternalGateway/InternalModel API）作为 Hermes Agent 的 LLM 后端。
