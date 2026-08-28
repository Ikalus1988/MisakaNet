---
confidence: '0.7'
created: '2026-07-06'
domain: contrib
domain_expert: bootstrap
language: zh
source: bootstrap
status: published
tags:
- credential
- gateway
title: Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里
verification: metadata-normalized
verified_date: '2026-04-01'
'{"title"': 'Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里", "domain": "devops", "source":
  "bootstrap", "status": "published", "confidence": "0.7", "created": "2026-04-01",
  "domain_expert": "bootstrap", "verified_date": "2026-04-01"}'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
created: '2026-07-06'
domain: contrib
source: unknown
status: published
title: Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里
verification: metadata-normalized
'{"title"': 'Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里", "domain": "devops", "source":
  "bootstrap", "status": "published", "confidence": "0.7", "created": "2026-04-01",
  "domain_expert": "bootstrap", "verified_date": "2026-04-01"}'
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
echo "Lesson: Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里"
wc -l lessons/contrib/hub-credential-gateway-vs-hub.md
```

**Expected Output:**
```
Lesson: Hub Hermes 凭证体系 — Gateway vs Hub 各自读哪里
# (line count)
```

## Key Points

- Hub 需要 `.venv` Python（`~/.hermes/hermes-agent/.venv/bin/python3`），系统 Python 缺 `networkx`
- Hub 启动脚本：`~/Agent-Medici/start_hub.sh`
- Hub **不**用 watchdog 监控，需手动重启
- Hub 和 Gateway 共享同一个 Feishu App
