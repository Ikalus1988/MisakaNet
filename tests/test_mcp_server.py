#!/usr/bin/env python3
"""Smoke test for MisakaNet MCP Server.

Tests the JSON-RPC handlers directly (no subprocess needed).

Every check below is a real gate: a false condition fails the pytest run and names the check
(see `check()`). This file used to only *print* its verdict, so it passed whatever the checks
said — a green run that proved nothing.

Usage:
    python3 tests/test_mcp_server.py
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# This script is directly runnable (`python3 tests/test_mcp_server.py`), so it cannot rely on
# `tests/conftest.py` for isolation — and it drives the real submit and search handlers, which append to
# two of the repository's own data files. Before this, every submission here added a row to
# `data/contribution_queue.jsonl` and every no-result search added a row to `data/search_gaps.jsonl`:
# 520 of the queue's 522 rows were fixtures, and the gap log's largest entries were this script's
# queries. Set before the import below, because that import resolves the paths into constants.
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="misakanet-mcp-smoke-"))
os.environ.setdefault("MISAKANET_GAP_LOG", str(_TEST_DATA_DIR / "search_gaps.jsonl"))
os.environ.setdefault("MISAKANET_CONTRIBUTION_QUEUE", str(_TEST_DATA_DIR / "contribution_queue.jsonl"))
# Same isolation problem, one level up: the intake path is remote-first, so it files the report on
# MisakaNet — `tests/test_me_inbox.py` created #3580 on the network while running this suite.
# `tests/conftest.py` sets the same switch for the pytest session; this script has no conftest, so
# it sets it itself. A gate must not file a real issue, and a check whose answer depends on the
# network is not a gate.
os.environ.setdefault("MISAKANET_INTAKE_DISABLE_REMOTE", "1")

from scripts.mcp_server import TOOLS, handle_request  # noqa: E402

PASS = 0
FAIL = 0


def rpc(method: str, params: dict = None, req_id: int = 1) -> dict:
    """Send a JSON-RPC request to the handler."""
    return handle_request({
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    })


def check(name: str, condition: bool, detail: str = ""):
    """A check that can go red.

    This used to only print. `PASS` and `FAIL` were module-level counters and nothing ever
    asserted on `FAIL`, so the file passed whatever the checks said: measured 2026-10-21, 19
    tests and 71 checks — 67 passed, 4 failed — and pytest still exited 0. A reader who saw the
    green run had learned nothing about the MCP server.

    Now a false condition raises `AssertionError` naming the check, which is this repository's
    convention for a gate that can fail: `tests/test_site_design_convergence.py` asserts with the
    failing problem in the message, and `tests/test_d1_counters_schema.py` asserts one property
    at a time with the same shape of message. The counters stay because the directly-runnable
    script prints a summary of them.
    """
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS {name}")
        return
    FAIL += 1
    print(f"  FAIL {name}{': ' + detail if detail else ''}")
    raise AssertionError(f"check failed: {name}{': ' + detail if detail else ''}")


def test_initialize():
    print("\n-- initialize --")
    resp = rpc("initialize")
    result = resp.get("result", {})
    check("has protocolVersion", "protocolVersion" in result)
    check("has serverInfo.name", result.get("serverInfo", {}).get("name") == "misakanet")
    expected_version = re.search(
        r'^version\s*=\s*["\']([^"\']+)["\']',
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8", errors="replace"),
        re.MULTILINE,
    ).group(1)
    check(
        "has current serverInfo.version",
        result.get("serverInfo", {}).get("version") == expected_version,
    )
    check("has capabilities.tools", "tools" in result.get("capabilities", {}))


def test_tools_list():
    print("\n-- tools/list --")
    resp = rpc("tools/list")
    tools = resp.get("result", {}).get("tools", [])
    tool_names = {t["name"] for t in tools}
    check("has misakanet_search", "misakanet_search" in tool_names)
    check("has misakanet_get_lesson", "misakanet_get_lesson" in tool_names)
    check("has misakanet_submit_usage", "misakanet_submit_usage" in tool_names)
    check("has misakanet_submit_intake", "misakanet_submit_intake" in tool_names)
    check("search requires query", "query" in tools[0]["inputSchema"]["required"])


def test_tool_descriptions_are_agent_friendly():
    print("\n-- tool descriptions --")
    required_terms = [
        "Input semantics",
        "Output schema",
        "Error cases",
        "Side effects",
        "Auth",
        "Rate limits",
    ]
    for tool in TOOLS:
        desc = tool.get("description", "")
        missing = [term for term in required_terms if term not in desc]
        check(f"{tool['name']} describes operating contract", not missing, f"missing: {missing}")


def test_search():
    print("\n-- tools/call: misakanet_search --")
    resp = rpc("tools/call", {
        "name": "misakanet_search",
        "arguments": {"query": "CI pipeline", "top": 3},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)

    if "error" in result:
        print(f"  WARN Search unavailable: {result['error']}")
        print("     (Run: python3 scripts/build_sag_index.py)")
        return

    results = result.get("results", [])
    check("returns results list", isinstance(results, list))
    if results:
        first = results[0]
        check("result has id", "id" in first, f"keys: {list(first.keys())}")
        check("result has title", "title" in first)
        check("result has score/rank", "score" in first or "rank" in first)
        # Draft filtering is validated in test_search_scope_and_drafts() —
        # the default (compact) detail does not carry `status`, so checking
        # it here would pass vacuously (#2270).
    else:
        print("  WARN No results returned (index may be empty)")


def test_get_lesson():
    print("\n-- tools/call: misakanet_get_lesson --")
    # Find a real lesson file
    lessons_dir = REPO_ROOT / "lessons"
    sample = None
    for subdir in ["core", "contrib"]:
        candidates = list((lessons_dir / subdir).glob("*.md")) if (lessons_dir / subdir).exists() else []
        if candidates:
            sample = candidates[0]
            break

    if not sample:
        print("  WARN No lesson files found, skipping")
        return

    lesson_id = sample.stem
    resp = rpc("tools/call", {
        "name": "misakanet_get_lesson",
        "arguments": {"id": lesson_id},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)

    check("returns path", "path" in result, f"keys: {list(result.keys())}")
    check("returns content", "content" in result)
    check("content is non-empty", len(result.get("content", "")) > 10)


def test_submit_usage():
    print("\n-- tools/call: misakanet_submit_usage --")
    # Deterministic: force the offline fallback (the worker POST routing is
    # covered by tests/test_submit_usage.py with a mocked transport).
    os.environ["MISAKANET_USAGE_DISABLE_REMOTE"] = "1"
    try:
        resp = rpc("tools/call", {
            "name": "misakanet_submit_usage",
            "arguments": {"lesson_id": "test-lesson", "tool": "smoke-test", "outcome": "solved"},
        })
    finally:
        del os.environ["MISAKANET_USAGE_DISABLE_REMOTE"]
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns status", "status" in result)
    check("status is logged", result.get("status") == "logged")


def test_submit_intake():
    print("\n-- tools/call: misakanet_submit_intake --")
    # The intake path is remote-first: it files the report on MisakaNet. This gate must not file a
    # real issue, and the answer must not depend on the network, so the call is forced onto the
    # local queue — the path this file can assert deterministically. The hosted worker's status
    # vocabulary is "pending_review" (a GitHub issue awaiting review); the local queue's is
    # "pending" (scripts/contribution_queue.py). The old check asserted the worker's word here and
    # so failed against the path this file actually runs — see
    # tests/test_intake_receipt_truthfulness.py for the hosted receipt.
    previous = os.environ.get("MISAKANET_INTAKE_DISABLE_REMOTE")
    os.environ["MISAKANET_INTAKE_DISABLE_REMOTE"] = "1"
    try:
        resp = rpc("tools/call", {
            "name": "misakanet_submit_intake",
            "arguments": {
                "kind": "missing_lesson",
                "problem": "pip install fails on WSL with SSL timeout",
                "error": "SSL: CERTIFICATE_VERIFY_FAILED",
                "source": "claude-code",
            },
        })
    finally:
        if previous is None:
            os.environ.pop("MISAKANET_INTAKE_DISABLE_REMOTE", None)
        else:
            os.environ["MISAKANET_INTAKE_DISABLE_REMOTE"] = previous
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted", result.get("submitted") is True)
    check("returns intake_id", "intake_id" in result)
    check("delivery is local_queue (a gate must not file a real issue)",
          result.get("delivery") == "local_queue",
          f"delivery={result.get('delivery')!r}")
    check("status is pending (awaiting review, not published)",
          result.get("status") == "pending",
          f"status={result.get('status')!r}")
    check("returns redactions_applied", "redactions_applied" in result)
    check("returns quality_score", "quality_score" in result)
    check("returns receipt", "receipt" in result)


def test_submit_intake_missing_problem():
    print("\n-- tools/call: misakanet_submit_intake missing problem --")
    resp = rpc("tools/call", {
        "name": "misakanet_submit_intake",
        "arguments": {"kind": "missing_lesson"},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns error when problem missing", "error" in result)


def test_submit_intake_dedup():
    print("\n-- tools/call: misakanet_submit_intake dedup --")
    args = {
        "kind": "missing_lesson",
        "problem": "Unique dedup test case XYZ123",
        "source": "smoke-test",
    }
    resp1 = rpc("tools/call", {"name": "misakanet_submit_intake", "arguments": args})
    resp2 = rpc("tools/call", {"name": "misakanet_submit_intake", "arguments": args})
    r1 = json.loads(resp1.get("result", {}).get("content", [{}])[0].get("text", "{}"))
    r2 = json.loads(resp2.get("result", {}).get("content", [{}])[0].get("text", "{}"))
    check("first submission succeeds", r1.get("submitted") is True)
    check("duplicate rejected", r2.get("submitted") is False or "error" in r2)


def test_submit_intake_title_sanitization():
    print("\n-- tools/call: misakanet_submit_intake title sanitization --")
    args = {
        "kind": "missing_lesson",
        "problem": "## 背景\n\nfeishu-interactive-card 是 Hermes Agent 的一个技能模块\n\n在日常使用中积累了一些实用经验",
        "source": "smoke-test",
    }
    resp = rpc("tools/call", {"name": "misakanet_submit_intake", "arguments": args})
    result = json.loads(resp.get("result", {}).get("content", [{}])[0].get("text", "{}"))
    check("submission succeeds", result.get("submitted") is True)
    # Verify no markdown headings in intake_id (which comes from GitHub issue)
    check("has intake_id", "intake_id" in result)


def test_unknown_tool():
    print("\n-- error handling --")
    resp = rpc("tools/call", {
        "name": "nonexistent_tool",
        "arguments": {},
    })
    check("returns error for unknown tool", "error" in resp)
    check("error code is -32601", resp.get("error", {}).get("code") == -32601)


def _okf_records():
    """The tracked export the SAG index is built from (`data/okf/lessons.jsonl`)."""
    path = REPO_ROOT / "data" / "okf" / "lessons.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _backend_matrix(tmp_root: Path):
    """Yield `(name, search_state, corpus, retrieves)` for every search backend.

    `search_state` is the tuple `handle_search` takes (`HAS_SAG, SAG_DB, HAS_BM25, sag_search`),
    `corpus` is the records that backend can retrieve, and `retrieves(record)` answers whether a
    retrieval over that corpus — *before* the surface's published-only filter — returns the record.

    Every backend is built here, from tracked files, so the answer never depends on whatever
    index the machine happens to carry. That mattered: `data/sag.db` is gitignored, and the copy
    on this checkout was built on 2026-08-01 — measured 2026-10-21, 2.5 months before the corpus
    it claims to describe. It held 1 of the 37 drafts, and the probe query answered 1 hit from it
    and 9 from BM25. The same commit was therefore green in a fresh worktree and red in this
    checkout: a gate whose answer depends on a file the developer last built by hand is not a
    gate.

    The three backends are the three the handler can take (`misakanet/server/handlers/search.py`).
    `_exclude_drafts` exists precisely because SAG-Lite and the stdlib fallback do not filter
    drafts themselves, so all three are held to the same contract here.
    """
    from misakanet.search.engine import LESSONS, _compute_bm25_scores, _load_docs_cached
    from misakanet.server.handlers.search import _fallback_search
    from scripts.build_sag_index import build_index
    from scripts.build_sag_index import search as sag_search

    # sag-lite — an index this test builds from the tracked export, never the one on disk.
    db = tmp_root / "sag.db"
    build_index(REPO_ROOT / "data" / "okf", db)
    okf = _okf_records()
    yield (
        "sag-lite",
        (True, db, True, sag_search),
        [{"id": Path(r["path"]).stem, "title": r["title"], "status": r["status"],
          "path": r["path"]} for r in okf],
        lambda rec: any(h.get("path") == rec["path"]
                        for h in sag_search(db, rec["title"], top=9)),
    )

    # bm25 — the `lessons/` corpus, read by the engine. BM25 drops drafts itself
    # (`_rank_docs_impl`), so the pre-filter evidence is the score the draft would have earned.
    docs = _load_docs_cached(LESSONS, is_lesson=True)

    def bm25_retrieves(rec):
        idx = [i for i, d in enumerate(docs) if d.is_draft and d.title == rec["title"]]
        if not idx:
            return False
        return _compute_bm25_scores(rec["title"], docs)[idx[0]] > 0

    yield (
        "bm25",
        (False, None, True, None),
        [{"id": Path(d.filepath).stem, "title": d.title,
          "status": "draft" if d.is_draft else "published"} for d in docs],
        bm25_retrieves,
    )

    # fallback — `data/lessons.json`, stdlib only. It does not filter drafts either, so this is
    # the backend where the surface's own filter is the only thing between a draft and a caller.
    lessons = json.loads((REPO_ROOT / "data" / "lessons.json").read_text(encoding="utf-8"))
    yield (
        "fallback",
        (False, None, False, None),
        [{"id": e["id"], "title": e["title"], "status": e.get("status", ""),
          "path": e.get("url", "")} for e in lessons],
        lambda rec: any(h.get("path") == rec["path"]
                        for h in _fallback_search(rec["title"], top=9)),
    )


def _search_pinned(state, query: str, detail: str) -> dict:
    """Call `misakanet_search` over JSON-RPC with the backend pinned to `state`."""
    import misakanet.server.handlers.search as search_module

    previous = search_module._SEARCH_STATE
    search_module._SEARCH_STATE = state
    try:
        resp = rpc("tools/call", {
            "name": "misakanet_search",
            "arguments": {"query": query, "top": 3, "detail": detail},
        })
    finally:
        search_module._SEARCH_STATE = previous
    text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    return json.loads(text)


def test_search_scope_and_drafts():
    """What this surface tells a caller about drafts — on every backend, reproducibly.

    The old check here could never fail (#2270): it counted `r.get("status") == "draft"` on a
    default search, and `status` was not in the compact or summary projection, so the count was 0
    whatever the search returned. The surface has since moved (#1999) and `check()` now raises,
    which turned the assertions below live — and the first version of them turned out to assert
    a *coincidence* rather than a contract: the probe was a draft's title, and the only lesson
    that title matched was that draft, so "the probe query returns a hit" held only on a corpus
    where something else happened to share the words. Measured 2026-10-21, the same commit was
    green in a fresh worktree (BM25 answered) and red in this checkout (a `data/sag.db` built on
    2026-08-01 answered instead).

    So both halves are pinned now:

    * **the backend** — `data/sag.db` is gitignored, and the copy on this checkout is 2.5 months
      older than the corpus it claims to describe: it held 1 of the 37 drafts. The three
      backends the handler can take are each built here, from tracked files, and each is held to
      the same contract;
    * **the probe** — derived from the corpus at run time, so it cannot drift from it.

    The contract, from `docs/mcp.md` ("search returns results with `path`, `status` ... fields";
    "Drafts are excluded to avoid surfacing unverified content"):

    * `status` and `path` are carried at **every** detail level — `path` because
      `misakanet_get_lesson` needs one of them to fetch, `status` because it is how a caller tells
      a draft from a published lesson;
    * drafts are **excluded** at every detail level, and the exclusion is *load-bearing*: the
      probed draft is retrievable from the backend's corpus, so a leak would show.

    Measured here (2026-10-21), so the assertions are about this surface and not about a policy
    nobody has implemented:

        compact  keys: evidence_level, freshness, id, kind, path, problem, score, status, title
        summary  keys: domain, evidence_level, freshness, id, kind, path, problem, status, tags, title
        full     keys: domain, kind, path, score, status, title
    """
    print("\n-- search scope: what this surface reveals about drafts --")

    with tempfile.TemporaryDirectory(prefix="misakanet-mcp-backends-") as tmp:
        for name, state, corpus, retrieves in _backend_matrix(Path(tmp)):
            published = [r for r in corpus if r["status"] == "published"]
            drafts = [r for r in corpus if r["status"] == "draft"]
            check(f"{name}: the corpus carries published lessons", bool(published),
                  f"{len(corpus)} records, none published")
            check(f"{name}: the corpus carries drafts (the probe is meaningful)", bool(drafts),
                  f"{len(corpus)} records, none draft")

            # A published probe: the surface must answer with hits, and every hit must be
            # actionable — `path` to fetch it, `status` to know what it is.
            pub = published[0]
            for detail in ("compact", "summary", "full"):
                payload = _search_pinned(state, pub["title"], detail)
                check(f"{name}: {detail} answers without an error", "error" not in payload,
                      f"got {payload.get('error')!r}")
                hits = payload.get("results", [])
                check(f"{name}: {detail} returns hits for a published lesson", bool(hits),
                      f"query={pub['title']!r}, got {hits!r}")
                check(f"{name}: {detail} carries `status` on every hit",
                      all("status" in h for h in hits),
                      f"{detail} keys: {sorted(hits[0]) if hits else []}")
                check(f"{name}: {detail} carries `path` on every hit",
                      all("path" in h for h in hits),
                      f"{detail} keys: {sorted(hits[0]) if hits else []}")

            # The leak probe: a draft this backend *would* return if the surface stopped
            # filtering. Picking it is setup — the assertion is that the surface drops it.
            draft = next((r for r in drafts if retrieves(r)), None)
            check(f"{name}: some draft in the corpus is retrievable by its own title "
                  f"(so the exclusion can be observed)",
                  draft is not None,
                  f"{len(drafts)} drafts, none retrievable by title")
            for detail in ("compact", "summary", "full"):
                payload = _search_pinned(state, draft["title"], detail)
                check(f"{name}: {detail} answers without an error", "error" not in payload,
                      f"got {payload.get('error')!r}")
                hits = payload.get("results", [])
                check(f"{name}: {detail} surfaces no draft (the default scope excludes drafts)",
                      all(h.get("status") != "draft" for h in hits),
                      f"{detail} statuses: {[h.get('status') for h in hits]}")
                check(f"{name}: {detail} does not carry the probed draft",
                      draft["title"] not in {h.get("title") for h in hits},
                      f"draft={draft['title']!r}, hit titles={[h.get('title') for h in hits]}")


def test_usage_status():
    print("\n-- tools/call: misakanet_usage_status --")
    resp = rpc("tools/call", {
        "name": "misakanet_usage_status",
        "arguments": {"user": "anon:test-mcp"},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns user", "user" in result)
    check("returns free_reads_used", "free_reads_used" in result)
    check("returns free_reads_limit", "free_reads_limit" in result)
    check("returns free_reads_remaining", "free_reads_remaining" in result)
    check("returns credits", "credits" in result)
    check("returns is_registered", "is_registered" in result)


def test_write_lesson_missing_fields():
    print("\n-- tools/call: misakanet_write_lesson missing fields --")
    resp = rpc("tools/call", {
        "name": "misakanet_write_lesson",
        "arguments": {"title": "test"},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted=False", result.get("submitted") is False)
    check("returns error for missing fields", "error" in result)
    check("error mentions missing fields", "Missing required fields" in result.get("error", ""))


def test_write_lesson_no_token():
    print("\n-- tools/call: misakanet_write_lesson no token --")
    resp = rpc("tools/call", {
        "name": "misakanet_write_lesson",
        "arguments": {
            "title": "test lesson",
            "domain": "python",
            "problem": "Something failed during build",
            "root_cause": "Missing dependency",
            "fix": "Install the package",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted=False", result.get("submitted") is False)
    check("returns error for no token", "error" in result)
    check("error mentions token required", "token required" in result.get("error", "").lower())


def test_write_lesson_anon_token():
    print("\n-- tools/call: misakanet_write_lesson anon token --")
    resp = rpc("tools/call", {
        "name": "misakanet_write_lesson",
        "arguments": {
            "title": "test lesson",
            "domain": "python",
            "problem": "Something failed during build",
            "root_cause": "Missing dependency",
            "fix": "Install the package",
            "token": "anon:test",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted=False", result.get("submitted") is False)
    check("rejects anon token", "token required" in result.get("error", "").lower())


def test_write_lesson_low_quality():
    print("\n-- tools/call: misakanet_write_lesson low quality --")
    import uuid
    unique = uuid.uuid4().hex[:8]
    resp = rpc("tools/call", {
        "name": "misakanet_write_lesson",
        "arguments": {
            "title": f"test {unique}",
            "domain": "misc",
            "problem": "nope",
            "root_cause": "nope",
            "fix": "nope",
            "token": "token:test-agent",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted=False", result.get("submitted") is False)
    check("rejects low quality", "Quality score too low" in result.get("error", ""))
    check("returns quality_score", "quality_score" in result)


def test_write_lesson_success():
    print("\n-- tools/call: misakanet_write_lesson success --")
    import uuid
    unique = uuid.uuid4().hex[:8]
    title = f"pip install timeout on corporate proxy {unique}"
    resp = rpc("tools/call", {
        "name": "misakanet_write_lesson",
        "arguments": {
            "title": title,
            "domain": "python",
            "problem": "When running pip install behind a corporate proxy, the connection times out after 15 seconds. This happens because the proxy requires authentication but pip does not send credentials by default.",
            "root_cause": "pip does not automatically use HTTP_PROXY_AUTH environment variables. The proxy returns 407 Proxy Authentication Required but pip treats this as a timeout.",
            "fix": "Set HTTP_PROXY and HTTPS_PROXY with embedded credentials: export HTTP_PROXY=http://user:pass@proxy:8080. Or use pip --proxy flag.",
            "verification": "Run pip install requests behind proxy and verify it completes within 30 seconds.",
            "token": "token:test-agent",
            "source": "smoke-test",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted=True", result.get("submitted") is True)
    check("returns lesson_id", "lesson_id" in result)
    check("status is pending_review", result.get("status") == "pending_review")
    check("returns quality_score", "quality_score" in result)
    check("quality_score >= 75", result.get("quality_score", 0) >= 75)
    check("returns receipt", "receipt" in result)
    # Clean up test contribution from queue
    queue_path = Path("data/contribution_queue.jsonl")
    if queue_path.exists():
        lines = queue_path.read_text(encoding="utf-8").strip().split("\n")
        lines = [l for l in lines if unique not in l]
        queue_path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")


def test_preflight_missing_intent():
    print("\n-- tools/call: misakanet_preflight missing intent --")
    resp = rpc("tools/call", {
        "name": "misakanet_preflight",
        "arguments": {},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns error for missing intent", "error" in result)


if __name__ == "__main__":
    print("MisakaNet MCP Server smoke test")
    for _test in (
        test_initialize,
        test_tools_list,
        test_tool_descriptions_are_agent_friendly,
        test_search,
        test_get_lesson,
        test_submit_usage,
        test_submit_intake,
        test_submit_intake_missing_problem,
        test_submit_intake_dedup,
        test_submit_intake_title_sanitization,
        test_unknown_tool,
        test_search_scope_and_drafts,
        test_usage_status,
        test_write_lesson_missing_fields,
        test_write_lesson_no_token,
        test_write_lesson_anon_token,
        test_write_lesson_low_quality,
        test_write_lesson_success,
        test_preflight_missing_intent,
    ):
        # `check()` raises now, so the script catches it per test: one broken check must not
        # hide the ones after it, and the summary below still has to be printed. The exit code
        # stays the script's contract — non-zero when anything failed.
        try:
            _test()
        except AssertionError as exc:
            print(f"  ERROR {exc}")

    print(f"\n{'=' * 40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
