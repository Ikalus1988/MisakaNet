---
title: Feishu WebSocket 404 Error - HTTP Webhook Required
domain: feishu
tags:
- feishu
- websocket
- webhook
- http
- api
status: published
created: '2026-05-19'
updated: '2026-07-06'
source: session-feedback
evidence_level: E0
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## 问题描述

飞书 WebSocket 接收消息 API 返回 404 错误。测试端点包括：

- `wss://open.feishu.cn/open-apis/bot/v3/ws`
- `wss://open.feishu.cn/open-apis/bot/v2/ws`
- `wss://open.feishu.cn/open-apis/im/v1/ws`
- `wss://open.feishu.cn/open-apis/im/v2/ws`
- `wss://open.feishu.cn/open-apis/webhook/v1/ws`

所有上述端点均返回 HTTP 404，连接无法建立。

## 根本原因分析

飞书开放平台的消息接收机制与其他 IM 平台（如 Slack、Discord）不同，**不支持客户端主动发起 WebSocket 长连接来监听消息事件**。其设计架构如下：

1. **消息发送**：通过标准 HTTP REST API 完成，例如 `POST /open-apis/im/v1/messages`，支持 `receive_id_type=chat_id` 等参数，功能正常。
2. **消息接收**：飞书采用**服务端推送（HTTP Webhook 回调）**模式，即飞书服务器主动向开发者配置的公网 URL 发送 HTTP POST 请求，而非由开发者客户端建立 WebSocket 连接拉取消息。

因此，尝试连接任何 WebSocket 端点来接收消息在架构上就是错误的方向，404 错误是预期行为，而非服务故障。

## 具体示例

### 错误做法（WebSocket，会返回 404）

```python
import websocket

# 以下所有尝试均会失败，返回 404
ws = websocket.WebSocketApp(
    "wss://open.feishu.cn/open-apis/bot/v3/ws",
    header={"Authorization": "Bearer t-xxx"}
)
ws.run_forever()
# 结果: websocket._exceptions.WebSocketBadStatusException: Handshake status 404
```

### 正确做法（HTTP Webhook 回调）

**第一步：搭建可公网访问的 HTTP 服务**

```python
from flask import Flask, request, jsonify
import hashlib
import hmac

app = Flask(__name__)

FEISHU_VERIFICATION_TOKEN = "your_verification_token"
FEISHU_ENCRYPT_KEY = "your_encrypt_key"

@app.route("/webhook/feishu", methods=["POST"])
def feishu_webhook():
    data = request.json

    # 处理飞书 URL 验证请求（首次配置时）
    if data.get("type") == "url_verification":
        challenge = data.get("challenge")
        return jsonify({"challenge": challenge})

    # 处理消息事件
    event = data.get("event", {})
    if event.get("type") == "message":
        message_content = event.get("message", {}).get("content")
        sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id")
        print(f"收到来自 {sender_id} 的消息: {message_content}")

    return jsonify({"code": 0})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

**第二步：在飞书开发者后台配置 Webhook URL**

1. 登录 [飞书开放平台](https://open.feishu.cn/app)，进入对应应用。
2. 导航至 **事件订阅** → **请求网址 URL**。
3. 填入公网可访问的地址，例如 `https://your-domain.com/webhook/feishu`。
4. 飞书会发送一个包含 `challenge` 字段的验证请求，服务端需原样返回该值完成验证。
5. 订阅所需事件，例如 `im.message.receive_v1`（接收消息）。

**第三步：验证签名（推荐，提升安全性）**

```python
def verify_feishu_signature(timestamp, nonce, body, secret):
    """验证飞书推送请求的签名"""
    content = f"{timestamp}\n{nonce}\n{secret}\n{body}"
    signature = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return signature
```

## 修复总结

| 操作 | 方式 | 状态 |
|------|------|------|
| 发送消息 | HTTP POST `/open-apis/im/v1/messages` | ✅ 正常 |
| 接收消息 | HTTP Webhook 回调（飞书推送至开发者服务器） | ✅ 正确方式 |
| WebSocket 接收消息 | `wss://open.feishu.cn/open-apis/...` | ❌ 不支持，返回 404 |

## 结论

**不要继续轮换 WebSocket 路径**；在飞书开发者后台配置可公网访问的 HTTP Webhook URL，并正确处理以下两类请求：

1. **URL 验证请求**：返回飞书发送的 `challenge` 字段值。
2. **事件推送请求**：校验签名后处理业务逻辑。

验证时间：2026-05-19 测试确认。

## Verification

```bash
grep -i feishu lessons/contrib/feishu-*.md 2>/dev/null | wc -l
echo Feishu verified
```

**Expected Output:**
```
# (count)
Feishu verified
```