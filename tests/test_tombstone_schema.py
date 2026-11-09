#!/usr/bin/env python3
"""The tombstone payload has a machine-readable contract.

Before `docs/tombstone-protocol.schema.json`, the "contract" was prose plus a normalising consumer:
the Node wrapper writes `stackSnippet`, the Python sidecar writes `snippet`, and
`tombstone_to_draft._parse_tombstone` reconciles them in code. No artifact said which fields are
required, so a third producer (another language, another guard) had nothing to conform to.

These tests pin the schema to the two producers that actually exist and to the consumer's normalised
output — the three shapes that must all validate.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker

from scripts.tombstone_to_draft import _parse_tombstone

REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO / "docs" / "tombstone-protocol.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft7Validator(SCHEMA, format_checker=FormatChecker())

# As `packages/fatal-guard` writes it: the error text split into message + stackSnippet (#3645).
NODE_WRAPPER_PAYLOAD = {
    "schemaVersion": 1,
    "reason": "process_crash",
    "timestamp": "2026-10-21T12:00:00.000Z",
    "pid": 4242,
    "errorName": "Error",
    "message": "Error: EACCES: permission denied, open '/etc/shadow'",
    "stackSnippet": "at evalFunction (node:internal/process/execution:279:30)",
    "exit_code": 1,
}

# As a Python sidecar writes it: one `snippet`, plus labels the guard does not know.
PYTHON_SIDECAR_PAYLOAD = {
    "reason": "process_crash",
    "timestamp": "2026-10-21T12:00:00Z",
    "pid": 4242,
    "snippet": "Traceback (most recent call last): ...",
    "signal": "",
    "host": "build-1",
    "node_id": "unknown",
}

MINIMAL_PAYLOAD = {
    "reason": "uncaught_exception",
    "timestamp": "2026-11-09T00:00:00.000Z",
    "pid": 0,
}


def errors(payload: dict) -> list[str]:
    return [f"{list(e.path)}: {e.message}" for e in VALIDATOR.iter_errors(payload)]


def test_the_node_wrapper_payload_validates():
    assert errors(NODE_WRAPPER_PAYLOAD) == []


def test_the_python_sidecar_payload_validates():
    assert errors(PYTHON_SIDECAR_PAYLOAD) == []


def test_the_minimal_payload_validates():
    assert errors(MINIMAL_PAYLOAD) == []


def test_the_consumers_normalised_output_validates():
    """`_parse_tombstone` rewrites the payload (snippet, signal, host, node_id); that shape is legal too."""
    assert errors(_parse_tombstone(NODE_WRAPPER_PAYLOAD)) == []


@pytest.mark.parametrize("missing", ["reason", "timestamp", "pid"])
def test_a_required_field_cannot_be_dropped(missing):
    payload = {k: v for k, v in MINIMAL_PAYLOAD.items() if k != missing}
    assert errors(payload), f"a payload without {missing!r} must not validate"


def test_an_unknown_reason_is_refused():
    payload = {**MINIMAL_PAYLOAD, "reason": "gpu_exploded"}
    assert errors(payload), "the reason is a closed vocabulary; a new value needs a schema edit"


def test_a_v2_payload_is_not_silently_accepted_as_v1():
    payload = {**MINIMAL_PAYLOAD, "schemaVersion": 2}
    assert errors(payload), "schemaVersion 2 is a draft; validating it as v1 would describe the wrong shape"


def test_an_over_long_message_is_refused():
    payload = {**MINIMAL_PAYLOAD, "message": "x" * 501}
    assert errors(payload), "the wrapper truncates at 500; a longer payload means a producer bypassed the contract"


def test_a_malformed_timestamp_is_refused():
    payload = {**MINIMAL_PAYLOAD, "timestamp": "yesterday"}
    assert errors(payload), "format: date-time is part of the contract"
