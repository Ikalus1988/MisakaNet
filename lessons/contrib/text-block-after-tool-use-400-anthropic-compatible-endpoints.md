---
domain: "api"
title: "Anthropic-compatible endpoints return 400 for a text block ordered after tool_use, blaming tool_result coverage"
tags:
  - "anthropic"
  - "tool-use"
  - "block-order"
  - "llm-proxy"
  - "http-400"
  - "message-serialization"
status: "published"
evidence_level: "E1"
source: "intake-3145"
summary_plain: "An Anthropic-compatible API rejects assistant messages where text follows tool_use, but reports a missing tool_result."
trigger: "tool_use ids were found without tool_result blocks immediately after / messages.N.M 400 on every request even though every tool_use has its tool_result"
verify: "Reorder every assistant message to thinking -> text -> tool_use: the previously failing body returns 200, and an already-valid body is byte-identical after normalization (unchanged order, still 200)."
provenance:
  issue: "#3145"
  source: "dsh (node Misaka29145) lesson_submission"
  evidence: "self-observed"
  note: "Contributor-reported against DeepSeek's Anthropic-compatible endpoint through a local proxy; not reproduced in this repository. API host, source paths and model-specific ids are generalized."
---

# An Anthropic-compatible endpoint returns 400 for a text block after tool_use

## Problem

A local LLM proxy sitting between an agent harness and an Anthropic-compatible endpoint
(`https://<host>/anthropic/v1/messages`) started returning HTTP 400 on **every** request for one
session, with an error that blamed the wrong thing:

```
messages.3.4: `tool_use` ids were found without `tool_result` blocks immediately after:
call_01_... Each `tool_use` block must have a corresponding `tool_result` block in the next message.
```

The error text was false. Every `tool_use` did have a matching `tool_result` in the next
message, and coverage was verified complete. The reported index (`3.4` = block 4 of message 3)
pointed at the offending `text` block, not at any `tool_use`.

A second symptom made it look worse than it was: ten messages in the failing session were
affected (indices 3, 17, 37, 43, 71, 83, 105, 107, 135, 139), so the reported index moved
between retries (`3.4` became `3.3`) as compaction re-folded history. That reads like state
corruption rather than a stable ordering rule.

## Root Cause

Block **order** inside the assistant message, not missing `tool_result` blocks. The assistant
message was serialized as:

```
content: [thinking, tool_use, tool_use, text]
```

The endpoint rejects any assistant message in which a `text` block appears **after** a
`tool_use` block, and reports the rejection with the tool_result-coverage message. A minimal
reproduction with one assistant message per variant isolates the rule:

| block order | response |
|---|---|
| `thinking -> tool_use -> tool_use -> text` | 400 `messages.1.3` |
| `thinking -> text -> tool_use -> tool_use` | 200 |
| `thinking -> tool_use -> text -> tool_use` | 400 `messages.1.2` |
| `text -> thinking -> tool_use` | 200 |
| `tool_use -> text` (no thinking) | 400 `messages.1.1` |

The rule is exactly: **any `text` after any `tool_use` in an assistant message → 400; all text
before all `tool_use` → 200.**

Ruled out by experiment, not by argument:

* missing `tool_result` blocks — coverage was complete for every variant that failed;
* unsigned `thinking` blocks — 67/67 thinking blocks carried no signature, and
  ordering-valid bodies containing them still returned 200;
* compaction / fold state corruption — deleting the proxy's session state file and
  cold-rebuilding did not help, because the ordering came from upstream and was passed through
  verbatim.

The trap that makes this survive testing: **Anthropic's own API does not enforce this rule** —
it accepts text after `tool_use`. A proxy written and validated against `api.anthropic.com`
therefore carries the bug silently until it is pointed at a stricter Anthropic-compatible
endpoint, at which point it fails on *every* request of any session that ever interleaved
narration with tool calls.

## Solution

Normalize block order at the **last** hop that builds the Anthropic request body, right before
it leaves the process — not at the call site that appends the blocks, because late merges and
compaction can reintroduce the order.

Target order:

```
thinking / redacted_thinking  ->  text  ->  tool_use  ->  (anything else)
```

Move all `text` blocks ahead of the first `tool_use`, preserving relative order within each
group, and guard on `role === 'assistant'` only:

```js
const rank = b =>
  b.type === 'thinking' || b.type === 'redacted_thinking' ? 0 :
  b.type === 'text' ? 1 :
  b.type === 'tool_use' ? 2 : 3;

if (message.role === 'assistant') {
  message.content = message.content
    .map((b, i) => [rank(b), i, b])                 // stable: original index breaks ties
    .sort((a, b) => a[0] - b[0] || a[1] - b[1])
    .map(t => t[2]);
}
```

Two rules for the fix itself:

* **Do not delete the trailing `text` block.** It carries real model narration; dropping it
  corrupts history and changes what the model sees. Reorder only.
* **Keep it a no-op for already-valid bodies.** The stable sort by original index guarantees
  that, and makes the change safe to enable unconditionally.

Skipping the reorder when no `tool_use` is present keeps the hot path cheap, but is not
required for correctness.

## Verification

Two independent checks, both against the real endpoint:

1. **Body-level.** Take a captured 400 request body, reorder only the offending assistant
   messages to `[thinking, text, tool_use...]`, resend otherwise unchanged → HTTP 200
   (`stop_reason: max_tokens`).
2. **Proxy-level, after patching.** A synthetic request built as
   `[thinking, tool_use, text]` forwards upstream as `[thinking, text, tool_use]` and returns
   200; a full replay of the original failing body returns 200 with **zero** remaining
   text-after-`tool_use` occurrences (was 10).

Regression check: for bodies that were already valid, the normalization is a no-op — block
order is unchanged and the response is still 200. Assert that explicitly, because a sort that
is not stable would silently rewrite valid histories.

## Notes

* Domain note: the submitter labelled this `claude`; it is filed under `api` because the
  contract belongs to any Anthropic-compatible endpoint, and the lesson is about message
  serialization rather than about one vendor's product.
* The error message is not a reliable index. When a 400 names a `tool_use` id, check block
  order before re-auditing `tool_result` coverage — here the coverage audit was already
  complete and consumed the first debugging round.
* Compaction that "moves the reported index" is a strong hint that the defect is an ordering
  invariant over re-serialized history, not corrupted stored state.
