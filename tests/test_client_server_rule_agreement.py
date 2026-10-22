#!/usr/bin/env python3
"""The client hook and the server must redact the SAME text (issue #3692).

There are two ends to the redaction, written by two different lines of work:

* the **client** — `integrations/agent-autostart/checkpoint_reminder.mjs` (and its Python twin) —
  redacts the error fragment *before it leaves the machine*;
* the **server** — `workers/lib/redact-patterns.json` and the worker's two inlined copies — redacts
  the query *before it is stored*, which is the only place that can cover the agent's own search
  call, which no client can intercept.

Two ends, one rule list — and nothing else compared them. They already drifted once during this
work: the client's mail rule was stricter than the server's until the two were aligned by hand,
and a rule that exists on one end only is a rule the other end silently does not have. The
promise "the client already redacted it" is exactly the kind of promise that must not be
half-true.

So this file pins the agreement:

* every rule id the client declares exists in the server's single source of truth;
* for every rule the two share, the **regex source is identical** — not merely similar, and not
  merely the same id: the client's rule table is expanded (its template constants are resolved
  and its string escapes are undone) and compared with the source of truth character by character;
* the client's Python twin declares the same ids as the client's Node hook.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PATTERN_FILE = REPO / "workers" / "lib" / "redact-patterns.json"
CLIENT_JS = REPO / "integrations" / "agent-autostart" / "checkpoint_reminder.mjs"
CLIENT_PY = REPO / "integrations" / "agent-autostart" / "checkpoint_reminder.py"

CONSTANTS = ("SEG", "FS_ROOTS", "FILE_EXT")

# The three classes both ends must agree on character for character. The secret rules are a
# DELIBERATE exception: the client's versions are narrower than the server's (a word boundary,
# so "task_identifier" is not read as the key "sk_identifier", and a six-character floor, so the
# phrase "Bearer token" in prose survives), because the client has to leave ordinary text alone.
# The server is the last line of defence and keeps its own, wider set. So for the secrets this
# file checks the ID, and for the three new classes it checks the text.
IDENTICAL_SOURCE_CLASSES = ("abs_path", "windows_path", "email")

# JavaScript string-literal escapes, as they appear in the client's source.
_JS_ESCAPES = {
    "\\": "\\", "'": "'", '"': '"', "`": "`", "$": "$",
    "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "0": "\0",
}


def _js_unescape(text: str) -> str:
    """Undo JavaScript string-literal escaping, so a source literal becomes its value."""
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            out.append(_JS_ESCAPES.get(text[i + 1], text[i + 1]))
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _server_patterns() -> dict[str, str]:
    data = json.loads(PATTERN_FILE.read_text(encoding="utf-8"))
    return {spec["id"]: spec["pattern"] for spec in data}


def _client_constants(source: str) -> dict[str, str]:
    """The template constants the client's rules are built from, as VALUES.

    A constant may be written as one string literal or as several joined with "+", so every
    literal of the statement is collected and concatenated.
    """
    values: dict[str, str] = {}
    for name in CONSTANTS:
        match = re.search(
            rf"const {name}\s*=\s*((?:\"(?:[^\"\\]|\\.)*\"\s*\+?\s*)+);", source
        )
        assert match, f"the client hook no longer defines {name}"
        literals = re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))
        assert literals, f"{name} is not a string literal any more"
        values[name] = "".join(_js_unescape(literal) for literal in literals)
    return values


def _client_rules(source: str) -> dict[str, str]:
    """The rule table the client hook applies: id -> pattern, with templates expanded."""
    table = re.search(r"const REDACT_RULES\s*=\s*\[(.*?)\n\];", source, re.DOTALL)
    assert table, "the client hook no longer has a REDACT_RULES table"
    body = table.group(1)

    constants = _client_constants(source)
    rules: dict[str, str] = {}

    # Template-literal rules: `pattern` with ${CONST} interpolations.
    for rule_id, pattern in re.findall(
        r"\{\s*id:\s*'([^']+)'\s*,\s*pattern:\s*`([^`]*)`", body
    ):
        value = _js_unescape(pattern)
        for name, constant in constants.items():
            value = value.replace("${" + name + "}", constant)
        rules[rule_id] = value

    # Single-quoted rules: 'pattern' with backslash escapes.
    for rule_id, pattern in re.findall(
        r"\{\s*id:\s*'([^']+)'\s*,\s*pattern:\s*'((?:[^'\\]|\\.)*)'", body
    ):
        rules[rule_id] = _js_unescape(pattern)

    assert rules, "no rules could be read out of the client's rule table"
    return rules


def test_the_client_hook_has_rules_to_begin_with() -> None:
    """A client with no rules would make every other assertion vacuously true."""
    rules = _client_rules(CLIENT_JS.read_text(encoding="utf-8"))
    assert len(rules) >= 3, f"the client hook barely has rules: {sorted(rules)}"
    for needed in ("abs_path", "windows_path", "email"):
        assert needed in rules, f"the client hook lost '{needed}': {sorted(rules)}"


def test_every_client_rule_id_exists_on_the_server() -> None:
    rules = _client_rules(CLIENT_JS.read_text(encoding="utf-8"))
    server = _server_patterns()
    missing = sorted(set(rules) - set(server))
    assert not missing, (
        f"the client applies rules the server does not know: {missing} — "
        "the server's source of truth has to carry every id the client uses"
    )


def test_the_two_ends_use_the_same_regex_source() -> None:
    """Same text, not merely the same id: the two ends have to redact the same thing."""
    source = CLIENT_JS.read_text(encoding="utf-8")
    rules = _client_rules(source)
    server = _server_patterns()
    for rule_id in IDENTICAL_SOURCE_CLASSES:
        assert rule_id in rules, f"the client hook lost '{rule_id}'"
        assert rules[rule_id] == server[rule_id], (
            f"'{rule_id}' is a different regex on the two ends:\n"
            f"  client: {rules[rule_id]}\n"
            f"  server: {server[rule_id]}\n"
            "The two ends have to redact the same text, or one of them silently does not."
        )


def test_the_client_is_deliberately_narrower_about_secrets() -> None:
    """The difference is a decision, not drift — and this pins that it stays a decision.

    The client's secret rules carry a word boundary and a length floor, so ordinary prose is not
    eaten. The server's own copy is wider, and it is the one that has to catch what the client
    let through. If somebody "aligns" the server to the client, the server silently stops
    catching short or glued secrets — so the difference is asserted here, in both directions.
    """
    source = CLIENT_JS.read_text(encoding="utf-8")
    rules = _client_rules(source)
    server = _server_patterns()
    for rule_id in ("bearer_token", "api_key", "github_token"):
        assert rule_id in rules, f"the client hook lost '{rule_id}'"
        assert rule_id in server, f"the server lost '{rule_id}'"
        assert rules[rule_id] != server[rule_id], (
            f"'{rule_id}' is now identical on the two ends — the client is supposed to be the "
            "narrower one here, so that ordinary prose is not eaten. If the server's wider rule "
            "was dropped on purpose, say so here."
        )


def test_the_python_twin_declares_the_same_rules_as_the_node_hook() -> None:
    source = CLIENT_PY.read_text(encoding="utf-8")
    ids = set(re.findall(r"['\"]id['\"]\s*:\s*['\"]([^'\"]+)['\"]", source))
    assert ids, "no rule ids could be read out of the Python twin"
    node_ids = set(_client_rules(CLIENT_JS.read_text(encoding="utf-8")))
    assert ids == node_ids, (
        f"the two hook implementations declare different rules: "
        f"only in Node: {sorted(node_ids - ids)}; only in Python: {sorted(ids - node_ids)}"
    )
