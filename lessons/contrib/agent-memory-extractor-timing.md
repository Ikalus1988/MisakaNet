{"title": "Agent Memory Extractor Timing — Eager vs Lazy with Implementation", "domain": "agent", "subdomain": "memory", "tags": ["agent-memory", "extractor", "timing", "token-efficiency", "quality"], "source": "brgsk.xyz", "status": "published", "confidence": "0.85", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

Agent memory extractors that run at the wrong time waste tokens or produce low-quality extractions. Eager extraction (every message) wastes tokens on small talk. Lazy extraction (end of session) degrades quality on long transcripts due to "lost in the middle" effect.

## Root Cause

LLMs attend worse to material placed in the middle of long contexts. A 50-message transcript degrades extraction quality compared to 5 focused messages.

## Solution

### Component Anatomy

Every agent memory library has 4 components:

| Component | Function | Key Choice |
|-----------|----------|------------|
| **Extractor** | Reads conversation, decides what to keep | Timing: eager vs lazy vs hybrid |
| **Statements** | Short abstracted facts | Granularity: atomic vs composite |
| **Retriever** | Recalls relevant memories | Strategy: vector + keyword + time decay |
| **Store** | Persistence | Backend: vector / relational / hybrid |

### Hybrid Timing Strategy

```python
import re

HIGH_DENSITY_PATTERNS = [
    r"(?i)(prefer|like|always|never|remember that|my .+ is)",
    r"(?i)(fix|solve|workaround|the issue was|root cause)",
    r"(?i)(decision|chose|picked|going with|locked in)",
]

LOW_DENSITY_PATTERNS = [
    r"(?i)^(hi|hello|thanks|ok|sure|got it|yes|no)\s*[.!?]?$",
    r"(?i)^(lol|haha|nice|cool|great)\s*[.!?]?$",
]

def should_extract(message: str) -> bool:
    for pattern in HIGH_DENSITY_PATTERNS:
        if re.search(pattern, message):
            return True
    for pattern in LOW_DENSITY_PATTERNS:
        if re.match(pattern, message.strip()):
            return False
    return len(message) > 50
```

### Extraction Prompts

```python
EXTRACT_PROMPT = """Analyze this message and extract factual statements.
Only extract: preferences, corrections, decisions, facts.
Skip: greetings, acknowledgments, questions, opinions.

Format: one statement per line, prefixed with type:
- PREF: user preference
- FACT: world knowledge
- CORR: correction to previous belief
- DEC: decision made

Message: {message}
Statements:"""

SUMMARY_PROMPT = """Given this transcript, extract the 5 most important
durable facts. Focus on preferences, decisions, corrections, key facts.

Transcript: {transcript}
Top 5 facts:"""
```

### Token Usage Comparison

| Strategy | Tokens (50 msgs) | Quality | Latency |
|----------|-----------------|---------|---------|
| Eager (every message) | ~15,000 | High | High (50 calls) |
| Lazy (session end) | ~2,000 | Low (lost-in-middle) | Low (1 call) |
| **Hybrid (density filter)** | **~4,000** | **High** | **Medium (~10 calls)** |

## Verification

1. Run eager extraction on a 50-message conversation — note token count
2. Run hybrid extraction — should use ~70% fewer tokens
3. Compare extracted statements — hybrid should capture same key facts
4. Test with 40 low-density + 10 high-density messages

## Notes

- Episodic/Semantic/Procedural labels from Tulving (1972) but many libraries just贴标签
- Source: https://brgsk.xyz/agent-memory-anatomy/
