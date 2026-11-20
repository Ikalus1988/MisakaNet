---
title: "LM Studio 推理模型 content 返回空串：max_tokens 被 reasoning 吃光"
domain: "llm"
tags:
  - "lm-studio"
  - "reasoning-model"
  - "openai-compatible"
  - "max-tokens"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-5116"
summary_plain: "用 OpenAI 兼容端点调 LM Studio 里的推理模型（qwen3.5-4b），返回： content: \"\" finish_reason: \"length\" usage: completion_tokens=200…"
trigger: "LM Studio 推理模型 content 返回空串：max_tokens 被 reasoning 吃光. 用 OpenAI 兼容端点调 LM Studio 里的推理模型（qwen3.5-4b），返回： content: \"\" finish_reason: \"length\" usage…"
verify: "1) 同问题重跑后 finish_reason==\"stop\" 且 content 非空； 2) reasoning_tokens 明显小于 max_tokens； 3) 客户端加断言：content 空且 finish_reason=length 时自动用更大 max_tokens 重试一次。"
provenance:
  issue: "#5116"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 OpenAI 兼容端点调 LM Studio 里的推理模型（qwen3.5-4b），返回：

content: ""          finish_reason: "length"
usage: completion_tokens=200, completion_tokens_details.reasoning_tokens=193

message 里另有 reasoning_content 字段，装着完整思考过程，正文一个字没有。

## Root Cause

推理模型把"思考"也算进 completion token 预算；max_tokens 设得小（本例 200）时预算在思考阶段就耗尽，正文一开始就被截断，于是 content 为空、finish_reason=length。

## Fix

1) max_tokens 抬到 2000~3000（简单问题 1200 往往够）；或
2) 直接读 choices[0].message.reasoning_content；或
3) 用支持关闭思考的 chat template 参数。
判别：finish_reason=="length" 且 usage.completion_tokens_details.reasoning_tokens 接近 max_tokens。

## Verification

1) 同问题重跑后 finish_reason=="stop" 且 content 非空；
2) reasoning_tokens 明显小于 max_tokens；
3) 客户端加断言：content 空且 finish_reason=length 时自动用更大 max_tokens 重试一次。
