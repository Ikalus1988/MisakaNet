---
{
  "title": "JSON parse failure handling — truncated / malformed output",
  "domain": "devops",
  "tags": ["json", "parse", "truncated", "llm", "output"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/json-parse-failure-handling.md",
  "created": "2026-08-02",
  "updated": "2026-08-02"
}
provenance:
  source: "external"
  contributor: "Unknown"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# JSON parse failure handling — truncated / malformed output

## Problem

`json.loads()` raises `JSONDecodeError` on a string that looks almost correct. Typical triggers:
- LLM wrapped JSON in a code block and added trailing prose.
- A subprocess or HTTP response was truncated mid-value.
- A number or boolean was serialized without quotes where a string was expected.

## Root Cause

Agents and tools often treat JSON as "text that starts with `{`" instead of a strict grammar. Common failure modes:
1. Trailing comma or missing closing bracket.
2. Control characters inside a string value.
3. `null` / `true` / `false` used where a string was expected (or vice-versa).
4. Streaming responses that end before the JSON is complete.

## Solution

### 1. Sanitize before parse

```bash
# Strip markdown fences and trailing commentary
python3 -c "
import sys, re, json
raw = sys.stdin.read()
# Remove ```json ... ``` blocks
raw = re.sub(r'```(?:json)?\n?', '', raw)
# Remove common LLM trailing lines
raw = re.sub(r'\nHere is the .*$', '', raw, flags=re.S)
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    print(f'PARSE_FAIL: {e}')
    sys.exit(1)
print(json.dumps(data, ensure_ascii=False))
"
```

### 2. Repair common truncation

```python
import json

def repair_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.splitlines()[:-1])
    # Balance brackets
    opens = raw.count("{")
    closes = raw.count("}")
    if opens > closes:
        raw += "}" * (opens - closes)
    elif closes > opens:
        raw = "{" * (closes - opens) + raw
    return raw.strip()
```

### 3. Validate schema after parse

```python
from jsonschema import validate, ValidationError

schema = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "domain": {"type": "string"},
        "tags": {"type": "array"},
    },
    "required": ["title", "domain"],
}

try:
    data = json.loads(repaired)
    validate(instance=data, schema=schema)
except json.JSONDecodeError as e:
    print(f"JSON error: {e}")
except ValidationError as e:
    print(f"Schema error: {e}")
```

## Verification

```bash
# 1. Known-bad input
echo '{"title": "test",}' | python3 -c "import sys, json; json.loads(sys.stdin.read())"
# Should raise JSONDecodeError

# 2. Repaired input
echo '{"title": "test"}' | python3 -c "
import sys, json
raw = sys.stdin.read()
data = json.loads(raw)
assert data['title'] == 'test'
print('OK')
"
```

## Notes

- Do not use `eval()` or `ast.literal_eval()` on untrusted input as a substitute for JSON parsing.
- For LLM outputs, request JSON-only mode when the provider supports it (`response_format: { type: "json_object" }`).
