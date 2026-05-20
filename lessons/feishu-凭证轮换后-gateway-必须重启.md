---
title: Feishu 凭证轮换后 Gateway 必须重启
domain: feishu
source: bootstrap
status: published
confidence: 0.7
created: 2026-04-01
---


## 背景

飞书应用凭证（app_secret）轮换后，Gateway 仍用旧 secret 连接，导致 401 auth 失败。

## 根因

Gateway 启动时读取 `~/.hermes/.env` 中的 `FEISHU_APP_SECRET`，凭证轮换后进程持有旧值。

## 修复

凭证轮换后两步：

```bash
# 1. 更新 .env
# 旧值: [FEISHU_SECRET]
# 新值: [FEISHU_SECRET]
hermes config set FEISHU_APP_SECRET [FEISHU_SECRET]

# 2. 重启 Gateway（让新凭证生效）
pkill -f "hermes.*gateway"  # 或 systemctl --user restart hermes-gateway
```

## 验证

```bash
grep "Connected in websocket mode" ~/.hermes/logs/gateway.log
# 或
tail -5 ~/.hermes/logs/gateway.log | grep Feishu
```

## 关键点

- 新 app_id：`cli_a93f960281389bcd`
- 新 app_secret：`[FEISHU_SECRET]`
- Hub 和 Gateway 都用同一个 Feishu App，凭证同步更新
- 魔术师重新配对 = Gateway 用新凭证重连飞书 WS
