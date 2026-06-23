---
domain: "contrib"
title: "Internal Gateway — Incompatible with Anthropic Format, Requires OpenAI Proxy"
verification: "metadata-normalized"
{"created": "2026-04-30 09:00 UTC", "domain": "devops", "machine": "hp-wsl", "source": "hermes_wsl", "status": "published", "tags": "", "title": "Internal Gateway — Incompatible with Anthropic Format, Requires OpenAI Proxy", "updated": "2026-04-30 09:00 UTC", "domain_expert": "hermes_wsl", "verified_date": "2026-04-30"}
---

## 问题

internal-gateway.local API 端点 (`https://api.internal-gateway.local/v1`) 只接受 OpenAI 格式 (`/v1/chat/compositions`)，不支持 Anthropic 原生格式 (`/v1/messages`)。

这意味着：
- Hermes Agent → 直接连，因为 Hermes 用 OpenAI 格式 ✅
- Claude Code / cc-haha 原生 → 连不上，因为发的是 `/v1/messages` ❌
- Hermes + cc-haha 在同一台机器时 → cc-haha 不能直接用同一个 key

## 修复

需要在本地跑一个格式转换代理：

```bash
# Internal Gateway — Incompatible with Anthropic Format, Requires OpenAI Proxy
# 监听 localhost:8765
# 把 Anthropic 格式转成 OpenAI 格式发到 internal-gateway.local
```

## 验证

```bash
# 代理启动后
curl -X POST http://127.0.0.1:8765/v1/messages \
  -H "x-api-key: sk-xxx" \
  -d '{"model":"claude-sonnet-4","messages":[{"role":"user","content":"hi"}]}'
```

预期：返回 Anthropic 格式的响应。

## 关联

Node 2 和 3 在同一台电脑时，Node 3 (cc-haha) 需要这个代理才能共用同一家的 API。