#!/usr/bin/env python3
"""Node-counter reading invariants (2026-09-15, issue #1683; rewritten 2026-09-28).

Background — the failure these tests exist to prevent
----------------------------------------------------
``data/counter.json`` was written only by the issue-based registration workflow, while every
MCP registration (the npx installer's path) incremented the worker's counter. Two independent
sequences described one fact: the file said 10073, KV said 10178, the site showed 178 nodes and the
public surfaces said "52+"/"59" (issue #1683).

The file had one writer left after that was fixed — ``scripts/node_status.py --mirror``, called daily
by ``sync-node-counter.yml`` — and one reader: ``/api/counter``'s last resort. Both are gone
(2026-09-28), because a *second copy* is the wrong shape for this particular number: the endpoint is
read to predict the id the next registrant is handed, so a mirror that can be arbitrarily behind
(issue #1820: the ``data`` branch's copy sat frozen 3.5 months) is worse than no answer at all.

What is pinned here now is the reading half, because deleting the writer is only half the change:

* the script reads the endpoint and nothing else — no file, no ``--mirror``;
* a payload without a usable ``current`` is reported as unavailable (exit 1), never printed as a
  number: a 5xx body parsed as JSON, ``{"current": null}`` and ``{"current": true}`` are all shapes
  that end up as ``Node Counter: 0`` or ``None`` if nobody looks;
* the guards the mirror used to carry that still apply — a bool is not an int, and a zero or negative
  count is not a counter.
"""
import ast
import contextlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import node_status  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "node_status.py"


# ── the file is gone, and nothing may quietly bring it back ──────────────────

def _code_only(path: Path) -> str:
    """The module's code: no comments and no docstring.

    The docstring *explains* the deletion (`data/counter.json` appears in it, on purpose), so a
    substring search over the whole file would fail on the prose that documents the fix — the trap
    this repository has hit often enough to name. `ast` finds the docstring rather than a `\"\"\"`
    split, which would break the day a second triple-quoted string appears.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    body = tree.body
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        lines = lines[body[1].lineno - 1:] if len(body) > 1 else []
    return "\n".join(line for line in lines if not line.strip().startswith("#"))


def test_the_counter_file_is_not_read_or_written_any_more():
    """The inverse gate for the deletion: no file I/O, no writer, no CLI flag, no file."""
    code = _code_only(REPO / "scripts" / "node_status.py")
    touches = re.findall(r"\.(read_text|write_text|read_bytes|write_bytes|open|unlink)\(", code)
    assert touches == [], (
        f"node_status.py touches files again ({touches}) — it reads the endpoint and nothing else; "
        "the file it used to mirror was a second copy of one number (#1683/#1820)"
    )
    assert "mirror_counter" not in code, (
        "the mirror writer is back — it existed to refresh a file that no longer exists, and "
        "recreating it would restore the second copy of the number"
    )
    assert "COUNTER_URL" in code, "the script no longer names the endpoint it reads"
    assert not hasattr(node_status, "mirror_counter"), "mirror_counter is importable again"
    assert not hasattr(node_status, "read_counter_file"), "read_counter_file is importable again"
    assert not (REPO / "data" / "counter.json").exists(), (
        "data/counter.json is back in the tree — nothing writes it, so it is a number that only "
        "looks authoritative"
    )


def test_the_cli_has_no_mirror_mode():
    proc = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "--mirror" not in proc.stdout, (
        "`--mirror` is an accepted flag again, but the file it wrote is gone — the mode would either "
        "crash or recreate it"
    )


# ── a number is printed only when the endpoint actually gave one ─────────────

def test_usable_current_rejects_everything_that_is_not_a_counter():
    for broken in (None, {}, {"current": None}, {"current": "10179"}, {"current": True},
                   {"current": False}, {"current": 0}, {"current": -5}, {"current": 10179.5},
                   [10179], "10179"):
        assert node_status.usable_current(broken) is None, broken
    assert node_status.usable_current({"current": 10179}) == 10179
    assert node_status.usable_current({"current": 10179, "updated": "2026-09-27"}) == 10179


def test_cli_reports_unavailable_instead_of_a_number(tmp_path):
    """The endpoint unreachable: exit 1, and no counter in the output."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", "--url", "http://127.0.0.1:9/counter"],
        capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "no local fallback" in result.stderr, result.stderr
    assert "Node Counter" not in result.stdout


def _run_main(monkeypatch, payload, argv):
    monkeypatch.setattr(node_status, "fetch_counter",
                        lambda url=node_status.COUNTER_URL: payload)
    monkeypatch.setattr(sys, "argv", argv)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = node_status.main()
    return code, buffer.getvalue()


def test_cli_prints_the_number_when_the_endpoint_gives_one(monkeypatch):
    code, out = _run_main(monkeypatch, {"current": 15774, "updated": "2026-09-27", "source": "d1"},
                          ["node_status.py", "--json"])
    assert code == 0
    data = json.loads(out)
    assert data["counter"] == 15774
    assert data["latest_node_id"] == "Misaka15774"
    assert data["source"] == "d1", "the payload's own source is reported, not assumed"


def test_cli_exits_nonzero_when_the_body_carries_no_counter(monkeypatch):
    """A 200 with `{"current": null}` is the endpoint's *unavailable* answer, not a value.

    `main()` has to treat it as such on both channels: exit 1 (so a script cannot read "0") and no
    number in the output.
    """
    code, out = _run_main(monkeypatch, {"current": None, "source": "unavailable"},
                          ["node_status.py"])
    assert code == 1, out
    assert "Node Counter:     unknown" in out, out


def test_the_lesson_count_is_read_from_disk(tmp_path):
    (tmp_path / "lessons" / "core").mkdir(parents=True)
    (tmp_path / "lessons" / "contrib").mkdir(parents=True)
    (tmp_path / "lessons" / "core" / "a.md").write_text("# a\n", encoding="utf-8")
    (tmp_path / "lessons" / "contrib" / "b.md").write_text("# b\n", encoding="utf-8")
    assert node_status.count_lessons(tmp_path) == 2
