---
title: "Vertex AI vs Gemini API: model ID naming conventions differ by provider"
domain: llm
tags:
  - vertex-ai
  - gemini
  - openrouter
  - model-id
  - naming
  - provider
status: published
created: 2026-08-21
language: en
confidence: 0.9
verified_date: 2026-08-21
provenance:
  source: "intake"
  issue: "#1472"
  contributor: "Community"
  merged_at: "2026-08-21"
  evidence: "reproduction"
---

## Problem

Calling Gemini models via different providers (Vertex AI direct, Google AI direct, OpenRouter) fails with "model not found" when using wrong ID format.

**Symptoms:**
- `google/gemini-3.8-flash` works on OpenRouter but fails on Vertex AI
- `gemini-3.8-flash` works on Google AI but fails on Vertex AI
- Error: `404 Not Found: Model gemini-3.8-flash not found`
- Or: `400 Invalid model format`

**Minimal reproduction:**
```python
# This works on OpenRouter
response = openrouter.chat.completions.create(
    model="google/gemini-3.8-flash",
    messages=[...]
)

# This FAILS on Vertex AI
response = vertex_ai.chat.completions.create(
    model="google/gemini-3.8-flash",  # Wrong format
    messages=[...]
)
```

## Root Cause

Different providers use different model ID namespaces:

| Provider | Correct ID | Wrong ID |
|----------|------------|----------|
| **Vertex AI** | `gemini-3.8-flash` | `google/gemini-3.8-flash` |
| **Google AI** | `gemini-3.8-flash` | `models/gemini-3.8-flash` |
| **OpenRouter** | `google/gemini-3.8-flash` | `gemini-3.8-flash` |

The prefix `google/` is OpenRouter's namespace convention, not Google's.

**Why it's confusing:**
- Error messages just say "model not found" — don't suggest correct format
- Documentation examples use different formats for different providers
- Some SDKs silently strip prefixes, others don't

## Solution

**Diagnosis:**
```python
# Check which provider you're using
import os
provider = os.getenv("LLM_PROVIDER", "openrouter")

# Use correct ID per provider
MODEL_IDS = {
    "vertex": "gemini-3.8-flash",
    "google": "gemini-3.8-flash",
    "openrouter": "google/gemini-3.8-flash"
}
model_id = MODEL_IDS[provider]
```

**Multi-provider abstraction:**
```python
def normalize_model_id(model: str, provider: str) -> str:
    """Strip or add provider prefix based on target."""
    if provider == "openrouter":
        if not model.startswith("google/"):
            return f"google/{model}"
    elif provider in ("vertex", "google"):
        model = model.removeprefix("google/")
    return model
```

**Configuration pattern:**
```yaml
# config.yaml
providers:
  openrouter:
    base_url: "https://openrouter.ai/api/v1"
    model_prefix: "google/"
  vertex:
    base_url: "https://aiplatform.googleapis.com/v1"
    model_prefix: ""
```

## Prevention

1. **Test with actual provider**: Don't assume OpenRouter examples work on Vertex
2. **Log the full URL**: Include model ID in request logs
3. **Validate early**: Check model ID format before sending request

## Verification

```bash
# Test each provider directly
curl -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_KEY" \
  -d '{"model":"google/gemini-3.8-flash","messages":[{"role":"user","content":"hi"}]}'

curl -X POST "https://aiplatform.googleapis.com/v1/projects/$PROJECT/locations/us-central1/publishers/google/models/gemini-3.8-flash:generateContent" \
  -H "Authorization: Bearer $VERTEX_TOKEN" \
  -d '{"contents":[{"role":"user","parts":[{"text":"hi"}]}]}'
```

## References

- [Vertex AI Model IDs](https://cloud.google.com/vertex-ai/docs/generative-ai/learn/models)
- [OpenRouter Model IDs](https://openrouter.ai/docs/models)
- [Google AI Model IDs](https://ai.google.dev/gemini-api/docs/models/gemini)
