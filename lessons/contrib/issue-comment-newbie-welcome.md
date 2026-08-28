---
created: '2026-07-06'
domain: automation
domain_expert: deepseek
source: deepseek
status: published
tags:
- github-actions
- ci
- community
- newbie
- good-first-issue
- automation
title: Auto-Welcome Newcomers via issue_comment Event
updated: 2026-06-12 00:00:00 UTC
verification: metadata-normalized
verified_date: '2026-06-12'
'{"title"': 'Auto-Welcome Newcomers via issue_comment Event", "domain": "devops",
  "tags": ["github-actions", "ci", "community", "newbie", "good-first-issue", "automation"],
  "status": "published", "source": "deepseek", "created": "2026-06-12 00:00:00 UTC",
  "updated": "2026-06-12 00:00:00 UTC", "domain_expert": "deepseek", "verified_date":
  "2026-06-12"}'
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
title: Auto-Welcome Newcomers via issue_comment Event
verification: metadata-normalized
'{"title"': 'Auto-Welcome Newcomers via issue_comment Event", "domain": "devops",
  "tags": ["github-actions", "ci", "community", "newbie", "good-first-issue", "automation"],
  "status": "published", "source": "deepseek", "created": "2026-06-12 00:00:00 UTC",
  "updated": "2026-06-12 00:00:00 UTC", "domain_expert": "deepseek", "verified_date":
  "2026-06-12"}'
---
## Problem

开源项目设置 Good First Issues 后，新手贡献者往往不知道如何开始。需要一种自动化的方式在贡献者评论 Issue 时立即给予引导。

## Solution

利用 `issue_comment` 事件 + `github-actions[bot]` 自动回复。

### 工作流

```yaml
# Auto-Welcome Newcomers via issue_comment Event
name: Newbie Welcome
on:
  issue_comment:
    types: [created]

permissions:
  issues: write
  pull-requests: read

jobs:
  welcome:
    if: |
      !github.event.issue.pull_request &&
      contains(github.event.issue.labels.*.name, 'good first issue') &&
      !contains(fromJSON('["MEMBER", "OWNER", "COLLABORATOR"]'), github.event.comment.author_association)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/github-script@v7
        with:
          script: |
            const body = `## 👋 Welcome to MisakaNet!

            You're commenting on a **Good First Issue**.

            1. Read the CONTRIBUTING.md guide
            2. Claim by commenting \`/claim\` — 8h exclusive window
            3. Implement with \`git commit -s\`
            4. Submit a PR — CI audits automatically`;
            await github.rest.issues.createComment({ ... });
```

### Key Points

1. **触发条件过滤** — 仅对非 PR 的 Issue 评论、且带 `good first issue` 标签、且非项目成员（MEMBER/OWNER/COLLABORATOR）触发。避免骚扰维护者自己的对话。
2. **无需注册 Bot** — 使用 `github-actions[bot]` 内置身份即可，不需要单独创建 GitHub App。
3. **权限最小化** — `issues: write`（写评论）+ `pull-requests: read`（判断是否为 PR）。

## Results

- 新手贡献者在评论 Good First Issue 后几秒内收到引导
- 消息内含 `/claim` 指令说明、`git commit -s` 要求、CI 流程简介
- 可附带 Star 提示（⭐ If you find this project useful, consider starring the repo）
## Verification

```bash
echo "Lesson: Auto-Welcome Newcomers via issue_comment Event"
wc -l lessons/contrib/issue-comment-newbie-welcome.md
```

**Expected Output:**
```
Lesson: Auto-Welcome Newcomers via issue_comment Event
# (line count)
```

## 注意事项

- 同一 Issue 每次有人评论都会触发——如需去重，可在 JS 中检查是否已有 Bot 历史评论
- 对大量并发 Issue 评论的场景，建议设置 `concurrency` 限制
