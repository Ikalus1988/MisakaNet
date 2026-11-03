#!/usr/bin/env python3
"""One contract for one tool name, and no stdio dependency the hosted surface does not serve (#4383).

Four incidents share this shape, and each was fixed on its own:

| issue | what the two surfaces disagreed about |
|---|---|
| #2967 | `minProperties` in a tool schema cost one client every tool on the server |
| #4360 | a three-branch `oneOf` rejected the call the tool's own description allows |
| #3577 | `dedup_key` and the status vocabulary, described differently on each surface |
| #4378 | the stdio `me_inbox` called `/api/inbox`, a route that **never existed** in the worker |

The two rules below are the general form. They are checks, not a policy: they do not say what the
surfaces may teach, only that they must not silently teach different things.

**Rule A — schema parity.** For every tool name served by both surfaces, the input contracts are
equal. "Contract" is structure — property names, `type`, `enum`, `required`, `items`, `oneOf` — not
prose: a reworded argument description is not drift, and pinning every description string would
make either file impossible to edit while protecting nothing (`#3577`'s prose half is covered where
it mattered: the status vocabulary is asserted in `test_mcp_capability_parity.py`). Where the two
surfaces are deliberately different, the difference is **declared** in `DECLARED_DIVERGENCES` with a
reason; a new difference fails, and a fixed one fails until it is removed from the declaration.

**Rule B — no invented dependency.** A stdio handler may reach the hosted surface only through
something the hosted surface actually serves: a name in the hosted tool set, or a path in the
worker's route table. `/api/inbox` was neither, and nothing looked.

Both parsers are self-tested at the bottom: a planted unknown tool, a planted unknown route, and a
real dependency hidden behind a module constant (`_TOOL = "misakanet_me_inbox"`) — the shape that a
text search for the tool name misses.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

import _worker_tools  # noqa: E402  (the one JS-to-JSON reader, shared with the parity tests)

from misakanet.server.tools import TOOLS as LOCAL_TOOLS  # noqa: E402

HANDLERS_DIR = REPO / "misakanet" / "server" / "handlers"
WORKER = REPO / "workers" / "register-proxy-sw.js"

HOSTED = _worker_tools.hosted_definitions()
LOCAL = {tool["name"]: tool for tool in LOCAL_TOOLS}
SHARED = sorted(set(HOSTED) & set(LOCAL))

#: Every deliberate difference, with the reason it is allowed to exist. The rule is the opposite of
#: a silencer: the set is compared for equality, so an undeclared new difference fails and a fixed
#: one has to be removed here too. Key format: `+path` = only local, `-path` = only hosted,
#: `~path` = both present, different structure.
DECLARED_DIVERGENCES: dict[str, dict[str, str]] = {
    "misakanet_register": {
        "-/required": (
            "hosted requires `agent_type`; the stdio tool documents it as optional and defaults to "
            "'unknown'. Same property, different obligation — deliberately left until the local "
            "callers (the installer) are audited."
        ),
    },
    "misakanet_search": {
        "+/properties/explain": "local-only: explains the ranking from the in-memory index.",
        "+/properties/include_stale": (
            "local-only: reads this checkout's `data/`, where a stale snapshot is the normal state "
            "and the caller may want to see it rather than be told the index is behind."
        ),
    },
    "misakanet_submit_intake": {
        "-/properties/contributor": (
            "hosted records attribution on the GitHub issue; the stdio path files through the same "
            "worker, so the field could be forwarded — it is declared rather than fixed because it "
            "needs a decision about which name a local agent should claim."
        ),
        "+/properties/kind/enum": (
            "the local schema restricts `kind` to the worker's current whitelist; the hosted one "
            "lists no enum and lets the handler refuse. Structurally stricter here, and the enum "
            "has to be updated by hand when the whitelist grows — the reason it is visible."
        ),
    },
    "misakanet_write_lesson": {
        "-/properties/contributor": "same attribution gap as submit_intake.",
        "+/properties/token": (
            "deprecated argument: the Bearer header is the only auth path (AGENTS.md §3.3). Kept in "
            "the local schema so an older client with `token:` still gets a stated refusal instead "
            "of a schema error."
        ),
    },
}

#: The route the worker answers for *any* unknown `/api/…` path with a 404 body. Counting it as
#: "served" would make rule B pass on exactly the defect it exists to catch (`/api/inbox`).
CATCH_ALL_PREFIXES = ("/api/",)

_PATH_LITERAL = re.compile(r'pathname\s*===\s*"([^"]+)"')
_PATH_PREFIX = re.compile(r'pathname\.startsWith\(\s*"([^"]+)"\s*\)')


# ── Rule A: schema structure ─────────────────────────────────────────────────────────────────────

STRUCTURAL_KEYS = ("type", "enum", "required", "items", "oneOf", "anyOf", "const")


def schema_structure(schema):
    """The part of a schema a client is accepted or rejected by, normalised for comparison.

    Descriptions are dropped on purpose (see the module docstring): they are prose, and comparing
    them would make every rewording a red build while checking no meaning. `properties` is kept as
    a mapping of the same shape, so a renamed or removed argument is still a difference.
    """
    if not isinstance(schema, dict):
        return schema
    out = {}
    for key in STRUCTURAL_KEYS:
        if key in schema:
            out[key] = schema[key]
    if "properties" in schema:
        out["properties"] = {
            name: schema_structure(value) for name, value in schema["properties"].items()
        }
    return out


def structure_diff(hosted, local, path="") -> list[str]:
    """`+path` local-only, `-path` hosted-only, `~path` both present and different."""
    if isinstance(hosted, dict) and isinstance(local, dict):
        found: list[str] = []
        for key in sorted(set(hosted) | set(local)):
            child = f"{path}/{key}"
            if key not in local:
                found.append(f"-{child}")
            elif key not in hosted:
                found.append(f"+{child}")
            else:
                found.extend(structure_diff(hosted[key], local[key], child))
        return found
    if isinstance(hosted, list) and isinstance(local, list) and len(hosted) == len(local):
        found = []
        for index, (h, l) in enumerate(zip(hosted, local)):
            found.extend(structure_diff(h, l, f"{path}[{index}]"))
        return found
    if hosted != local:
        return [f"~{path or '/'}"]
    return []


def shared_schema_differences() -> dict[str, list[str]]:
    out = {}
    for name in SHARED:
        hosted = schema_structure(HOSTED[name].get("inputSchema") or {})
        local = schema_structure(LOCAL[name].get("inputSchema") or {})
        diff = structure_diff(hosted, local)
        if diff:
            out[name] = diff
    return out


def test_every_shared_schema_difference_is_declared():
    measured = shared_schema_differences()
    undeclared = {
        name: sorted(set(paths) - set(DECLARED_DIVERGENCES.get(name, {})))
        for name, paths in measured.items()
    }
    undeclared = {name: paths for name, paths in undeclared.items() if paths}
    assert undeclared == {}, (
        "the two surfaces disagree about these arguments and nothing declared it. Either align the "
        "schemas, or add the path to DECLARED_DIVERGENCES with the reason it is allowed:\n"
        + "\n".join(f"  {name}: {paths}" for name, paths in sorted(undeclared.items()))
    )


def test_a_declared_difference_that_no_longer_exists_is_removed():
    """Otherwise the declaration outlives the divergence and silences the next one at that path."""
    measured = shared_schema_differences()
    stale = {
        name: sorted(set(reasons) - set(measured.get(name, [])))
        for name, reasons in DECLARED_DIVERGENCES.items()
    }
    stale = {name: paths for name, paths in stale.items() if paths}
    assert stale == {}, (
        "these declared differences no longer exist — delete them from DECLARED_DIVERGENCES so the "
        "declaration keeps meaning something:\n"
        + "\n".join(f"  {name}: {paths}" for name, paths in sorted(stale.items()))
    )


def test_every_shared_tool_is_compared():
    """A tool present on both surfaces must not be skipped because its schema is empty."""
    assert SHARED == sorted(
        ["misakanet_get_lesson", "misakanet_me_events", "misakanet_me_inbox",
         "misakanet_preflight", "misakanet_register", "misakanet_search",
         "misakanet_submit_intake", "misakanet_write_lesson"]
    ), SHARED


def missing_enum_values(description: str, enum) -> list[str]:
    """The values of a hosted output enum a local description never names.

    This is the automatable half of "carries the hosted wording": a caller branches on `status`,
    `risk_level` or `evidence`, so those exact strings are the contract, and a local description
    that invents a different vocabulary sends an agent down a branch the hosted answer never takes
    (#3577).
    """
    return [value for value in enum if value not in description]


def test_every_hosted_output_enum_is_named_in_the_local_description():
    checked = 0
    problems: list[str] = []
    for name in SHARED:
        hosted = HOSTED[name].get("outputSchema") or {}
        for prop, schema in (hosted.get("properties") or {}).items():
            if not isinstance(schema, dict) or not schema.get("enum"):
                continue
            checked += 1
            missing = missing_enum_values(LOCAL[name]["description"], schema["enum"])
            if missing:
                problems.append(f"{name}.{prop}: local description never names {missing}")
    assert checked >= 3, (
        "the enum scan found fewer than the three enums the hosted surface serves today — the "
        "parser has gone blind, not the surface clean"
    )
    assert problems == [], (
        "a caller branches on these values; the two surfaces must name the same ones:\n  "
        + "\n  ".join(problems)
    )


def test_a_description_missing_one_enum_value_is_reported():
    assert missing_enum_values("status is answered or pending", ["answered", "pending", "unknown"]) \
        == ["unknown"]


# ── Rule B: no invented dependency ──────────────────────────────────────────────────────────────

def worker_routes(source: str) -> tuple[set[str], set[str]]:
    """`(literal routes, prefixes)` from the worker's route table."""
    literals = {match for match in _PATH_LITERAL.findall(source)}
    prefixes = {match for match in _PATH_PREFIX.findall(source)}
    return literals, prefixes - set(CATCH_ALL_PREFIXES)


def handler_constant_strings(source: str) -> dict[str, str]:
    """Module-level `NAME = "..."` assignments — how a handler hides its tool name from a grep."""
    constants: dict[str, str] = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                constants[target.id] = node.value.value
    return constants


def handler_dependencies(source: str) -> tuple[set[str], set[str]]:
    """`(tool names, api paths)` a handler reaches for, resolving module constants."""
    constants = handler_constant_strings(source)
    tools: set[str] = set()
    paths: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "call" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                tools.add(first.value)
            elif isinstance(first, ast.Name) and first.id in constants:
                tools.add(constants[first.id])
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value.startswith("/api/"):
            paths.add(node.value)
    return tools, paths


def handler_sources() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(HANDLERS_DIR.glob("*.py"))
        if path.name != "__init__.py"
    }


def test_stdio_handlers_only_depend_on_what_the_hosted_surface_serves():
    literals, prefixes = worker_routes(WORKER.read_text(encoding="utf-8"))
    hosted_tools = set(HOSTED)
    problems: list[str] = []
    dependencies = 0
    for name, source in handler_sources().items():
        tools, paths = handler_dependencies(source)
        for tool in sorted(tools):
            dependencies += 1
            if tool not in hosted_tools:
                problems.append(f"{name} calls remote tool {tool!r}, which the hosted surface does not serve")
        for path in sorted(paths):
            dependencies += 1
            served = path in literals or any(path.startswith(prefix) for prefix in prefixes)
            if not served:
                problems.append(f"{name} reaches {path!r}, which is not in the worker's route table")
    assert dependencies > 0, (
        "no dependency was found at all — the parser has stopped seeing them, which is how a gate "
        "goes quiet without failing"
    )
    assert problems == [], "handlers depend on things the hosted surface does not serve:\n  " + \
        "\n  ".join(problems)


# ── the gate can see the defects it forbids ────────────────────────────────────────────────────

def test_a_planted_unknown_tool_is_reported():
    tools, paths = handler_dependencies('remote.call("misakanet_not_a_tool", {})\n')
    assert tools == {"misakanet_not_a_tool"}
    assert tools - set(HOSTED), "an unknown tool name has to be outside the hosted set"


def test_a_planted_unknown_route_is_reported():
    literals, prefixes = worker_routes(WORKER.read_text(encoding="utf-8"))
    _, paths = handler_dependencies('url = f"{base}/api/inbox"\n')
    assert paths == {"/api/inbox"}, "#4382's shape: a path the worker never had"
    assert not (paths & literals), "the planted route must not exist in the real route table"


def test_a_dependency_hidden_behind_a_module_constant_is_resolved():
    source = '_TOOL = "misakanet_me_inbox"\nresponse = remote.call(_TOOL, {"intake_id": "x"})\n'
    tools, _ = handler_dependencies(source)
    assert tools == {"misakanet_me_inbox"}, (
        "a text search for `remote.call(\"` misses this shape, and it is the shape two of the "
        "three handlers use"
    )


def test_a_planted_schema_difference_is_reported():
    hosted = schema_structure({"type": "object", "properties": {"a": {"type": "string"}}})
    local = schema_structure({"type": "object", "properties": {"a": {"type": "string"},
                                                               "b": {"type": "string"}}})
    assert structure_diff(hosted, local) == ["+/properties/b"]


def test_a_reworded_description_is_not_a_difference():
    """Prose is not the contract: pinning it would make either file uneditable."""
    hosted = schema_structure({"type": "object", "properties": {
        "a": {"type": "string", "description": "the hosted wording"}}})
    local = schema_structure({"type": "object", "properties": {
        "a": {"type": "string", "description": "the local wording"}}})
    assert structure_diff(hosted, local) == []


def test_the_worker_route_parser_reads_the_real_route_table():
    literals, prefixes = worker_routes(WORKER.read_text(encoding="utf-8"))
    assert "/api/helpful" in literals and "/api/feedback" in literals, (
        "the two routes the stdio submit handler reaches for must be visible to the parser"
    )
    assert "/api/inbox" not in literals
    assert "/api/" not in prefixes, (
        "the catch-all answers unknown /api paths with a 404; counting it as served would pass the "
        "very dependency this rule forbids"
    )
