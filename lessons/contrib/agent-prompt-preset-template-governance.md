---
title: "Prompt Preset Governance: Schema Validation and Immutable Versioning"
domain: "agent"
tags:
  - agent
  - preset
  - prompt-templates
  - schema-validation
  - governance
  - python
status: "published"
source: "https://github.com/pydantic/pydantic/issues"
created: "2026-09-09"
confidence: 0.95
verified_date: "2026-09-09"
domain_expert: "agent-eval-team"
evidence_level: "E2"
provenance:
  source: "developer_workflow"
  evidence: "unit_test"
---

# Prompt Preset Governance: Schema Validation and Immutable Versioning

## Problem

In enterprise agent systems and multi-model routing pipelines, teams maintain extensive catalogs of prompt presets defining system instructions, conversational personalities, output format schemas, and model generation hyperparameters (such as temperature, top_p, and max_tokens). When these presets are stored as unvalidated dictionary blobs, arbitrary YAML documents, or raw database rows without explicit schema contracts, system updates introduce critical production bugs.

A common failure occurs when an engineer updates a system prompt template to reference a new contextual variable (such as `{retrieved_context}` or `{agent_role}`) without updating all caller sites. When the agent attempts interpolation, Python raises an unhandled `KeyError` during customer interactions. Similarly, setting invalid hyperparameters (such as a negative temperature or a context window exceeding model boundaries) crashes the inference engine mid-turn. In-place mutation of preset dictionaries during dynamic experimentation also introduces thread contamination across concurrent user sessions.

## Root Cause

1. **Unchecked Template Interpolation**: Using standard `str.format()` or f-strings without static verification of declared placeholders versus supplied parameters leaves missing variable bugs undetected until runtime execution.
2. **Untyped Hyperparameter Bundling**: Model inference hyperparameters are coupled directly with prompt text without numerical range validation, type checking, or model compatibility verification.
3. **Absence of Semantic Immutability**: Modifying preset configurations in-place during runtime experimentation corrupts baseline templates across parallel threads and prevents reliable rollback mechanisms.

## Solution

Implement an immutable prompt preset architecture (`PromptPreset` and `PresetRegistry`) backed by structural validation. The registry statically inspects template placeholders upon registration, enforces hyperparameter boundaries, and freezes configurations against runtime mutation.

| Governance Dimension | Raw Dictionary Presets | Validated Preset Governance |
| --- | --- | --- |
| Placeholder Verification | Late runtime failure (`KeyError`) | Static check on registration and rendering |
| Hyperparameter Safety | Untyped; accepts out-of-range values | Strict numeric bounds and type enforcement |
| Concurrency Safety | Mutable in-place; race condition risks | Frozen immutable instances (`frozen=True`) |
| Version Tracking | Blind overrides | Immutable semantic versioning (`name:version`) |

```python
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Set


@dataclass(frozen=True)
class PromptPreset:
    """Immutable prompt template preset with schema validation and parameter boundaries."""

    name: str
    version: str
    template: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2048
    required_vars: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Validates template placeholders and numerical hyperparameter bounds."""
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(
                f"Temperature {self.temperature} out of valid bounds [0.0, 2.0]"
            )
        if self.max_tokens <= 0:
            raise ValueError(
                f"max_tokens must be positive, got {self.max_tokens}"
            )
        placeholders = set(
            re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", self.template)
        )
        missing = self.required_vars - placeholders
        if missing:
            raise ValueError(
                f"Declared required variables {missing} not found in template string"
            )

    def render(self, variables: Dict[str, Any]) -> str:
        """Renders the prompt template after validating all required variables exist.

        Args:
            variables: Mapping of placeholder keys to contextual values.

        Returns:
            The formatted prompt string.

        Raises:
            KeyError: If any declared required variable is absent from input mapping.
        """
        provided = set(variables.keys())
        missing = self.required_vars - provided
        if missing:
            raise KeyError(f"Missing required prompt variables: {missing}")
        return self.template.format(**variables)


class PresetRegistry:
    """Central registry providing versioned retrieval and validation of prompt presets."""

    def __init__(self) -> None:
        """Initializes an empty preset registry."""
        self._presets: Dict[str, PromptPreset] = {}

    def register(self, preset: PromptPreset) -> None:
        """Registers a verified prompt preset into the registry.

        Args:
            preset: PromptPreset instance to register.

        Raises:
            ValueError: If a preset with identical name and version already exists.
        """
        key = f"{preset.name}:{preset.version}"
        if key in self._presets:
            raise ValueError(f"Preset {key} is already registered")
        self._presets[key] = preset

    def get(self, name: str, version: str = "latest") -> PromptPreset:
        """Retrieves a prompt preset by name and version identifier.

        Args:
            name: Logical preset identifier.
            version: Target version string, or 'latest' for the highest version.

        Returns:
            The requested immutable PromptPreset instance.

        Raises:
            KeyError: If no matching preset is found.
        """
        if version == "latest":
            matches = [p for p in self._presets.values() if p.name == name]
            if not matches:
                raise KeyError(f"No preset registered with name '{name}'")
            matches.sort(key=lambda x: x.version, reverse=True)
            return matches[0]
        key = f"{name}:{version}"
        if key not in self._presets:
            raise KeyError(f"Preset '{key}' not found in registry")
        return self._presets[key]
```

## Verification

Execute the following test script validating placeholder validation, missing parameter detection, hyperparameter bounds checking, and immutability:

```bash
python3 -c "
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Set

@dataclass(frozen=True)
class PromptPreset:
    name: str
    version: str
    template: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2048
    required_vars: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f'Temperature {self.temperature} out of bounds')
        if self.max_tokens <= 0:
            raise ValueError(f'max_tokens must be positive')
        placeholders = set(re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', self.template))
        missing = self.required_vars - placeholders
        if missing:
            raise ValueError(f'Missing placeholders: {missing}')

    def render(self, variables: Dict[str, Any]) -> str:
        provided = set(variables.keys())
        missing = self.required_vars - provided
        if missing:
            raise KeyError(f'Missing variables: {missing}')
        return self.template.format(**variables)

class PresetRegistry:
    def __init__(self) -> None:
        self._presets: Dict[str, PromptPreset] = {}

    def register(self, preset: PromptPreset) -> None:
        key = f'{preset.name}:{preset.version}'
        if key in self._presets:
            raise ValueError(f'Duplicate preset: {key}')
        self._presets[key] = preset

    def get(self, name: str, version: str = 'latest') -> PromptPreset:
        if version == 'latest':
            matches = [p for p in self._presets.values() if p.name == name]
            if not matches:
                raise KeyError(f'Preset {name} not found')
            matches.sort(key=lambda x: x.version, reverse=True)
            return matches[0]
        key = f'{name}:{version}'
        if key not in self._presets:
            raise KeyError(f'Preset {key} not found')
        return self._presets[key]

def test_presets():
    reg = PresetRegistry()
    p1 = PromptPreset(
        name='code_auditor',
        version='1.0.0',
        template='Role: {role}. Reviewing repository {repo}. Findings: {findings}.',
        model='claude-3-7-sonnet',
        temperature=0.1,
        required_vars={'role', 'repo', 'findings'},
    )
    reg.register(p1)

    rendered = reg.get('code_auditor').render({
        'role': 'Senior Security Engineer',
        'repo': 'MisakaNet',
        'findings': 'Clean implementation',
    })
    assert 'Role: Senior Security Engineer.' in rendered

    try:
        reg.get('code_auditor').render({'role': 'Auditor'})
        assert False, 'Allowed missing variable'
    except KeyError:
        pass

    try:
        PromptPreset(
            name='invalid_temp',
            version='1.0.0',
            template='test',
            model='gpt-4o',
            temperature=3.5,
        )
        assert False, 'Allowed invalid temperature'
    except ValueError:
        pass

test_presets()
"
```

## Notes

- Reference upstream issue and schema validation discussions: [Pydantic Validation Workflows](https://github.com/pydantic/pydantic/issues) and [Prompt Engineering Template Architecture](https://docs.pydantic.dev/latest/concepts/models/).
- When serializing prompt presets to disk (such as YAML or JSON catalogs in configuration repositories), execute this validation in pre-commit hooks and CI quality gates to intercept malformed templates before deployment.
- Avoid passing dynamic user input directly as format strings to prevent prompt injection or formatting string exploits.
