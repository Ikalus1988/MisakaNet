---
title: "Vertex AI vs Gemini model ID naming conventions differ"
domain: devops
tags: [vertex-ai, gemini, model-id, configuration, llm, google-cloud]
status: published
created: '2026-09-15'
updated: '2026-09-16'
source: "intake #1472 + #1473 — bare model ID for Vertex AI chat/completions and Gemini via OpenRouter"
evidence_level: E3
provenance:
  source: "intake"
  issue: "#1472"
---

## Problem

Switching between Gemini API and Vertex AI causes "model not found" errors. A config that works with `GOOGLE_API_KEY` (Gemini API) fails with `GOOGLE_APPLICATION_CREDENTIALS` (Vertex AI), and vice versa.

## Root Cause

**Same model, different ID namespaces per provider:**

| Provider | Model ID format | Example |
|----------|----------------|---------|
| Gemini API | bare name | `gemini-2.0-flash` |
| Vertex AI | bare name (same) | `gemini-2.0-flash` |
| OpenRouter | `google/` prefix | `google/gemini-2.0-flash` |
| LiteLLM | `vertex_ai/` or `gemini/` prefix | `vertex_ai/gemini-2.0-flash` |

The trap: Vertex AI and Gemini API use the **same** bare model ID, but the authentication and endpoint are completely different. Users conflate "same model name" with "same config" and get auth errors or 404s.

## Solution

Map provider to model ID and endpoint explicitly:

```python
PROVIDER_CONFIG = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model_id": "gemini-2.0-flash",  # bare name
        "auth": "GOOGLE_API_KEY",
    },
    "vertex": {
        "base_url": "https://{region}-aiplatform.googleapis.com/v1/projects/{project}/locations/{region}/publishers/google/models",
        "model_id": "gemini-2.0-flash",  # same bare name
        "auth": "GOOGLE_APPLICATION_CREDENTIALS",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model_id": "google/gemini-2.0-flash",  # prefix required
        "auth": "OPENROUTER_API_KEY",
    },
}
```

## Verification

```bash
# 1. Test with Gemini API key
export GOOGLE_API_KEY="your-key"
python -c "
from your_module import resolve_model
m = resolve_model('gemini')
assert m['model_id'] == 'gemini-2.0-flash'
assert 'generativelanguage.googleapis.com' in m['base_url']
print('Gemini OK')
"

# 2. Test with Vertex AI credentials
unset GOOGLE_API_KEY
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
python -c "
from your_module import resolve_model
m = resolve_model('vertex')
assert m['model_id'] == 'gemini-2.0-flash'
assert 'aiplatform.googleapis.com' in m['base_url']
print('Vertex OK')
"

# 3. Verify no cross-contamination
python -c "
from your_module import resolve_model
g = resolve_model('gemini')
v = resolve_model('vertex')
assert g['base_url'] != v['base_url'], 'Endpoints must differ'
assert g['model_id'] == v['model_id'], 'Model ID can be same'
print('Isolation OK')
"
```

## Prevention

- Always pair model ID with provider name in config files
- Log the resolved model ID + endpoint at startup to catch mismatches early
- Don't assume model IDs are portable across providers — verify against each provider's model list
- Use a config validator that checks model ID format matches the declared provider