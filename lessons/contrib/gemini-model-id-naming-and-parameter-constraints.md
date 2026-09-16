---
domain: "llm-integration"
title: "Gemini Model ID Naming and Parameter Constraints Across Providers"
status: "draft"
verification: "metadata-normalized"
{"title": "Gemini Model ID Naming and Parameter Constraints Across Providers", "domain": "llm-integration", "tags": ["gemini", "vertex-ai", "openrouter", "model-id", "api-compatibility", "naming-convention"], "status": "published", "confidence": "0.95", "created": "2026-09-16", "updated": "2026-09-16", "source": "intake-1472-intake-1473", "verified_date": "2026-09-16", "domain_expert": "AUTO", "provenance": {"issue": "#1472", "related": ["#1473"]}}
---

# Gemini Model ID Naming and Parameter Constraints Across Providers

## Problem

When calling Gemini models through different providers (Vertex AI, OpenRouter, direct Gemini API), two common failures occur:

1. **Model ID Format Error**: Vertex AI rejects bare model IDs like `gemini-3.7-flash` with HTTP 400: "Malformed publisher model name: expected format '<publisher>/<model>'"
2. **Parameter Constraint Error**: Gemini models reject frequency/presence/repetition penalty parameters with HTTP 400: "Penalty is not enabled for this model"

These failures happen because **the same model has different naming conventions and parameter constraints across different API endpoints**, and error messages don't clearly indicate the root cause.

Related issues: #1472 (Vertex AI model ID), #1473 (OpenRouter parameter constraints)

## Root Cause

### Issue 1: Model ID Namespacing

Different providers use different model ID formats:

| Provider | Endpoint Type | Model ID Format | Example |
|----------|--------------|-----------------|---------|
| **Vertex AI** | OpenAI-compatible | `<publisher>/<model>` | `google/gemini-3.7-flash` |
| **Vertex AI** | Native REST | Full resource path | `projects/<project>/locations/<location>/publishers/google/models/gemini-3.7-flash` |
| **Gemini API (AI Studio)** | Direct API | Bare model name | `gemini-3.7-flash` |
| **OpenRouter** | OpenAI-compatible | `<publisher>/<model>` | `google/gemini-3.8-flash` |

**Why this matters**: The same string `gemini-3.7-flash` works in Gemini API but fails in Vertex AI. The error message "Malformed publisher model name" doesn't tell you what format is expected.

**Failure layer**: Model name parsing at the provider gateway level. Vertex AI expects the publisher namespace prefix; Gemini API doesn't.

### Issue 2: Parameter Constraints

Gemini models have different parameter support compared to OpenAI models:

| Parameter | OpenAI GPT | Gemini | OpenRouter Gemini |
|-----------|-----------|--------|-------------------|
| `frequency_penalty` | Supported | Not supported | Rejected (HTTP 400) |
| `presence_penalty` | Supported | Not supported | Rejected (HTTP 400) |
| `repetition_penalty` | N/A | Not supported | Rejected (HTTP 400) |
| `temperature` | Supported | Supported | Supported |
| `top_p` | Supported | Supported | Supported |

**Why this matters**: Code written for OpenAI models often includes penalty parameters. When porting to Gemini (via OpenRouter or direct API), these parameters cause HTTP 400 errors. The error "Penalty is not enabled for this model" doesn't explain that you need to omit these fields entirely.

**Failure layer**: Parameter validation at the model inference layer. Gemini models don't support these sampling strategies.

## Solution

### Fix 1: Normalize Model IDs by Provider

**Three-step identification method** when you get "model not found" or "malformed model name":

1. **Identify your endpoint type**: OpenAI-compatible? Native REST? Direct API?
2. **Check the required format**: Does it need `<publisher>/<model>` or bare name?
3. **Verify with a minimal request**: Test with correct format before full integration

**Correct model ID by provider**:

```python
import os

def get_model_id(provider: str, model: str) -> str:
    """Return correct model ID format for the given provider."""
    if provider == "vertex_ai":
        # Vertex AI OpenAI-compatible endpoint
        return f"google/{model}" if not model.startswith("google/") else model
    elif provider == "gemini_api":
        # Direct Gemini API (AI Studio)
        return model.replace("google/", "")
    elif provider == "openrouter":
        # OpenRouter uses publisher/model format
        return f"google/{model}" if not model.startswith("google/") else model
    else:
        return model

# Examples:
# Vertex AI: get_model_id("vertex_ai", "gemini-3.7-flash") -> "google/gemini-3.7-flash"
# Gemini API: get_model_id("gemini_api", "google/gemini-3.7-flash") -> "gemini-3.7-flash"
# OpenRouter: get_model_id("openrouter", "gemini-3.8-flash") -> "google/gemini-3.8-flash"
```

**For Vertex AI native REST** (with project + location):

```python
def get_vertex_resource_path(project: str, location: str, model: str) -> str:
    """Full Vertex AI resource path for native REST API."""
    model_id = model if model.startswith("google/") else f"google/{model}"
    return f"projects/{project}/locations/{location}/publishers/{model_id.split('/')[0]}/models/{model_id.split('/')[1]}"

# Example:
# get_vertex_resource_path("my-project", "us-central1", "gemini-3.7-flash")
# -> "projects/my-project/locations/us-central1/publishers/google/models/gemini-3.7-flash"
```

### Fix 2: Omit Penalty Parameters for Gemini

**Detection and removal**:

```python
def sanitize_params_for_gemini(params: dict, model: str) -> dict:
    """Remove unsupported penalty parameters for Gemini models."""
    is_gemini = "gemini" in model.lower()
    
    if is_gemini:
        # Gemini doesn't support these penalties
        unsupported = ["frequency_penalty", "presence_penalty", "repetition_penalty"]
        return {k: v for k, v in params.items() if k not in unsupported}
    
    return params

# Example:
# params = {"temperature": 0.7, "frequency_penalty": 0.5, "presence_penalty": 0.3}
# sanitize_params_for_gemini(params, "gemini-3.7-flash")
# -> {"temperature": 0.7}
```

**Alternative: Use provider-specific presets**:

```python
GEMINI_PRESETS = {
    "default": {
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 1024,
        # No penalty parameters
    }
}

def get_params_for_model(model: str) -> dict:
    """Return safe default parameters for the given model."""
    if "gemini" in model.lower():
        return GEMINI_PRESETS["default"].copy()
    else:
        # OpenAI-style defaults
        return {
            "temperature": 0.7,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "max_tokens": 1024,
        }
```

## Verification

### Test 1: Model ID Format (Vertex AI)

```bash
# WRONG: Bare model ID will fail
# curl with gemini-3.7-flash -> HTTP 400

# CORRECT: Use google/gemini-3.7-flash for OpenAI-compatible endpoint
curl -X POST "https://us-central1-aiplatform.googleapis.com/v1/projects/my-project/locations/us-central1/endpoints/openapi" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{"model": "google/gemini-3.7-flash", "messages": [{"role": "user", "content": "Hello"}]}'
```

**Success criteria**: HTTP 200 with generated content in response.

### Test 2: Parameter Constraints (Gemini)

```python
import requests

# WRONG: Includes penalty parameters -> HTTP 400
response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": "Bearer YOUR_KEY"},
    json={
        "model": "google/gemini-3.8-flash",
        "messages": [{"role": "user", "content": "Hello"}],
        "frequency_penalty": 0.5,  # Gemini doesn't support this
    }
)

# CORRECT: Omit penalty parameters -> HTTP 200
response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": "Bearer YOUR_KEY"},
    json={
        "model": "google/gemini-3.8-flash",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
        "top_p": 0.9
    }
)
```

**Success criteria**: HTTP 200, no penalty-related errors.

### Test 3: Provider Detection

```python
# Verify model ID normalization
assert get_model_id("vertex_ai", "gemini-3.7-flash") == "google/gemini-3.7-flash"
assert get_model_id("gemini_api", "google/gemini-3.7-flash") == "gemini-3.7-flash"
assert get_model_id("openrouter", "gemini-3.8-flash") == "google/gemini-3.8-flash"

# Verify parameter sanitization
params = {"temperature": 0.7, "frequency_penalty": 0.5}
sanitized = sanitize_params_for_gemini(params, "gemini-3.7-flash")
assert "frequency_penalty" not in sanitized
assert sanitized["temperature"] == 0.7
```

## Notes

### Edge Cases

1. **Model name variations**: Some models use different naming (e.g., `gemini-pro` vs `gemini-3.7-flash`). Always check provider documentation for exact model IDs.

2. **Regional availability**: Vertex AI models are region-specific. The full resource path includes `<location>` which affects availability and pricing.

3. **API version differences**: Gemini API v1 vs v1beta may have different model IDs. Pin your API version explicitly.

4. **OpenRouter model mapping**: OpenRouter may use slightly different model IDs than direct Gemini API. Check their model list for exact strings.

### Related Issues

- #1472: Vertex AI bare model ID rejection
- #1473: OpenRouter Gemini penalty parameter rejection

### Verification Status

**Not tested with live API calls**. The solution is based on error message analysis and provider documentation. Verification commands are provided for users to test in their environment.

---

*Lesson created by AUTO (AI Agent) | Bilingual Chinese-English capability | 2026-09-16*
