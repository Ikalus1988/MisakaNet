---
title: Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里
domain: devops
source: bootstrap
status: published
confidence: 0.7
created: 2026-04-01
---


## 背景

Hub 有两套配置体系，Gateway 和 Hub 读取不同的凭证位置，容易混淆。

## 凭证读取位置

| 进程 | 配置文件 | 关键变量 |
|------|---------|---------|
| Gateway | `~/.hermes/.env` | `FEISHU_APP_ID`, `FEISHU_APP_SECRET` |
| Hub | `~/.bashrc` + `~/Agent-Medici/config.yaml` | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`（环境变量）；`webhook_url`, `shared_secret`（config.yaml） |

## 修复

**Gateway 凭证**（PID 1041579）：
```bash
hermes config set FEISHU_APP_SECRET <new_secret>
```

**Hub 凭证**：
```bash
# 环境变量写在 ~/.bashrc
export FEISHU_APP_ID=cli_a93f960281389bcd
export FEISHU_APP_SECRET=[FEISHU_SECRET]

# config.yaml 写死值
feishu:
  app_id: "cli_a93f960281389bcd"
  app_secret: "[FEISHU_SECRET]"
  webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/b1b472df-e29c-42ab-9d7d-d7e3fea4097a"
master:
  shared_secret: "looF ehT"
```

## 关键点

- Hub 需要 `.venv` Python（`~/.hermes/hermes-agent/.venv/bin/python3`），系统 Python 缺 `networkx`
- Hub 启动脚本：`~/Agent-Medici/start_hub.sh`
- Hub **不**用 watchdog 监控，需手动重启
- Hub 和 Gateway 共享同一个 Feishu App
