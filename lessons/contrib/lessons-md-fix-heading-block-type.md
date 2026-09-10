---
title: lessons md fix heading block type
domain: contrib
tags:
- lessons
- heading
- block
- type
status: published
created: '2026-07-06'
source: bootstrap
confidence: 0.7
domain_expert: bootstrap
verified_date: '2026-04-01'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# Document block writes: heading types are unusable, bold paragraphs are the fallback

## Problem

Writing a Markdown document through the document-block API, `paragraph` blocks are
accepted while every `heading` block fails with `code=1770001 invalid param`. Images are
worse: the API reports success and returns a real `block_id` with `blocks_created=1`, but
the token is silently emptied, so the image never renders.

Early revisions of this lesson were worse than the bug: the Problem section contained
pasted agent-transcript fragments (`[assistant] …`), one code fence was never closed, and
a results table had been flattened into loose lines. All three were cleaned up on
2026-09-11 by the content-injection/pollution scan (`scripts/injection_scan.py`) — the
knowledge below is unchanged, only its presentation was repaired.

## Observed results

```
文档共 24 个 block

=== 写入测试 ===
✅ paragraph (type=2, 字段 text):   code=0  block_id=doxcnuj1...  success
❌ heading1  (type=4, 字段 heading1): code=1770001  invalid param
❌ heading2  (type=5, 字段 heading2): code=1770001  invalid param
✅ bullet    (type=12, 字段 bullet):  code=0  success
✅ divider   (type=19):               code=0  success
⚠️ image     (type=27):               code=0 + block_id 返回，但 token 被清空 → 图片不显示
```

| 项目 | 旧结论 | 修正后 |
|---|---|---|
| heading block（type=4~6） | “heading1/2/3 不可用”（含糊） | 全部 heading type 实测均为 `1770001`，全部不可用 |
| heading2 block_type | `type=5` | 仍不可用；所有 heading 的替代方案统一改为**粗体 paragraph** |
| divider block | — | `type=19` ✅ 可用 |
| 429 Rate Limit | 认为是 API 限制 | 非硬限制，但实际批量使用中会触发，需要分批 |
| image block | “`code=0 + blocks_created=0`（静默失败）” | `code=0` + `block_id` 正常返回，但 token 被静默清空，图片不显示 |

## Final usable subset

- ✅ `paragraph` — type=2, field `text`（以及用粗体 paragraph 表达标题层级）
- ✅ `bullet` — type=12, field `bullet`
- ✅ `divider` — type=19
- ✅ 批量追加 — 每批 ≤20 个 block，且不带 `index`
- ⚠️ `image` — type=27：API 成功但 token 会被清空 → 实际不可用
- ❌ `heading` — type=4/5/6 全部返回 `1770001`

## Fix

1. Do not use heading block types; express hierarchy with **bold paragraphs** instead.
2. Batch appends: ≤20 blocks per request, omit `index`.
3. Treat images as unsupported on this path (token loss), or re-upload the image through a
   path that preserves the token.
4. Expect `429` under sustained批量写; add backoff between batches.

## Verification

```bash
# Structure check: the lesson parses and has the expected sections
grep -n "^## " lessons/contrib/lessons-md-fix-heading-block-type.md
```

**Expected output:** `## Problem`, `## Observed results`, `## Final usable subset`,
`## Fix`, `## Verification`.
