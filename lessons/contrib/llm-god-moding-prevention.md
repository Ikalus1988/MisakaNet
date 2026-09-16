---
domain: "roleplay-safety"
title: "LLM God-Moding: Preventing Models from Speaking or Acting for the User"
status: "draft"
verification: "metadata-normalized"
{"title": "LLM God-Moding: Preventing Models from Speaking or Acting for the User", "domain": "roleplay-safety", "tags": ["roleplay", "god-moding", "user-agency", "speaker-boundary", "output-filtering", "multi-turn"], "status": "published", "confidence": "0.95", "created": "2026-09-16", "updated": "2026-09-16", "source": "intake-1574", "verified_date": "2026-09-16", "domain_expert": "AUTO", "provenance": {"issue": "#1574"}}
---

# LLM God-Moding: Preventing Models from Speaking or Acting for the User

## Problem

In multi-turn roleplay scenarios, LLMs generate responses that speak or act on behalf of the user (god-moding), creating:

1. **User dialogue generation**: Model writes "User says: ..." or generates dialogue attributed to the user
2. **User action narration**: Model describes user actions in 2nd person ("You walk to the door" when user hasn't input this)
3. **Speaker boundary violation**: Model continues generating user's turn instead of stopping at its own turn boundary

**Example failure**:

```
User: "I enter the tavern and look around."

LLM (WRONG):
  The barkeeper nods at you. You walk to the bar and say, "What's the news today?"
  The barkeeper replies, "Not much happening..."
  
  ^^^ PROBLEM: Model generated user action ("You walk to the bar") 
      and user dialogue ("What's the news today?")
```

**Impact**: Breaks user agency, creates confusion about who said/did what, undermines roleplay immersion.

Related issue: #1574

## Root Cause

### Mechanism 1: Autoregressive Decoding Treats User Text as Continuable

**Why it happens**: LLMs are trained to predict the next token. When the conversation history includes user turns, the model sees user dialogue as just another text pattern to continue.

**Technical detail**:

```python
# Conversation history as seen by model
conversation = [
    {"role": "user", "content": "I enter the tavern."},
    {"role": "assistant", "content": "The barkeeper nods."},
    # Model now generates next tokens
    # PROBLEM: Nothing stops it from continuing as "user" again
]

# Model sees this as a sequence to continue:
# "I enter the tavern." -> "The barkeeper nods." -> [continues...]
# It might generate: "You walk to the bar and say..."
```

**Why training data amplifies this**: In training data (novels, scripts, conversations), dialogue often alternates between speakers. The model learns to predict "what comes next" which can include the other speaker's response.

### Mechanism 2: System Prompts Don't Enforce Turn Boundaries

**Why it happens**: Most roleplay system prompts describe characters and scenarios but don't explicitly mark turn boundaries or prohibit speaking for the user.

**Insufficient prompt**:

```
You are a roleplay assistant. You play the role of the barkeeper in a medieval tavern.
The user is a traveler. Respond in character.

PROBLEM: No explicit instruction about turn boundaries.
Model might interpret "respond in character" as "continue the scene" 
which could include describing user actions.
```

**Missing constraints**:
- No explicit "do not speak for the user"
- No turn boundary markers
- No distinction between "describe environment" vs "describe user actions"

### Mechanism 3: Multi-Turn Concatenation Lacks Speaker Constraints

**Why it happens**: When conversation history is concatenated into a single prompt, speaker boundaries become implicit. The model doesn't have structural information about whose turn it is.

**Technical detail**:

```python
# Typical multi-turn prompt construction
prompt = f"""
System: You are a barkeeper in a medieval tavern.

User: I enter the tavern and look around.
Assistant: The barkeeper nods at you from behind the counter.
User: [WAITING FOR INPUT]

# PROBLEM: Model sees this as continuous text, not structured turns
# It might generate: "You walk to the bar and say..."
# because there's no structural marker saying "STOP - it's user's turn now"
```

**Why this compounds**: Each turn added to history makes the pattern more ambiguous. After 10+ turns, the model has seen many speaker alternations and might "helpfully" generate the next user turn.

## Solution

### Fix 1: Explicit Turn Boundary Instructions in System Prompt

**Add clear constraints**:

```python
system_prompt = """
You are a roleplay assistant playing the barkeeper in a medieval tavern.
The user plays a traveler.

CRITICAL RULES:
1. ONLY generate dialogue and actions for YOUR character (the barkeeper)
2. NEVER generate dialogue or actions for the user's character
3. NEVER write "You say..." or "You do..." - only describe your character's reactions
4. Stop immediately after your character's turn
5. Wait for user input before continuing

TURN BOUNDARY:
- Your turn: Describe barkeeper's dialogue, actions, reactions
- User's turn: Describe traveler's dialogue, actions, decisions
- NEVER cross the boundary

EXAMPLE (CORRECT):
User: "I enter the tavern."
Assistant: "The barkeeper looks up from cleaning a glass. 'Welcome, traveler. What brings you to our humble tavern?'"

EXAMPLE (WRONG - god-moding):
User: "I enter the tavern."
Assistant: "You walk to the bar and sit down. 'Give me ale,' you say. The barkeeper nods."
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                      GOD-MODING: Generated user action and dialogue
"""
```

### Fix 2: Structured Speaker Fields Instead of Plain Text

**Use structured format to enforce boundaries**:

```python
# Instead of plain text conversation, use structured format
conversation = {
    "system": "You are a barkeeper...",
    "turns": [
        {
            "speaker": "user",
            "character": "traveler",
            "content": "I enter the tavern and look around.",
            "actions": ["enter", "look_around"]
        },
        {
            "speaker": "assistant",
            "character": "barkeeper",
            "content": "The barkeeper nods at you from behind the counter.",
            "actions": ["nod"],
            "dialogue": "Welcome, traveler."
        }
    ],
    "current_turn": "assistant",  # <- Explicit turn marker
    "allowed_speaker": "assistant"  # <- Constraint
}

# Model generates within structure
output = generate_with_structure(conversation)

# Output is constrained to current_turn speaker
assert output["speaker"] == "assistant"
assert output["character"] == "barkeeper"
```

**Implementation**:

```python
def generate_roleplay_turn(conversation, allowed_speaker):
    """Generate response constrained to allowed speaker."""
    
    prompt = f"""
Current turn: {allowed_speaker}
Allowed character: {conversation['characters'][allowed_speaker]}

Generate ONLY dialogue and actions for {allowed_speaker}.
Do NOT generate content for other characters.

Output format:
{{
    "speaker": "{allowed_speaker}",
    "character": "{conversation['characters'][allowed_speaker]}",
    "dialogue": "...",
    "actions": [...]
}}
"""
    
    response = llm.generate(prompt)
    parsed = parse_json(response)
    
    # Validate speaker constraint
    if parsed["speaker"] != allowed_speaker:
        raise SpeakerViolation(f"Model generated for {parsed['speaker']} instead of {allowed_speaker}")
    
    return parsed
```

### Fix 3: Output-Side Filtering for User-Attributed Content

**Detect and strip god-moding**:

```python
import re

def detect_godmoding(output, user_character_name):
    """Detect if output contains user dialogue or actions."""
    
    violations = []
    
    # Pattern 1: "You say..." or "You do..."
    you_patterns = [
        r'You\s+(say|ask|reply|shout|whisper|do|walk|run|sit|stand)',
        r'"[^"]*"\s*,\s*you\s+(say|ask|reply)',
        r'You\s+\w+[^.]*\?',  # "You do something?"
    ]
    
    for pattern in you_patterns:
        matches = re.findall(pattern, output, re.IGNORECASE)
        if matches:
            violations.append(f"User action/dialogue detected: {matches[0]}")
    
    # Pattern 2: User character name in dialogue tags
    if user_character_name:
        name_pattern = rf'{user_character_name}\s+(says|asks|replies|does)'
        matches = re.findall(name_pattern, output, re.IGNORECASE)
        if matches:
            violations.append(f"User character dialogue detected: {matches[0]}")
    
    # Pattern 3: 2nd person action narration
    second_person = re.findall(r'You\s+\w+\s+\w+[^.]*\.', output)
    if len(second_person) > 1:  # More than one 2nd person sentence
        violations.append(f"2nd person narration detected: {len(second_person)} sentences")
    
    return violations

def filter_godmoding(output, user_character_name):
    """Strip god-moding content from output."""
    
    violations = detect_godmoding(output, user_character_name)
    
    if violations:
        # Find where god-moding starts and truncate
        you_match = re.search(r'You\s+(say|do|walk|run|sit)', output, re.IGNORECASE)
        if you_match:
            # Truncate before user action
            clean_output = output[:you_match.start()].strip()
            return clean_output, violations
    
    return output, []
```

### Fix 4: Guardrail with Targeted Retry

**Retry with explicit correction**:

```python
def generate_with_guardrail(conversation, user_character_name, max_retries=2):
    """Generate with god-moding detection and retry."""
    
    for attempt in range(max_retries + 1):
        output = generate_roleplay_turn(conversation, "assistant")
        
        # Check for god-moding
        violations = detect_godmoding(output, user_character_name)
        
        if not violations:
            return output  # Clean output
        
        if attempt < max_retries:
            # Retry with explicit correction
            correction_prompt = f"""
PREVIOUS OUTPUT (REJECTED - contained god-moding):
{output}

VIOLATIONS DETECTED:
{chr(10).join(violations)}

CORRECTION INSTRUCTIONS:
1. Remove all user dialogue and actions
2. Generate ONLY barkeeper's response
3. Do NOT write "You say..." or "You do..."
4. Stop after barkeeper's turn

Regenerate:
"""
            output = llm.generate(correction_prompt)
        else:
            # Max retries exceeded - return filtered version
            clean_output, _ = filter_godmoding(output, user_character_name)
            return clean_output
    
    return output
```

### Fix 5: Stop Sequences for Turn Boundaries

**Use stop tokens to prevent overflow**:

```python
def generate_with_stop_sequences(conversation):
    """Generate with stop sequences at turn boundaries."""
    
    # Define stop sequences that indicate user turn
    stop_sequences = [
        "\nUser:",
        "\nYou say:",
        "\nYou do:",
        f"\n{conversation['user_character']}:",
    ]
    
    response = llm.generate(
        conversation['prompt'],
        stop=stop_sequences,  # Stop at these sequences
        max_tokens=200
    )
    
    # Verify we didn't generate user turn
    for stop_seq in stop_sequences:
        if stop_seq in response:
            # Truncate at stop sequence
            response = response.split(stop_seq)[0].strip()
    
    return response
```

## Verification

### Test 1: God-Moding Detection

```python
def test_godmoding_detection():
    # CORRECT output (no god-moding)
    correct = "The barkeeper nods. 'Welcome, traveler. What brings you here?'"
    violations = detect_godmoding(correct, "traveler")
    assert len(violations) == 0
    
    # WRONG output (god-moding: user action)
    wrong1 = "You walk to the bar and sit down. The barkeeper nods."
    violations1 = detect_godmoding(wrong1, "traveler")
    assert len(violations1) > 0
    assert any("user action" in v.lower() for v in violations1)
    
    # WRONG output (god-moding: user dialogue)
    wrong2 = "The barkeeper looks up. You say, 'Give me ale.' He nods."
    violations2 = detect_godmoding(wrong2, "traveler")
    assert len(violations2) > 0
    assert any("user dialogue" in v.lower() or "user character" in v.lower() for v in violations2)
```

### Test 2: Output Filtering

```python
def test_godmoding_filtering():
    # Output with god-moding
    dirty = "The barkeeper nods. You walk to the bar and say, 'Ale please.' He pours a drink."
    
    clean, violations = filter_godmoding(dirty, "traveler")
    
    # Should truncate before user action
    assert "You walk" not in clean
    assert "You say" not in clean
    assert "barkeeper nods" in clean
    assert len(violations) > 0
```

### Test 3: Guardrail Retry

```python
def test_guardrail_retry():
    # Mock LLM that initially god-modes
    mock_llm = MockLLM(responses=[
        "You enter the tavern. The barkeeper nods.",  # God-moding
        "The barkeeper nods. 'Welcome.'",  # Correct (retry)
    ])
    
    conversation = {"prompt": "Continue the roleplay...", "user_character": "traveler"}
    
    output = generate_with_guardrail(conversation, "traveler", max_retries=2)
    
    # Should not contain god-moding
    violations = detect_godmoding(output, "traveler")
    assert len(violations) == 0
```

### Test 4: Turn Boundary Measurement

```python
def test_turn_boundary_accuracy():
    """Measure god-moding rate before and after fix."""
    
    test_cases = [
        "I enter the tavern.",
        "I look around the room.",
        "I approach the bar.",
    ]
    
    # BEFORE fix: high god-moding rate
    before_violations = 0
    for case in test_cases:
        output = generate_without_fix(case)
        violations = detect_godmoding(output, "traveler")
        if violations:
            before_violations += 1
    
    before_rate = before_violations / len(test_cases)
    
    # AFTER fix: low god-moding rate
    after_violations = 0
    for case in test_cases:
        output = generate_with_fix(case)
        violations = detect_godmoding(output, "traveler")
        if violations:
            after_violations += 1
    
    after_rate = after_violations / len(test_cases)
    
    # Fix should reduce god-moding rate by >80%
    reduction = (before_rate - after_rate) / before_rate
    assert reduction > 0.8, f"Fix only reduced god-moding by {reduction:.1%}"
```

### Test 5: Integration Test

```python
def test_multi_turn_no_godmoding():
    """Run 10 turns and verify no god-moding."""
    
    conversation = initialize_conversation()
    
    for turn in range(10):
        # Generate assistant turn
        output = generate_with_guardrail(conversation, "traveler")
        
        # Verify no god-moding
        violations = detect_godmoding(output, "traveler")
        assert len(violations) == 0, f"Turn {turn}: god-moding detected: {violations}"
        
        # Add to conversation
        conversation['turns'].append({
            "speaker": "assistant",
            "content": output
        })
        
        # Simulate user input
        user_input = get_user_input()
        conversation['turns'].append({
            "speaker": "user",
            "content": user_input
        })
```

## Notes

### Edge Cases

1. **Narrator voice**: Some roleplay styles use 3rd person narrator ("The traveler enters the tavern"). Distinguish narrator description from user action generation.

2. **Group scenes**: When multiple NPCs are present, model might generate actions for all of them. Constrain to only the assigned character(s).

3. **Flashback/memory**: User might say "Remember when I said...". Model should not generate the full quoted dialogue, only reference it.

4. **Implicit actions**: "I walk to the bar" is explicit user action. Model should react, not continue with "You order a drink."

5. **Dialogue tags**: "You say" is obvious god-moding. But also watch for "'Ale,' you mutter" or similar patterns.

### Related Lessons

- NPC dispatch and speaker disambiguation (#1643)
- Vocative/entity disambiguation in roleplay
- Dialogue loop and context poisoning

### Implementation Priority

1. **High**: Explicit system prompt instructions (immediate fix)
2. **High**: Output-side filtering (catches violations)
3. **Medium**: Structured speaker fields (prevents violations)
4. **Medium**: Stop sequences (prevents overflow)
5. **Low**: Guardrail retry (expensive but thorough)

### Verification Status

**Not tested with live roleplay system**. The solution is based on error analysis and roleplay best practices. Verification tests are provided for users to implement in their environment.

---

*Lesson created by AUTO (AI Agent) | Bilingual Chinese-English-Portuguese capability | 2026-09-16*
