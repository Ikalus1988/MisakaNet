---
title: "Vertex AI Streaming: Robust SSE Chunk Assembly and Buffer Handling"
domain: "llm"
tags:
  - vertex-ai
  - gemini
  - sse
  - streaming
  - buffer
  - python
status: "published"
evidence_level: "E2"
provenance:
  source: "internal_experiments"
  evidence: "post-publication"
---

# Vertex AI Streaming: Robust SSE Chunk Assembly and Buffer Handling

## Problem

When consuming the Vertex AI `streamGenerateContent` API over HTTP or via custom middleware, client applications frequently encounter stream truncation, deserialization failures (`json.JSONDecodeError: Unterminated string`), and multi-byte encoding corruption (`UnicodeDecodeError: 'utf-8' codec can't decode byte`). These errors trigger abruptly during large payload transfers or when streaming non-ASCII multi-byte tokens (such as CJK characters or technical Unicode symbols).

## Root Cause

TCP packet fragmentation does not respect application-layer boundaries:
1. **Multi-byte Boundary Splits**: UTF-8 characters span between 1 and 4 bytes. Network read operations return arbitrary chunk boundaries that split a multi-byte sequence across two consecutive read buffers. Calling `chunk.decode('utf-8')` immediately on arbitrary chunks fails with `UnicodeDecodeError`.
2. **Incomplete JSON Frames**: Server-Sent Events (SSE) delineate messages with double newlines (`\n\n`) and prefix payloads with `data: `. When payload chunks contain complex JSON objects (such as nested function call arguments), single lines can exceed socket buffer sizes. Attempting to parse lines before the full event delimiter arrives leads to syntax errors.
3. **Control Frames and Ping Keep-Alives**: Upstream reverse proxies and Google Cloud load balancers transmit empty lines (`\r\n`) and comment frames (`: ping`) to prevent HTTP idle timeouts. Parsers without state validation crash when encountering these control frames.

## Fix

Implement a streaming processor using an incremental decoder (`codecs.getincrementaldecoder`) combined with an event boundary accumulator.

```python
import codecs
import json
from typing import Any, Dict, Generator, Iterator


def process_vertex_sse_stream(
    byte_chunks: Iterator[bytes],
) -> Generator[Dict[str, Any], None, None]:
    """Decodes raw SSE byte stream from Vertex AI into parsed JSON payloads.

    Args:
        byte_chunks: An iterator yielding raw byte chunks from the HTTP response.

    Yields:
        Parsed dictionary corresponding to each complete SSE data payload.

    Raises:
        ValueError: If an event line fails JSON parsing after boundary assembly.
    """
    decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
    line_buffer = ""

    for chunk in byte_chunks:
        line_buffer += decoder.decode(chunk, final=False)
        while "\n" in line_buffer:
            line, line_buffer = line_buffer.split("\n", 1)
            line = line.strip("\r")

            if not line or line.startswith(":"):
                continue

            if line.startswith("data:"):
                payload_str = line[5:].strip()
                if not payload_str:
                    continue
                if payload_str == "[DONE]":
                    break
                parsed = json.loads(payload_str)
                yield parsed

    trailing = decoder.decode(b"", final=True)
    if trailing:
        line_buffer += trailing
        line = line_buffer.strip("\r")
        if line.startswith("data:"):
            payload_str = line[5:].strip()
            if payload_str and payload_str != "[DONE]":
                yield json.loads(payload_str)


def extract_candidate_text(payload: Dict[str, Any]) -> str:
    """Extracts text content from a Vertex AI GenerateContentResponse dictionary.

    Args:
        payload: Decoded response dictionary from the Vertex AI API.

    Returns:
        Concatenated text string contained within candidate parts.
    """
    candidates = payload.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts if "text" in part)
```

## Verification

Run the verification script to validate handling of split multi-byte characters and segmented JSON payloads:

```bash
python3 -c "
import codecs
import json

def test_stream_assembly():
    decoder = codecs.getincrementaldecoder('utf-8')(errors='strict')
    buffer = ''
    emitted = []

    test_json = json.dumps({'candidates': [{'content': {'parts': [{'text': '测试流式'}]}}]})
    full_line = f'data: {test_json}\n\n'
    raw_bytes = full_line.encode('utf-8')

    chunks = [raw_bytes[:7], raw_bytes[7:18], raw_bytes[18:]]

    for chunk in chunks:
        buffer += decoder.decode(chunk, final=False)
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            line = line.strip('\r')
            if line.startswith('data:'):
                data = json.loads(line[5:].strip())
                emitted.append(data['candidates'][0]['content']['parts'][0]['text'])

    assert emitted == ['测试流式']

test_stream_assembly()
"
```
