---
domain: "mcp"
title: "An undocumented vendor validator rejects your payload: determine the rules empirically, do not guess the enum"
tags:
  - "integration"
  - "api-validation"
  - "undocumented-spec"
  - "enum-guessing"
  - "error-message"
status: "draft"
created: "2026-10-28"
updated: "2026-10-28"
summary_plain: "对接方的配置校验规则没有文档，报错只说「格式不正确」。不要猜字段取值——用最小变更试探法逐项确定规则，并把确定下来的结果写成对方向可回读的规格。"
trigger: "提交配置 → 只回「连接器配置格式不正确，请检查后重试」→ 无字段名、无期望值、无路径"
verify: "每次只改一个字段的构造，记录接受/拒绝；把接受集写成表格，逐项可复现"
evidence_level: "E0"
evidence_refs:
  - "issue:#3926"
provenance:
  source: "MCP intake question #3926 (claude-code)"
  contributor: "zsxh1990"
  evidence: "**not verified against the vendor** — no access to its schema, source, or a running instance. This lesson is the method for determining an undocumented validator's rules, not a statement of what the vendor's rules are. Every concrete question in #3926 (transport 取值、url 是否必须内网域名、header_inputs 的字段校验) is explicitly **unanswered** here."
---

# An undocumented vendor validator rejects your payload: determine the rules empirically, do not guess the enum

## Problem

Submitting a connector config to a third-party publisher returns:

> 连接器配置格式不正确，请检查后重试

No field name. No expected value. No path. The payload:

```json
{"mcp_template": {"url": "https://…/mcp", "transport": "streamable_http",
 "header_inputs": [{"name": "Authorization", "label": "Authorization", "required": true}]}}
```

Three questions follow naturally — what the field rules are, whether `transport` takes
`streamable_http` or `streamable-http`, whether `url` must be an internal domain — and
**none of them can be answered from the error message**.

## Root Cause

The validator rejects without discriminating. A single opaque message covering every
failure mode means the caller has no gradient to descend: any change might fix it, or
none might. That turns a bounded problem (which field?) into an unbounded one (which of
my many choices?).

The secondary trap is **guessing the enum**. `streamable_http` vs `streamable-http` is
exactly the kind of thing people resolve by trying one and, if it fails, silently
switching — which sometimes works and teaches nothing, because it may have been a
different field that flipped it.

## Solution

**Minimal-change probing.** Start from the smallest payload the platform will plausibly
accept, then add exactly one thing at a time and record accepted/rejected.

1. **Establish a baseline that passes.** Send the minimal config with every optional field
   removed. If even that fails, the problem is structural (shape, nesting, required keys),
   not a value.
2. **Add one field per request.** Never vary two things. The point is to attribute the
   flip to a single change.
3. **When an enum is in doubt, probe both spellings in the same minimal context.** A
   hyphen-vs-underscore question is answered by two adjacent requests that differ only in
   that token — not by trying one, failing elsewhere, and changing your mind.
4. **Record the accepted set as a table**, not prose:

   | field | accepted | rejected | notes |
   |---|---|---|---|
   | `transport` | (probe both spellings) | | |

5. **Feed the table back to the vendor** as a spec question, and — if you are the vendor —
   make the error name the field and the expectation. "格式不正确" is a message that
   cannot be acted on.

The method does not depend on knowing the answer. It converts "I do not know the rules"
into "I have a table of what this accepts", which is checkable.

## Verification

**This lesson is E0 — nothing here has been verified against the target system.**

No access to the vendor's schema, source, or a running instance. Every concrete question in
#3926 is **unanswered**:

- what the `mcp_template` field rules actually are
- whether `transport` is `streamable_http` or `streamable-http`
- whether `url` must be a company-internal domain

What is offered is the procedure. Whoever has access can run it and should replace this
lesson with the resulting table.

## Note

The failure mode this guards against is **fabricating an answer to look useful**. A
confident "it must be `streamable-http`" is worse than "here is how to find out", because
the first one gets copied into the next three integrations.

When the error message does not discriminate, the work is to build the discrimination
yourself — and to record it so the next person does not repeat it.
