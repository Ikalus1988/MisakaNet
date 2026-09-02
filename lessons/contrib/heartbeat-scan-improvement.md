---
title: GitHub Contribution Heartbeat Scan
domain: devops
tags:
- github
- heartbeat
- monitoring
- pull-request
- issues
status: published
created: '2026-08-04'
updated: '2026-08-04'
source: session-feedback
evidence_level: E0
metadata:
  type: feedback
  originSessionId: c8d99950-7aef-46ad-b4ce-4d0f910c86e9
  modified: '2026-08-04T10:19:56.150Z'

provenance:
  source: "external"
  contributor: "session-feedback"
  merged_at: "2026-08-26"
  evidence: "post-publication"
---

## Problem

心跳只用 `gh search prs --author` 扫描，漏掉了：
1. 已关闭的 PR（被拒后不在 open 结果里）
2. 只 claim 没提 PR 的 issue（issue 不在 PR 搜索结果里）

## Solution

心跳必须同时运行 3 个扫描：

```bash
# A. 开放 PR
gh search prs --author=<user> --state=open --limit=30

# B. Claimed issues（防丢失！）
gh search issues --involves=<user> --state=open --updated='>YYYY-MM-DD' --limit=20

# C. 近期关闭的 PR（追认贡献墙）
gh search prs --author=<user> --state=closed --sort=updated --limit=10
```

## Key Points

- `--involves` 包含评论、review、assign 等所有参与方式
- 已关 PR 不在 open 结果里，但可能需要追认贡献墙
- Claimed issue 没有 PR 时，心跳完全看不到它

**Why:** Claimed issue 丢失会导致承诺的任务被遗忘
**How to apply:** 心跳脚本必须包含 A+B+C 三个扫描


## Verification

```bash
git status --short | head -5
git log --oneline -3
```

**Expected Output:**
```
# (status)
# (recent)
```