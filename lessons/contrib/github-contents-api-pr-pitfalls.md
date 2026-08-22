---
{
  "title": "GitHub Contents API PR 提交的 4 个陷阱",
  "domain": "devops",
  "tags": [
    "github",
    "api",
    "contents",
    "pr",
    "base64"
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

GitHub Contents API PR 提交有 4 个陷阱：base64 换行、SHA 不匹配、ruff 空行、fork diff 膨胀。

## Root Cause

1. **base64 换行**：GitHub API 要求 base64 内容无换行，但某些编码器会自动换行
2. **SHA 不匹配**：使用错误的 blob SHA 导致 409 conflict
3. **ruff 空行**：pre-commit 格式化工具添加空行导致 diff 膨胀
4. **fork diff 膨胀**：fork 与上游差异过大导致 PR 无法 review

## Solution

**1. base64 无换行：**
```python
import base64
content_b64 = base64.b64encode(content.encode()).decode().replace('\n', '')
```

**2. SHA 正确获取：**
```python
# 先获取当前 SHA
resp = requests.get(f"{api_url}/contents/{path}", headers=headers)
current_sha = resp.json()['sha']

# 更新时使用正确的 SHA
data = {
    'message': 'Update file',
    'content': content_b64,
    'sha': current_sha,  # 必须使用当前 SHA
    'branch': branch
}
```

**3. ruff 空行：**
```yaml
# .pre-commit-config.yaml
- repo: https://github.com/psf/black
  hooks:
    - id: black
      args: ["--line-length=88"]
```

**4. fork diff 控制：**
```bash
# 定期同步上游
git fetch upstream
git rebase upstream/main
git push --force-with-lease
```

## Verification

- API 调用返回 200
- PR diff 干净（无多余空行）
- SHA 匹配无 409 conflict

## Key Points

- base64 必须无换行
- 更新文件必须使用当前 SHA
- ruff/black 格式化可能导致 diff 膨胀
- 定期同步 fork 避免 diff 过大
