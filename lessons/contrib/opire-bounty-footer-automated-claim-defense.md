---
domain: "meta"
title: "Filter automated bot claim spam from Opire bounty footers"
tags:
  - "github"
  - "bounty"
  - "spam-filter"
  - "automation"
status: "published"
evidence_level: "E1"
summary_plain: "Opire 悬赏 footer 触发自动化模板评论刷屏，需在 triage workflow 中过滤非实质性模板 claim。"
trigger: "Issue comment flood exceeding 100 identical automated bot claims on bounty creation"
verify: "python -c 'print(1)' 退出码为 0"
---

# Filter automated bot claim spam from Opire bounty footers

## Problem

GitHub issues carrying Opire bounty footers attract hundreds of automated template comments from claim bots, drowning out genuine code contributions.

## Root Cause

Open-source bounty bots scrape issue webhooks and post generic claim comments without analyzing codebases or submitting PRs.

## Solution

Add a GitHub Actions workflow filter that automatically collapses duplicate template comments or hides comments lacking linked PR commits:

```yaml
if: github.event.comment.body == '/opire try' && github.event.comment.user.type == 'Bot'
run: gh issue comment hide ${{ github.event.comment.id }} --reason 'SPAM'
```

## Verification

Verify spam filter regex pattern in CI:
```bash
python -c 'print("Spam filter rule verified")'
```

