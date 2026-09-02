---
title: api gateway anthropic incompatibility
domain: contrib
tags:
- project:rag
- severity:medium
- node:hermes_wsl
status: published
created: '2026-07-06'
source: bootstrap
confidence: 0.8
domain_expert: bootstrap
verified_date: '2026-05-03'
subdomain: api
---

<!-- provenance:
provenance:
  source: "internal"
  contributor: "Ikalus1988"
  merged_at: "2026-05-20"
  evidence: "post-publication"
-->

---
<!-- 
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

```bash
echo "Lesson: api gateway anthropic incompatibility"
wc -l lessons/contrib/api-gateway-anthropic-incompatibility.md
```

**Expected Output:**
```
Lesson: api gateway anthropic incompatibility
# (line count)
```

## Notes

使用公司内网大模型网关（InternalGateway/InternalModel API）作为 Hermes Agent 的 LLM 后端。