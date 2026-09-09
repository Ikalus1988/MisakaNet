---
title: Centralized LLM SDK Client Provider and Connection Pool Architecture
domain: contrib
tags:
- sdk\n- architecture\n- concurrency\n- http-client\n- connection-pool
status: published
created: '2026-09-09'
source: community
evidence_level: E2
evidence_refs:
- issue:#1571
provenance:
  source: community
  contributor: Community
  evidence: post-publication
---

## Problem

Instantiating SDK clients (such as `genai.Client()`, `openai.OpenAI()`, or `anthropic.Anthropic()`) inside individual request handlers, FastAPI routes, or agent loop steps degrades application stability and performance.

Consequences include:
1. **Socket Exhaustion:** High-frequency tasks create thousands of short-lived TCP connections, leading to `OSError: [Errno 24] Too many open files` or ephemeral port starvation (`TIME_WAIT`).
2. **Latency Overhead:** Re-creating clients forces repeated TLS negotiation and handshake handoffs, adding 120ms to 350ms of needless latency to every inference call.
3. **Configuration Drift:** API keys, base URLs, retry policies, and timeout limits become duplicated and fragmented across multiple worker files.

## Root Cause

1. Python garbage collection disposes of underlying `httpx.Client` or `urllib3.PoolManager` instances when local client variables go out of scope.
2. Developers fail to share persistent HTTP connection pools across concurrent threads or asynchronous tasks.
3. Lack of a centralized dependency injection or singleton provider architecture.

## Solution

Establish a thread-safe, centralized Client Provider with connection pooling and singleton lifecycle management:

```python
import os
import threading
from typing import Optional
from google import genai
import httpx

class CentralizedGenAIClientProvider:
    """
    Singleton provider managing a centralized LLM client instance
    with persistent connection pooling and thread-safe initialization.
    """
    _instance: Optional['CentralizedGenAIClientProvider'] = None
    _lock = threading.Lock()

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        api_key = os.environ.get("GEMINI_API_KEY", "")
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=30.0)
        http_client = httpx.Client(limits=limits, timeout=60.0)
        self.client = genai.Client(api_key=api_key, http_options={"client": http_client})
        self._initialized = True

    @classmethod
    def get_client(cls) -> genai.Client:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance.client
```

Usage in worker threads or web handlers:
```python
client = CentralizedGenAIClientProvider.get_client()
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Hello from centralized pool"
)
```

## Verification

```bash
python -c '
from sdk_provider import CentralizedGenAIClientProvider
c1 = CentralizedGenAIClientProvider.get_client()
c2 = CentralizedGenAIClientProvider.get_client()
assert c1 is c2, "Singleton violation: clients must share the identical instance"
print("Verification passed: fix command exited 0")
'
```

**Expected Output:** command completes without error, then `Verification passed: fix command exited 0` is printed.
