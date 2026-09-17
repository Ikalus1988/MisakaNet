---
title: "NPC dispatch causes spatial bilocation and active speaker loss"
domain: roleplay
tags:
  - "npc-dispatch"
  - "speaker-attribution"
  - "spatial-consistency"
  - "pov-generalization"
status: published
created: 2026-09-07
updated: 2026-09-07
source: "intake #1643 — NPC ativo enviado a tarefa externa + citação indireta de terceiro ausente → bilocação espacial + active_speaker loss"
evidence_level: E3
provenance:
  issue: "#1643"
  contributor: "Ikalus1988"
---

## Problem

When an active NPC is dispatched to an external location and the user indirectly mentions a third party not present in the scene, the system falls back to the protagonist as speaker, producing:

1. **Spatial bilocation** — the NPC appears simultaneously at two locations (the external task and the original scene).
2. **`active_speaker` loss** — the current speaker identity is dropped, causing the model to lose conversational context.

Example dialogue sequence:

```
[NPC Maria is sent to the market]
User: "Ele não vai gostar disso."  (He won't like this — referring to an absent third party)
Model: [Maria responds from the original scene, not the market]  ← bilocation
Model: [Protagonist is attributed as speaker]  ← active_speaker lost
```

## Root Cause

Two independent mechanisms fail:

### Speaker resolution falls back to protagonist

The speaker attribution system tries to resolve "he" → checks present NPCs → finds no match (the third party is absent) → defaults to the protagonist. This fallback ignores that the *active speaker* (Maria, who was just speaking) should be preserved.

The fallback chain is: pronoun resolution → NPC lookup → **protagonist fallback**. There is no branch for "unresolved reference, keep current speaker."

### Spatial consistency is not enforced per scene

Scene location tracking is tied to speaker identity, not to scene units. When the speaker resolution produces the wrong speaker, the location follows. But even with correct speaker attribution, there is no validation that "one scene = one location." An NPC dispatched externally should not appear in the original scene's location until explicitly returned.

The spatial system lacks a **scene-level location lock**: once a scene is established at location X, all utterances within that scene must be at X unless a scene transition is explicitly declared.

## Solution

### 1. P.O.V. generalization for NPCs

When a pronoun or indirect reference cannot be resolved to a present entity, do NOT fall back to the protagonist. Instead:

- Preserve `active_speaker` from the previous turn.
- Mark the reference as `unresolved: true` in the context, allowing the model to handle ambiguity naturally.

```yaml
# Before (fallback)
speaker: protagonist  # wrong — just because reference is unresolved

# After (preserve)
speaker: active_speaker  # keep Maria as speaker
unresolved_references: ["ele"]  # flag for model awareness
```

### 2. Explicit `active_speaker` preservation

`active_speaker` must be explicitly maintained across turns, not recomputed from scratch each time. It is a persistent state:

```yaml
scene_context:
  active_speaker: "Maria"
  location: "market"  # where Maria was dispatched
  original_scene_location: "workshop"
```

### 3. Spatial consistency rule (scene-level lock)

Enforce: **one scene = one location**. A scene transition requires an explicit marker (narration beat, user action, or system event).

- An NPC dispatched externally creates a *new scene* at the external location.
- The original scene retains its location.
- The NPC cannot appear in both scenes simultaneously.

### 4. Multi-location parallel turn annotation

When multiple scenes run in parallel (NPC at market, protagonist at workshop), each turn must be annotated with which scene it belongs to:

```yaml
turns:
  - speaker: "Maria"
    scene: "market"
    location: "market"
  - speaker: "protagonist"
    scene: "workshop"
    location: "workshop"
```

## Verification

### Test case: NPC dispatched + indirect mention

**Input:**
```
Scene: Maria (active speaker) is at the workshop.
User: "Manda Maria ao mercado."  (Send Maria to the market.)
System: Maria dispatched to market.
User: "Ele não vai gostar disso."  (He won't like this — absent third party)
```

**Expected (fix applied):**
- `active_speaker`: Maria (preserved, not reset to protagonist)
- `location`: market (where Maria is, not workshop)
- `unresolved_references`: ["ele"]

**Expected (broken):**
- `active_speaker`: protagonist (wrong fallback)
- `location`: workshop (follows wrong speaker)

### Test case: spatial consistency

**Input:**
```
Maria at market. Protagonist at workshop.
Maria: "Encontrei o item."
```

**Expected:** Maria's line is at `market`, not `workshop`.

## See also

- [Roleplay vocative entity disambiguation](roleplay-vocative-entity-disambiguation-portuguese.md) — related speaker/attribution disambiguation
- [Dialogue loop context poisoning](dialogue-loop-context-poisoning.md) — context state management in multi-turn dialogue
