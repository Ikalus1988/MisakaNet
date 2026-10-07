#!/usr/bin/env python3
"""`scripts/mcp_preflight.py` must not report "no risk lesson" about a lesson index it never read.

Why this matters here specifically: the MCP tool description told clients that an empty
`matched_lessons` means "the profile matched but no lesson was close enough". So a corrupted
`data/lessons.json` was not merely silent — it was indistinguishable from the documented normal
case, to exactly the clients most likely to act on the field (#2940).

Measured on the real corpus, same intent both times:

    healthy index     -> risk: critical, matched_lessons: 1
    truncated index   -> risk: high,    matched_lessons: 0

The `high` came from the static keyword profile, so the only thing that had disappeared was the
lesson evidence — and nothing in the payload said so.

The positive direction is pinned too: a healthy index must still say `index_status: "ok"`. A gate
that only proves the corrupt case fails will also pass an implementation that refuses to read the
index at all.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import mcp_preflight as pf  # noqa: E402

# An intent that matches the one lesson in the shipped corpus that carries triggers
# (`rag-build-strategy-batch`, severity critical).
INTENT = "build a chroma embedding index in batch"

# Every one of these is a way the index can fail to be evidence without looking like "no lessons".
BROKEN_INDEXES = {
    "truncated json": '{"bad json',
    "valid json, wrong shape": '{"lessons": []}',
    "empty file": "",
    "json null": "null",
    "json string": '"lessons"',
}


def _point_at(tmp_path: pathlib.Path, monkeypatch, payload: str | None) -> pathlib.Path:
    """Bind the module's index to `payload` inside tmp_path. `None` means the file is absent."""
    index = tmp_path / "lessons.json"
    if payload is not None:
        index.write_text(payload, encoding="utf-8")
    monkeypatch.setattr(pf, "DATA_LESSONS", index)
    return index


# ── the loader refuses rather than reporting nothing ─────────────────────────

@pytest.mark.parametrize("payload", BROKEN_INDEXES.values(), ids=BROKEN_INDEXES.keys())
def test_loader_raises_instead_of_reporting_no_lessons(tmp_path, monkeypatch, payload):
    _point_at(tmp_path, monkeypatch, payload)
    with pytest.raises(pf.LessonIndexUnreadable):
        pf.load_lessons_with_triggers()


def test_loader_raises_when_the_index_is_absent(tmp_path, monkeypatch):
    # An absent index is the same evidence gap as an unparseable one, and it used to be the first
    # of the two silent `return []`s.
    _point_at(tmp_path, monkeypatch, None)
    with pytest.raises(pf.LessonIndexUnreadable):
        pf.load_lessons_with_triggers()


def test_a_readable_index_still_loads(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch, json.dumps([
        {"id": "a", "triggers": {"intents": ["rag"]}},
        {"id": "b", "no": "triggers"},
    ]))
    assert [lesson["id"] for lesson in pf.load_lessons_with_triggers()] == ["a"]


# ── the caller states the gap rather than absorbing it ───────────────────────

@pytest.mark.parametrize("payload", BROKEN_INDEXES.values(), ids=BROKEN_INDEXES.keys())
def test_preflight_marks_the_index_unreadable(tmp_path, monkeypatch, payload):
    _point_at(tmp_path, monkeypatch, payload)
    result = pf.preflight_check(INTENT)

    assert result["index_status"] == "unreadable"
    assert result["index_error"], "an unreadable index must say why"
    assert result["index_error"] != result["recommendation"]


def test_preflight_does_not_call_an_unchecked_operation_safe(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch, '{"bad json')
    result = pf.preflight_check("something with no matching profile")

    # The whole defect was this sentence: nothing had been verified, yet the payload said the
    # operation was fine to proceed with.
    assert result["recommendation"] != "Safe to proceed"
    assert "unreadable" in result["recommendation"].lower()


def test_the_shipped_index_is_reported_ok():
    # Guards against a fix that satisfies the corrupt cases by never reading the index.
    result = pf.preflight_check(INTENT)
    assert result["index_status"] == "ok"
    assert result["index_error"] is None
    assert [lesson["id"] for lesson in result["matched_lessons"]] == ["rag-build-strategy-batch"]
    assert result["risk"] == "critical"


# ── the CLI turns the gap into a non-zero exit ───────────────────────────────

def _run_cli(tmp_path: pathlib.Path, payload: str | None):
    """Run the real script bytes with their index pointed at a temporary file.

    `REPO_ROOT` is derived from `__file__`, so copying the script under `tmp/scripts/` is what
    redirects its index — the executed code is the shipped file, unmodified.
    """
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / "scripts" / "mcp_preflight.py", tmp_path / "scripts" / "mcp_preflight.py")
    if payload is not None:
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "lessons.json").write_text(payload, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(tmp_path / "scripts" / "mcp_preflight.py"), INTENT, "--json"],
        capture_output=True,
        text=True,
    )


def test_cli_exits_zero_on_a_healthy_index(tmp_path):
    done = _run_cli(tmp_path, json.dumps([{"id": "x", "triggers": {"intents": ["rag"]}}]))
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["index_status"] == "ok"


def test_cli_exits_non_zero_on_a_corrupt_index(tmp_path):
    done = _run_cli(tmp_path, '{"bad json')
    assert done.returncode == 1, f"stdout={done.stdout}\nstderr={done.stderr}"
    assert "unusable" in done.stderr
    # The reason also travels in the JSON, so a caller parsing stdout is not left guessing.
    assert json.loads(done.stdout)["index_status"] == "unreadable"


def test_cli_exits_non_zero_when_the_index_is_absent(tmp_path):
    done = _run_cli(tmp_path, None)
    assert done.returncode == 1, f"stdout={done.stdout}\nstderr={done.stderr}"
    assert "does not exist" in done.stderr