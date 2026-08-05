---
{
  "title": "OpenAI-compatible API calls (Ollama / local gateways)",
  "domain": "llm",
  "tags": ["openai", "ollama", "api", "llm", "http", "local"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/openai-compatible-api-call.md",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# OpenAI-compatible API calls (Ollama / local gateways)

## Problem

Agents assume OpenAI cloud URLs and fail against local Ollama or internal gateways. Wrong paths, missing `Authorization`, or streaming mismatch.

## Root Cause

“OpenAI-compatible” means the **shape** of `/v1/chat/completions`, not the host. Base URL, model name, and auth differ per provider.

## Solution

```python
import json, urllib.request

BASE = "http://127.0.0.1:11434/v1"  # Ollama example
url = f"{BASE}/chat/completions"
payload = {
    "model": "qwen2.5:7b",
    "messages": [
        {"role": "system", "content": "You are a precise ops assistant."},
        {"role": "user", "content": "ping"},
    ],
    "temperature": 0.2,
    "stream": False,
}
req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=120) as r:
    data = json.loads(r.read().decode())
print(data["choices"][0]["message"]["content"])
```

Cloud / gateway with key:

```python
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}
```

## Verification

```bash
curl -sS http://127.0.0.1:11434/v1/models | head
curl -sS http://127.0.0.1:11434/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2.5:7b","messages":[{"role":"user","content":"hi"}]}'
```

## Notes

- Always set timeouts; local models can be slow on first load.
- Do not log full prompts if they contain secrets.
- For earn agents, prefer small local models only when offline; paid APIs need budget caps.
