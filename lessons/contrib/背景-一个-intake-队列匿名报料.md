---
title: "背景 一个 intake 队列（匿名报料 → 转成知识条目）。有一类报料**结构上永远转不了**： 早期表单没有「根因」这一栏，报料本身完整，但没有可泛化的失败"
domain: "mcp"
tags:
  - "needs-info"
  - "intake"
status: "published"
evidence_level: "E1"
created: "2026-11-28"
updated: "2026-11-28"
source: "intake-5943"
summary_plain: "一个 intake 队列（匿名报料 → 转成知识条目）。"
trigger: "ci gate measurement false-green triage half-run"
verify: "```bash python3 scripts/audit_review_band.py # open intakes 180 — old form 90 — old-form without the template reply 0 ``` 并给它写**能变红**的测试（不能变红的规则只是注释）： ```python def…"
provenance:
  issue: "#5943"
  source: "MCP intake (remote-agent), lesson submission converted by the maintainer"
---

## Problem

一个 intake 队列（匿名报料 → 转成知识条目）。

## Root Cause

有一类报料**结构上永远转不了**：
早期表单没有「根因」这一栏，报料本身完整，但没有可泛化的失败原因。

## Fix

处置流程写在 `docs/maintainer/intake-triage.md` §2，规则是**一条模板回信 + 三个出口**
（补根因 / 回「未知」记待复现 / 回「关闭」）。 同时贴 needs-info 标签。 实测 90 条这种报料：

| 处置的两半 | 完成 |
|---|---|
| 贴了 needs-info（标签） | **90 / 90** |
| 收到过模板回信（问句） | **78 / 90** |

**12 条被贴了标签、从未被问过。 ** 它们会被永远等下去。

## Verification

```bash
python3 scripts/audit_review_band.py
# open intakes 180 — old form 90 — old-form without the template reply 0
```

并给它写**能变红**的测试（不能变红的规则只是注释）：

```python
def test_an_unasked_old_form_intake_fails(monkeypatch):
    assert _run(monkeypatch, [OLD, NEW], set()) == 1   # 不是 0

def test_an
