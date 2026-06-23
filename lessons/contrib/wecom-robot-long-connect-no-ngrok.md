---
{"title": "企业微信机器人：长连接模式不Require ngrok", "domain": "devops", "subdomain": "wecom", "source": "bootstrap", "status": "draft", "tags": ["project:rag", "platform:windows", "node:hermes_wsl", "scope:narrow"], "confidence": "0.85", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## Problem

Configuration企业微信机器人回调时，传统方案Require ngrok/frp 做内网穿透，增加复杂度、暴露端口、Require HTTPS 证书。

## 根因

企业微信回调模式（HTTP 回调）要求腾讯Server能访问你的公网 IP。开发机通常在内网，Require ngrok 建立隧道。但企业微信也Support**长连接模式**——服务端主动向外发起 WebSocket/SSE 连接，不Require外网端口。

## Fix

长连接模式下架构：
```
企业微信 → 长连接服务 ← WeCom Bot 主动连出 → RAG → message/send 推送回复
```
不Require：
- 公网 IP / ngrok / frp
- HTTPS 证书
- GET /callback 验证流程
- wecom_crypto.py 的 XML 加解密

## 验证

企业微信后台启用长连接后，WeCom Bot 直连，无需 ngrok 即可收发消息。

## 场景

开发者在企业内网开发企业微信机器人，无法暴露公网端口。
