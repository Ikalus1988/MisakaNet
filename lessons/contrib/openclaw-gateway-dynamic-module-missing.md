---
created: '2026-07-06'
domain: openclaw
source: unknown
status: published
tags:
- openclaw
- gateway
- dynamic
- module
- missing
title: openclaw gateway dynamic module missing
verification: metadata-normalized
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## Problem

飞书单聊和群聊均无回应。飞书长连接正常（WebSocket 显示 ON · OK），消息能收到，但 Bot 不回复。

## Root Cause

**单聊：** OpenClaw 动态生成的 JS 模块文件丢失，导致消息分发时 ERR_MODULE_NOT_FOUND。

日志关键报错：
```
Error [ERR_MODULE_NOT_FOUND]: Cannot find module
'/home/<user>/.nvm/versions/node/v22.22.2/lib/node_modules/openclaw/dist/directive-handling.fast-lane-BAhyQLdx.js'
imported from .../get-reply-462JLlw-.js
```

**群聊：** 群组不在 allowFrom 白名单中，groupPolicy 为 allowlist 模式。

日志关键报错：
```
group oc_51cd445c9162f2d622f1a984e8bc3f4f not in groupAllowFrom (groupPolicy=allowlist)
```

## Solution

### 单聊：重启 Gateway

```bash
systemctl --user restart openclaw-gateway
```

Gateway 重启后动态模块会重新生成。

### 群聊：添加群 ID 到 allowFrom

配置文件路径：
```
~/.openclaw/credentials/feishu-default-allowFrom.json
```

原始内容（只有用户 ID）：
```json
{
  "version": 1,
  "allowFrom": [
    "ou_3dc2416c9a7a4c297a19d87fd8edbccc"
  ]
}
```

添加群 ID：
```json
{
  "version": 1,
  "allowFrom": [
    "ou_3dc2416c9a7a4c297a19d87fd8edbccc",
    "oc_51cd445c9162f2d622f1a984e8bc3f4f"
  ]
}
```

修改后需重启 Gateway：
```bash
systemctl --user restart openclaw-gateway
```

## Verification

```bash
echo "Lesson: openclaw gateway dynamic module missing"
wc -l lessons/contrib/openclaw-gateway-dynamic-module-missing.md
```

**Expected Output:**
```
Lesson: openclaw gateway dynamic module missing
# (line count)
```

## 诊断命令

查看实时日志：
```bash
journalctl --user -u openclaw-gateway --no-pager -f
```

查看飞书 channel 状态：
```bash
openclaw status
```

查看所有 session：
```bash
openclaw sessions list
```
