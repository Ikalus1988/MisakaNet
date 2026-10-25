---
title: "Before reviving a stale PR, check each half against current upstream"
domain: "github"
tags:
  - "pull-request"
  - "stale-branch"
  - "rebase"
  - "force-push"
  - "upstream-verification"
  - "dead-code"
  - "contribution-workflow"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "数月未动的 PR 别直接 rebase 再 force push：要逐个「半」核验上游是否已有更完整的实现、被改代码是否还在，只把存活的那半重做。"
trigger: "stale PR CONFLICTING CI failing rebase force push upstream already implemented narrower duplicate dead code 陈旧 PR"
verify: "每个「半」都有可复跑判据：git show <upstream>:<被改文件> 显示上游已有等价或更全实现；git grep <被改函数名> <upstream> 零命中即落点已消失"
source: "intake-3529"
provenance:
  issue: "#3529"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

陈旧（数月未动）的 PR 被要求处理 CI/合并失败时，最容易犯的错是直接 rebase 到当前上游再 force push。实测两个 PR 同时踩到两种不同情形，硬 rebase 会把不该进主线的东西塞回去：

1. **A 半已被更完整的实现取代。** PR 的 A 半（给某查询工具加可选 `namespace` 参数）在数月前提交，期间上游已合并一个更完整的实现（`namespace` + `label_selector` + `field_selector`，且处理了「同名 Jinja 全局在参数缺省时仍被定义」「strict 调用对未设可选参传 None」两个坑）。硬 rebase 会把一个更窄的重复实现叠回主线。
2. **B 半的落点已被删除。** PR 的 B 半（给某函数加 3 行类型守卫）在数月前提交，期间该函数已从主线整体删除/重构。硬 rebase 会把补丁打在死代码上，冲突且无意义。

真正还在主线存活、仍需修的是 PR 的第三部分（另一文件里的行为修复）。

报料者未给出仓库名、PR 号与被改符号的实名，已按「某查询工具」「某函数」匿名化，需复现确认。

## Root Cause

把「CI 挂了 + CONFLICTING」当成「需要 rebase + force push」的问题。冲突只是信号，它不区分三种完全不同的处置：

- 上游已用更完整的实现取代 → 你那一半应**丢弃**
- 落点代码已被删除/重构 → 补丁无意义，应**基于当前代码路径重写**
- 落点仍存活 → 这才是真正要救的那一半

把三者当一件事处理，就会把窄实现和死代码补丁一起塞回主线。

第二层原因是收口缺失：硬 rebase 之后 PR 看起来「处理完了」，但若原 PR 没写 `Fixes`，关联 issue 不会自动关闭，会一直挂在那里；这条漏网与 rebase 无关，却总是和它同时发生。

## Solution

复活陈旧 PR 前，把改动拆成独立的「半」，逐半对当前上游核验两件事：

- **(a) 上游是否已实现同一能力且更完整**——若是，丢弃自己那半，不要把窄版本叠回去。
- **(b) 被修改的目标代码是否还存在**——若已被删除或重构，不要 rebase 三行补丁到死代码上，应基于当前代码路径重写。

两条核验各配一个可复跑命令：

```bash
# (a) 上游是否已有等价或更全的实现
git show <upstream>:<被改文件>    # 再在其中查目标符号/参数

# (b) 落点是否还在
git grep <被改函数名> <upstream>
```

收口动作：

1. 能落地的部分**基于当前上游新开分支重做**（不是在旧 PR 分支上反复 rebase）。
2. 其余部分在原 PR 留下书面说明后关闭，说明写清「已被上游更全实现取代」或「落点已删除」。
3. 顺带检查关联 issue 是否因 PR 未写 `Fixes` 而一直挂着未关，在 issue 上留言指出已由哪条 PR 解决。
4. 用 fail-before / pass-after 测试锁住存活的那半，并对相邻既有套件跑一遍确认无回归。

## Verification

对每个「半」分别执行并留下可复跑判据：

- **(a)** `git show <upstream>:<被改文件>` 后查目标符号/能力，确认上游是否已有等价或更全实现。本例实测：上游文件里已能看到更全的 selector 参数与那两个边界处理。
- **(b)** `git grep <被改函数名> <upstream>` 无命中即证明落点已消失。本例实测：全仓零命中，仅剩另一模块里同名概念的另一个实现。
- **存活的那半**：只有它被基于当前上游新开分支重做，并由 fail-before / pass-after 测试锁住（无修复时断言红、有修复时绿），相邻既有套件全绿无回归。
- **收口**：原 PR 有书面说明并已关闭；因漏写 `Fixes` 而未自动关闭的关联 issue 上，有一条指出已由哪条 PR 解决的留言。

反例基准：如果动手前没有留下这两条核验的输出，那么「rebase 成功、CI 转绿」并不能说明该 PR 应该合——它只说明冲突被解决了。
