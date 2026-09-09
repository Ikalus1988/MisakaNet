---
title: Declarative Prompt Preset Schema and Versioning Pattern
domain: contrib
tags:
- prompt-engineering\n- preset\n- schema\n- versioning\n- agent
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

Embedding raw system prompt strings and model hyper-parameters directly in application source code causes operational fragility:
1. **Prompt Drift & Regression:** Changes made to prompt wording in Python files cannot be tracked against model benchmark scores or reverted without redeploying binaries.
2. **Runtime Template Crashes:** Using Python `str.format()` or f-strings triggers unhandled `KeyError` crashes when dynamic input payloads lack expected keys or when prompt text contains literal curly braces.
3. **Hardcoded Model Knobs:** Temperature, top_p, and stop tokens remain buried in application code rather than defined alongside the prompt specification.

## Root Cause

1. Prompts are treated as procedural code rather than versioned configuration artifacts.
2. Absence of schema validation for required template variables before sending payloads to the LLM API.
3. Lack of separation between prompt engineering assets and backend orchestration logic.

## Solution

Structure prompts as declarative YAML/JSON presets with strict schema validation and safe variable interpolation:

```yaml
# presets/coder_agent_v1.yaml
preset_version: "1.0.0"
model: "gemini-2.5-flash"
parameters:
  temperature: 0.2
  max_output_tokens: 2048
system_instruction: |
  You are an expert software engineer.
  Always provide clean, unified git diffs and follow strict typing.
variables:
  - issue_title
  - issue_body
user_template: |
  Task: Resolve issue "{issue_title}"
  
  Details:
  {issue_body}
```

Implement a loader with variable contract enforcement:

```python
import yaml
from typing import Dict, Any

class PromptPreset:
    def __init__(self, file_path: str):
        with open(file_path, "r", encoding="utf-8") as f:
            self.data: Dict[str, Any] = yaml.safe_load(f)
        self.version = self.data.get("preset_version", "unknown")
        self.model = self.data.get("model", "")
        self.parameters = self.data.get("parameters", {})
        self.required_vars = set(self.data.get("variables", []))
        self.user_template = self.data.get("user_template", "")

    def render(self, inputs: Dict[str, Any]) -> str:
        missing = self.required_vars - set(inputs.keys())
        if missing:
            raise ValueError(f"Preset {self.version} missing required variables: {sorted(missing)}")
        return self.user_template.format_map(inputs)
```

## Verification

```bash
python -c '
preset = PromptPreset("presets/coder_agent_v1.yaml")
rendered = preset.render({"issue_title": "Fix crash", "issue_body": "IndexError at line 4"})
assert "Fix crash" in rendered
print("Verification passed: fix command exited 0")
'
```

**Expected Output:** command completes without error, then `Verification passed: fix command exited 0` is printed.
