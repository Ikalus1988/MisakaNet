"""One reader for an MCP reply, whatever frame it arrived in.

Why this exists (#3548): the endpoint frames a `tools/call` answer as **SSE** whenever the request's
`Accept` mentions `text/event-stream`, and as plain JSON otherwise. The payload is identical — measured
2026-10-19, both halves byte-for-byte equal — but every caller that did `json.loads(response.read())`
died at byte zero (`'e'` of `event:`), swallowed the exception, and printed something like
``intake_id=RAW``. "The submission failed" and "I could not decode the reply" then look the same to the
person reading the output, which is worse than either.

Two rules, and the second one is the point:

1. **Decode both frames.** Plain JSON is one document; SSE is a sequence of events whose `data:` lines
   may be split across several lines and which may be preceded by comments/keepalives.
2. **Never return a placeholder.** An unreadable body raises `McpReplyUnreadable` carrying the HTTP
   status and a short snippet; a JSON-RPC error raises `McpRpcError` with its code. A caller that
   wants to print "RAW" has to do it on purpose, and can tell the two failures apart.

Unwrapping follows the wire, not a guess: `structuredContent` when it is an object (the worker always
sends one), else the first `content[]` text block that parses as JSON (the local stdio server sends
only that), else the raw `result`.
"""
from __future__ import annotations

import json
from typing import Any

__all__ = ["McpReplyUnreadable", "McpRpcError", "parse_mcp_reply"]


class McpReplyUnreadable(RuntimeError):
    """The bytes were not a reply this reader could decode. Never raised for a JSON-RPC error."""

    def __init__(self, message: str, *, status: int | None = None,
                 endpoint: str = "", snippet: str = "") -> None:
        self.status = status
        self.endpoint = endpoint
        self.snippet = snippet[:200]
        detail = " ".join(x for x in (
            f"HTTP {status}" if status is not None else "",
            endpoint,
            f"body starts {self.snippet!r}" if self.snippet else "",
        ) if x)
        super().__init__(f"{message}" + (f" ({detail})" if detail else ""))


class McpRpcError(RuntimeError):
    """The reply was decodable and carried a JSON-RPC error."""

    def __init__(self, error: Any) -> None:
        self.error = error
        if isinstance(error, dict):
            self.code = error.get("code")
            self.message = str(error.get("message") or error)
        else:
            self.code = None
            self.message = str(error)
        super().__init__(self.message)


def _text_of(raw: bytes | str) -> str:
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw).decode("utf-8", "replace")
    return str(raw)


def _documents_from_sse(text: str) -> list[Any]:
    """Every JSON document carried by an SSE body, in order.

    Split on a blank line into events (the SSE framing rule), then join **all** `data:` lines of an
    event: a payload may legally be split across them, and a `^data: (.*)$` regex — which this repo
    had in two places — takes only the first line and breaks on multi-line data.
    """
    documents: list[Any] = []
    for event in text.replace("\r\n", "\n").split("\n\n"):
        data: list[str] = []
        for line in event.split("\n"):
            if not line or line.startswith(":"):
                continue  # comment / keepalive
            if line.startswith("data:"):
                data.append(line[5:].lstrip(" "))
            # `event:`, `id:`, `retry:` are framing, not payload
        if not data:
            continue
        chunk = "\n".join(data)
        try:
            documents.append(json.loads(chunk))
        except ValueError:
            continue
    return documents


def _pick_document(text: str) -> Any:
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)  # ValueError is the caller's to report
    if "data:" in text or stripped.startswith("event:") or stripped.startswith(":"):
        documents = _documents_from_sse(text)
        if not documents:
            raise ValueError("SSE body carried no JSON data line")
        # The JSON-RPC reply is the last document that looks like one; a keepalive `data: {}` is
        # earlier and must not win.
        for document in reversed(documents):
            if isinstance(document, dict) and ("result" in document or "error" in document):
                return document
        return documents[-1]
    raise ValueError("body is neither JSON nor an SSE frame")


def parse_mcp_reply(raw: bytes | str, *, status: int | None = None,
                    endpoint: str = "") -> Any:
    """Decode one MCP reply and return the tool's payload.

    Raises `McpReplyUnreadable` when the body cannot be decoded, `McpRpcError` when it decoded to a
    JSON-RPC error. It never returns an empty dict as a stand-in for either.
    """
    text = _text_of(raw)
    if not text.strip():
        raise McpReplyUnreadable("empty reply body", status=status, endpoint=endpoint)
    try:
        document = _pick_document(text)
    except ValueError as exc:
        raise McpReplyUnreadable(f"could not decode reply: {exc}", status=status,
                                 endpoint=endpoint, snippet=text) from exc

    if isinstance(document, dict) and document.get("error"):
        raise McpRpcError(document["error"])

    result = document.get("result") if isinstance(document, dict) else document
    if result is None:
        # A JSON-RPC *notification* has no `result`; treating it as an empty tool answer is how a
        # missing field becomes a plausible zero.
        raise McpReplyUnreadable("reply carried neither result nor error", status=status,
                                 endpoint=endpoint, snippet=text)
    if not isinstance(result, dict):
        return result

    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    # The local stdio server sends only text blocks; the worker sends both. Prefer a text block that
    # parses, and only then the bare `result` (initialize / tools/list answers have no blocks).
    blocks = result.get("content")
    if isinstance(blocks, list):
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            payload = block.get("text")
            if not isinstance(payload, str):
                continue
            try:
                return json.loads(payload)
            except ValueError:
                continue
    return result
