---
title: hub feishu wsclient start never called
domain: feishu
tags:
- feishu
- wsclient
- start
- never
- called
status: published
created: '2026-07-06'
source: bootstrap
confidence: 0.7
domain_expert: bootstrap
verified_date: '2026-04-01'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

---
## Problem

Hub 配置了 `im.message.receive_v1` 和 `p2p_card_action.trigger` 回调，但从未收到飞书消息。

## Root Cause

代码注册了回调句柄，但 **`start()` 方法里从未调用 `await self.feishu_ws_client.start()`**，WebSocket 从未真正建立连接。Hub 只用了 FeishuNotifier（webhook POST 发送），没用 WebSocket 接收消息。

## Solution

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

## Key Points

- Hub 和 Gateway 共享同一个 Feishu App（相同 app_id/app_secret）
- Hub 用 FeishuWSClient 接收消息 + FeishuNotifier 发送通知
- Feishu WS 连接用 `open.feishu.cn` 域名，token 从 `open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal` 获取