---
domain: "contrib"
title: "hub feishu wsclient start never called"
verification: "metadata-normalized"
{"title": "Hub FeishuWSClient.start() 从未调用 — WebSocket 接收死代码", "domain": "feishu", "source": "bootstrap", "status": "published", "confidence": "0.7", "created": "2026-04-01", "domain_expert": "bootstrap", "verified_date": "2026-04-01"}
---


## 背景

Hub 配置了 `im.message.receive_v1` 和 `p2p_card_action.trigger` 回调，但从未收到飞书消息。

## 根因

代码注册了回调句柄，但 **`start()` 方法里从未调用 `await self.feishu_ws_client.start()`**，WebSocket 从未真正建立连接。Hub 只用了 FeishuNotifier（webhook POST 发送），没用 WebSocket 接收消息。

## 修复

在 `hermes_hub.py` 的 `start()` 方法中添加：

```python
async def start(self):
    await self._load_config()
    await self._init_storage()
    await self._init_feishu_client()
    await self._init_vector_store()
    # 必须调用，否则 WS 从未启动
    await self.feishu_ws_client.start()  # ← 添加这行
    await self._register_handlers()
    self._start_background_tasks()
```

已在 commit `56f690b` 中修复。

## 验证

重启 Hub 后检查日志：

```
grep "长连接已启动" ~/.hermes/logs/hermes_hub_new.log
```

## 关键点

- Hub 和 Gateway 共享同一个 Feishu App（相同 app_id/app_secret）
- Hub 用 FeishuWSClient 接收消息 + FeishuNotifier 发送通知
- Feishu WS 连接用 `open.feishu.cn` 域名，token 从 `open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal` 获取
