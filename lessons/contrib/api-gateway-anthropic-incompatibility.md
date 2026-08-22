---
{
  "domain": "contrib",
  "title": "api gateway anthropic incompatibility",
  "created": "2026-07-06",
  "source": "manual",
  "subdomain": "api",
  "status": "published",
  "tags": [
    "project:rag",
    "severity:medium",
    "node:hermes_wsl"
  ],
  "confidence": "0.8",
  "domain_expert": "bootstrap",
  "verified_date": "2026-05-03",
  "author": "Liona Can",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

## Problem

Hermes Agent 配置 Anthropic provider 使用 internal-gateway.local API 时失败，
API 返回 400 错误。

## Root Cause

internal-gateway.local API 端点 (https://api.internal-gateway.local/v1) 只接受 OpenAI 格式
(/v1/chat/completions)，不支持 Anthropic 原生格式 (/v1/messages)。
Hermes 配置了 Anthropic provider 会发送 Anthropic 格式请求。

## Solution

在 Hermes 的 config.yaml 中将 provider 配置为 OpenAI 兼容格式而非 Anthropic：
```yaml
provider: openai
api_base: https://api.internal-gateway.local/v1
```

或者在 Hermes Gateway 中配置代理转换层。

## Verification

配置为 OpenAI provider 后，API 调用正常返回，模型响应正确。

## Notes

使用公司内网大模型网关（InternalGateway/InternalModel API）作为 Hermes Agent 的 LLM 后端。
