---
title: "Prompt cache prefix invalidation causes location hallucination in roleplay"
domain: llm
tags: [prompt-caching, roleplay, context-window, hallucination, location, spatial-anchoring]
status: published
created: '2026-09-07'
updated: '2026-09-07'
source: "intake #1501 — multi-turn roleplay with prompt caching, location regresses to earlier scene"
evidence_level: E3
provenance:
  source: "intake"
  issue: "#1501"
summary_plain: "角色扮演中地点信息只放在静态前缀里，长对话后 LLM 因近因偏置回到旧场景。"
trigger: "prompt caching location hallucination roleplay static dynamic context scene regression"
verify: "修复后同一长对话下角色位置与当前场景一致，不回退到旧场景"
---

## Problem

In multi-turn character roleplay with prompt caching (e.g. Claude, GPT-4o), the context is split into:

- **Stable prefix** (system message 0): character persona, world rules, location → cached
- **Dynamic prefix** (system message before current turn): recent context → changes each turn

When the current location is only defined in the stable prefix, long conversation histories cause **recency bias**: the LLM gives more weight to locations mentioned in recent dialogue turns than to the location buried deep in the cached prefix. Result:

```
Stable prefix says: "Current location: apartment"
Recent turns mention: coffee shop (from 30 turns ago)
LLM output: *sips coffee at the café* ← regressed to old location
```

## Root Cause

Prompt caching optimizes for cost by keeping the prefix stable. But the LLM's attention distribution follows recency — recent tokens get more weight. A location mentioned once in a 10K-token prefix is outcompeted by a location mentioned in 3 of the last5 turns, even if those turns were about a flashback.

## Fix

### 1. Inject location into dynamic system prompt

```python
# ❌ Location only in stable prefix (buried)
stable_prompt = f"""You are {character.name}. Setting: {location}. ..."""

# ✅ Location also in dynamic prefix (high-recency position)
dynamic_prompt = f"""CURRENT SCENE STATE (always enforce):
- Location: {current_location}
- Characters present: {present_characters}
- Time: {current_time}

Recent conversation:
{recent_turns}"""
```

### 2. Anti-regression constraints

Add explicit negative instructions to the dynamic prompt:

```
RULES:
- Characters are CURRENTLY at {current_location}
- Do NOT move characters to locations from past dialogue unless explicitly described
- If unsure about location, use {current_location} — never assume from history
```

### 3. Spatial anchoring token

Include a structured state block at the end of the dynamic prompt (right before user message) for maximum attention:

```
[STATE] location={current_location} | time={current_time} | present={characters} [/STATE]
```

## Verification

```bash
# 1. Run a50-turn test conversation
pytest tests/test_roleplay_consistency.py -k "location_regression" -v
# Expected: location stays at current_location throughout

# 2. Check prompt composition
python -c "from roleplay import build_prompt; print(build_prompt(turn=50))"
# Verify location appears in both stable and dynamic prefixes

# 3. Measure cache hit rate (if using API with cache metrics)
# Location in dynamic prefix costs ~200 tokens per turn
# Stable prefix cache still works for persona/world rules
```

## Key Insight

Prompt caching creates a **two-tier attention model**: high-recency (dynamic) and low-recency (cached). Information that must be **actively enforced** (current state, location, active constraints) belongs in the dynamic prefix — not just the cached one. This trades a small token cost per turn for dramatically better consistency.
