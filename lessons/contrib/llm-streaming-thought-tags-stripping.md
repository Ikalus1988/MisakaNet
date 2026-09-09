---
title: "Streaming Thought Tags Stripping: State-Machine Buffer for Reasoning Models"
domain: "llm"
tags:
  - deepseek-r1
  - reasoning
  - streaming
  - thought-tags
  - parser
  - python
status: "published"
source: "https://github.com/vllm-project/vllm/issues"
created: "2026-09-09"
confidence: 0.95
verified_date: "2026-09-09"
domain_expert: "agent-runtime-team"
evidence_level: "E2"
provenance:
  source: "agent_runtime"
  evidence: "unit_test"
---

# Streaming Thought Tags Stripping: State-Machine Buffer for Reasoning Models

## Problem

Reasoning models such as DeepSeek-R1, Qwen-QwQ, and OpenAI-compatible reasoning variants emit internal chain-of-thought traces wrapped within structural markup tags such as `<think>...</think>` or `<thought>...</thought>`. In streaming agent pipelines and gateway proxies, passing these raw tokens directly to client interfaces or tool call executors causes severe degradation. End-user chat interfaces display internal model monologues, downstream structured output parsers encounter schema validation crashes, and automated function calling agents ingest internal reasoning tokens as tool arguments, triggering unexpected execution errors.

Naive post-processing methods such as single-pass regular expressions (`re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)`) work only on complete, non-streaming completions. When applied to streaming chunks, regular expressions fail because tag boundaries fragment across network read buffers. Attempting to suppress chunks until closing tags arrive introduces unacceptable Time-To-First-Token (TTFT) latency spikes or leaks partial markers when tag tokens are split.

## Root Cause

1. **Arbitrary Chunk Boundary Splitting**: Stream chunks emitted over HTTP Server-Sent Events (SSE) or WebSockets slice token strings arbitrarily. An opening tag like `<think>` often arrives partitioned across multiple chunks (for example chunk N ends with `<th`, and chunk N+1 begins with `ink>`). Per-chunk string searching misses these boundary-straddling patterns.
2. **Greedy Flushing and False Positives**: Naive buffering layers that pause emission upon seeing any `<` character stall standard markdown or HTML output (such as `x < y` or `<div>`). Without lookahead prefix matching, parsers either emit incomplete tag fragments prematurely or hold non-tag content indefinitely.
3. **Premature Termination on Truncated Streams**: If a model reaches its maximum generation token limit (`finish_reason: length`) while still inside a thinking block, the closing `</think>` tag is never emitted. Parsers lacking explicit stream termination handlers leak incomplete buffers or fail to finalize internal state cleanly.

## Solution

Implement a stateful streaming processor with bounded prefix lookahead. The processor manages explicit transitions between content emission, speculative prefix buffering, and reasoning suppression.

| State | Buffer Condition | Operational Action |
| --- | --- | --- |
| `EMITTING` | No tag prefix detected in buffer tail | Yield content tokens immediately to maintain low TTFT |
| `EMITTING` | Buffer tail matches partial tag prefix | Hold matching prefix; yield preceding confirmed text |
| `INSIDE_THOUGHT` | Content between `<think>` and `</think>` | Suppress tokens or route to secondary reasoning stream |
| `INSIDE_THOUGHT` | Buffer tail matches partial closing tag prefix | Retain prefix candidate until match confirmation or mismatch |

```python
from enum import Enum
from typing import Generator


class StreamState(Enum):
    EMITTING = 1
    INSIDE_THOUGHT = 2


class StreamingThoughtStripper:
    """Stateful streaming filter that strips reasoning thought tags across arbitrary chunk boundaries."""

    def __init__(
        self,
        open_tag: str = "<think>",
        close_tag: str = "</think>",
    ) -> None:
        """Initializes the stream filter with designated opening and closing boundary tags.

        Args:
            open_tag: Opening tag marking the start of internal thought traces.
            close_tag: Closing tag marking the end of internal thought traces.
        """
        self.open_tag = open_tag
        self.close_tag = close_tag
        self.state = StreamState.EMITTING
        self.buffer = ""

    def process_chunk(self, chunk: str) -> Generator[str, None, None]:
        """Ingests an incoming streaming text chunk and yields cleaned content tokens.

        Args:
            chunk: Arbitrary text chunk received from a streaming LLM response.

        Yields:
            Clean string tokens with thought tags and enclosed reasoning stripped.
        """
        self.buffer += chunk
        while self.buffer:
            if self.state == StreamState.EMITTING:
                idx = self.buffer.find(self.open_tag)
                if idx != -1:
                    if idx > 0:
                        yield self.buffer[:idx]
                    self.buffer = self.buffer[idx + len(self.open_tag) :]
                    self.state = StreamState.INSIDE_THOUGHT
                    continue

                matched_prefix = False
                for i in range(len(self.open_tag) - 1, 0, -1):
                    prefix = self.open_tag[:i]
                    if self.buffer.endswith(prefix):
                        safe_len = len(self.buffer) - i
                        if safe_len > 0:
                            yield self.buffer[:safe_len]
                            self.buffer = self.buffer[safe_len:]
                        matched_prefix = True
                        break

                if matched_prefix:
                    break

                yield self.buffer
                self.buffer = ""
                break

            elif self.state == StreamState.INSIDE_THOUGHT:
                idx = self.buffer.find(self.close_tag)
                if idx != -1:
                    self.buffer = self.buffer[idx + len(self.close_tag) :]
                    self.state = StreamState.EMITTING
                    continue

                matched_prefix = False
                for i in range(len(self.close_tag) - 1, 0, -1):
                    prefix = self.close_tag[:i]
                    if self.buffer.endswith(prefix):
                        self.buffer = prefix
                        matched_prefix = True
                        break

                if matched_prefix:
                    break

                self.buffer = ""
                break

    def flush(self) -> Generator[str, None, None]:
        """Flushes any remaining buffered text upon stream termination.

        Yields:
            Remaining uncommitted buffer content if stream ends outside a thought block.
        """
        if self.state == StreamState.EMITTING and self.buffer:
            yield self.buffer
            self.buffer = ""
        elif self.state == StreamState.INSIDE_THOUGHT:
            self.buffer = ""
```

## Verification

Execute the following unit test script verifying chunk split boundaries, partial tag prefixes, non-tag angle brackets, and stream flush behavior:

```bash
python3 -c "
from enum import Enum
from typing import Generator

class StreamState(Enum):
    EMITTING = 1
    INSIDE_THOUGHT = 2

class StreamingThoughtStripper:
    def __init__(self, open_tag: str = '<think>', close_tag: str = '</think>') -> None:
        self.open_tag = open_tag
        self.close_tag = close_tag
        self.state = StreamState.EMITTING
        self.buffer = ''

    def process_chunk(self, chunk: str) -> Generator[str, None, None]:
        self.buffer += chunk
        while self.buffer:
            if self.state == StreamState.EMITTING:
                idx = self.buffer.find(self.open_tag)
                if idx != -1:
                    if idx > 0:
                        yield self.buffer[:idx]
                    self.buffer = self.buffer[idx + len(self.open_tag):]
                    self.state = StreamState.INSIDE_THOUGHT
                    continue

                matched_prefix = False
                for i in range(len(self.open_tag) - 1, 0, -1):
                    prefix = self.open_tag[:i]
                    if self.buffer.endswith(prefix):
                        safe_len = len(self.buffer) - i
                        if safe_len > 0:
                            yield self.buffer[:safe_len]
                            self.buffer = self.buffer[safe_len:]
                        matched_prefix = True
                        break

                if matched_prefix:
                    break

                yield self.buffer
                self.buffer = ''
                break

            elif self.state == StreamState.INSIDE_THOUGHT:
                idx = self.buffer.find(self.close_tag)
                if idx != -1:
                    self.buffer = self.buffer[idx + len(self.close_tag):]
                    self.state = StreamState.EMITTING
                    continue

                matched_prefix = False
                for i in range(len(self.close_tag) - 1, 0, -1):
                    prefix = self.close_tag[:i]
                    if self.buffer.endswith(prefix):
                        self.buffer = prefix
                        matched_prefix = True
                        break

                if matched_prefix:
                    break

                self.buffer = ''
                break

    def flush(self) -> Generator[str, None, None]:
        if self.state == StreamState.EMITTING and self.buffer:
            yield self.buffer
            self.buffer = ''
        elif self.state == StreamState.INSIDE_THOUGHT:
            self.buffer = ''

def test_streaming():
    stripper = StreamingThoughtStripper()
    stream_chunks = [
        'Prefix answer. ',
        '<th',
        'ink>Evaluating token budget and step plan.</th',
        'ink> Final confirmed resolution.',
    ]
    emitted = []
    for c in stream_chunks:
        emitted.extend(list(stripper.process_chunk(c)))
    emitted.extend(list(stripper.flush()))
    combined = ''.join(emitted)
    assert combined == 'Prefix answer.  Final confirmed resolution.', f'Got {combined!r}'

    stripper_edge = StreamingThoughtStripper()
    edge_chunks = ['Compare if x < 10 and y <th', 'ink>discard</think> then output is valid']
    emitted_edge = []
    for c in edge_chunks:
        emitted_edge.extend(list(stripper_edge.process_chunk(c)))
    emitted_edge.extend(list(stripper_edge.flush()))
    assert ''.join(emitted_edge) == 'Compare if x < 10 and y  then output is valid'

    stripper_unclosed = StreamingThoughtStripper()
    for c in ['Ready: ', '<think>Unclosed model thought...']:
        list(stripper_unclosed.process_chunk(c))
    assert ''.join(stripper_unclosed.flush()) == ''

test_streaming()
"
```

## Notes

- Reference upstream issue and reasoning token discussion: [vLLM Reasoning Outputs](https://github.com/vllm-project/vllm/issues) and [DeepSeek R1 Specification](https://docs.vllm.ai/en/latest/models/deepseek_r1.html).
- For proxy architectures serving dual streams (forwarding thoughts to an auditing observability sink while emitting clean text to UI clients), the `INSIDE_THOUGHT` block can route yielded tokens to an audit queue rather than discarding them.
- When configuring Ollama, LiteLLM, or vLLM upstream gateways, set `drop_reasoning: true` or deploy this state machine in the ASGI/WSGI reverse proxy layer.
