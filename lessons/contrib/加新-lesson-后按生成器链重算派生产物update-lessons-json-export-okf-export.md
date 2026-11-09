---
title: "加新 lesson 后按生成器链重算派生产物（update_lessons_json / export_okf / export_public_vocabula"
domain: "mcp"
tags:
  - "lesson"
  - "update"
  - "lessons"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4413"
summary_plain: "加新 lesson 后按生成器链重算派生产物（update_lessons_json / export_okf / export_public_vocabulary / gen_ranking_snapshot /…"
trigger: "加新 lesson 后按生成器链重算派生产物（update_lessons_json / export_okf / export_public_vocabula. 加新 lesson 后按生成器链重算派生产物（update_lessons_json / export_okf /…"
verify: "`--check` 输出 \"ok: docs/trust-semantics.md matches the corpus\"；重跑 CI 全部 test 腿转绿。"
provenance:
  issue: "#4413"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

加新 lesson 后按生成器链重算派生产物（update_lessons_json / export_okf / export_public_vocabulary / gen_ranking_snapshot / build_lesson_pages / sync_lesson_count），本地门禁全绿，但 PR 上全部 test 腿（跨 3 OS × 3 Python）确定性失败，audit 同步红。

## Root Cause

`docs/trust-semantics.md` 里的证据分布表是派生物，但**不在**上述自动生成链里：它由 `scripts/evidence_distribution.py` 生成并需手动贴回文档。新 lesson 进语料后分布表 stale，`tests/test_evidence_distribution.py` 断言表与语料一致 → 每条 test 腿都挂在这一个断言上。批量 PR 的 checklist 写了 "evidence distribution" 但它容易被当成 6 件套之一漏掉。

## Fix

新增 lesson 后单独跑 `python3 scripts/evidence_distribution.py`，把输出表贴进 docs/trust-semantics.md 的 Generated 注释块；用 `python3 scripts/evidence_distribution.py --check docs/trust-semantics.md` 验证。

## Verification

`--check` 输出 "ok: docs/trust-semantics.md matches the corpus"；重跑 CI 全部 test 腿转绿。
