---
title: "Injected scene state is a cache, not the roster: filter it before the model reads it"
domain: roleplay-engine
tags:
  - roleplay
  - context-injection
  - stale-state
  - npc-presence
  - speaker-attribution
  - prompt-hygiene
  - state-reconciliation
status: published
created: "2026-10-03"
updated: "2026-10-03"
source: "intake #1678 — absent NPCs kept being narrated in the physical scene from stale stored state; extraction hook labelled NPC lines with the protagonist"
evidence_level: E0
evidence_refs:
  - 'issue:#1678'
summary_plain: "A stored scene kept being injected after its cast changed, so characters who had left were still narrated as present."
trigger: "injected scene state lists departed NPC as present stale store prompt roster reconciliation"
verify: "After an entity leaves the roster, one turn's injected block carries no sentence naming it, and an unresolvable speaker never yields the protagonist's id."
provenance:
  source: "intake"
  issue: "#1678"
  contributor: "Ikalus1988"
  node: "Misaka10099"
  evidence: "single-node report; no reproduction script, log excerpt, or before/after count supplied"
---

# Injected scene state is a cache, not the roster: filter it before the model reads it

## Problem

Two distinct symptoms, both silent — no exception, no failed request, fluent output throughout.

1. **Absent entities stayed in the scene.** After an NPC left — dispatched elsewhere, dismissed, moved to another room — later turns kept narrating it as physically present in the physical scene. The model re-anchored a character that was no longer there, and kept doing so for the rest of the session.

2. **NPC lines were stamped with the protagonist's name.** The transcript attributed messages that NPCs had produced to the protagonist.

The two symptoms are independent: the first is a read-path defect, the second a write-path defect. They are recorded together because they shipped together and because both come from the same underlying habit — letting a stored or defaulted value stand in for something that was never verified.

What makes this class expensive is that the failure is invisible in the output. The prose is fluent, the format is correct, and nothing anywhere reports a fault. The only observable is that the story quietly stops being true to its own world state.

## Root Cause

### 1. The stored snapshot was injected verbatim, never reconciled against the current roster

Scene state is written once when a scene is established and read back on every subsequent turn. Between the write and the read, the world moves: entities leave, are dispatched, die, get dismissed. The read path did the obvious thing — fetch the blob, concatenate it into the system prompt:

```python
state = store.get(SCENE_STATE_KEY)      # a snapshot of one past moment
system_prompt += state.narrative         # no diff, no TTL, no membership check
```

The missing invariant is: **every entity named in injected state must be present in the current roster at the moment of injection.** The store is permitted to be stale. The prompt is not.

Why this fails silently rather than obviously: injected context carries no provenance. To the model, a sentence in a system prompt is indistinguishable from a rule it is obliged to obey. Stale presence is not a weak hint competing with a stronger signal — it is a fact stated in the most authoritative position the prompt has, and the user turns that contradict it carry strictly less weight. The effect compounds with session length: the same stale claim is re-injected every turn, so a single wrong sentence accumulates more in-context repetitions than any correction the user can make in one message.

The trust inversion is the real hazard. A store read is a *cache lookup*, and cache reads are treated as cheap and safe, so the value goes straight into the highest-trust slot in the prompt. Anything crossing that boundary from storage to instruction needs an explicit check, because the boundary is precisely where a cached value silently acquires authority it was never verified for.

### 2. The attribution hook had a default, and the default was the protagonist

The hook that post-processes a message has to emit a speaker field. When its resolution path fell through, it emitted the protagonist's id.

A default in an attribution field is not a neutral placeholder. It is a positive assertion that the protagonist produced that line — and once persisted, it is byte-identical to a correct attribution. Nothing downstream can tell a guessed speaker from a resolved one, which means the corruption is invisible to every reader, including the person debugging it weeks later.

## Fix

### 1. Filter injected state against the live roster at read time

Filter at **read time, every turn** — not at write time. Write time does not know the future roster, so a write-time filter reproduces the same staleness one turn later. The read is the only point where the current roster is actually known.

> The submitter's implementation puts this filter in a store wrapper (named `FilterAbsentFromPhysical` in their codebase) called from their protagonist prompt builder. The name is local to that project; the mechanism is the filter and its call site.

```python
def build_scene_state(store, roster, now):
    state = store.get(SCENE_STATE_KEY)
    if not state:
        return ""

    present = {e.id for e in roster if e.active_at(now)}
    kept, dropped = [], []

    for sentence in split_sentences(state.narrative):
        named = entities_in(sentence)          # ids, not display names
        if named and not (named & present):
            dropped.append(sentence)
        else:
            kept.append(sentence)

    parts = ["\n".join(kept)]
    if dropped:
        # Say what was removed. Silence would let the model re-infer presence
        # from the gap, which is the same bug wearing a different hat.
        parts.append("Not present in this scene: " + ", ".join(names_of(dropped)))
    return "\n".join(p for p in parts if p)
```

Three properties that matter more than the specific code:

- **Filter at clause granularity, not name granularity.** Deleting the name from "Maria waits by the door" leaves "___ waits by the door" — a presence assertion with a hole in it, which the model will fill in. Drop the whole clause.
- **The roster is the authority; the store is the cache.** Never the reverse. Any reconciliation that trusts the store over the live roster has the same bug one level down.
- **Represent absence as absence.** Listing what was dropped is what stops the model from inferring presence from the omission.

### 2. Make the speaker explicit; delete the default

> The submitter's fix threads a resolved speaker object through their NPC-extraction hook (their `npcExtractionHook`, via a `MessageSpeaker` field). Local naming; the mechanism is the removal of the fall-through.

```python
# Before — a fall-through attribute is a silent positive claim
def extract_speaker(msg):
    return resolve(msg.candidates) or PROTAGONIST_ID

# After — unresolved is a state the caller must resolve, not a value to guess
class SpeakerUnresolved(Exception):
    pass

def extract_speaker(msg):
    hit = resolve(msg.candidates)
    if hit is None:
        raise SpeakerUnresolved(msg.id)     # never substitute the protagonist
    return hit
```

The rule generalizes past speaker fields: **in an attribution field, `unknown` is a legal value and a default is not.** An unresolved speaker must fail at the point of resolution, where a human or a retry can still see it, rather than being filled in downstream where it becomes indistinguishable from a real answer.

## Verification

**Evidence boundary, stated up front:** the submission is a single-node report and carries **no reproduction script, no log excerpt, and no before/after count**. The two behavioural outcomes described below are what the submitter observed in their own deployment. Nothing here is a result reproduced elsewhere, and no numbers are claimed.

What the submitter reports observing after the change: entities that had left the scene stopped being narrated as present, and NPC-authored lines carried their own speaker label rather than the protagonist's.

The rest of this section is the criterion set a reader can apply in their own system. These are **tests to run, not results already obtained**.

1. **Roster-drift check.** Change the roster (mark an entity departed) while leaving the stored scene blob byte-for-byte untouched, then run exactly one turn. Pass: the injected scene block contains no sentence naming that entity. Fail: the sentence is still there — which proves the read path is injecting unfiltered storage.
2. **Clause-not-name check.** Use a stored block containing a full presence clause about an off-roster entity. Pass: the clause is removed whole, leaving no residual presence assertion with a missing name. This is the case a naive name-filter passes and a reader would never see.
3. **Unresolved-speaker check.** Feed the attribution hook a message whose speaker cannot be resolved. Pass: it raises or returns an explicit unresolved marker. Fail: it returns the protagonist's id — the default is still installed, and symptom 2 is unfixed regardless of what the transcript currently shows.
4. **Persistence check.** After a turn, read the stored transcript back and confirm the speaker field on an NPC line equals that NPC's id, including after a restart. This distinguishes "corrected in flight" from "never mislabelled" — only the second one is a fix, because an in-flight correction that still persists the wrong id reproduces the original defect on reload.

Checks 1–2 isolate the read path and check 3–4 the write path, so a pass on one does not mask a failure on the other.

## See also

- [NPC dispatch causes spatial bilocation and active speaker loss](npc-dispatch-speaker-dislocation.md) — also ends in a protagonist fallback, but via *pronoun resolution failing to match a present NPC*. This lesson covers the fallback living in an *attribution hook with a default*, and the stale-state half is not covered there.
- [A cloned confirmation line poisons the context](roleplay-dialogue-loop-context-poisoning.md) — history pollution from a repetition loop; complementary on the write path.
- [Prompt cache prefix invalidation causes location hallucination](prompt-cache-prefix-invalidation-roleplay.md) — where a fact sits in the prompt (stable vs dynamic prefix). This lesson is about whether the fact is *true at read time*; a correct fact in the wrong slot and a true-at-write fact in the right slot are different bugs.
