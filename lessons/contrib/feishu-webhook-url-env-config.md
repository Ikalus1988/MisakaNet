---
confidence: '0.8'
created: '2026-07-06'
domain: feishu
domain_expert: bootstrap
source: bootstrap
status: published
subdomain: feishu
tags:
- project:agent-medici
- severity:critical
- node:hermes_wsl
title: feishu webhook url env config
verification: metadata-normalized
verified_date: '2026-05-03'
'{"title"': '飞书 webhook URL 必须用环境变量或 gitignored 的 config.yaml", "domain": "devops",
  "subdomain": "feishu", "source": "bootstrap", "status": "published", "tags": ["project:agent-medici",
  "severity:critical", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03",
  "domain_expert": "bootstrap", "verified_date": "2026-05-03"}'
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
title: feishu webhook url env config
verification: metadata-normalized
'{"title"': '飞书 webhook URL 必须用环境变量或 gitignored 的 config.yaml", "domain": "devops",
  "subdomain": "feishu", "source": "bootstrap", "status": "published", "tags": ["project:agent-medici",
  "severity:critical", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03",
  "domain_expert": "bootstrap", "verified_date": "2026-05-03"}'
---
## Problem

Feishu webhook URL、app_id、app_secret 被误提交到 git 仓库，
commit b7de627 包含明文凭据（后已轮换）。

## Root Cause

config.yaml 在 .gitignore 之前就已经被 git add，导致后续 .gitignore 不生效。
配置中的凭据以明文形式进入 git 历史。

## Solution

1. 轮换 app_secret（飞书开放平台后台操作）
2. git rm --cached config.yaml（从 git 跟踪移除）
3. config.yaml 改为用 ${ENV_VAR} 占位符，运行时从环境变量读取
4. .gitignore 添加 config.yaml
5. 凭据写入 ~/.bashrc（export 命令）

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

## Notes

任何使用飞书集成的 Hermes Agent-Medici 节点。
