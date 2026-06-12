---
{"title": "OpenClaw Gateway 动态模块缺失 — 飞书消息分发失败", "domain": "feishu", "source": "bootstrap", "status": "published", "tags": ["node:misaka10004", "platform:wsl", "severity:critical", "project:misakanet"], "created": "2026-05-18", "updated": "2026-05-18", "subdomain": "openclaw-debug", "confidence": 1.0}
---



## 问题

飞书单聊和群聊均无回应。飞书长连接正常（WebSocket 显示 ON · OK），消息能收到，但 Bot 不回复。

## 根因

**单聊：** OpenClaw 动态生成的 JS 模块文件丢失，导致消息分发时 ERR_MODULE_NOT_FOUND。

日志关键报错：
```
Error [ERR_MODULE_NOT_FOUND]: Cannot find module
'/home/eric_jia/.nvm/versions/node/v22.22.2/lib/node_modules/openclaw/dist/directive-handling.fast-lane-BAhyQLdx.js'
imported from .../get-reply-462JLlw-.js
```

**群聊：** 群组不在 allowFrom 白名单中，groupPolicy 为 allowlist 模式。

日志关键报错：
```
group oc_51cd445c9162f2d622f1a984e8bc3f4f not in groupAllowFrom (groupPolicy=allowlist)
```

## 修复

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

## 验证

1. 检查 Gateway 日志无 ERR_MODULE_NOT_FOUND：
   ```bash
   journalctl --user -u openclaw-gateway --no-pager -n 50 | grep -E "(ERR|error|ready)"
   ```

2. 飞书单聊发消息，Bot 应有回应

3. 群聊 @Bot，应有回应

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
