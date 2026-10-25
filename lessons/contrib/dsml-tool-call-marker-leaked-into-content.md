---
title: "DeepSeek-Family Model Leaks Tool Calls as DSML Text Markers into content"
domain: "llm"
tags:
  - "tool-calling"
  - "deepseek"
  - "content-parsing"
  - "long-context"
  - "retry"
  - "llm-degeneration"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: '模型偶尔把工具调用写成带全角竖线的文本标记混进正文，客户端没识别就当成普通回答，这一轮等于什么都没执行。'
trigger: "DSML tool_calls invoke fullwidth U+FF5C marker leaked into content no structured tool_calls finish reason stop"
verify: '含全角竖线 DSML 标记的正文被判为 unparsed_tool_call 并允许重试；而正文提到工具名、代码块里出现 <invoke> 的正常文本不被判错'
source: "intake-3095"
provenance:
  issue: "#3095"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

A DeepSeek-family model reached through a third-party channel occasionally emits its tool-call protocol as **plain text inside `content`**. The client does not parse it, so that turn executes no tool at all and the UI renders the markers as ordinary prose.

The marker shape is angle brackets plus the **fullwidth vertical bar U+FF5C**, not the ASCII pipe:

```
<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="...">
```

Observed shape, quoted from the report:

```
assistant content 中出现 `<｜｜DSML｜｜tool_calls>` 文本，无结构化 tool_calls，finish reason 为 stop
```

Frequency and pattern from the same session: 200+ tool calls behaved normally, and only an occasional turn degraded. Two regularities were observed — the degradation only appeared on the **first step of each turn**, and it appeared on **consecutive turns once the context had accumulated to roughly 180k tokens**.

## Root Cause

The model's structured tool-call channel degenerates into ordinary text tokens under long context, so the marker that would normally be a parsed field ends up inside `content`. Because `finish_reason` is still `stop` and the content is non-empty, the client's "no tool calls, but there is prose" branch classifies the turn as a normal assistant reply: it is saved, shown to the user, and never retried. The turn is lost silently — there is no exception to catch.

The second half of the cause is string matching. A detector written against the ASCII pipe (`|`) never matches this output, because the model emits U+FF5C (`｜`). The two characters are visually near-identical in most chat fonts, which is why the marker survives a manual glance at the transcript.

Evidence level, per the reporter: this is a correlation, not an instrumented causal proof — same model and channel fine for 200+ calls, degradation on the first step of a turn and after ~180k tokens. Not given by the reporter — 报料者未给出，需复现确认: why specifically the first step of a turn, whether the fullwidth bar originates from the model or from the gateway's markdown normalization, and the exact token threshold at which degradation starts.

## Solution

On the branch where the assistant returns **no tool call but non-empty content**, test the prose for an unparsed tool-call marker before persisting it. If it matches, treat the turn as a failure (`unparsed_tool_call`) and allow a bounded retry, instead of storing the marker as a normal reply.

Keep the pattern narrow so ordinary prose is not caught:

```js
const UNPARSED_TOOL_CALL_RE =
  /<\s*\/?\s*[|｜]{1,2}\s*(?:DSML\s*[|｜]{1,2}\s*)?(?:tool_calls|invoke)\b/i;
```

Why each part is there:

- `[|｜]{1,2}` accepts the ASCII pipe, the fullwidth U+FF5C, or a doubled pair — the observed output uses `｜｜`.
- The pattern is anchored on `<` followed by an optional `/` and then a bar. So `<invoke>` alone does not match: a lesson or a code block that merely mentions `<invoke>` stays safe.
- `(?:DSML\s*[|｜]{1,2}\s*)?` keeps the `DSML` segment optional, so a marker emitted without it is still caught.

Two operating rules that go with the fix:

- Run the check **before** persistence, and cap the retry (one retry is enough in practice; an unbounded retry loop turns a degraded model into an expensive one).
- Do not surface the raw markers to the user on the final attempt. A wall of `<｜｜DSML｜｜...>` reads as a client bug, which is what it is — report it as a failed turn.
- Control context length and compress in time. Long context is the one variable the reporter's observations correlate with, and it is the only one you can act on cheaply.

## Verification

Reporter's criteria: build assistant prose that contains a fullwidth-bar DSML marker and assert it is classified as an error rather than a normal reply; then assert that ordinary text is **not** misclassified — prose that merely mentions a tool name, and a code block that contains `<invoke>`.

Run both directions, because the failure mode this guard introduces is a false positive on legitimate prose that discusses tool calls (documentation, diffs, lessons about this very bug).

Not given by the reporter — 报料者未给出，需复现确认: a captured real degraded turn (streaming and non-streaming each) replayed through the detector, and the measured token count at which degradation first appears.
