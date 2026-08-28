---
created: '2026-08-18'
domain: devops
domain_expert: ''
evidence_level: E2
language: zh
source: mcp-intake-1102
status: published
tags:
- github-actions
- composite
- yaml
- shell-injection
title: GitHub Actions composite action 3 个常见陷阱
updated: ''
verified_date: ''
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## Problem

GitHub Actions composite action 有 3 个常见陷阱：重复 YAML inputs、shell 注入、diff_stat 在单 commit 时为空。

## Root Cause

1. **重复 YAML inputs**：同名 input 被多次定义，导致 "inputs is already defined" 错误
2. **Shell 注入**：PR body 直接拼接到 shell 命令中，可能导致命令注入
3. **diff_stat 空**：单 commit PR 的 diff_stat 为空，导致后续逻辑失败

## Solution

**1. 避免重复 inputs：**
```yaml
# 错误
inputs:
  token:
    description: "Token"
inputs:  # 重复！
  token:
    description: "Token"

# 正确
inputs:
  token:
    description: "GitHub token"
  # 只定义一次
```

**2. 防止 shell 注入：**
```yaml
# 错误：直接拼接 PR body
- run: echo "${{ github.event.pull_request.body }}"

# 正确：使用环境变量
- run: echo "$PR_BODY"
  env:
    PR_BODY: ${{ github.event.pull_request.body }}
```

**3. 处理空 diff_stat：**
```yaml
# 正确：检查 diff_stat 是否为空
- name: Check diff
  run: |
    if [ -z "${{ steps.diff.outputs.stat }}" ]; then
      echo "No changes detected"
      exit 0
    fi
```

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

## Key Points

- YAML inputs 只能定义一次
- 永远不要直接拼接用户输入到 shell 命令
- diff_stat 在单 commit 时可能为空，需要处理
