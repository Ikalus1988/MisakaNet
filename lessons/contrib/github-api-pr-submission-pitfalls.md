---
title: GitHub API PR Submission Pitfalls
domain: devops
tags:
- github
- api
- pull-request
- base64
- git
status: published
created: '2026-08-04'
updated: '2026-08-04'
source: session-feedback
evidence_level: E0
metadata:
  type: feedback
  originSessionId: c8d99950-7aef-46ad-b4ce-4d0f910c86e9
  modified: '2026-08-04T09:43:52.372Z'
---

## Problem

网络慢无法 clone 大仓时，可用 GitHub Contents API 直接创建分支、修改文件、提 PR。但有 4 个常见坑。

## 坑 1: base64 换行导致 JSON 解析失败

**症状**: `PUT /repos/.../contents/...` 返回 `400 Problems parsing JSON`

**根因**: `base64 -i file` 输出含换行符，嵌入 JSON 后破坏结构

**解法**:
```bash
# 必须去掉换行
ENCODED=$(base64 -i file.py | tr -d '\n')
```

## 坑 2: SHA 不匹配导致 409 冲突

**症状**: `409 does not match`

**根因**: fork sync (`merge-upstream`) 后文件 SHA 变了，但用的是旧 SHA

**解法**: 每次 PUT 前重新获取 SHA
```bash
# sync 后重新取 SHA
gh api "repos/FORK/REPO/contents/PATH?ref=BRANCH" --jq '.sha'
```

## 坑 3: ruff formatter 空白行敏感

**症状**: `pre-commit` CI 失败，diff 显示删除一个空行

**根因**: Python heredoc 插入代码时，`\n\n    @decorator` 会产生两个空行，ruff 只允许一个

**解法**: 插入代码时确保方法间只有一个空行
```python
# 错误：两个空行
head -N file.py > new.py
echo -e "\n\n    @pytest.mark.anyio" >> new.py  # 多了一个空行

# 正确：一个空行
head -N file.py > new.py
echo -e "\n    @pytest.mark.anyio" >> new.py
```

## 坑 4: fork 分支 diff 膨胀

**症状**: PR 只改了 13 行，但 diff 显示 409 行（含上游改动）

**根因**: 分支创建时 fork main 落后于 upstream main，`compare` API 显示所有差异

**解法**: 提 PR 前检查 diff 干净度
```bash
gh api "repos/UPSTREAM/REPO/compare/main...FORK:BRANCH" \
  --jq '{ahead_by, behind_by, files: [.files[] | {filename, changes}]}'
# behind_by 必须为 0，否则需 rebase
```

## 完整流程

```bash
# 1. Sync fork
gh api repos/FORK/REPO/merge-upstream -X POST -f branch=main

# 2. 创建分支
SHA=$(gh api repos/UPSTREAM/REPO/git/refs/heads/main --jq '.object.sha')
gh api repos/FORK/REPO/git/refs -f ref="refs/heads/fix/xxx" -f sha="$SHA"

# 3. 获取文件 SHA + 修改 + PUT
FILE_SHA=$(gh api "repos/FORK/REPO/contents/PATH?ref=BRANCH" --jq '.sha')
# ... 修改文件 ...
ENCODED=$(base64 -i file.py | tr -d '\n')
jq -n --arg msg "fix: ..." --arg sha "$FILE_SHA" --arg branch "BRANCH" --arg content "$ENCODED" \
  '{message: $msg, sha: $sha, branch: $branch, content: $content}' > payload.json
gh api repos/FORK/REPO/contents/PATH -X PUT --input payload.json

# 4. 验证 diff
gh api "repos/UPSTREAM/REPO/compare/main...FORK:BRANCH" --jq '{ahead_by, behind_by}'

# 5. 创建 PR
gh pr create --repo UPSTREAM/REPO --head FORK:BRANCH --base main --title "..." --body "..."
```

**Why:** 大仓 clone 慢时 API 是唯一选择，但踩坑成本高
**How to apply:** 用 API 提 PR 前逐项检查这 4 个坑


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