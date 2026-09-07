---
title: GitGuardian 误报 Basic Auth String：教程里凭证占位符必须用尖括号，不写完整 user:pass@host
domain: security
tags:
- gitguardian
- secret-scanner
- placeholder
- basic-auth
- url_credential
- gitleaks
- pre-commit
status: published
created: '2026-08-29'
language: zh
source: intake-issue-1377
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

文档、lesson、教程里写"凭证占位符"时如果用真实 URL 形状 `https://username:TOKEN@host`，GitGuardian 会报 `Secret type: Basic Auth String`，触发：

- 仓库的 Secret Scanning alert（false positive）。
- PR 检查失败（如果开了 GitGuardian 检查）。
- gitleaks pre-commit hook 拦截。
- 团队 / maintainer 收到噪音告警，必须人工 dismiss。

典型场景：

```markdown
# 错误示范（会被 GitGuardian 命中）
git push https://[REDACTED:url_credential]@github.com/owner/repo.git
#                       └──────── 即使脱敏，仍命中"Basic Auth String" pattern ────────┘
```

```json
// lessons.json previews 字段里也命中
"preview": "git push https://username:TOKEN@github.com/..."
```

## Error

```text
GitGuardian: Secret type: Basic Auth String detected at lessons/xxx.md:32
Pattern: https?://[^:]+:[^@]+@
```

实际扫描：

- 4 个 lesson 文件 + 2 个 task JSON + lessons.json previews 全部命中。
- 全历史 40 位 `ghp_/gho_/github_pat_` token 扫描 0 命中 → 确认是**误报**。
- 但字面 `user:pass@host` URL 形状会持续触发扫描器噪音。

## What was tried

核实全历史无真实 token 后确认是误报；但保留字面形状会持续触发。

## Solution

**统一占位符格式：用尖括号 + 抽象名字，不匹配 `user:pass@host` regex：**

```markdown
# ✅ 推荐：用尖括号
git push https://[REDACTED:url_credential]@github.com/owner/repo.git
git push https://<account>:<pat>@github.com/owner/repo.git
git push https://[REDACTED:url_credential]@github.com/owner/repo.git

# ✅ 也可：拆开写
git push https://github.com/owner/repo.git
# 然后：
#   username: <your-github-username>
#   password: <your-PAT>
```

**规则：**

1. **任何 `https://xxx:yyy@` 形状的占位符必须用尖括号或 `<placeholder>` 标记。**
2. **截断的 PAT 示例也避免完整 user:`ghp_...`@host 形状** —— 即使 `ghp_DqIF...` 是脱敏的，仍命中 regex。
3. **lesson 文件 frontmatter 的 `preview` 字段也要遵守** —— 它进 `lessons.json`，等于把 pattern 扩散到 1 个文件之外。
4. **task JSON 的示例同样要改**。

**写完后用下面 grep 自检：**

```bash
# 找出所有可能的 user:pass@host 形状（排除尖括号包围的）
git grep -nE 'https://[^<\s"]+:[^<\s"]+@' \
  -- '*.md' '*.json' ':!lessons/en/' ':!docs/'

# gitleaks 本地扫一遍
gitleaks detect --source . --no-banner
```

## Verification

```bash
# 1. 全仓库扫不到 user:pass@host 形状（排除尖括号、占位符）
git grep -nE 'https://[^<\s"]+:[^<\s"]+@' -- '*.md' '*.json'

# 2. JSON 文件仍可解析
python3 -c "import json; d=json.load(open('data/lessons.json')); print(f'{len(d)} lessons parsed')"

# 3. gitleaks pre-commit 通过
gitleaks detect --source . --no-banner --redact
echo "Verification passed: gitleaks clean"
```

**Expected Output:** grep 无命中 + JSON 解析成功 + gitleaks `no leaks found`。

## Related经验

- 同样的占位符规则适用于 AWS key（`AKIA...`）、Slack token（`xoxb-...`）、OpenAI key（`sk-...`）—— 用尖括号 `<aws_access_key>`、`<slack_bot_token>`、`<openai_key>` 替代完整字符串。
- 如果团队已经积累了一堆历史 PR 触发 GitGuardian alert，可以用 `git filter-repo` 或 GitHub UI batch-dismiss 一次性清理（仅限确认 0 真实命中后）。
- lesson preview 字段是扩散点：写一个 lesson 影响一个 lessons.json，影响整个搜索页 + MCP 索引，所以 preview 的脱敏比正文更严格。
