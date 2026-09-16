---
title: "Character Creator Assistants — Repetitive Name and Archetype Loop from Prompt Anchors"
domain: "agent"
tags:
  - roleplay
  - character-creation
  - repetition
  - prompt-engineering
  - sampling-params
  - llm
status: "published"
evidence_level: "E2"
created: "2026-09-11"
updated: "2026-09-11"
source: "issue-1477"
provenance:
  source: "antigravity"
  contributor: "Community"
  evidence: "locally reproduced + unit tested"
---

# Character Creator Assistants — Repetitive Name and Archetype Loop from Prompt Anchors

## Problem

When building character creator assistants using LLMs, models tend to produce repetitive names and archetypes across runs. Typical symptoms:

```
Run 1: Luna — curiosa, teimosa, adora explorar
Run 2: Luna — criativa, teimosa, sonhadora
Run 3: Luna — Determined, stubborn, loves the stars
```

The name "Luna" and the trait "teimosa/stubborn" recur in every generation. Over dozens of runs, the output converges to a small set of ~5 names and ~3 archetype bundles, even when the prompt asks for "unique, diverse characters."

This is caused by two compounding factors:

1. **Isolation from existing catalog** — the model has no visibility into characters it already generated, so it cannot avoid repeating itself.
2. **Static example anchors in prompt instructions** — examples like `ex: Luna` or `ex: curiosa, teimosa` in the system prompt act as attention anchors. Instruction-following LLMs overfit to these examples, treating them as prototypical rather than illustrative.

The combination creates a **self-reinforcing loop**: the prompt example biases the model toward a specific name/trait cluster, the model generates similar output, and without catalog awareness there is no signal to break the cycle.

## Root Cause

Three mechanisms interact:

### 1. Prompt anchor overfitting

Instruction-tuned LLMs treat examples in the system prompt as high-priority templates. When the prompt contains:

```
Generate a unique character. ex: Luna, curiosa e teimosa
```

The model interprets "Luna" and "curiosa, teimosa" as the *intended* output shape, not merely an illustration. The attention mechanism assigns disproportionate weight to these tokens during decoding, making them statistically likely to reappear.

### 2. Absence of catalog-aware deduplication

Without injecting a summary of previously generated characters, the model has no negative signal to avoid repetition. Each generation starts from a blank slate, and the same prompt anchors produce the same outputs.

### 3. Sampling parameter amplification

Default sampling settings compound the problem:

| Parameter | Default | Effect on repetition |
|-----------|---------|---------------------|
| `temperature` | 0.7 | Moderate diversity, but anchor tokens dominate the distribution |
| `top_p` | 1.0 | No filtering — high-probability anchor tokens always included |
| `frequency_penalty` | 0.0 | No penalty for repeating tokens across turns |
| `presence_penalty` | 0.0 | No penalty for reusing concepts already mentioned |

With `frequency_penalty=0` and `presence_penalty=0`, the model freely reuses the same names and traits across runs.

## Solution

Separate **stable context** (catalog awareness, anti-redundancy rules) from **variable context** (generation parameters, creativity), and tune sampling to break the self-reinforcing loop.

### 1. Inject existing catalog summaries into the prompt

Before each generation, query the character database and inject a condensed summary:

```python
def build_generation_prompt(catalog: list[dict], max_chars: int = 500) -> str:
    """Build prompt with anti-redundancy context from existing catalog."""
    existing_names = [c["name"] for c in catalog]
    existing_archetypes = list({c["archetype"] for c in catalog})

    catalog_block = (
        f"EXISTING CHARACTERS (do NOT reuse these names): "
        f"{', '.join(existing_names[:20])}\n"
        f"EXISTING ARCHETYPES (avoid repeating these): "
        f"{', '.join(existing_archetypes[:10])}\n"
    )

    return f"""You are a character creator assistant.
{catalog_block}
RULES:
- Generate a UNIQUE character with a name not in the list above.
- Use a different archetype from those listed above.
- Do NOT use example names from previous instructions as your output.
- Vary personality traits, backstory, and visual description.
"""
```

### 2. Remove static single-example anchors

**Before** (creates anchor):
```
Generate a unique character. ex: Luna, curiosa e teimosa
```

**After** (no anchor):
```
Generate a unique character. The name and traits must be different from
all existing characters. Do not use placeholder examples as templates.
```

If examples are necessary for formatting clarity, use **multiple diverse examples** and mark them explicitly:

```
Example outputs (for format reference ONLY — do not copy names or traits):
1. Kai — restless inventor who speaks to machines
2. Mira — archivist of forgotten languages
3. Tavo — ex-gardener turned storm chaser
```

### 3. Tune sampling parameters

```python
generation_params = {
    "temperature": 0.9,        # higher than default 0.7 for more variety
    "top_p": 0.92,             # slightly filtered to exclude tail anchors
    "frequency_penalty": 0.4,  # penalize repeated token usage
    "presence_penalty": 0.3,   # penalize reusing already-mentioned concepts
    "max_tokens": 300,
}
```

| Parameter | Recommended | Rationale |
|-----------|-------------|-----------|
| `temperature` | 0.85–1.0 | Higher temperature increases name/trait diversity |
| `top_p` | 0.9–0.95 | Filters the long tail where anchor tokens cluster |
| `frequency_penalty` | 0.3–0.5 | Directly penalizes token repetition across runs |
| `presence_penalty` | 0.2–0.4 | Penalizes concept reuse (e.g., "stubborn" appearing again) |

### 4. Post-generation deduplication check

```python
def is_duplicate(new_char: dict, catalog: list[dict], threshold: float = 0.8) -> bool:
    """Check if generated character is too similar to existing ones."""
    new_traits = set(new_char["traits"])
    for existing in catalog:
        existing_traits = set(existing["traits"])
        overlap = len(new_traits & existing_traits) / max(len(new_traits), 1)
        if new_char["name"] == existing["name"] or overlap > threshold:
            return True
    return False

# Retry with fresh seed if duplicate detected
for attempt in range(3):
    char = generate_character(catalog)
    if not is_duplicate(char, catalog):
        break
```

## Verification

### Repetition rate comparison

Run 50 generations with the same prompt, before and after the fix:

```python
import json
from collections import Counter

def measure_repetition(generations: list[dict]) -> dict:
    names = [g["name"] for g in generations]
    archetypes = [g["archetype"] for g in generations]
    name_counts = Counter(names)
    archetype_counts = Counter(archetypes)
    return {
        "unique_names": len(set(names)),
        "total_generations": len(names),
        "name_repetition_rate": 1 - (len(set(names)) / len(names)),
        "top_name": name_counts.most_common(1)[0],
        "unique_archetypes": len(set(archetypes)),
    }

# Before fix: expect high repetition
# After fix: expect name_repetition_rate < 0.1 (fewer than 10% repeats)
```

**Expected results:**

| Metric | Before fix | After fix |
|--------|-----------|-----------|
| Unique names / 50 runs | 8–12 | 45–50 |
| Name repetition rate | 0.76–0.84 | 0.0–0.10 |
| Top name count | 30+ ("Luna") | 1–2 |
| Unique archetypes / 50 runs | 4–6 | 20+ |

### Automated verification

```bash
python3 scripts/lesson_gate.py lessons/contrib/character-assistant-repetition-loop.md
python3 scripts/injection_scan.py lessons/contrib/character-assistant-repetition-loop.md
```

Both must pass with 0 high-severity findings.

## Related

- Issue [#1499](https://github.com/Ikalus1988/MisakaNet/issues/1499) — In roleplay chat, third-person narrative or pronoun "Ele" was interpreted by the model as a character name (entity disambiguation failure in the same roleplay domain).
- Issue [#1501](https://github.com/Ikalus1988/MisakaNet/issues/1501) — In multi-turn character roleplay with prompt caching, static/stable context drifts when cached prompts are reused across sessions (related to the stable/variable context separation this lesson prescribes).
- Issue [#1630](https://github.com/Ikalus1988/MisakaNet/issues/1630) — Roleplay chat app: user wrote "Arlete, vá até a loja da Ana" and the protagonist spoke as the NPC (vocative vs mention disambiguation failure — same domain, different failure mode).
- `lessons/contrib/agent-roleplay-time-consistency-hallucination.md` — time consistency hallucinations in roleplay agents (different failure class, same domain).
