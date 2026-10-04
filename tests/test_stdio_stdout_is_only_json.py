#!/usr/bin/env python3
"""stdout of the machine-readable surfaces must be machine-readable.

Both surfaces this guards write their payload to stdout: `search_knowledge.py --json` for the
CLI, and `misakanet/server/protocol.py` for the MCP stdio transport, which is JSON-RPC line by
line on stdout. A human-facing notice printed to stdout lands *inside* that payload, and the
caller sees unparseable bytes rather than a clean error.

Measured 2026-10-04, and this is what made it worth a test:

    $ # L2 cache moved aside, so the next search repopulates it
    $ python3 scripts/mcp_server.py   # initialize, then misakanet_search
    stdout line 1: {"jsonrpc":"2.0","id":1,...}   valid
    stdout line 2:   📦 L2缓存: 464 篇变动          NOT JSON
    stdout line 3: {"jsonrpc":"2.0","id":2,...}   valid

`misakanet/search/engine.py::_load_docs_cached` printed that notice on a bare `print()`. It sits
in the data path — it runs on every search regardless of output mode, and the MCP search handler
reaches it — so the notice was unconditional, and it fired on exactly the first search after a
fresh install, which is when a new agent is most likely to break.

The same shape reached the CLI: `misakanet/profile.py` printed its stage-upgrade notice to
stdout, and `tests/test_search_quota.py` already treats "the documented local command's `--json`
output parses" as a contract — but it only ever saw the failure by accident. The notice is
one-shot, so it fires for whichever caller happens to cross the threshold, and a fresh profile
reaches it partway through a suite run. **The tests below set the state themselves** rather than
depending on what ran before them, which is what made that one unreliable.

Usage:
    python3 tests/test_stdio_stdout_is_only_json.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CACHE_DB = REPO / ".cache" / "search_cache.db"
PROFILE = REPO / "misakanet" / "profile.json"
CLI = REPO / "search_knowledge.py"
MCP = REPO / "scripts" / "mcp_server.py"


def _non_json_lines(text: str) -> list[tuple[int, str]]:
    """Non-empty lines that do not parse as JSON on their own, with 1-based line numbers.

    This models **JSON-RPC framing**, where the transport really is one document per line. It
    does not model the CLI's `--json`, which is a single pretty-printed document; that one is
    parsed whole, below, because line-by-line is the wrong contract there.
    """
    bad = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            bad.append((i, line))
    return bad


def _cold_cache() -> Path:
    """Move the L2 cache aside so the next search repopulates it, and return where it went.

    Without this the notice never fires and the test asserts nothing. `_load_docs_cached` prints
    only `if changed:`, so a warm cache is the one state in which the bug is invisible — which is
    also why it survived.
    """
    aside = REPO / ".cache" / "search_cache_db_aside_for_test"
    if aside.exists():
        shutil.rmtree(aside)
    aside.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        src = Path(str(CACHE_DB) + suffix)
        if src.exists():
            shutil.move(str(src), str(Path(str(aside) + suffix)))
    return aside


def _restore_cache(aside: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        src = Path(str(aside) + suffix)
        if src.exists():
            dst = Path(str(CACHE_DB) + suffix)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    shutil.rmtree(aside, ignore_errors=True)


def test_the_mcp_stdio_stream_stays_pure_json_on_a_cold_cache():
    """The one that corrupts a protocol, not just a payload: JSON-RPC, one line per message."""
    aside = _cold_cache()
    try:
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "misakanet_search",
                        "arguments": {"query": "context window exceeded", "limit": 3}}},
        ]
        result = subprocess.run(
            [sys.executable, str(MCP)],
            input="\n".join(json.dumps(r) for r in requests) + "\n",
            capture_output=True, text=True, timeout=240, cwd=str(REPO),
        )
    finally:
        _restore_cache(aside)

    assert result.returncode == 0, f"the server exited {result.returncode}:\n{result.stderr[-2000:]}"
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert lines, f"the server wrote nothing to stdout:\n{result.stderr[-2000:]}"

    bad = _non_json_lines(result.stdout)
    assert not bad, (
        f"{len(bad)} line(s) of the MCP stdio stream are not JSON. A client parsing stdout "
        f"line-by-line fails on them, and it fails on the *first search after install*, which is "
        f"when the L2 cache repopulates and the notice fires:\n"
        + "\n".join(f"  line {i}: {line!r}" for i, line in bad[:6])
        + "\nAnything human-facing belongs on stderr; see misakanet/search/engine.py and "
          "misakanet/profile.py."
    )


def test_the_documented_json_command_stays_parseable_when_the_profile_upgrades():
    """The profile notice is one-shot, so this sets the counter one below the threshold itself.

    Relying on it firing by accident is what made the coverage in `test_search_quota.py`
    unreliable — the outcome depended on which tests ran first. Pinning the state makes the
    guard deterministic in both directions.
    """
    sys.path.insert(0, str(REPO / "misakanet"))
    from profile import STAGE_SEARCH_THRESHOLD  # noqa: PLC0415  (after sys.path)

    original = PROFILE.read_text(encoding="utf-8") if PROFILE.exists() else None
    state = json.loads(original) if original else {}
    state["stage"] = "newcomer"
    state["search_count"] = max(0, STAGE_SEARCH_THRESHOLD - 1)
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE.write_text(json.dumps(state), encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(CLI), "context window exceeded", "--json"],
            capture_output=True, text=True, timeout=240, cwd=str(REPO),
        )
    finally:
        if original is None:
            PROFILE.unlink(missing_ok=True)
        else:
            PROFILE.write_text(original, encoding="utf-8")

    assert result.returncode == 0, f"exited {result.returncode}:\n{result.stderr[-2000:]}"
    # The upgrade must actually have fired, or this test is asserting nothing.
    assert "升级" in result.stderr, (
        "expected the stage-upgrade notice on stderr, so this run did not exercise the bug — "
        f"stdout was:\n{result.stdout[:400]!r}\nstderr was:\n{result.stderr[:400]!r}")

    # `--json` is one pretty-printed document, so the contract is "all of stdout parses" rather
    # than JSON-RPC's one-document-per-line. The notice used to land at the top of it, which is
    # what produced `Expecting value: line 1 column 3` in test_search_quota.py.
    try:
        hits = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        head = "\n".join(f"  {i:>2}| {line}" for i, line in
                         enumerate(result.stdout.splitlines()[:6], 1))
        raise AssertionError(
            f"`search_knowledge.py --json` did not produce JSON: {e}. An agent parsing this gets "
            f"garbage instead of results, and it happens the first time a node crosses the stage "
            f"threshold, because the upgrade notice used to be printed to stdout:\n{head}"
        ) from e
    assert isinstance(hits, list) and hits, "the payload should be the result list itself"

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  {name} ... ", end="", flush=True)
            try:
                fn()
                print("PASS")
            except Exception as e:  # noqa: BLE001  (a smoke runner reports, it does not raise)
                print(f"FAIL: {e}")
