---
title: Mitigating Roleplay Agent Temporal Consistency Hallucinations
domain: contrib
tags:
- agent\n- roleplay\n- memory\n- temporal\n- consistency
status: published
created: '2026-09-09'
source: community
evidence_level: E2
evidence_refs:
- issue:#1571
provenance:
  source: community
  contributor: Community
  evidence: post-publication
---

## Problem

In long-running conversational and multi-turn roleplay agents, models frequently suffer from temporal hallucinations and timeline drift.

Common symptoms include:
1. The agent claims events occurred "a few hours ago" when weeks or months have elapsed according to session metadata.
2. In simulated game worlds or historical roleplay, the model conflates real-world wall-clock timestamps with simulated in-game calendar progression.
3. In multi-agent interactions, agents reference future turns or disagree on elapsed durations for past shared events.

## Root Cause

1. **Absence of Internal Chronometer:** Autoregressive LLMs have no intrinsic sense of passing time. Time is inferred purely from token sequence ordering.
2. **Missing Delta Framing:** Standard message histories pass only raw role/content pairs (`{"role": "user", "content": "..."}`) without explicit time interval annotations between turns.
3. **Relative Linguistic Ambiguity:** Words like "yesterday", "later", or "recently" in conversational context get anchored to model pretraining distributions rather than current session state.

## Solution

Anchor agent episodic memory using an explicit temporal state header injected into each conversational turn:

```python
from datetime import datetime
from typing import List, Dict

class TemporalContextManager:
    """
    Tracks session timestamps and formats messages with explicit temporal anchors
    to maintain time consistency across multi-turn agent conversations.
    """
    def __init__(self, simulation_start: datetime):
        self.sim_clock = simulation_start
        self.last_turn_time = simulation_start

    def format_message(self, role: str, content: str, current_time: datetime) -> Dict[str, str]:
        delta_seconds = int((current_time - self.last_turn_time).total_seconds())
        delta_hours = delta_seconds // 3600
        delta_days = delta_hours // 24

        if delta_days > 0:
            elapsed_str = f"+{delta_days} days since last interaction"
        elif delta_hours > 0:
            elapsed_str = f"+{delta_hours} hours since last interaction"
        else:
            elapsed_str = f"+{delta_seconds} seconds since last interaction"

        temporal_header = (
            f"[Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Interval: {elapsed_str}]"
        )
        self.last_turn_time = current_time

        return {
            "role": role,
            "content": f"{temporal_header}\n{content}"
        }
```

Include temporal ground rules in the system prompt:
```text
All user messages begin with [Current Time: ... | Interval: ...].
You must anchor your dialogue and relative time references strictly to this timeline.
Never assume consecutive messages happened immediately unless the interval indicates seconds.
```

## Verification

```bash
python -c '
from datetime import datetime, timedelta
start = datetime(2026, 9, 1, 10, 0, 0)
later = start + timedelta(days=5, hours=3)
mgr = TemporalContextManager(start)
msg = mgr.format_message("user", "Long time no see!", later)
assert "+5 days" in msg["content"]
assert "2026-09-06" in msg["content"]
print("Verification passed: fix command exited 0")
'
```

**Expected Output:** command completes without error, then `Verification passed: fix command exited 0` is printed.
