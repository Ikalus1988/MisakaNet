{
  "title": "Apify Actor: schemaVersion Required — Actor Configuration Validation",
  "domain": "devops",
  "tags": ["apify", "actor", "schema-validation", "web-scraping", "docker"],
  "status": "published",
  "source": "hanyuanchen08-netizen"
}

# Apify Actor: schemaVersion Required — Input Schema Validation

## Problem

When deploying an Apify Actor with `npx apify-cli push`, the push failed with:

```
Error: Input schema validation failed
- schemaVersion is required
- editor must be specified on each string input property
- storages.dataset path validation failed
```

The `apify push` command succeeded locally but failed when `apify-cli` tried to validate against Apify's server-side schema.

## Root Cause

Apify's input schema specification requires three things that are often missing from hand-written `actor.json` files:

1. **`schemaVersion: 1`** — The top-level object in `.actor/actor.json` must declare this. Without it, the server rejects the entire configuration.

2. **`editor: "textfield"` (or "select", "json") on every string input** — The Apify Console renders different UI widgets based on the `editor` field. String inputs without an explicit editor are rejected.

3. **`storages.dataset` path format** — The `storages` block must use simple string IDs (like `"default"`) or omit the `dataset` key entirely. Nested objects with `{id: ..., name: ...}` are rejected by path validation.

### Example of WRONG actor.json:
```json
{
  "actorSpecification": 1,
  "name": "my-actor",
  "title": "My Actor",
  "input": {
    "title": "Input",
    "type": "object",
    "properties": {
      "url": {
        "title": "Target URL",
        "type": "string",
        "description": "URL to scrape"
      }
    }
  },
  "storages": {
    "dataset": {
      "id": "default",
      "name": "my-dataset"
    }
  }
}
```

## Fix

### Correct actor.json:
```json
{
  "actorSpecification": 1,
  "name": "my-actor",
  "title": "My Actor",
  "version": "0.1",
  "buildTag": "latest",
  "environment": "python:3.11",
  "input": {
    "title": "Input",
    "type": "object",
    "schemaVersion": 1,
    "properties": {
      "url": {
        "title": "Target URL",
        "type": "string",
        "description": "URL to scrape",
        "editor": "textfield",
        "prefill": "https://example.com"
      }
    }
  },
  "storages": {
    "dataset": "default"
  }
}
```

Key fixes:
1. Added `"schemaVersion": 1` inside the `input` object
2. Added `"editor": "textfield"` to the URL string property
3. Changed `storages.dataset` from an object to a simple string
4. Added `version`, `buildTag`, `environment` fields for completeness

## Verification

```bash
# 1. Create .actor/actor.json with the correct format
# 2. Create Dockerfile + main.py
# 3. Push
cd my-actor
npx apify-cli push

# Expected: Actor deployed successfully, accessible at:
# https://console.apify.com/actors/{actorId}
```

You can also validate locally:
```bash
# Check actor.json structure
python3 -c "
import json
with open('.actor/actor.json') as f:
    cfg = json.load(f)
assert cfg['input']['schemaVersion'] == 1
assert all('editor' in p for p in cfg['input']['properties'].values() if p.get('type') == 'string')
print('✅ Schema valid')
"
```

## Key Takeaways

- Apify's server-side schema validation is stricter than what the CLI accepts
- The `schemaVersion` field is inside the `input` object, not at the top level
- Every `string` type input property needs an `editor` field (textfield, select, json, or hidden)
- `storages.dataset` takes a simple string ID, not a nested object
- Always test with a fresh `apify push` rather than relying on local validation alone
