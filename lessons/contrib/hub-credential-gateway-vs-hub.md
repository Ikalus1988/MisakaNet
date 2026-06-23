---
{"title": "Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里", "domain": "devops", "source": "bootstrap", "status": "published", "confidence": "0.7", "created": "2026-04-01", "domain_expert": "bootstrap", "verified_date": "2026-04-01"}
---


## Background

Hub 有两套Configuration体系，Gateway 和 Hub 读取不同的凭证位置，容易混淆。

## 凭证读取位置

| 进程 | Configuration file | 关键Variable |
|------|---------|---------|
| Gateway | `~/.hermes/.env` | `FEISHU_APP_ID`, `FEISHU_APP_SECRET` |
| Hub | `~/.bashrc` + `~/Agent-Medici/config.yaml` | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`（Environment variable）；`webhook_url`, `shared_secret`（config.yaml） |

## Fix

**Gateway 凭证**（PID 1041579）：
```bash
hermes config set FEISHU_APP_SECRET <new_secret>
```

**Hub 凭证**：
```bash
# Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里
export FEISHU_APP_ID=cli_a93f960281389bcd
export FEISHU_APP_SECRET=[FEISHU_SECRET]

# config.yaml 写死Value
feishu:
  app_id: "cli_a93f960281389bcd"
  app_secret: "[FEISHU_SECRET]"
  webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/b1b472df-e29c-42ab-9d7d-d7e3fea4097a"
master:
  shared_secret: "looF ehT"
```
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 关键点

- Hub Require `.venv` Python（`~/.hermes/hermes-agent/.venv/bin/python3`），系统 Python 缺 `networkx`
- Hub Start脚本：`~/Agent-Medici/start_hub.sh`
- Hub **不**用 watchdog 监控，需Manual重启
- Hub 和 Gateway 共享同一个 Feishu App
