#!/usr/bin/env python3
"""Node-counter mirror invariants (2026-09-15, issue #1683).

Background — the failure these tests exist to prevent
----------------------------------------------------
``data/counter.json`` was written only by the issue-based registration workflow, while every
MCP registration (the npx installer's path) incremented the worker's KV counter. Two
independent sequences described one fact: the file said 10073, KV said 10178, the site showed
178 nodes and the public surfaces said "52+"/"59".

``scripts/node_status.py --mirror`` copies the live counter into the file. The dangerous half
is what it writes, so the guards are pinned here: it must never move the published number
backwards (a failed KV read makes the endpoint fall back to its own GitHub copy, i.e. to a
stale value) and must never persist a payload it cannot trust.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import node_status  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "node_status.py"


def _counter_file(tmp_path: Path, current: int) -> Path:
    (tmp_path / "data").mkdir(exist_ok=True)
    path = tmp_path / "data" / "counter.json"
    path.write_text(json.dumps({"current": current, "updated": "2026-01-01T00:00:00Z"}) + "\n",
                    encoding="utf-8")
    return path


def test_mirror_writes_only_when_the_live_counter_is_ahead(tmp_path):
    path = _counter_file(tmp_path, 10073)
    assert node_status.mirror_counter(tmp_path, {"current": 10179}) == 10179
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["current"] == 10179
    assert data["updated"] != "2026-01-01T00:00:00Z", "the mirror stamps when it copied"

    # equal or behind: nothing to do (and the second call must be a no-op)
    assert node_status.mirror_counter(tmp_path, {"current": 10179}) is None
    assert json.loads(path.read_text(encoding="utf-8"))["current"] == 10179


def test_mirror_never_moves_the_published_number_backwards(tmp_path):
    """The endpoint answers from its GitHub copy when KV is unreachable, i.e. with the very
    value this file already holds — or an older one. Writing that would publish a retreat."""
    path = _counter_file(tmp_path, 10179)
    for behind in ({"current": 10178}, {"current": 10073}, {"current": 1}):
        assert node_status.mirror_counter(tmp_path, behind) is None, behind
    assert json.loads(path.read_text(encoding="utf-8"))["current"] == 10179


def test_mirror_refuses_a_payload_it_cannot_trust(tmp_path):
    path = _counter_file(tmp_path, 10073)
    for broken in ({}, {"current": "10179"}, {"current": True}, {"current": 0},
                   {"current": -5}, {"current": None}):
        try:
            node_status.mirror_counter(tmp_path, broken)
        except ValueError:
            continue
        raise AssertionError(f"payload {broken!r} should have been refused")
    assert json.loads(path.read_text(encoding="utf-8"))["current"] == 10073


def test_mirror_keeps_fields_it_does_not_own(tmp_path):
    (tmp_path / "data").mkdir()
    path = tmp_path / "data" / "counter.json"
    path.write_text(json.dumps({"current": 10073, "note": "keep me"}), encoding="utf-8")
    node_status.mirror_counter(tmp_path, {"current": 10100}, today="2026-09-15T00:00:00Z")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"current": 10100, "note": "keep me", "updated": "2026-09-15T00:00:00Z"}


def test_cli_mirror_leaves_the_file_alone_when_the_endpoint_is_unreachable(tmp_path):
    """The workflow must fail rather than commit a guess — offline is the tested default."""
    path = _counter_file(tmp_path, 10073)
    before = path.read_text(encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--mirror", "--url", "http://127.0.0.1:9/counter"],
        capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "left alone" in result.stderr
    assert path.read_text(encoding="utf-8") == before
