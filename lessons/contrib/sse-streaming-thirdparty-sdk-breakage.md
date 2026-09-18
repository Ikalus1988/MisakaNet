---
domain: "llm"
title: "Third-Party SDK SSE Streaming Breakage: Proxy Buffering vs Accept Mismatch"
tags:
  - "sse"
  - "streaming"
  - "openrouter"
  - "sdk"
  - "proxy"
  - "timeout"
status: "published"
evidence_level: "E1"
source: "mcp-intake-1555"
evidence_refs:
  - "issue:#1555"
provenance:
  source: "mcp-intake-1555"
  issue: "#1555"
  evidence: "reported"
summary_plain: "AI 流式回答经第三方 SDK 调用时卡死超时，多半是中间代理缓冲或请求头不对，用 curl 直连可判别。"
trigger: "SSE streaming context deadline exceeded third-party SDK"
verify: "curl -N 直连逐块输出 data: 帧且 SDK 端同样逐块产出，不再触发首包超时"
---

# Third-Party SDK SSE Streaming Breakage: Proxy Buffering vs Accept Mismatch

## Problem

Streaming chat completions issued through an OpenRouter-style SDK pointed at a
third-party base URL (`nano-gpt.com`) fail with `context deadline exceeded`,
while the **same prompt with `stream: false` succeeds**. Minimal reproduction
conditions:

- Client: OpenRouter SDK (or any OpenAI-compatible SDK) with `stream: true`.
- Endpoint: a third-party gateway (`nano-gpt.com`) rather than the SDK vendor's
  own API, possibly reached through a corporate proxy or CDN.
- Failure mode: no token is ever yielded; the call hangs until the client-side
  deadline fires. Non-streaming calls and unrelated endpoints are unaffected.

The intake (#1555) additionally notes two request-shape details on the failing
path: the client sent `Accept` with a deprioritized streaming value
(`text/event-stream;q=0`) and there was no `session_id` gating, so stream
affinity across the gateway could not be established.

## Root Cause

Two distinct mechanisms produce the identical symptom (hang, then deadline),
which is why this class of failure is systematically misdiagnosed:

### (a) A middlebox buffers the SSE stream into one response

Proxies, API gateways, and CDNs commonly buffer upstream responses to inspect,
compress, or log them. SSE (`Content-Type: text/event-stream`) requires the
opposite: every chunk must be flushed to the client immediately. When a proxy
buffers, the client waits for the first `data:` frame while the proxy waits
for the upstream to finish — a silent deadlock that only ends when the client
deadline fires. Typical enablers: nginx `proxy_buffering on` (default),
`gzip` on streaming routes, CDN "optimize" features, corporate MITM proxies.

### (b) The client parses `text/event-stream` as a non-streaming body (or vice versa)

The SDK (or user code around it) may:

- send an `Accept` header that deprioritizes or omits streaming
  (`Accept: text/event-stream;q=0`, or plain `application/json`), so the
  gateway answers with a buffered/non-streamed body while the client waits on
  an event parser that never sees a frame boundary;
- read the whole body (`resp.json()` / `await resp.text()`) instead of
  iterating `data:`-delimited frames, which hangs identically when the server
  *does* stream and never closes the connection until `[DONE]`;
- skip per-request stream affinity (`session_id` or equivalent) that the
  gateway needs to pin chunks of one stream to one upstream connection.

### Why they look the same, and how to tell them apart

Both present as "streaming hangs, non-streaming works". The discriminator is a
direct `curl -N` probe against the origin with `stream: true`:

| Probe result | Meaning | Next step |
| --- | --- | --- |
| `curl -N` also hangs / times out | Server side or middlebox (case a, or gateway refusing to stream) | Fix headers first; if still hung, disable buffering on the path |
| `curl -N` prints `data:` frames immediately | Transport is fine; the SDK/client parsing is at fault (case b) | Fix the client parser, `Accept` header, and timeouts |

`curl -N` (`--no-buffer`) is essential: without it, curl itself buffers and
every origin looks broken.

## Solution

Apply in order; stop at the first step that restores incremental output.

### Step 1 — Send the correct streaming request shape

```bash
curl -N https://nano-gpt.com/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "Authorization: Bearer $NANO_GPT_KEY" \
  --max-time 60 \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Say hi."}],"stream":true}'
```

Requirements: `Accept: text/event-stream` with no `q=0` downgrade,
`Content-Type: application/json`, `stream: true` in the JSON body, and a
generous `--max-time` (the deadline must exceed time-to-first-token, not just
average throughput). In SDK code, set the vendor's streaming flag explicitly
and pass through any gateway-required affinity field (`session_id` or
equivalent) instead of letting defaults drop it.

### Step 2 — Parse `data:` frames incrementally, handle `[DONE]`

```python
import json


def iter_sse_text(lines):
    """Yield text deltas from raw SSE lines; stop cleanly at [DONE]."""
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(":"):  # keep-alive / comment frame
            continue
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if payload == "[DONE]":
            return
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue  # partial frame; wait for the next chunk
        for choice in event.get("choices", []):
            delta = choice.get("delta", {}).get("content")
            if delta:
                yield delta
```

Never call `response.json()` on a streaming body: a stream has no end until
`[DONE]`, so whole-body reads hang by construction.

### Step 3 — Split your timeouts and add reconnects

- **First-token timeout** (e.g. 20–30 s): fires only when *nothing* arrives;
  this is the hang detector for case (a).
- **Idle-between-chunks timeout** (e.g. 30–60 s) plus an overall ceiling.
- **Reconnect with backoff** (3 attempts, exponential, jitter): transient
  gateway stalls recover; persistent first-token timeouts confirm a buffering
  problem, not a blip.

### Step 4 — Turn off buffering on the proxy path

For self-managed nginx/API gateways on the route:

- `proxy_buffering off;` and `proxy_cache off;` for the streaming location.
- Forward (or set) `X-Accel-Buffering: no` and avoid `gzip` on
  `text/event-stream`.
- Corporate proxy users: verify `https_proxy`/`HTTPS_PROXY` reachability to
  the gateway host first, and confirm the proxy does not re-chunk or hold
  `text/event-stream` bodies.

### Step 5 — Fallback branch: disable streaming deliberately

If the gateway demonstrably cannot stream (Step 1 probe hangs even with
correct headers and no proxy in path), set `stream: false` and accept one-shot
responses. A working non-streaming call beats a broken streaming one; revisit
when the gateway advertises SSE support.

## Verification

The parser above is verifiable offline with synthetic SSE bytes — no network
needed. Save the check and run it with `python3`:

```python
import json
from io import StringIO


def iter_sse_text(lines):
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(":"):
            continue
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if payload == "[DONE]":
            return
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        for choice in event.get("choices", []):
            delta = choice.get("delta", {}).get("content")
            if delta:
                yield delta


frames = [
    ": ping keep-alive\n",
    'data: {"choices": [{"delta": {"content": "Hel"}}]}\n',
    'data: {"choices": [{"delta": {"content": "lo"}}]}\n',
    "data: [DONE]\n",
]
assert "".join(iter_sse_text(StringIO("".join(frames)))) == "Hello"

# Truncated frame must not raise; the next chunk completes the sentence.
partial = ['data: {"choices": [{"delta": {"content": "Hi"}}', "data: [DONE]\n"]
assert list(iter_sse_text(partial)) == []
print("SSE parser check passed")
```

Expected result: `SSE parser check passed` on stdout with exit code 0.

Against a live gateway, run the Step 1 `curl -N` probe with the same prompt
used by the SDK and compare: both should emit `data: {"choices": ...}` frames
incrementally, ending with `data: [DONE]`. If curl streams but the SDK does
not, the fault is case (b); if both hang, it is case (a).

This lesson was transcribed from intake report #1555 and the offline parser
check above; it was **not** live-tested against `nano-gpt.com`, so treat the
gateway-specific header details as a starting probe, not a confirmed capture.

## Notes

- Related lesson: `vertex-ai-streaming-response-sse.md` covers robust chunk
  assembly (multi-byte splits, boundary accumulators) once bytes *do* flow;
  this lesson covers the prior question of why nothing flows at all.
- `Accept: ...;q=0` means "only if nothing else is available" per RFC 7231 —
  never send it for a stream you actually want.
- Timeouts measure different things: connect, first token, idle gap, total.
  A single "30 s timeout" conflates all four and mislabels every slow stream
  as a failure.
