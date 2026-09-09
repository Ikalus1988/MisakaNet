---
title: LLM Streaming Output Thought Tags Stripping Protocol
domain: contrib
tags:
- llm\n- deepseek\n- streaming\n- parsing\n- agent
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

When consuming streaming tokens from reasoning models (such as DeepSeek-R1, QwQ, or Gemini Thinking), models wrap their internal chain of thought in `<thought>...</thought>` or `<think>...</think>` tags.

In streaming applications and tool-calling agent loops, these raw tokens leak into user interfaces or cause fatal errors:
1. UI chat interfaces display raw internal reasoning before the actual response.
2. Structured output extractors (e.g. JSON tool arguments) fail with `json.decoder.JSONDecodeError` because opening or closing thinking tags corrupt the JSON envelope.
3. Partial token chunks split tags across boundaries (e.g., chunk 1: `<thi`, chunk 2: `nk>`), breaking naive string replacement.

## Root Cause

1. **Chunk Boundary Splitting:** Streaming response chunks do not align with XML/HTML tag boundaries. A tag like `</think>` can arrive fragmented across multiple SSE packets.
2. **Stateless Filter Failures:** Applying stateless `.replace("<think>", "")` on individual streaming chunks fails because the opening tag, thinking body, and closing tag arrive across dozens of separate chunks.
3. **Preamble Contamination:** Agent tool callers often pipe the raw model response directly into a JSON parser without verifying whether thinking tokens preceded the JSON payload.

## Solution

Implement a stateful streaming filter with a boundary lookahead buffer:

```python
import re

class StreamingThoughtStripper:
    """
    Stateful filter that strips <think>...</think> and <thought>...</thought>
    blocks from an LLM token stream while handling partial chunk boundaries.
    """
    def __init__(self):
        self.in_thought = False
        self.buffer = ""
        self.tag_start_re = re.compile(r"<(think|thought)>", re.IGNORECASE)
        self.tag_end_re = re.compile(r"</(think|thought)>", re.IGNORECASE)

    def process_chunk(self, chunk: str) -> str:
        self.buffer += chunk
        visible_output = []

        while self.buffer:
            if not self.in_thought:
                start_match = self.tag_start_re.search(self.buffer)
                if start_match:
                    visible_output.append(self.buffer[:start_match.start()])
                    self.buffer = self.buffer[start_match.end():]
                    self.in_thought = True
                else:
                    potential_idx = self.buffer.rfind("<")
                    if potential_idx != -1 and potential_idx >= len(self.buffer) - 10:
                        visible_output.append(self.buffer[:potential_idx])
                        self.buffer = self.buffer[potential_idx:]
                        break
                    else:
                        visible_output.append(self.buffer)
                        self.buffer = ""
            else:
                end_match = self.tag_end_re.search(self.buffer)
                if end_match:
                    self.buffer = self.buffer[end_match.end():]
                    self.in_thought = False
                else:
                    potential_idx = self.buffer.rfind("<")
                    if potential_idx != -1 and potential_idx >= len(self.buffer) - 10:
                        self.buffer = self.buffer[potential_idx:]
                    else:
                        self.buffer = ""
                    break

        return "".join(visible_output)

    def flush(self) -> str:
        if self.in_thought:
            self.buffer = ""
            return ""
        out = self.buffer
        self.buffer = ""
        return out
```

For non-streaming complete outputs, strip using clean regex before JSON parsing:

```python
def clean_reasoning_tags(raw_text: str) -> str:
    cleaned = re.sub(r"<(think|thought)>[\s\S]*?</\1>", "", raw_text, flags=re.IGNORECASE)
    return cleaned.strip()
```

## Verification

```bash
python -c '
from thought_stripper import StreamingThoughtStripper
stripper = StreamingThoughtStripper()
chunks = ["Hello! ", "<thi", "nk>secret reasoning</thi", "nk>Here is the final answer."]
result = "".join(stripper.process_chunk(c) for c in chunks) + stripper.flush()
assert result == "Hello! Here is the final answer.", f"Unexpected: {result}"
print("Verification passed: fix command exited 0")
'
```

**Expected Output:** command completes without error, then `Verification passed: fix command exited 0` is printed.
