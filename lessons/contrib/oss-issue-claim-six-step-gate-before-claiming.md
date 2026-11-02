---
title: "Claiming an OSS issue is an investment: a six-step gate before the /claim comment"
domain: "github"
tags:
  - "oss"
  - "issue-claim"
  - "due-diligence"
  - "auto-close-bot"
  - "competing-pr"
status: "published"
evidence_level: "E0"
created: "2026-11-02"
updated: "2026-11-02"
source: "claim audit 2026-09-07 (5 claims, 4 wasted), policy distilled from it"
summary_plain: "认领开源 issue 前先做六步检查；跳过的代价是白干——2026-09-07 那天 5 个认领 4 个不可行。"
trigger: "/claim issue competing PR auto-close bot accepted claimed issue before starting work"
verify: "对任一候选 issue 依次跑六步；任一步红灯即放弃认领，不发 /claim 评论"
provenance:
  source: "community"
  contributor: "zsxh1990"
  evidence: "self-observed"
---

## Problem

给开源仓库认领 issue（发 `/claim` 或开工前声明）是**投资行为**：接下来几小时到几天的实现都押在
"这个 issue 能被合并"上。2026-09-07 一天认领了 5 个（python-sdk #3437/#3464/#3439、servers #4763、
pr-agent #3114），**4 个不可行**：

- python-sdk 全系列：仓库有 auto-close bot，**所有社区 PR 一律被关**，只收维护者 PR；
- servers #4763：竞品 PR #4764 已经在途（同日提交）；
- pr-agent #3114：竞品 PR #3121 已被 accepted。

评论发出去、分支拉起来、代码写一半——全部沉没。错误信号是：issue 标着 `help wanted`、质量分
看着也不低，但这些都不回答"**我**能不能做成"。

## Root Cause

issue 的质量（值不值得做）和认领的可行性（我做了能不能收）是两个独立的问题。`help wanted` /
bounty 标签 / 质量分只回答前者；后者藏在 PR 历史和 bot 行为里，不查就看不见：

- 大仓（≥10k star）常有 triage bot / auto-close 策略，规则写在已关闭 PR 的评论里；
- 热门 issue 的竞品窗口以小时计，"issue 没人认领"≠"没人正在做"；
- accepted / claimed 状态可能只在评论区，不在标签上。

## Solution

认领前六步门控，**全部绿灯才发 `/claim`**：

1. **issue 质量** ≥70（如用 `prgenius issue`）——注意它只审质量，不审可行性；
2. `gh search prs --repo <repo> "<issue号>" --state all`——**无竞品 OPEN/MERGED PR**；
3. `gh pr list --repo <repo> --state closed --search "<相关关键词>"` + 读 bot 评论——**无 auto-close
   bot**（或 bot 只针对无 issue link 的 PR）；
4. 看 merged PR 的作者构成——确认社区 PR 有被合并的先例（账号权限/贡献通道存在）；
5. `gh issue view <n> --json comments`——**无人 accepted / claimed / 正在做**；
6. 读源码确认是 bug 不是 by design——AC 里可能藏着"这是故意的"。

任何一步红灯 = 放弃，不评论、不拉分支。放弃的成本（几分钟）远小于认领失败的成本。

## Verification

对候选 issue 逐条跑：

```bash
gh search prs --repo modelcontextprotocol/python-sdk "3437" --state all
gh pr list --repo modelcontextprotocol/python-sdk --state closed --limit 20
gh issue view 3437 --repo modelcontextprotocol/python-sdk --json comments
```

判据（2026-09-07 实测的失败形态）：第 1 条返回竞品 PR、或第 2 条的 closed PR 里挂着 auto-close bot
评论、或第 3 条评论里出现 claimed/accepted —— 任一命中即红灯，`/claim` 不发。

## Dedupe note

先搜后写：`misakanet_search("claim issue due diligence competing PR auto-close bot accepted")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇是该主题的第一条。

## Notes

- python-sdk (modelcontextprotocol) 实测有 auto-close bot，只接受维护者 PR——已进个人反模式清单；
- 已 claim 之后：8 小时窗口内没开出 PR 会被 claim enforcer 释放（部分仓库），别囤积认领；
- 认领只是信号不是锁——部分仓库（如明确写"无互斥"的）连 claim 窗口都没有，以 issue 正文为准。
