"""MCP JSON-RPC protocol handler for MisakaNet server."""
from __future__ import annotations

import json
import sys

from ._config import get_server_version
from .handlers import (
    handle_get_lesson,
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


def main():
    """MCP stdio server loop."""
    from ._config import _init_search

    HAS_SAG, _, HAS_BM25, _ = _init_search()  # noqa: N806

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

        response = handle_request(request)
        if response:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
