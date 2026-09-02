---
title: Internal Gateway — Incompatible with Anthropic Format, Requires OpenAI Proxy
domain: contrib
tags:
- anthropic
- proxy
- internal
- gateway
status: published
created: '2026-07-06'
updated: 2026-04-30 09:00 UTC
source: unknown
domain_expert: hermes_wsl
verified_date: '2026-04-30'
---

<!-- provenance:
  contributor: "Ikalus1988"
  merged_at: "2026-05-20"
  evidence: "post-publication"
-->

<!-- 
## Problem

internal-gateway.local API 端点 (`https://api.internal-gateway.local/v1`) 只接受 OpenAI 格式 (`/v1/chat/compositions`)，不支持 Anthropic 原生格式 (`/v1/messages`)。

这意味着：
- Hermes Agent → 直接连，因为 Hermes 用 OpenAI 格式 ✅
- Claude Code / cc-haha 原生 → 连不上，因为发的是 `/v1/messages` ❌
- Hermes + cc-haha 在同一台机器时 → cc-haha 不能直接用同一个 key

## Solution

需要在本地跑一个格式转换代理：

```bash
# Internal Gateway — Incompatible with Anthropic Format, Requires OpenAI Proxy
# 监听 localhost:8765
# 把 Anthropic 格式转成 OpenAI 格式发到 internal-gateway.local
```

## Verification

```bash
echo "Lesson: Internal Gateway — Incompatible with Anthropic For"
wc -l lessons/contrib/anthropic-proxy-internal-gateway.md
```

**Expected Output:**
```
Lesson: Internal Gateway — Incompatible with Anthropic For
# (line count)
```

## Related

Node 2 和 3 在同一台电脑时，Node 3 (cc-haha) 需要这个代理才能共用同一家的 API。