---
title: "SSE streaming fails silently when proxy buffers or client parses incorrectly"
domain: networking
tags:
  - sse
  - streaming
  - openrouter
  - proxy
  - llm
  - event-stream
status: published
created: 2026-08-21
language: en
confidence: 0.85
verified_date: 2026-08-21
provenance:
  source: "intake"
  issue: "#1555"
  contributor: "Community"
  merged_at: "2026-08-21"
  evidence: "reproduction"
---

## Problem

Calling nano-gpt.com via OpenRouter SDK with SSE streaming fails. Non-streaming calls work fine.

**Symptoms:**
- Request hangs indefinitely waiting for chunks
- Or: receives full response at once (no streaming effect)
- Or: `JSON.parse` errors on partial chunks
- No error in HTTP status (still 200)

**Minimal reproduction:**
```javascript
const response = await openai.chat.completions.create({
  model: "nano-gpt/model",
  messages: [{ role: "user", content: "Hello" }],
  stream: true
});
// Hangs here, never yields chunks
for await (const chunk of response) {
  console.log(chunk); // Never reached
}
```

## Root Cause

Two distinct failure modes with identical symptoms:

**Mode A: Proxy/gateway buffering**
- Proxy (nginx, Cloudflare, corporate proxy) buffers `text/event-stream` response
- Client waits for `Content-Length` or connection close
- SSE requires `X-Accel-Buffering: no` and `Cache-Control: no-cache` headers
- Some proxies strip these or ignore them

**Mode B: Client parsing mismatch**
- Client uses `fetch()` + `response.json()` instead of line-by-line SSE parsing
- Or: SSE parser expects `\n\n` delimiter but server sends `\r\n`
- Or: Parser treats `data:` prefix as part of JSON

**Diagnosis:**
```bash
# Test raw SSE with curl
curl -N -H "Accept: text/event-stream" \
  -H "Authorization: Bearer $KEY" \
  "https://api.example.com/v1/chat/completions" \
  -d '{"model":"x","messages":[{"role":"user","content":"hi"}],"stream":true}'

# If you see chunks arriving: server is fine, client parsing is wrong
# If nothing arrives until timeout: proxy is buffering
```

## Solution

**For proxy buffering:**
```python
# In requests, disable buffering
response = requests.post(url, json=payload, stream=True, headers={
    "Accept": "text/event-stream",
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no"
})
for line in response.iter_lines():
    if line:
        print(line.decode())
```

**For Node.js SSE parsing:**
```javascript
const response = await fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ stream: true, ... })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const text = decoder.decode(value);
  // Parse SSE format: "data: {json}\n\n"
  for (const line of text.split("\n")) {
    if (line.startsWith("data: ")) {
      const data = JSON.parse(line.slice(6));
      yield data;
    }
  }
}
```

**For OpenRouter SDK specifically:**
```python
# Ensure stream=True is passed correctly
response = client.chat.completions.create(
    model="provider/model",
    messages=[...],
    stream=True,
    stream_options={"include_usage": True}
)
```

## Prevention

1. **Test raw SSE first**: Use `curl -N` before blaming the client
2. **Check proxy config**: Add `proxy_buffering off;` in nginx
3. **Add timeout**: Don't hang forever on streaming
4. **Log raw response**: Capture first few bytes to diagnose

## Verification

```bash
# Should see incremental chunks
curl -N --max-time 10 \
  -H "Accept: text/event-stream" \
  "$API_URL" -d '{"stream":true,...}'

# Expected output (incremental):
# data: {"choices":[{"delta":{"content":"Hello"}}]}
# data: {"choices":[{"delta":{"content":" world"}}]}
# data: [DONE]
```

## References

- [MDN: Server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [OpenRouter Streaming Docs](https://openrouter.ai/docs/streaming)
