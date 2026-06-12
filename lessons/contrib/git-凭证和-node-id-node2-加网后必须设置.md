---
{"title": "Git 凭证和 Node ID — Node2 加网后必须设置", "domain": "devops", "source": "bootstrap", "status": "published", "tags": [], "created": "2026-04-01", "updated": "2026-04-01", "confidence": 0.7}
---



## 背景

Node2（魔术师）加入虫群前需要配置 Git 身份和节点标识。

## 修复

```bash
# 1. 设置 Git 用户
cd ~/Agent-Medici
git config user.name "魔术师"
git config user.email "you@example.com"

# 2. 设置 GitHub PAT（用于推送 document-classify 仓库）
git config --global credential.helper store
echo "https://[GITHUB_TOKEN]@github.com" > ~/.git-credentials

# 3. 设置 Node ID
echo "node2" > ~/.hermes/node_id

# 4. 确认 Hub 联结
# 从 Hub 获取 node2 的 license
```

## 关键点

- GitHub PAT：`[GITHUB_TOKEN]`
- Hub 在 Node2 的 git pull 是单向的（Node → Hub），Hub 不往节点推代码
- Node2 每 10 分钟自动 git pull（`*/10 * * * *` cron）
