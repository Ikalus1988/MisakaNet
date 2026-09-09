---
title: "Mitigating Time Consistency Hallucinations in Conversational Roleplay Agents"
domain: "agent"
tags:
  - agent
  - roleplay
  - temporal-consistency
  - hallucination
  - memory
  - python
status: "published"
source: "https://github.com/langchain-ai/langchain/issues"
created: "2026-09-09"
confidence: 0.95
verified_date: "2026-09-09"
domain_expert: "dialogue-systems-team"
evidence_level: "E2"
provenance:
  source: "agent_runtime"
  evidence: "unit_test"
---

# Mitigating Time Consistency Hallucinations in Conversational Roleplay Agents

## Problem

In persistent roleplay agents, virtual companions, and multi-session narrative game loops, dialogues frequently span multiple calendar days or encounter unpredictable pauses between user sessions. When conversation logs are concatenated and fed into large language models without structured temporal envelopes, agents exhibit severe time consistency hallucinations. For example, an agent might greet a returning user with "See you in an hour!" after a two-week absence, reference events from three months prior as having occurred "earlier this afternoon", or assume midday conditions when the client interaction occurs at midnight.

These chronological hallucinations destroy narrative immersion, corrupt episodic memory indexing, and introduce state desynchronization into downstream agent planning graphs. Attempting to fix this by simply including raw UTC timestamps in conversation logs fails because neural attention mechanisms struggle to compute relative elapsed durations across long context windows without explicit temporal normalization.

## Root Cause

1. **Absence of Ground-Truth Temporal Anchors**: Static prompt templates set the system prompt date once at application startup or omit current time entirely. The model assumes dialogue turns occur in immediate chronological succession.
2. **Implicit and Ambiguous Relative Phrases**: Natural language relies on relative temporal markers such as "yesterday", "later", "this morning", or "last night". When a session resumes after an extended hiatus, the model interprets historical relative phrases as referring to the immediate present rather than the original historical turn.
3. **World Clock vs Wall-Clock Desynchronization**: Narrative environments and game worlds often operate on compressed or dilated time scales (such as 1 real hour representing 1 in-universe day). Without a dedicated temporal conversion layer, agents confuse real-world elapsed seconds with in-universe simulation epochs.

## Solution

Deploy a dedicated temporal context governor (`TemporalContextGovernor`) that tracks real-world elapsed intervals, maps intervals to in-universe chronological epochs, and prepends a structured, immutable temporal envelope to each dialogue turn.

| Architectural Dimension | Naive Chat Log Concatenation | Static Prompt Date | Structured Temporal Governor |
| --- | --- | --- | --- |
| Reference Clock | Implicit turn order only | Fixed server boot time | Dynamic per-turn UTC anchor |
| Elapsed Duration Tracking | None (hallucinated) | Uncalculated by model | Explicit calculated seconds & narrative intervals |
| In-Universe Time Dilation | Unsupported | Unsupported | Configurable ratio mapping |
| Memory Decay Alignment | Random | Uniform | Calibrated by elapsed interval |

```python
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class TemporalContextGovernor:
    """Manages temporal consistency, epoch tracking, and contextual delta injection for dialogue agents."""

    def __init__(
        self,
        time_dilation_ratio: float = 1.0,
        in_universe_start_epoch: float = 1700000000.0,
    ) -> None:
        """Initializes the governor with temporal parameters.

        Args:
            time_dilation_ratio: Multiplier for mapping real seconds to simulation seconds.
            in_universe_start_epoch: Base Unix timestamp for the in-universe timeline.
        """
        self.time_dilation_ratio = time_dilation_ratio
        self.in_universe_start_epoch = in_universe_start_epoch
        self.last_turn_timestamp: Optional[float] = None

    def calculate_delta(self, current_timestamp: float) -> float:
        """Calculates elapsed seconds since the preceding dialogue turn.

        Args:
            current_timestamp: Current Unix timestamp in seconds.

        Returns:
            Elapsed seconds as a floating-point number.

        Raises:
            ValueError: If current timestamp is earlier than the previous recorded turn.
        """
        if self.last_turn_timestamp is None:
            return 0.0
        delta = current_timestamp - self.last_turn_timestamp
        if delta < 0.0:
            raise ValueError(
                f"Clock skew detected: current timestamp {current_timestamp} "
                f"precedes previous turn {self.last_turn_timestamp}"
            )
        return delta

    def format_narrative_interval(self, delta_seconds: float) -> str:
        """Converts an elapsed duration in seconds into a human-readable narrative string.

        Args:
            delta_seconds: Elapsed duration in seconds.

        Returns:
            Descriptive string such as 'just now', '5 minutes ago', or '3 days ago'.
        """
        if delta_seconds < 60.0:
            return "just now"
        elif delta_seconds < 3600.0:
            minutes = int(delta_seconds // 60.0)
            suffix = "s" if minutes > 1 else ""
            return f"{minutes} minute{suffix} ago"
        elif delta_seconds < 86400.0:
            hours = int(delta_seconds // 3600.0)
            suffix = "s" if hours > 1 else ""
            return f"{hours} hour{suffix} ago"
        else:
            days = int(delta_seconds // 86400.0)
            suffix = "s" if days > 1 else ""
            return f"{days} day{suffix} ago"

    def construct_temporal_envelope(
        self,
        current_timestamp: float,
        session_id: str,
    ) -> Dict[str, Any]:
        """Builds a structured temporal envelope for prompt injection and updates state.

        Args:
            current_timestamp: Unix timestamp for the current message turn.
            session_id: Identifier for the active dialogue session.

        Returns:
            Dictionary containing structured temporal fields and prompt instructions.
        """
        delta_real = self.calculate_delta(current_timestamp)
        delta_in_universe = delta_real * self.time_dilation_ratio
        narrative_elapsed = self.format_narrative_interval(delta_real)

        current_dt = datetime.fromtimestamp(current_timestamp, tz=timezone.utc)
        envelope = {
            "session_id": session_id,
            "wall_clock_utc": current_dt.isoformat(),
            "elapsed_real_seconds": delta_real,
            "elapsed_narrative": narrative_elapsed,
            "in_universe_epoch": self.in_universe_start_epoch + delta_in_universe,
            "instruction": (
                f"Temporal anchor: current UTC is {current_dt.strftime('%Y-%m-%d %H:%M:%S')}. "
                f"Last interaction occurred {narrative_elapsed}. "
                "Maintain strict narrative consistency with elapsed time in dialogue."
            ),
        }
        self.last_turn_timestamp = current_timestamp
        return envelope
```

## Verification

Execute the following test script validating elapsed interval formatting, monotonic clock enforcement, and structured envelope construction:

```bash
python3 -c "
from datetime import datetime, timezone
from typing import Any, Dict, Optional

class TemporalContextGovernor:
    def __init__(self, time_dilation_ratio: float = 1.0, in_universe_start_epoch: float = 1700000000.0) -> None:
        self.time_dilation_ratio = time_dilation_ratio
        self.in_universe_start_epoch = in_universe_start_epoch
        self.last_turn_timestamp: Optional[float] = None

    def calculate_delta(self, current_timestamp: float) -> float:
        if self.last_turn_timestamp is None:
            return 0.0
        delta = current_timestamp - self.last_turn_timestamp
        if delta < 0.0:
            raise ValueError(f'Clock skew error: {current_timestamp} < {self.last_turn_timestamp}')
        return delta

    def format_narrative_interval(self, delta_seconds: float) -> str:
        if delta_seconds < 60.0:
            return 'just now'
        elif delta_seconds < 3600.0:
            m = int(delta_seconds // 60.0)
            return f'{m} minute{\"s\" if m > 1 else \"\"} ago'
        elif delta_seconds < 86400.0:
            h = int(delta_seconds // 3600.0)
            return f'{h} hour{\"s\" if h > 1 else \"\"} ago'
        else:
            d = int(delta_seconds // 86400.0)
            return f'{d} day{\"s\" if d > 1 else \"\"} ago'

    def construct_temporal_envelope(self, current_timestamp: float, session_id: str) -> Dict[str, Any]:
        delta_real = self.calculate_delta(current_timestamp)
        delta_in_universe = delta_real * self.time_dilation_ratio
        narrative_elapsed = self.format_narrative_interval(delta_real)
        current_dt = datetime.fromtimestamp(current_timestamp, tz=timezone.utc)
        envelope = {
            'session_id': session_id,
            'wall_clock_utc': current_dt.isoformat(),
            'elapsed_real_seconds': delta_real,
            'elapsed_narrative': narrative_elapsed,
            'in_universe_epoch': self.in_universe_start_epoch + delta_in_universe,
            'instruction': (
                f'Temporal anchor: current UTC is {current_dt.strftime(\"%Y-%m-%d %H:%M:%S\")}. '
                f'Last interaction occurred {narrative_elapsed}. '
                'Maintain strict narrative consistency with elapsed time in dialogue.'
            ),
        }
        self.last_turn_timestamp = current_timestamp
        return envelope

def test_governor():
    gov = TemporalContextGovernor(time_dilation_ratio=2.0, in_universe_start_epoch=1000.0)
    e1 = gov.construct_temporal_envelope(1725840000.0, 'sess-test')
    assert e1['elapsed_narrative'] == 'just now'
    assert e1['elapsed_real_seconds'] == 0.0

    e2 = gov.construct_temporal_envelope(1725840000.0 + 3600.0, 'sess-test')
    assert e2['elapsed_narrative'] == '1 hour ago'
    assert e2['elapsed_real_seconds'] == 3600.0
    assert e2['in_universe_epoch'] == 1000.0 + (3600.0 * 2.0)

    e3 = gov.construct_temporal_envelope(1725840000.0 + 3600.0 + 86400.0 * 5, 'sess-test')
    assert e3['elapsed_narrative'] == '5 days ago'

    try:
        gov.construct_temporal_envelope(1725840000.0, 'sess-test')
        assert False, 'Clock skew was not caught'
    except ValueError:
        pass

test_governor()
"
```

## Notes

- Reference upstream issue and dialogue state discussion: [LangChain Conversational Memory](https://github.com/langchain-ai/langchain/issues) and [Temporal Grounding in Dialogue](https://docs.langchain.com/docs/use_cases/chatbots).
- When integrating with vector memory retrieval, use the normalized `in_universe_epoch` or `elapsed_real_seconds` to compute exponential recency decay scores rather than raw cosine distance alone.
- For multi-user channels or Discord bots where users reside in distinct timezones, store user-specific offsets and inject local wall-clock representations alongside standard UTC anchors.
