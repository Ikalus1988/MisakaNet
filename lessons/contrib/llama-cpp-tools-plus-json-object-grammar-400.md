---
title: "llama.cpp returns 400 failed to parse grammar when tools and response_format are sent together"
domain: "llm"
tags:
  - "llama-cpp"
  - "grammar"
  - "response-format"
  - "tool-calling"
  - "openai-compatible"
  - "gateway"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "带 tools 又带 response_format=json_object 时 llama.cpp 直接 400 说语法解析失败，在网关剥掉后者就好。"
trigger: "Failed to initialize samplers: failed to parse grammar"
verify: "形状矩阵：仅 json_object 200、仅 tools 200 且 finish_reason=tool_calls、tools+json_object 400；补丁后原 400 形状全部 200 且 tool_calls 仍结构化"
source: "intake-3254"
provenance:
  issue: "#3254"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# llama.cpp returns 400 failed to parse grammar when tools and response_format are sent together

## Problem

A self-hosted llama.cpp `llama-server` (0.6.0-dev, started with `--jinja` and a custom chat
template) serves an OpenAI-compatible `/v1/chat/completions`. Requests that carry **both** a
non-empty `tools` array **and** `response_format={"type":"json_object"}` fail in about 0.1 s:

```json
{"error":{"code":400,"message":"Failed to initialize samplers: failed to parse grammar",
         "type":"invalid_request_error"}}
```

Each feature alone works: `response_format` only → 200, `tools` only → 200. The failure does not
depend on `tool_choice` — omitting it, `"none"` and `"auto"` all return 400.

The downstream consequence is what makes this expensive to diagnose. The agent framework
(`langchain_openai`) classifies 400 as a permanent `provider_bad_request` and does not retry, so
every role agent that has tools fails while an agent without tools runs fine. That looks exactly
like "the backend's `json_object` support regressed" or "the inference service is degrading" — and
restarting the model service does nothing, because the process state is not the cause.

## Root Cause

With `--jinja` and a tool-aware template, llama.cpp builds a **GBNF grammar** from the request so
that sampling can only produce a valid tool call. `response_format=json_object` asks for a *second*
grammar, of JSON shape. On the affected version the two are not composed into one grammar; the
resulting grammar fails to parse at sampler initialization, and the request is rejected before
generation starts — hence the sub-second 400 and the "Failed to initialize samplers" prefix.

The endpoint is otherwise healthy, which is why the single-feature probes return 200: the bug needs
the *combination*, and only a shape-matrix bisection finds it.

## Solution

### Workaround: strip `response_format` in the compatible gateway

Put the rewrite between the client and `llama-server`, and drop `response_format` when a tool list
is present:

```python
if body.get("tools") and body.get("response_format") is not None:
    body.pop("response_format")
```

Keep the JSON-ness requirement in the prompt instead (ask for "JSON only, no prose, no Markdown
fence") and validate/parse the result on your side. This trades enforcement for availability: the
server no longer guarantees JSON, so the caller must.

### Do not substitute `tool_choice="none"`

It does stop the 400, but llama.cpp then stops emitting structured tool calls: `finish_reason` is
`stop` and a bare `<tool_call>…</tool_call>` text block is left inside `content`. Any agent layer
that keys on structured `tool_calls` — including subagent-to-subagent communication — breaks
silently instead of loudly.

### Root fix

Upgrade llama.cpp to a version that can combine a tool grammar and a JSON grammar in one sampler
setup, then remove the gateway rewrite. The rewrite should stay behind a flag with a comment naming
this issue, so it is removable rather than archaeology later.

## Verification

Shape matrix measured on the endpoint (reporter's numbers):

| Request shape | Result |
|---|---|
| `response_format=json_object` only | 200 |
| `tools` only | 200, `finish_reason=tool_calls` |
| `tools` + `tool_choice="none"` | 200, but tool call degrades to raw text in `content` |
| `tools` + `response_format=json_object` (with or without `tool_choice`) | **400**, 0.118 s |

After the gateway patch:

- every previously-400 shape returns 200, and `tool_calls` is still structured;
- the multimodal path shows no regression;
- end to end, the pipeline retries the failed node (attempt 3 → 4, completed) and advances to the
  next node; the gateway log records **0** 400s in that window;
- the node's persisted JSON artifact parses directly — no Markdown fence to strip, which is the
  pass/fail signal that the prompt-level JSON constraint actually landed.

## Notes

- The reporter's version is `0.6.0-dev`; the exact commit that fixes grammar composition is not
  stated in the report, so verify the upgrade against this matrix before deleting the workaround.
- Any "works alone, 400 together" pattern in an OpenAI-compatible server is worth bisecting by
  request shape rather than by reading release notes: the failing dimension here (`tools` ×
  `response_format`) is a single cell, and a two-feature matrix finds it in four requests.
- Time-to-failure is itself a clue: a 0.1 s 400 means validation/sampler setup, not generation. A
  slow 400/500 would point at the model or the template instead.
