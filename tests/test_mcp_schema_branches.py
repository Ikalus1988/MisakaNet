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

import _worker_tools  # noqa: E402 — tests dir is on sys.path

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "workers" / "register-proxy-sw.js"
LOCAL_TOOLS = REPO / "misakanet" / "server" / "tools.py"

#: Keywords whose value is a list of subschemas.
COMBINATORS = ("oneOf", "anyOf", "allOf")

#: Keys whose value maps names to schemas. The keys inside are argument names, not keywords.
MAP_OF_SCHEMAS = frozenset({"properties", "patternProperties", "$defs", "definitions"})


def _hosted_input_schemas() -> dict[str, dict]:
    """`{tool: inputSchema}` for the hosted surface, from the shared reader."""
    return {name: tool["inputSchema"] for name, tool in _worker_tools.hosted_definitions().items()}


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

# ── the contract the schema must not contradict ────────────────────────────────────────────────

#: Keywords this repository has used to express "at least one of these fields", each of which
#: enforced something else:
#:
#: * `oneOf` is *exactly one*, so the documented call that supplies both `path` and `id` matched two
#:   branches and was rejected before the handler ran (#4360);
#: * `minProperties` sits outside the subset a conservative client accepts and cost one client every
#:   tool on the server once already — and came back on `misakanet_me_inbox` (#4361, #2967).
FORBIDDEN = ("oneOf", "anyOf", "minProperties")


def _tool_schemas() -> list[tuple[str, str, dict]]:
    """(surface, tool, inputSchema) for both faces."""
    import sys as _sys  # noqa: PLC0415

    _sys.path.insert(0, str(REPO))
    from misakanet.server.tools import TOOLS  # noqa: PLC0415

    out = [("hosted", name, schema) for name, schema in _hosted_input_schemas().items()]
    out += [("stdio", tool["name"], tool["inputSchema"]) for tool in TOOLS]
    return out


def test_no_tool_schema_turns_at_least_one_into_a_composition_keyword():
    problems = []
    for surface, name, schema in _tool_schemas():
        for keyword in FORBIDDEN:
            if keyword in schema:
                problems.append(f"{surface} {name}: {keyword}")
    assert not problems, (
        "these schemas express a requirement with a keyword that either means something else or "
        "costs a conservative client every tool on the server: " + ", ".join(problems) + ". "
        "State the requirement in the descriptions and let the handler refuse the empty call — "
        "it returns a code and a hint, which a schema rejection cannot.")


def test_the_handler_refuses_what_the_schema_no_longer_does():
    """The constraint moved from the schema to the handler; this is that the handler really has it.

    Both faces are checked by reading their source for the error they return, because running the
    worker means running the handler and this suite is offline.
    """
    worker = WORKER.read_text(encoding="utf-8")
    for needle in (
        '"lesson_id or lesson_path is required"',
        '"intake_id or dedup_key is required"',
        '"invalid_lesson_path"',
    ):
        assert needle in worker, f"the hosted handler lost its refusal: {needle}"
    tools_src = LOCAL_TOOLS.read_text(encoding="utf-8")
    assert "missing_lesson_reference" in tools_src or "lesson_id or lesson_path" in tools_src, (
        "the stdio me_events handler no longer refuses an empty reference")
