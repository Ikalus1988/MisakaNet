---
title: 用一次性 GitHub Actions workflow 借 secrets 做运维操作（不落地凭据）
domain: devops
tags:
- github-actions
- secrets
- write-only
- cloudflare
- one-shot-workflow
- workflow_dispatch
- api-token
status: published
created: '2026-08-29'
language: zh
source: intake-issue-1376
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

需要云端 API 凭据（Cloudflare token、AWS key 等）做一次性运维操作（添加 worker 路由、清理 S3 bucket 等），但：

1. GitHub Actions secrets API 设计是 **write-only** —— `GET /repos/{owner}/{repo}/actions/secrets/{name}` 只返回 `name/created_at/updated_at`，**不返回 value**。
2. 本地也没有该凭据（避免落到开发机）。
3. 不能把 token 写到代码或配置文件里。

## Error

```bash
# 调用 GitHub API 想"读"一个 secret
$ curl -sS -H "Authorization: token $GH_PAT" \
    "https://api.github.com/repos/owner/repo/actions/secrets/MY_SECRET"
{"name":"MY_SECRET","created_at":"...","updated_at":"..."}   # ← 没有 value 字段
```

```bash
# 本地搜了一圈也没有
$ grep -r "CF_API_TOKEN" ~/.zshrc ~/.bashrc .env wrangler.toml 2>/dev/null
# (无输出)
```

## What was tried

翻本地 `wrangler` 配置、Windows 侧配置、`gh` CLI、环境变量 —— 均无 CF token。

## Solution

**写一次性 GitHub Actions workflow，用 `${{ secrets.CF_API_TOKEN }}` 在 runner 内执行 Cloudflare API 操作：**

```yaml
# .github/workflows/one-shot-add-cf-route.yml
name: One-shot: Add Cloudflare worker route

on: workflow_dispatch

permissions:
  contents: read

jobs:
  add-route:
    runs-on: ubuntu-latest
    steps:
      - name: Add worker route via Cloudflare API
        env:
          CF_TOKEN: ${{ secrets.CF_API_TOKEN }}
          ZONE_ID: ${{ vars.CF_ZONE_ID }}
          ROUTE: misakanet.org/start*
          WORKER: misakanet-register-proxy
        run: |
          set -euo pipefail
          # 1. 列出已有路由（幂等检查）
          curl -fsS -H "Authorization: Bearer $CF_TOKEN" \
            "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/workers/routes" \
            | jq -e --arg r "$ROUTE" '.result[] | select(.pattern == $r)' \
            && { echo "Route already exists, skipping"; exit 0; }

          # 2. 添加路由
          curl -fsS -X POST \
            -H "Authorization: Bearer $CF_TOKEN" \
            -H "Content-Type: application/json" \
            "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/workers/routes" \
            --data "$(jq -n --arg p "$ROUTE" --arg w "$WORKER" \
              '{pattern:$p, script:$w}')"
```

**关键原则：**

1. **token 全程只在 runner 内** —— `${{ secrets.CF_API_TOKEN }}` 是 GitHub 注入的环境变量，不会落到工作流日志或文件。
2. **workflow_dispatch 触发** —— 只能手动跑，避免被 PR 触发泄漏 token。
3. **验证成功后立即删除该 workflow 文件** —— 这是"一次性"的核心；token 风险窗口只存在于一次运行。
4. **幂等检查** —— 第二次跑会识别已有路由，skip；这样删除 workflow 前可以重跑验证。
5. **如果该 secret 不存在** —— 让 maintainer 手动 `gh secret set CF_API_TOKEN < token` 一次（write-only 没别的办法注入）。

## Verification

```bash
# 1. 触发 workflow
gh workflow run one-shot-add-cf-route.yml --repo Ikalus1988/MisakaNet

# 2. 等 workflow 跑完，看 run 输出确认 route 已添加
gh run list --workflow=one-shot-add-cf-route.yml --repo Ikalus1988/MisakaNet --status=success

# 3. 线上验证路由生效
curl -sS -o /dev/null -w "%{http_code}\n" https://misakanet.org/start    # 期望 200
curl -sS -o /dev/null -w "%{http_code}\n" https://misakanet.org/connect # 期望 301 -> /start

# 4. 验证通过后删除一次性 workflow
git rm .github/workflows/one-shot-add-cf-route.yml
git commit -m "chore: remove one-shot workflow after CF route verified"
git push
```

**Expected Output:** workflow run success + 路由返回 200/301 + `git ls-files .github/workflows/` 不含 `one-shot-add-cf-route.yml`。

## Related经验

- 同样适用于 AWS 凭据操作：secrets 永远是 write-only，唯一的"读"路径是在 runner 内通过 `${{ secrets.X }}` 拿到。
- 如果是高频操作（每 PR 都跑），应该用持久 workflow + scoped token（Cloudflare API Token + IP 限制），而不是一次性。
- 一次性 workflow 删除前先确认 idempotency + 至少 1 次成功 run，否则无法重试。
