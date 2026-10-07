#!/usr/bin/env python3
"""A `oneOf` branch that names a property the schema does not define is silently inert.

## Why this file exists, and why it is not what it first looked like

`#2967` reported that dsh 0.2.0-rc.2 registers **zero tools** for a server whose `inputSchema`
uses a keyword outside its own subset, because its bundle sets `failOnStartupError: false`. The
first version of this gate took that subset as the rule and failed any keyword outside it.

**That premise is wrong, and the authoritative schema says so.** `Tool.inputSchema` in
`schema/2026-07-28/schema.json`:

> Beyond that, any JSON Schema 2020-12 keyword may appear alongside `type` — including composition
> keywords (`oneOf`, `anyOf`, `allOf`, `not`), conditional keywords (`if`/`then`/`else`), reference
> keywords (`$ref`, `$defs`, `$anchor`), and any other standard validation or annotation keywords.

So `minProperties: 1` — which this repository emitted — was **spec-compliant**, and a rule that
forbids it would have been encoding one client's tolerance as a standard. There is no such rule here
now.

What survives is narrower and is about *our* schemas rather than about anybody's validator:

* writing "at least one of these two" as three `oneOf` branches is a hand-expansion, and
* JSON Schema does not check that a name inside `required` exists. A branch saying
  `{required: ["lesson_id"]}` in a schema whose `properties` has no `lesson_id` validates happily
  and constrains nothing. That failure is invisible to the client, to the spec, and to any test
  that only runs the happy path — and it would leave a tool accepting the empty call it was written
  to refuse.

So the rule is: **every property named by a `oneOf`/`anyOf`/`allOf` branch's `required` must exist
in the sibling `properties`.** `tests/test_mcp_capability_parity.py` already holds the two surfaces
in step; this holds the shape of the schema itself.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "workers" / "register-proxy-sw.js"
LOCAL_TOOLS = REPO / "misakanet" / "server" / "tools.py"

#: Keywords whose value is a list of subschemas.
COMBINATORS = ("oneOf", "anyOf", "allOf")

#: Keys whose value maps names to schemas. The keys inside are argument names, not keywords.
MAP_OF_SCHEMAS = frozenset({"properties", "patternProperties", "$defs", "definitions"})


def _hosted_input_schemas() -> dict[str, dict]:
    """The worker's `MCP_TOOLS`, parsed from source — running the module would run the handler."""
    text = WORKER.read_text(encoding="utf-8")
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
        if char == "/" and source[index + 1:index + 2] == "/":
            newline = source.find("\n", index)
            index = len(source) if newline == -1 else newline
            continue
        if char == ",":
            if source[index + 1:].lstrip()[:1] in ("}", "]"):
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
    return {tool["name"]: tool["inputSchema"] for tool in json.loads("".join(out))}


def _dangling_required(schema, path="") -> list[str]:
    """Names a `required` array asks for that the enclosing schema does not define.

    A branch is checked against the schema node it sits in, so a nested property's own `required`
    is judged by that property's own `properties` rather than the root's.
    """
    problems: list[str] = []
    if not isinstance(schema, dict):
        return problems
    defined = set((schema.get("properties") or {}))
    for combinator in COMBINATORS:
        for index, branch in enumerate(schema.get(combinator) or []):
            if not isinstance(branch, dict):
                continue
            for name in branch.get("required") or []:
                if name not in defined:
                    problems.append(f"{path}{combinator}[{index}].required -> {name!r}")
    for key, value in schema.items():
        if key in MAP_OF_SCHEMAS and isinstance(value, dict):
            for name, child in value.items():
                problems += _dangling_required(child, f"{path}properties.{name}.")
        else:
            problems += _dangling_required(value, f"{path}{key}.")
    return problems


def test_no_hosted_tool_schema_requires_a_property_it_does_not_define():
    offending = []
    for name, schema in _hosted_input_schemas().items():
        problems = _dangling_required(schema)
        if problems:
            offending.append(f"{name}: {problems}")
    assert not offending, (
        f"these branches constrain names the schema never defines, so they enforce nothing while "
        f"looking like validation: {offending}. A tool written to refuse the empty call would "
        f"accept it.")


def test_the_local_definitions_obey_the_same_rule():
    import sys

    sys.path.insert(0, str(REPO))
    from misakanet.server.tools import TOOLS

    offending = [
        f"{tool['name']}: {_dangling_required(tool['inputSchema'])}"
        for tool in TOOLS
        if _dangling_required(tool["inputSchema"])
    ]
    assert not offending, f"these local schemas require names they do not define: {offending}"


def test_the_gate_can_see_the_defect_it_forbids():
    """Both directions, so the rule is shown rather than only asserted on passing files."""
    good = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "id": {"type": "string"}},
        "oneOf": [{"required": ["path"]}, {"required": ["id"]}, {"required": ["path", "id"]}],
    }
    assert _dangling_required(good) == []

    dangling = dict(good, oneOf=[{"required": ["path"]}, {"required": ["lesson_id"]}])
    assert _dangling_required(dangling) == ["oneOf[1].required -> 'lesson_id'"], (
        "a branch naming a property the schema does not define is exactly the defect")

    # The root's properties are not the ones a nested property is judged against.
    nested = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {"inner": {"type": "string"}},
                "oneOf": [{"required": ["inner"]}],
            },
        },
        "oneOf": [{"required": ["outer"]}],
    }
    assert _dangling_required(nested) == []