---
{"title": "Feishu WebSocket 404 Error - HTTP Webhook Required", "domain": "feishu-integration", "source": "hermes_wsl2", "status": "published", "tags": [], "created": "2026-05-19 01:19:29 UTC", "updated": "2026-05-19 01:19:29 UTC"}
---

问题: 飞书 WebSocket 接收消息 API 返回 404 错误。测试端点: wss://open.feishu.cn/open-apis/bot/v3/ws, /bot/v2/ws, /im/v1/ws, /im/v2/ws, /webhook/v1/ws。所有端点均返回 404。修复: 消息发送功能正常 (通过 HTTP API with receive_id_type=chat_id), 但接收消息必须使用 HTTP Webhook 回调方式。验证: 2026-05-19 测试确认。
