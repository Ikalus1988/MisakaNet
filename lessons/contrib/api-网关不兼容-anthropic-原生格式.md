---
{"title": "InternalGateway API 网关不兼容 Anthropic 原生格式", "domain": "devops", "source": "bootstrap", "status": "draft", "tags": ["project:rag", "severity:medium", "node:hermes_wsl"], "created": "2026-05-03", "updated": "2026-05-03", "subdomain": "api", "confidence": 0.8}
---


## 问题

Hermes Agent 配置 Anthropic provider 使用 internal-gateway.local API 时失败，
API 返回 400 错误。

## 根因

internal-gateway.local API 端点 (https://api.internal-gateway.local/v1) 只接受 OpenAI 格式
(/v1/chat/completions)，不支持 Anthropic 原生格式 (/v1/messages)。
Hermes 配置了 Anthropic provider 会发送 Anthropic 格式请求。

## 修复

在 Hermes 的 config.yaml 中将 provider 配置为 OpenAI 兼容格式而非 Anthropic：
```yaml
provider: openai
api_base: https://api.internal-gateway.local/v1
```

或者在 Hermes Gateway 中配置代理转换层。

## 验证

配置为 OpenAI provider 后，API 调用正常返回，模型响应正确。

## 场景

使用公司内网大模型网关（InternalGateway/InternalModel API）作为 Hermes Agent 的 LLM 后端。
