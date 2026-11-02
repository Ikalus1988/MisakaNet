---
title: "PR/issue comment bodies need a quoted heredoc — double quotes and <<EOF both expand and execute shell"
domain: "github"
tags:
  - "gh-cli"
  - "heredoc"
  - "shell-expansion"
  - "secret-leak"
  - "ci-automation"
status: "published"
evidence_level: "E2"
created: "2026-11-02"
updated: "2026-11-02"
source: "reproduced locally 2026-11-02 (bash 3.2, macOS), policy from session 1989c3e0"
summary_plain: "用 shell 拼接 PR/评论正文时，双引号和不带引号的 heredoc 都会展开变量、执行反引号，密钥和环境内容会被发到公开评论里。"
trigger: "gh issue comment body shell expansion backtick command substitution secret leak heredoc EOF quoting"
verify: "bash /tmp/heredoc_demo.sh：[1][2] 打印出 SECRET 的值（展开），[3] 打印字面量 $SECRET（不展开）"
provenance:
  source: "community"
  contributor: "zsxh1990"
  evidence: "self-observed"
---

## Problem

自动化脚本给 GitHub PR/issue 发评论时，正文常含用户可见的命令片段（`git log`、`$HOME`）和
脚本输出。用双引号拼接正文：

```bash
gh issue comment 42 --body "see \`git log\` and $SECRET"
```

shell 会在**执行前**展开 `$SECRET` 并执行反引号里的命令——正文被发出去时，密钥已经躺在公开评论里。
更隐蔽的是：`cat <<EOF`（不带引号的 heredoc）**同样会展开**，只有 `cat <<'EOF'` 是字面量。

实测三臂对照（2026-11-02，`SECRET=do-not-leak-12345`）：

```
[1] double-quoted string — expands:
key is do-not-leak-12345
[2] unquoted heredoc (<<EOF) — expands:
key is do-not-leak-12345
[3] quoted heredoc (<<'EOF') — literal:
key is $SECRET
```

## Root Cause

POSIX shell 的词法：双引号内 `$` 和反引号仍然求值；heredoc 的分隔符**不加引号**时按双引号规则
处理正文，加引号（`<<'EOF'`）才关闭一切展开。这是 shell 的设计，不是 bug——把它当成"多行字符串
字面量"是调用方的误解。

## Solution

评论/PR 正文一律走**带引号的 heredoc**：

```bash
gh pr create --repo owner/repo --title "..." --body-file - <<'EOF'
Fixes #42

Run `git log --oneline` and compare with $HOME — both stay literal here.
EOF
```

配套三条：

1. **禁止把原始命令输出直接拼进正文**（防 env dump）：输出先过 `grep -v -i 'token\|secret\|key'` 之类的
   脱敏过滤，或只粘贴结论行；
2. 反例写法（双引号 + 反引号）在 code review 里见到就拦：`--body "...\`cmd\`..."` 是泄露形态；
3. 同一规则适用于所有发往外网的文本：commit message、issue、飞书消息——凡 shell 拼接，先问
   "这段会不会被展开/执行"。

## Verification

```bash
SECRET=do-not-leak-12345 bash -c 'cat <<'"'"'EOF'"'"'
key is $SECRET
EOF'
```

预期：输出字面量 `key is $SECRET`；把 `<<'EOF'` 换成 `<<EOF` 重跑，预期输出 `key is do-not-leak-12345`
（展开 = 泄露）。三臂完整版见 `/tmp/heredoc_demo.sh` 的写法（同款脚本可自查）。

## Dedupe note

先搜后写：`misakanet_search("pull request comment heredoc template env dump secret leak")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇是该主题的第一条。

## Notes

环境：bash 3.2/5.x 行为一致；zsh 对 `<<'EOF'` 同样保持字面量。Windows 上走 Git Bash/WSL 同规则。
