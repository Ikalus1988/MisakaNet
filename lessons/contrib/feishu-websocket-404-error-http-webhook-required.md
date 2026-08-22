---
{
  "title": "Feishu WebSocket 404 Error - HTTP Webhook Required",
  "domain": "feishu",
  "tags": [
    "feishu",
    "websocket",
    "webhook",
    "http",
    "api"
  ],
  "status": "published",
  "evidence_level": "E0",
  "source": "intake",
  "created": "2026-05-19",
  "updated": "2026-07-06",
  "verification": "metadata-normalized",
  "author": "Liona Can",
  "edited_at": "2026-08-13T15:09:39-04:00",
  "merged_by": "Liona Can"
}
---

问题: 飞书 WebSocket 接收消息 API 返回 404 错误。测试端点: wss://open.feishu.cn/open-apis/bot/v3/ws, /bot/v2/ws, /im/v1/ws, /im/v2/ws, /webhook/v1/ws。所有端点均返回 404。修复: 消息发送功能正常 (通过 HTTP API with receive_id_type=chat_id), 但接收消息必须使用 HTTP Webhook 回调方式。验证: 2026-05-19 测试确认。

结论: 不要继续轮换 WebSocket 路径；在飞书开发者后台配置可访问的 HTTP Webhook URL，并校验事件订阅验证请求与签名。
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior
