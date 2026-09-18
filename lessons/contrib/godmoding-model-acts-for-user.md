---
title: "LLM god-moding: model speaks or acts for the user in roleplay"
domain: roleplay-engine
tags:
  - "godmoding"
  - "speaker-attribution"
  - "action-narration"
  - "roleplay-guardrails"
status: published
created: 2026-09-07
updated: 2026-09-07
source: "intake #1574 — LLM generates responses that speak or act for the user (godmoding) in roleplay"
evidence_level: E3
summary_plain: "LLM在角色扮演中替用户说话或行动（god-moding），需要三层防御。"
trigger: "LLM speaking acting user godmoding roleplay"
verify: "修复后50轮角色扮演中越权回合数为0"
provenance:
  issue: "#1574"
  contributor: "Ikalus1988"
---

## Problem

In roleplay conversations, the LLM generates dialogue blocks attributed to the user's character or narrates actions in second person ("you walk to the door"), effectively controlling the user's character. This is known as **god-moding** — the model takes agency away from the user.

Example of god-moded output:

```
Assistant: "I think we should check the basement," Maria says.
You nod and walk toward the basement door, feeling a chill run down your spine.
You open the door slowly.  ← model narrating user's actions
```

The user never chose these actions. The model assumed control of the user's character.

## Root Cause

Two factors combine:

### 1. Training data contains "assistant completes both sides"

Many roleplay training examples show the assistant generating dialogue for all characters, including the user's. The model learns to "keep the story moving" by filling in the user's part when the user pauses or gives a short prompt.

This is especially prevalent in:
- Collaborative fiction datasets
- Chat logs where the human was a passive reader
- Automated roleplay evaluation datasets

### 2. No explicit turn boundary in roleplay prompts

Standard chat formatting treats each message as one speaker's turn. In roleplay, the model doesn't know where the user's agency boundary is unless explicitly told. Without a clear rule like "only output your own character's actions," the model treats the entire scene as its canvas.

## Solution

Three-layer defense, each catching what the previous layer misses:

### Layer 1: System prompt anti-godmoding instructions

Explicit instructions in the system prompt that define the boundary:

```markdown
## Turn rules
- Only narrate actions and dialogue for YOUR character(s).
- Never write dialogue, actions, or internal thoughts for the user's character.
- If the user's character needs to respond, WAIT for the user to write it.
- Acceptable: "Maria looks at you expectantly." (describes NPC, implies user should respond)
- Forbidden: "You nod and follow her." (user action)
```

### Layer 2: Output parser filter

A post-generation filter that detects and strips god-moded content:

```python
def strip_godmoding(text: str, user_name: str) -> tuple[str, bool]:
    """Strip blocks attributed to user or containing 2nd-person actions."""
    patterns = [
        rf'^{re.escape(user_name)}:.*$',  # "You: ..." dialogue
        r'^(You|Você)\s+(walk|open|nod|say|think|feel|look|turn|grab|run)\b',  # 2nd-person actions
        r'^(Você)\s+(caminha|abre|acena|diz|pensa|sente|olha|vira|pega|corre)\b',  # Portuguese
    ]
    lines = text.split('\n')
    filtered = []
    stripped = False
    for line in lines:
        if any(re.match(p, line, re.IGNORECASE) for p in patterns):
            stripped = True
            continue
        filtered.append(line)
    return '\n'.join(filtered), stripped
```

### Layer 3: Guardrail with targeted retry

When the parser strips content, retry with a reinforced instruction:

```
Your previous response contained actions for the user's character.
Regenerate, narrating ONLY your character(s). End with a prompt for the user.
```

This catches cases where the system prompt alone isn't strong enough (e.g., long roleplay context dilutes the instruction).

## Verification

### Quantitative: god-moding turn count

Before fix: Run 50 roleplay turns → count turns containing user-attributed dialogue or 2nd-person actions.

After fix: Same 50 turns → expect 0 god-moded turns.

### Unit tests

```python
def test_strip_user_dialogue():
    text = 'Maria smiles.\nYou: "I agree."\nMaria nods.'
    result, stripped = strip_godmoding(text, "You")
    assert stripped is True
    assert "I agree" not in result

def test_strip_second_person_action():
    text = 'Maria waits.\nYou walk to the door.'
    result, stripped = strip_godmoding(text, "You")
    assert stripped is True
    assert "walk to the door" not in result

def test_preserve_npc_dialogue():
    text = 'Maria: "Let\'s go."\nShe leads the way.'
    result, stripped = strip_godmoding(text, "You")
    assert stripped is False
    assert "Let's go" in result
```

### Integration test

Run a full roleplay session with the3-layer defense active. Verify:
- No user-attributed dialogue in any output
- No 2nd-person action narration
- Conversation still flows naturally (NPC describes scene, asks questions, waits)

## See also

- [Roleplay vocative entity disambiguation](roleplay-vocative-entity-disambiguation-portuguese.md) — speaker attribution in roleplay
- [NPC dispatch speaker dislocation](npc-dispatch-speaker-dislocation.md) — related speaker/attribution failure
