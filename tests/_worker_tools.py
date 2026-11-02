#!/usr/bin/env python3
"""Read the worker's `MCP_TOOLS` array out of its source, for tests that must not run the handler.

Why this is a module and not two functions
------------------------------------------
`test_mcp_capability_parity.py` and `test_mcp_schema_branches.py` both need the hosted tool
definitions, and each grew its own copy of this parser. Two copies of a JS-to-JSON reader is how a
fix lands in one and not the other: on 2026-11-03 a trailing comma before a closing bracket became
reachable when a comment was added at the end of a schema object, one copy was taught to skip
comments and the other still failed with "Illegal trailing comma" — pointing at the schema rather
than at the reader.

Parsed rather than evaluated: running the worker module would execute the edge handler.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKER = REPO / "workers" / "register-proxy-sw.js"


def hosted_definitions(worker: Path = WORKER) -> dict[str, dict]:
    """`{tool name: tool definition}` for the hosted surface."""
    text = worker.read_text(encoding="utf-8")
    start = text.index("const MCP_TOOLS = [")
    cursor = text.index("[", start)
    depth, in_string, escaped = 0, False, False
    while cursor < len(text):
        char = text[cursor]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                break
        cursor += 1
    source = text[text.index("[", start):cursor + 1]

    out: list[str] = []
    index, in_string, escaped = 0, False, False
    while index < len(source):
        char = source[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char == "/" and source[index + 1:index + 2] == "/":     # a `//` comment: not JSON
            newline = source.find("\n", index)
            index = len(source) if newline == -1 else newline
            continue
        if char == ",":                                            # JS trailing commas: not JSON
            rest = source[index + 1:]
            while rest.lstrip().startswith("//"):
                rest = rest.lstrip()
                newline = rest.find("\n")
                rest = "" if newline == -1 else rest[newline + 1:]
            if rest[:1] in ("}", "]"):
                index += 1
                continue
            out.append(char)
            index += 1
            continue
        if char.isalpha() or char == "_":
            ident = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source[index:])
            if ident and source[index + len(ident.group(0)):].lstrip().startswith(":"):
                out.append(f'"{ident.group(0)}"')
                index += len(ident.group(0))
                continue
        out.append(char)
        index += 1

    cleaned = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
    return {tool["name"]: tool for tool in json.loads(cleaned)}
