#!/usr/bin/env python3
"""`misakanet tombstone validate|draft` — the local half of the crash pipeline.

The validator is the executable form of `docs/tombstone-protocol.schema.json`: the wheel cannot ship
`jsonschema` (stdlib-only by design), so the rules live in `misakanet/tombstone.py`. The cross-check
below feeds the same payloads through both and is what keeps them from drifting.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from misakanet.cli import tombstone as cli  # noqa: E402
from misakanet.tombstone import validate_payload  # noqa: E402

VALID = {
    "schemaVersion": 1,
    "reason": "process_crash",
    "timestamp": "2026-11-09T00:00:00.000Z",
    "pid": 42,
    "message": "boom",
    "exit_code": 1,
}
SCHEMA = json.loads((REPO / "docs" / "tombstone-protocol.schema.json").read_text(encoding="utf-8"))


def write(tmp_path, payload) -> str:
    path = tmp_path / "tombstone.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_a_valid_tombstone_passes(tmp_path, capsys):
    assert cli.main(["validate", write(tmp_path, VALID)]) == cli.EXIT_OK
    assert "valid tombstone v1" in capsys.readouterr().out


def test_validate_reads_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps(VALID)))
    assert cli.main(["validate", "-"]) == cli.EXIT_OK


@pytest.mark.parametrize("broken, needle", [
    ({"reason": "gpu_exploded"}, "reason"),
    ({"timestamp": "yesterday"}, "ISO 8601"),
    ({"pid": -1}, "pid"),
    ({"message": "x" * 501}, "message"),
    ({"schemaVersion": 2}, "schemaVersion"),
])
def test_broken_payloads_name_the_field(tmp_path, capsys, broken, needle):
    payload = {**VALID, **broken}
    assert cli.main(["validate", write(tmp_path, payload)]) == cli.EXIT_INVALID
    assert needle in capsys.readouterr().err


def test_a_missing_required_field_is_named(tmp_path, capsys):
    payload = {k: v for k, v in VALID.items() if k != "pid"}
    assert cli.main(["validate", write(tmp_path, payload)]) == cli.EXIT_INVALID
    assert "missing required field: pid" in capsys.readouterr().err


def test_the_validator_and_the_json_schema_agree():
    jsonschema = pytest.importorskip("jsonschema", reason="the schema cross-check needs the dev dependency")
    validator = jsonschema.Draft7Validator(SCHEMA, format_checker=jsonschema.FormatChecker())
    cases = [
        VALID,
        {k: v for k, v in VALID.items() if k != "reason"},
        {**VALID, "reason": "gpu_exploded"},
        {**VALID, "timestamp": "yesterday"},
        {**VALID, "pid": -1},
        {**VALID, "pid": True},
        {**VALID, "message": "x" * 501},
        {**VALID, "schemaVersion": 2},
        {**VALID, "exit_code": 999},
        {"reason": "killed_by_SIGKILL", "timestamp": "2026-11-10T08:00:00+08:00", "pid": 0},
        {"reason": "uncaught_exception", "timestamp": "2026-11-10T08:00:00Z", "pid": 1, "unknown": "allowed"},
    ]
    for payload in cases:
        assert (not validate_payload(payload)) == validator.is_valid(payload), payload


def test_draft_refuses_without_a_checkout(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MISAKANET_REPO", raising=False)
    monkeypatch.chdir(tmp_path)  # no scripts/ up from here (tmp_path is not under the checkout)
    assert cli.main(["draft", write(tmp_path, VALID), "--dry-run"]) == cli.EXIT_USAGE
    assert "needs a MisakaNet checkout" in capsys.readouterr().err


def test_draft_dry_run_uses_the_repo_converter(tmp_path, monkeypatch):
    monkeypatch.setenv("MISAKANET_REPO", str(REPO))
    assert cli.main(["draft", write(tmp_path, VALID), "--dry-run"]) == cli.EXIT_OK


def test_an_invalid_payload_is_refused_before_drafting(tmp_path, capsys):
    payload = {**VALID, "reason": "gpu_exploded"}
    assert cli.main(["draft", write(tmp_path, payload)]) == cli.EXIT_INVALID
    assert "invalid tombstone v1" in capsys.readouterr().err
