---
domain: "contrib"
title: "feishu webhook url env config"
verification: "metadata-normalized"
{"title": "飞书 webhook URL 必须用环境变量或 gitignored 的 config.yaml", "domain": "devops", "subdomain": "feishu", "source": "bootstrap", "status": "published", "tags": ["project:agent-medici", "severity:critical", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
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

git log 中不再跟踪 config.yaml 变更。hermes_hub.py 中的 _load_config() 正确解析 ${FEISHU_APP_ID} 等占位符。

## Notes

任何使用飞书集成的 Hermes Agent-Medici 节点。
