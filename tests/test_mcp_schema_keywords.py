#!/usr/bin/env python3
"""Our advertised tool schemas must stay inside the keyword subset a strict client accepts.

`#2967` is the measurement behind this. dsh 0.2.0-rc.2 validates each tool's `inputSchema`
against a conservative subset —

    type, oneOf, properties, required, additionalProperties, items, enum, const

— and, because its bundle sets `failOnStartupError: false`, a keyword outside that subset does
not raise. It **silently registers zero tools for the entire server**, and the host reports
`server is disconnected` or says nothing at all. The report attributed it to `minProperties: 1`,
which this repository emitted in two worker tool schemas and one local definition.

So the failure is not "one tool validates badly". It is "one unrecognised keyword costs a client
every tool this server offers", which is why a lint rule about *our* schemas is the right shape
of gate: the cost of an unfamiliar keyword is borne entirely by someone else's validator.

This reads the definitions out of the source rather than importing them — the same approach
`tests/test_mcp_capability_parity.py` uses, because running the worker module would execute the
whole edge handler.

## The subset is a floor, not a ceiling

A keyword outside this list is not automatically wrong; it is a decision that has to be made
knowingly and recorded here. `anyOf` is the obvious next candidate — it expresses "at least one
of" more directly than the three-branch `oneOf` the two tools use — and it is deliberately
absent, because dsh does not accept it. Adding it would reintroduce exactly the bug above.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow-free tool tables")

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "workers" / "register-proxy-sw.js"
LOCAL_TOOLS = REPO / "misakanet" / "server" / "tools.py"

#: What dsh 0.2.0-rc.2 accepts. Quoted from the report in #2967; see the module docstring.
ACCEPTED_KEYWORDS = frozenset({
    "type", "oneOf", "properties", "required",
    "additionalProperties", "items", "enum", "const",
})

#: Purely structural or documentation keys that are not validation at all.
STRUCTURAL_KEYWORDS = frozenset({"description", "title", "$schema", "default", "examples"})


def _hosted_input_schemas() -> dict[str, dict]:
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


#: Keys whose value is a map of *names* to schemas. The keys inside are argument names, not
#: schema keywords — reading `properties: {query: {...}}` as "the keyword `query`" is how the
#: first version of this gate reported every argument in the repository as an offending keyword.
MAP_OF_SCHEMAS = frozenset({"properties", "patternProperties", "$defs", "definitions"})


def _walk_keywords(schema) -> set[str]:
    """Every keyword anywhere in the schema, descending into properties and combinators."""
    found: set[str] = set()
    if isinstance(schema, dict):
        for key, value in schema.items():
            found.add(key)
            if key in MAP_OF_SCHEMAS and isinstance(value, dict):
                for child in value.values():
                    found |= _walk_keywords(child)
            else:
                found |= _walk_keywords(value)
    elif isinstance(schema, list):
        for item in schema:
            found |= _walk_keywords(item)
    return found


def test_no_hosted_tool_schema_uses_a_keyword_outside_the_accepted_subset():
    offending = []
    for name, schema in _hosted_input_schemas().items():
        unknown = sorted(
            _walk_keywords(schema) - ACCEPTED_KEYWORDS - STRUCTURAL_KEYWORDS
        )
        if unknown:
            offending.append(f"{name}: {unknown}")
    assert not offending, (
        f"these hosted tool schemas use keywords a conservative MCP client may not accept: "
        f"{offending}. One unrecognised keyword does not raise there — it registers zero tools for "
        f"the whole server, and the host says 'server is disconnected' (#2967). Keep every "
        f"validation keyword inside {sorted(ACCEPTED_KEYWORDS)}.")


def test_the_local_definitions_obey_the_same_rule():
    """The stdio server advertises the same schemas, so it has the same exposure."""
    import sys

    sys.path.insert(0, str(REPO))
    from misakanet.server.tools import TOOLS

    offending = []
    for tool in TOOLS:
        unknown = sorted(
            _walk_keywords(tool["inputSchema"]) - ACCEPTED_KEYWORDS - STRUCTURAL_KEYWORDS
        )
        if unknown:
            offending.append(f"{tool['name']}: {unknown}")
    assert not offending, (
        f"these local tool schemas use keywords outside the accepted subset: {offending}. See "
        "the hosted rule above for why an unrecognised keyword costs every tool (#2967).")


def test_the_gate_can_see_a_keyword_it_forbids():
    """The rule is exercised against the shape it forbids, not only against files that pass."""
    assert "minProperties" in _walk_keywords({"type": "object", "minProperties": 1})
    assert not (_walk_keywords({"type": "object", "oneOf": [{"required": ["a"]}]})
                - ACCEPTED_KEYWORDS - STRUCTURAL_KEYWORDS)
    # Argument names are not keywords. The first version of this walk reported every argument in
    # the repository (`query`, `path`, `kind`, …) as an offending keyword and flagged all seven
    # tools — a rule that cannot tell a name from a keyword is not a rule.
    nested = _walk_keywords({"type": "object", "properties": {"query": {"type": "string"}}})
    assert nested == {"type", "properties"}, nested
    # …but a keyword nested under a property still counts, or the walk only ever sees the top level.
    assert "pattern" in _walk_keywords(
        {"type": "object", "properties": {"query": {"type": "string", "pattern": "x"}}}
    )