---
confidence: '0.85'
created: '2026-07-06'
domain: contrib
domain_expert: bootstrap
source: bootstrap
status: published
subdomain: wecom
tags:
- project:rag
- platform:windows
- node:hermes_wsl
- scope:narrow
title: wecom robot long connect no ngrok
verification: metadata-normalized
verified_date: '2026-05-03'
'{"title"': '企业微信机器人：长连接模式不需要 ngrok", "domain": "devops", "subdomain": "wecom", "source":
  "bootstrap", "status": "published", "tags": ["project:rag", "platform:windows",
  "node:hermes_wsl", "scope:narrow"], "confidence": "0.85", "created": "2026-05-03",
  "domain_expert": "bootstrap", "verified_date": "2026-05-03"}'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
created: '2026-07-06'
domain: contrib
source: unknown
status: published
title: wecom robot long connect no ngrok
verification: metadata-normalized
'{"title"': '企业微信机器人：长连接模式不需要 ngrok", "domain": "devops", "subdomain": "wecom", "source":
  "bootstrap", "status": "published", "tags": ["project:rag", "platform:windows",
  "node:hermes_wsl", "scope:narrow"], "confidence": "0.85", "created": "2026-05-03",
  "domain_expert": "bootstrap", "verified_date": "2026-05-03"}'
---
## Problem

配置企业微信机器人回调时，传统方案需要 ngrok/frp 做内网穿透，增加复杂度、暴露端口、需要 HTTPS 证书。

## Root Cause

企业微信回调模式（HTTP 回调）要求腾讯服务器能访问你的公网 IP。开发机通常在内网，需要 ngrok 建立隧道。但企业微信也支持**长连接模式**——服务端主动向外发起 WebSocket/SSE 连接，不需要外网端口。

## Solution

长连接模式下架构：
```
企业微信 → 长连接服务 ← WeCom Bot 主动连出 → RAG → message/send 推送回复
```
不需要：
- 公网 IP / ngrok / frp
- HTTPS 证书
- GET /callback 验证流程
- wecom_crypto.py 的 XML 加解密

## Verification

```bash
echo "Lesson: wecom robot long connect no ngrok"
wc -l lessons/contrib/wecom-robot-long-connect-no-ngrok.md
```

**Expected Output:**
```
Lesson: wecom robot long connect no ngrok
# (line count)
```

## Notes

开发者在企业内网开发企业微信机器人，无法暴露公网端口。
