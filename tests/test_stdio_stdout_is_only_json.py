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

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CACHE_DB = REPO / ".cache" / "search_cache.db"  # noqa: F841 - documented default, see _cold_cache_env
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


def _cold_cache_env(cache_dir: Path) -> dict[str, str]:
    """Environment that points the server's L2 cache at an empty directory of its own.

    `_load_docs_cached` prints only `if changed:`, so a warm cache is the one state in which
    the bug is invisible — which is also why it survived. An empty directory is cold by
    construction, with nothing to move and nothing to put back.

    This used to `shutil.move` the real `.cache/search_cache.db` aside and move it back in a
    `finally`. That worked on Linux and failed on every Windows runner with
    `PermissionError: [WinError 32] ... .cache\\search_cache.db`, because the server the test
    had just spawned recreates and re-locks that file while SQLite/WAL still holds a handle.
    A derived, gitignored cache has no business being shuffled around by a test at all.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    return {**os.environ, "MISAKANET_CACHE_DIR": str(cache_dir)}


def test_the_mcp_stdio_stream_stays_pure_json_on_a_cold_cache(tmp_path):
    """The one that corrupts a protocol, not just a payload: JSON-RPC, one line per message."""
    env = _cold_cache_env(tmp_path / "l2")
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
        capture_output=True, text=True, timeout=240, cwd=str(REPO), env=env,
    )

    assert result.returncode == 0, f"the server exited {result.returncode}:\n{result.stderr[-2000:]}"
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert lines, f"the server wrote nothing to stdout:\n{result.stderr[-2000:]}"

    # The cache must actually have been cold, or everything below asserts nothing.
    # `_load_docs_cached` prints only `if changed:`, so a warm cache means no notice —
    # and a test that looks for stray notices then passes for the wrong reason. This is
    # the same guard the profile test uses, and it is what makes a warm-cache run fail
    # loudly instead of turning green on a payload it never had a chance to corrupt.
    #
    # **But the notice only exists on the BM25 path, and which path runs is not this
    # test's decision.** `misakanet/server/handlers/search.py:411` takes the SAG-Lite
    # backend whenever `data/sag.db` exists, and that branch never calls
    # `_load_docs_cached` at all. `data/sag.db` is gitignored (`.gitignore:54`), so CI —
    # which never builds the index — always sees the notice, while any machine that has
    # built it once does not. Measured 2026-10-05: this test failed on both local checkouts
    # and passed in CI, on the same commit, for exactly that reason.
    #
    # So this test no longer *fails* when the notice is absent. It reports which path it
    # took, and `test_the_l2_loader_itself_writes_nothing_to_stdout` below carries the
    # L2-specific coverage unconditionally, because it calls the loader directly and does
    # not depend on any backend being selected. The end-to-end half of this test keeps
    # its own value either way: a cold-cache stdio exchange must be pure JSON whichever
    # backend answers it.
    if "L2缓存" not in result.stderr:
        assert "SAG-Lite: available" in result.stderr, (
            "the L2 repopulation notice is absent and the server did not report SAG-Lite "
            "either, so this run followed neither documented path and the assertions below "
            f"are measuring an unknown state. stdout was:\n{result.stdout[:400]!r}\n"
            f"stderr was:\n{result.stderr[:400]!r}"
        )

    bad = _non_json_lines(result.stdout)
    assert not bad, (
        f"{len(bad)} line(s) of the MCP stdio stream are not JSON. A client parsing stdout "
        f"line-by-line fails on them, and it fails on the *first search after install*, which is "
        f"when the L2 cache repopulates and the notice fires:\n"
        + "\n".join(f"  line {i}: {line!r}" for i, line in bad[:6])
        + "\nAnything human-facing belongs on stderr; see misakanet/search/engine.py and "
          "misakanet/profile.py."
    )


def test_the_l2_loader_itself_writes_nothing_to_stdout(tmp_path, monkeypatch):
    """The regression itself, asserted where it lives — no backend, no subprocess, no luck.

    The end-to-end test above can only reach `_load_docs_cached` when the BM25 backend is
    selected, and that is not something a test controls: `data/sag.db` decides it, that file is
    gitignored, so the same commit exercises this code on CI and skips it on a machine that has
    built the index. Coverage that depends on a build artifact's absence is coverage that
    disappears exactly where someone is working.

    Calling the loader directly removes the dependency. Two assertions, and the second is what
    makes the first mean something:

      * stdout must be empty — that is the regression (`#2806`);
      * stderr must carry the notice — proving this run really did repopulate a cold cache,
        so "stdout was empty" is not just "the code printed nothing this time".

    The cache directory is redirected the same way the end-to-end test does it, and the
    module-level connection is reset so this test's cold directory is the one that gets used.
    """
    sys.path.insert(0, str(REPO))
    cache_dir = tmp_path / "l2-inplace"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MISAKANET_CACHE_DIR", str(cache_dir))

    import misakanet.search.engine as engine  # noqa: PLC0415  (after monkeypatch.setenv)

    # `_CACHE_DB` and `_L2_CONN` are resolved at import time, and a module-level connection
    # would keep this process pointing at whatever `.cache/` the rest of the suite warmed.
    monkeypatch.setattr(engine, "_CACHE_DIR", cache_dir)
    monkeypatch.setattr(engine, "_CACHE_DB", cache_dir / "search_cache.db")
    monkeypatch.setattr(engine, "_L2_CONN", None)

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        docs = engine._load_docs_cached(engine.LESSONS, is_lesson=True)

    assert docs, f"the loader returned nothing, so this run measured nothing:\n{err.getvalue()!r}"
    # stdout first, on purpose. Moving the notice off stderr is the regression, and it makes
    # stderr empty too — so asserting the precondition first would report "the cache was not
    # cold", which is true and useless. In this order the same mutation says what it did.
    assert out.getvalue() == "", (
        "misakanet/search/engine.py::_load_docs_cached wrote to stdout:\n"
        f"{out.getvalue()!r}\nThat is the bug this file exists for — `protocol.py:199` writes "
        "JSON-RPC to stdout one line per message, so a human-facing notice here becomes an "
        "unparseable line inside a valid exchange. Human output belongs on stderr; see the "
        "cross-encoder warnings a few lines below it, which already use file=sys.stderr."
    )
    assert "L2缓存" in err.getvalue(), (
        "the L2 repopulation notice never appeared on stderr, so the cache was not cold and the "
        f"stdout assertion above proves nothing. stderr was:\n{err.getvalue()!r}"
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
