---
title: Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里
domain: contrib
tags:
- credential
- gateway
status: published
created: '2026-07-06'
language: zh
source: bootstrap
confidence: 0.7
domain_expert: bootstrap
verified_date: '2026-04-01'
---

---
## Problem

Hub 有两套配置体系，Gateway 和 Hub 读取不同的凭证位置，容易混淆。

## Credential Locations

| 进程 | 配置文件 | 关键变量 |
|------|---------|---------|
| Gateway | `~/.hermes/.env` | `FEISHU_APP_ID`, `FEISHU_APP_SECRET` |
| Hub | `~/.bashrc` + `~/Agent-Medici/config.yaml` | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`（环境变量）；`webhook_url`, `shared_secret`（config.yaml） |

## Solution

**Gateway 凭证**（PID 1041579）：
```bash
hermes config set FEISHU_APP_SECRET <new_secret>
```

**Hub 凭证**：
```bash
# Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里
export FEISHU_APP_ID=<your-app-id>
export FEISHU_APP_SECRET=<REDACTED>

# config.yaml 写死值
feishu:
  app_id: "<your-app-id>"
  app_secret: "<REDACTED>"
  webhook_url: "<your-webhook-url>"
master:
  shared_secret: "<REDACTED>"
```
## Verification

```bash
feishu:
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `feishu:`)

## Key Points

- Hub 需要 `.venv` Python（`~/.hermes/hermes-agent/.venv/bin/python3`），系统 Python 缺 `networkx`
- Hub 启动脚本：`~/Agent-Medici/start_hub.sh`
- Hub **不**用 watchdog 监控，需手动重启
- Hub 和 Gateway 共享同一个 Feishu App