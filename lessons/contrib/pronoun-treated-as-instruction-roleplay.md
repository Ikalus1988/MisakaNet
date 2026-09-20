---
title: "Pronoun misidentified as NPC in roleplay extraction"
domain: roleplay-engine
tags: [roleplay, npc, pronoun, disambiguation, extraction, llm, godmoding]
status: published
created: '2026-09-07'
updated: '2026-09-07'
source: "intake #1499 — Portuguese pronoun 'Ele' registered as NPC name, causing user impersonation"
evidence_level: E3
provenance:
  source: "intake"
  issue: "#1499"
summary_plain: "LLM 把第三人称叙事中的代词（如葡语 'Ele'）当成 NPC 名字注册，导致系统不断匹配并代用户说话。"
trigger: "pronoun treated as NPC name roleplay extraction impersonation godmoding"
verify: "代词不再被注册为 NPC，同一输入下系统不代用户说话"
---

## Problem

In roleplay chat, third-person narrative containing pronouns (e.g. Portuguese "Ele" = "He") is processed by the NPC extraction LLM, which registers the pronoun as a new character name. The system then:

1. Constantly matches "Ele" in conversation text
2. Treats it as an active NPC that needs to respond
3. The model begins speaking/acting on behalf of the user (godmoding)

```
User: "Ele entrou na sala e sentou." (He entered the room and sat down.)
→ Extraction LLM: "New NPC detected: 'Ele'"
→ System: "Ele diz: ..." (Ele says: ...) ← speaking AS the user
```

## Root Cause

The NPC extraction prompt doesn't distinguish between:
- **Proper names** ("Maria", "João") → valid NPC candidates
- **Pronouns** ("Ele", "Ela", "Ele/Ela", "He", "She") → should be excluded

LLMs are biased toward treating capitalized words in narrative text as entity names.

## Fix

### 1. Deterministic blacklist filter (post-extraction)

```python
INVALID_NPC_NAMES = {
    # Portuguese pronouns
    "ele", "ela", "eles", "elas", "o", "a", "os", "as",
    # English pronouns
    "he", "she", "they", "him", "her", "them",
    # Generic user terms
    "user", "player", "you", "eu", "você", "tu",
}

def is_invalid_npc_name(name: str) -> bool:
    return name.lower().strip() in INVALID_NPC_NAMES

def purge_invalid_npcs(npcs: list[dict]) -> list[dict]:
    return [npc for npc in npcs if not is_invalid_npc_name(npc["name"])]
```

### 2. Whole-word boundary matching

```python
import re

def match_npc_in_text(npc_name: str, text: str) -> bool:
    # "Ele" should not match "Elefante"
    pattern = rf'\b{re.escape(npc_name)}\b'
    return bool(re.search(pattern, text, re.IGNORECASE))
```

### 3. Extraction prompt hardening

Add to the extraction prompt:

```
Rules:
- NEVER extract pronouns (he/she/they/ele/ela/eles/elas) as character names
- NEVER extract common nouns (man, woman, person, guy) as character names
- Only extract proper names that refer to specific characters in the scene
```

## Verification

```bash
# Unit test: pronouns rejected
pytest tests/test_npc_extraction.py -k "pronoun" -v
# Expected: "Ele", "He", "She" all rejected

# Unit test: valid names still extracted
pytest tests/test_npc_extraction.py -k "proper_name" -v
# Expected: "Maria", "João" correctly identified

# Integration: no godmoding with pronoun-heavy input
pytest tests/test_chat_integration.py -k "third_person_narrative" -v
# Expected: system does not speak on behalf of user
```

## Key Insight

NPC extraction LLMs are entity-recall-biased — they over-extract. A deterministic post-extraction filter is cheaper and more reliable than prompt tuning alone. Apply it as a safety net regardless of LLM quality.
