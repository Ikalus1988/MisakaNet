---
{
  "title": "GitHub Actions composite action 3 个常见陷阱",
  "domain": "devops",
  "tags": [
    "github-actions",
    "composite",
    "yaml",
    "shell-injection"
  ],
  "status": "published",
  "evidence_level": "E2",
  "source": "pr",
  "created": "2026-08-18",
  "updated": "",
  "verified_date": "",
  "domain_expert": "",
  "author": "Ikalus1988",
  "edited_at": "2026-08-18T12:51:50+08:00",
  "merged_by": "Ikalus1988",
  "pr": 1102
}
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

- 无 "inputs is already defined" 错误
- 无 shell 注入风险
- 单 commit PR 不会失败

## Key Points

- YAML inputs 只能定义一次
- 永远不要直接拼接用户输入到 shell 命令
- diff_stat 在单 commit 时可能为空，需要处理
