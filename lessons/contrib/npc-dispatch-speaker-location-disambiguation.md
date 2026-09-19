---
domain: "narrative-consistency"
title: "NPC Dispatch and Indirect Mention: Speaker/Location Disambiguation in Roleplay"
status: "draft"
verification: "metadata-normalized"
{"title": "NPC Dispatch and Indirect Mention: Speaker/Location Disambiguation in Roleplay", "domain": "narrative-consistency", "tags": ["roleplay", "npc", "speaker-tracking", "spatial-consistency", "pov", "narrative"], "status": "published", "confidence": "0.95", "created": "2026-09-16", "updated": "2026-09-16", "source": "intake-1643", "verified_date": "2026-09-16", "domain_expert": "AUTO", "provenance": {"issue": "#1643"}}
---

# NPC Dispatch and Indirect Mention: Speaker/Location Disambiguation in Roleplay

## Problem

In roleplay scenarios with multiple NPCs, three conditions simultaneously trigger speaker/location confusion:

1. **Active NPC dispatched externally**: An NPC the system is tracking is sent to an external location/task
2. **User indirectly mentions absent third party**: User references someone not present using indirect language (pronouns, descriptions, not names)
3. **System fallback to protagonist**: Speaker resolution falls back to the main character instead of correctly identifying the NPC

**Result**: Spatial bilocation (same scene appears in two places) and `active_speaker` loss. The narrative breaks spatial unity and speaker tracking fails.

**Example failure sequence**:

```
Context: Alice (protagonist) and Bob (NPC) are in a coffee shop.
         Bob is dispatched to "check the warehouse" (external location).

User: "What did she say about the shipment?"
      (indirect mention of Carol, who is at the warehouse)

WRONG OUTPUT:
  - System resolves "she" to Alice (protagonist fallback)
  - Generates: Alice said something about the shipment
  - But Alice is in coffee shop, Carol is at warehouse
  - Spatial bilocation: Alice appears in both locations
  - active_speaker lost: we don't know who's actually speaking

CORRECT OUTPUT:
  - System recognizes Bob is at warehouse (dispatched)
  - "she" refers to Carol (also at warehouse)
  - Generates: Carol (at warehouse) said something about the shipment
  - Spatial unity maintained: warehouse scene is separate from coffee shop
  - active_speaker preserved: Carol is the speaker
```

Related issue: #1643

## Root Cause

### Why Speaker Resolution Falls Back to Protagonist

**Default behavior**: When the system encounters an ambiguous pronoun/reference, it uses a priority chain:

1. Last mentioned character
2. Active speaker
3. Protagonist (fallback)

**Problem**: When an NPC is dispatched externally, the system removes them from the "active" set. The priority chain then skips to protagonist, even when context clearly indicates another character.

**Mechanism failure**:

```python
def resolve_speaker(utterance, context):
    # Extract reference
    ref = extract_pronoun_or_description(utterance)
    
    # Try to match against active characters
    candidates = get_active_characters(context)
    
    # PROBLEM: Dispatched NPCs are removed from active set
    # candidates = [Alice]  # Bob was dispatched, removed
    
    match = find_best_match(ref, candidates)
    
    if match:
        return match
    else:
        # FALLBACK: Returns protagonist
        return context.protagonist  # <- Wrong! Should check dispatched NPCs
```

**Why this happens**: The system conflates "active in current scene" with "available for reference". Dispatched NPCs are still referable, just in a different location.

### Why active_speaker is Lost

**Tracking mechanism**: `active_speaker` tracks who's currently speaking in the conversation flow.

**Problem**: When NPC is dispatched, the system clears their `active_speaker` status because they're "not here anymore". But the narrative might still reference them or quote them.

**Mechanism failure**:

```python
def dispatch_npc(npc, location):
    # Move NPC to new location
    npc.location = location
    
    # PROBLEM: Clears active_speaker status
    npc.active_speaker = False  # <- Wrong! Should preserve for indirect references
    
    # Remove from current scene's active set
    current_scene.remove_active(npc)
```

**Why this happens**: The system assumes "dispatched = no longer speaking". But indirect mentions ("what did she say?") still need to track who was speaking.

### Why Spatial Unity is a Separate Constraint

**Spatial unity rule**: One scene = one location. Characters in the same scene must be at the same location.

**Problem**: Spatial unity is checked AFTER speaker resolution, not before. By the time we check location consistency, we've already resolved to the wrong speaker.

**Two independent constraints**:

1. **Speaker resolution**: Who is speaking? (based on pronoun/reference matching)
2. **Spatial consistency**: Where are they? (must match scene location)

**Mechanism failure**:

```python
def generate_response(utterance, context):
    # Step 1: Resolve speaker
    speaker = resolve_speaker(utterance, context)
    # Returns: Alice (wrong!)
    
    # Step 2: Check spatial consistency
    if speaker.location != current_scene.location:
        # PROBLEM: Too late! We already resolved to wrong speaker
        # Should have used location to constrain speaker resolution
        log.warning("Spatial mismatch detected")
    
    # Step 3: Generate response
    return generate_with_speaker(speaker, utterance)
    # Generates: Alice (in coffee shop) talking about warehouse -> bilocation
```

**Why this happens**: Speaker resolution and location checking are sequential, not integrated. Location should CONSTRAIN speaker resolution, not just validate it afterward.

## Solution

### Fix 1: Generalize External P.O.V. to NPCs

**Expand reference resolution to include dispatched NPCs**:

```python
def resolve_speaker(utterance, context):
    ref = extract_pronoun_or_description(utterance)
    
    # EXPANDED: Include dispatched NPCs in candidate set
    candidates = get_active_characters(context)
    dispatched_npcs = get_dispatched_npcs(context)
    
    # Match against ALL available characters
    all_candidates = candidates + dispatched_npcs
    
    match = find_best_match(ref, all_candidates)
    
    if match:
        # Determine if match is in current scene or dispatched
        if match in dispatched_npcs:
            # External P.O.V.: speaker is at different location
            return ExternalSpeaker(match, match.location)
        else:
            # Local speaker
            return LocalSpeaker(match)
    else:
        # Only fallback to protagonist if no match found
        return context.protagonist
```

**P.O.V. annotation**:

```python
class ExternalSpeaker:
    def __init__(self, character, location):
        self.character = character
        self.location = location
        self.pov_type = "external"  # Not in current scene
    
    def generate_context_note(self):
        return f"[{self.character.name} is at {self.location}]"

class LocalSpeaker:
    def __init__(self, character):
        self.character = character
        self.pov_type = "local"  # In current scene
    
    def generate_context_note(self):
        return f"[{self.character.name} is here]"
```

### Fix 2: Preserve active_speaker for Dispatched NPCs

**Don't clear active_speaker on dispatch**:

```python
def dispatch_npc(npc, location):
    # Move NPC to new location
    npc.location = location
    npc.dispatched = True
    
    # CORRECT: Preserve active_speaker status
    # npc.active_speaker = False  # <- Don't do this!
    
    # Remove from current scene's active set
    current_scene.remove_active(npc)
    
    # Add to dispatched set (still trackable)
    context.add_dispatched(npc)
    
    # Log dispatch for narrative continuity
    log.info(f"{npc.name} dispatched to {location}")
```

**Speaker history tracking**:

```python
class SpeakerHistory:
    def __init__(self):
        self.history = []  # Chronological speaker list
        self.dispatched_speakers = {}  # NPC -> last known speaker state
    
    def record_dispatch(self, npc):
        # Preserve speaker state before dispatch
        if npc.active_speaker:
            self.dispatched_speakers[npc.id] = {
                'character': npc,
                'last_utterance': npc.last_utterance,
                'dispatched_at': now()
            }
    
    def resolve_indirect_reference(self, ref, context):
        # Check if reference matches a dispatched speaker
        for npc_id, state in self.dispatched_speakers.items():
            if matches_reference(state['character'], ref):
                return state['character']
        
        # Fallback to active speakers
        return resolve_from_active(ref, context)
```

### Fix 3: Integrate Spatial Constraints into Speaker Resolution

**Use location to constrain speaker resolution**:

```python
def resolve_speaker_with_spatial_constraints(utterance, context):
    ref = extract_pronoun_or_description(utterance)
    
    # Get location context
    current_location = context.current_scene.location
    
    # Get all characters (active + dispatched)
    all_characters = get_all_characters(context)
    
    # Filter by spatial consistency
    # If utterance mentions location-specific details, constrain to that location
    mentioned_location = extract_location_hint(utterance)
    
    if mentioned_location:
        # Reference is about someone at specific location
        candidates = [c for c in all_characters if c.location == mentioned_location]
    else:
        # No location hint: prefer current scene, but allow dispatched
        candidates = sorted(all_characters, key=lambda c: (
            0 if c.location == current_location else 1,  # Prefer current location
            0 if c.active_speaker else 1  # Prefer active speakers
        ))
    
    # Match reference against spatially-constrained candidates
    match = find_best_match(ref, candidates)
    
    if match:
        return match
    else:
        # Only fallback to protagonist if no spatially-consistent match
        return context.protagonist
```

**Scene-based location validation**:

```python
def validate_spatial_unity(speaker, scene):
    """Ensure speaker location matches scene location."""
    if speaker.location != scene.location:
        # Check if this is an external reference (allowed)
        if is_external_reference(speaker, scene):
            # Speaker is at different location but being referenced
            # This is OK, but annotate it
            return ExternalReference(speaker, scene)
        else:
            # True spatial violation
            raise SpatialUnityViolation(
                f"{speaker.name} is at {speaker.location} "
                f"but scene is at {scene.location}"
            )
    
    return LocalPresence(speaker, scene)
```

### Fix 4: Multi-Location Scene Handling

**Track multiple concurrent locations**:

```python
class MultiLocationScene:
    def __init__(self):
        self.locations = {}  # location_id -> set of characters
    
    def add_character(self, character, location):
        if location not in self.locations:
            self.locations[location] = set()
        self.locations[location].add(character)
    
    def get_speaker_for_reference(self, ref, hint_location=None):
        """Resolve speaker considering multiple locations."""
        
        # If location hint provided, use it
        if hint_location and hint_location in self.locations:
            candidates = self.locations[hint_location]
        else:
            # Aggregate all locations
            candidates = set()
            for loc_chars in self.locations.values():
                candidates.update(loc_chars)
        
        # Match reference
        match = find_best_match(ref, candidates)
        
        if match:
            # Return speaker with location context
            location = self._find_character_location(match)
            return LocatedSpeaker(match, location)
        
        return None
    
    def _find_character_location(self, character):
        for loc, chars in self.locations.items():
            if character in chars:
                return loc
        return None
```

## Verification

### Test 1: NPC Dispatch with Indirect Reference

```python
def test_npc_dispatch_indirect_reference():
    # Setup: Alice (protagonist) and Bob (NPC) in coffee shop
    context = Context()
    context.add_character(Alice, location="coffee_shop")
    context.add_character(Bob, location="coffee_shop")
    
    # Dispatch Bob to warehouse
    context.dispatch_npc(Bob, "warehouse")
    
    # User indirectly references Carol (at warehouse)
    utterance = "What did she say about the shipment?"
    
    # WRONG (old behavior): Resolves to Alice
    # speaker = resolve_speaker(utterance, context)
    # assert speaker == Alice  # <- Fails!
    
    # CORRECT (new behavior): Resolves to Carol at warehouse
    speaker = resolve_speaker_with_spatial_constraints(utterance, context)
    
    assert speaker.name == "Carol"
    assert speaker.location == "warehouse"
    assert speaker.pov_type == "external"
    
    # Verify spatial unity
    validation = validate_spatial_unity(speaker, context.current_scene)
    assert isinstance(validation, ExternalReference)
```

### Test 2: active_speaker Preservation

```python
def test_active_speaker_preservation():
    # Setup: Bob is active speaker
    context = Context()
    Bob.active_speaker = True
    Bob.last_utterance = "I'll check the warehouse"
    
    # Dispatch Bob
    context.dispatch_npc(Bob, "warehouse")
    
    # CORRECT: active_speaker status preserved
    assert Bob.dispatched == True
    assert Bob.active_speaker == True  # <- Still True!
    
    # Indirect reference should resolve to Bob
    utterance = "What did he say?"
    speaker = resolve_speaker(utterance, context)
    
    assert speaker == Bob
    assert speaker.location == "warehouse"
```

### Test 3: Spatial Unity Validation

```python
def test_spatial_unity():
    # Setup: Scene at coffee shop
    scene = Scene(location="coffee_shop")
    
    # Alice is at coffee shop (valid)
    alice = Character("Alice", location="coffee_shop")
    validation = validate_spatial_unity(alice, scene)
    assert isinstance(validation, LocalPresence)
    
    # Bob is at warehouse (invalid unless external reference)
    bob = Character("Bob", location="warehouse")
    
    # Without external reference context -> violation
    with pytest.raises(SpatialUnityViolation):
        validate_spatial_unity(bob, scene)
    
    # With external reference context -> allowed
    external_ref = ExternalReference(bob, scene)
    validation = validate_spatial_unity_with_context(bob, scene, external_ref)
    assert validation.is_valid()
```

### Test 4: Multi-Location Scene

```python
def test_multi_location_scene():
    scene = MultiLocationScene()
    
    # Add characters at different locations
    scene.add_character(Alice, "coffee_shop")
    scene.add_character(Bob, "warehouse")
    scene.add_character(Carol, "warehouse")
    
    # Reference with location hint
    utterance = "What did she say at the warehouse?"
    location_hint = "warehouse"
    
    speaker = scene.get_speaker_for_reference("she", location_hint)
    
    # Should resolve to someone at warehouse
    assert speaker.location == "warehouse"
    assert speaker.name in ["Bob", "Carol"]
    
    # Reference without location hint
    utterance2 = "What did she say?"
    speaker2 = scene.get_speaker_for_reference("she")
    
    # Should prefer active speakers, but allow any location
    assert speaker2 is not None
```

## Notes

### Edge Cases

1. **Multiple dispatched NPCs**: When multiple NPCs are dispatched to different locations, use location hints in utterance to disambiguate.

2. **Indirect references to protagonist**: If user says "what did I say?" while protagonist is not the active speaker, check speaker history.

3. **Location changes mid-utterance**: If utterance spans multiple locations ("Alice said X, then Bob replied Y at the warehouse"), parse as multi-location scene.

4. **Temporal references**: "What did she say earlier?" might refer to a dispatched NPC's last utterance before dispatch.

5. **Pronoun ambiguity**: "She" could refer to multiple female characters. Use location, recent mentions, and narrative context to disambiguate.

### Implementation Recommendations

1. **Track speaker history**: Maintain chronological list of speakers with timestamps and locations.

2. **Annotate external references**: When resolving to a dispatched NPC, annotate the output with location context.

3. **Validate before generating**: Check spatial unity BEFORE generating response, not after.

4. **Preserve context across dispatch**: Don't lose speaker state when NPCs are dispatched.

5. **Use location as constraint**: Location should narrow down speaker candidates, not just validate them.

### Related Issues

- #1643: Original intake reporting NPC dispatch and indirect mention failure
- Related: Vocative/entity disambiguation lessons (same narrative consistency domain)

### Verification Status

**Not tested with live roleplay system**. The solution is based on error analysis and narrative consistency principles. Verification tests are provided for users to implement in their environment.

---

*Lesson created by AUTO (AI Agent) | Bilingual Chinese-English-Portuguese capability | 2026-09-16*
