"""MCP JSON-RPC protocol handler for MisakaNet server."""
from __future__ import annotations

import json
import os
import sys

from ._config import get_server_version
from .handlers import (
    handle_get_lesson,
    handle_me_events,
    handle_me_inbox,
    handle_memory_context,
    handle_preflight,
    handle_register,
    handle_search,
    handle_submit_intake,
    handle_submit_usage,
    handle_usage_status,
    handle_write_lesson,
)
from .prompts import PROMPTS, handle_prompts_get
from .resources import handle_resources_list, handle_resources_read
from .tools import _filtered_tools

# Handler dispatch table
_HANDLERS = {
    "misakanet_search": handle_search,
    "misakanet_get_lesson": handle_get_lesson,
    "misakanet_submit_usage": handle_submit_usage,
    "misakanet_submit_intake": handle_submit_intake,
    "misakanet_write_lesson": handle_write_lesson,
    "misakanet_preflight": handle_preflight,
    "misakanet_usage_status": handle_usage_status,
    "misakanet_register": handle_register,
    "misakanet_memory_context": handle_memory_context,
    # Hosted tool, proxied since 2026-09-30 so a local install can run the skill's reuse-evidence
    # steps (D4=A, intake #2000). A name in tools/list with no row here answers "Unknown tool" —
    # tests/test_mcp_capability_parity.py pins the two lists against each other.
    "misakanet_me_events": handle_me_events,
    "misakanet_me_inbox": handle_me_inbox,
}


def handle_request(request: dict) -> dict:
    """Handle a JSON-RPC request."""
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                },
                "serverInfo": {
                    "name": "misakanet",
                    "version": get_server_version(),
                },
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": _filtered_tools()},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = _HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}",
                },
            }

        result = handler(tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False),
                    }
                ],
            },
        }

    elif method == "notifications/initialized":
        return None

    # ── Resources ──
    elif method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": handle_resources_list()},
        }

    elif method == "resources/read":
        uri = params.get("uri", "")
        content = handle_resources_read(uri)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(content, ensure_ascii=False),
                    }
                ]
            },
        }

    # ── Prompts ──
    elif method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"prompts": PROMPTS},
        }

    elif method == "prompts/get":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = handle_prompts_get(name, arguments)
        if "error" in result:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": result["error"]},
            }
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Unknown method: {method}",
            },
        }


def _enable_docs_cache() -> float:
    """Turn on the in-process corpus cache and return the window it uses, in seconds.

    This process lives as long as the client's session, and every tool call used to re-walk the
    corpus: measured 6.6 s per call on a WSL checkout (765 lessons on `/mnt/c`) against 0.007 ms
    for a cached load, because it is 765 `stat()` calls, not because anything changed. The window
    is a staleness budget, not a freshness guarantee — the corpus changes on a daily cron, so five
    seconds is invisible to a user and removes the walk from every call after the first.

    Separate from `main()` so the wiring can be tested without a stdin loop:
    `MISAKANET_DOCS_TTL_SECONDS=0` turns it off, and a value that is not a number falls back to 5
    rather than crashing a server before it can say anything.
    """
    from ..search.engine import set_docs_cache_ttl  # noqa: PLC0415

    raw = os.environ.get("MISAKANET_DOCS_TTL_SECONDS", "5")
    try:
        ttl = max(0.0, float(raw))
    except ValueError:
        sys.stderr.write(
            f"MISAKANET_DOCS_TTL_SECONDS={raw!r} is not a number; using 5 seconds\n")
        ttl = 5.0
    set_docs_cache_ttl(ttl)
    return ttl


def _try_enable_docs_cache() -> bool:
    """Enable the corpus cache, or say why not and keep serving.

    The cache is an optimisation, never a prerequisite. A git checkout that has not installed the
    optional `misakanet-core` wheel used to start and degrade (`BM25: not available`, search still
    answered 3 results); the cache call made that import unconditional and killed the server before
    it could say anything — install-smoke was red from 2026-11-02 to 2026-11-04 for this reason.
    """
    try:
        _enable_docs_cache()
        return True
    except Exception as exc:  # noqa: BLE001 - any failure here is non-fatal by definition
        sys.stderr.write(f"docs cache disabled ({type(exc).__name__}: {exc})\n")
        return False


def main():
    """MCP stdio server loop."""
    from ._config import _init_search

    HAS_SAG, _, HAS_BM25, _ = _init_search()  # noqa: N806

    _try_enable_docs_cache()
    sys.stderr.write("MisakaNet MCP Server started\n")
    sag_status = "available" if HAS_SAG else "not available (run build_sag_index.py)"
    bm25_status = "available" if HAS_BM25 else "not available"
    sys.stderr.write(f"SAG-Lite: {sag_status}\n")
    sys.stderr.write(f"BM25: {bm25_status}\n")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        # A tool handler that raises must not take the process down: the client
        # would lose the whole session, not just this call, and would see a
        # closed pipe instead of a diagnosable error. Report it as a JSON-RPC
        # error for this request and keep serving.
        try:
            response = handle_request(request)
        except Exception as exc:  # noqa: BLE001 - boundary guard, see above
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {type(exc).__name__}: {exc}",
                },
            }
        if response:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
