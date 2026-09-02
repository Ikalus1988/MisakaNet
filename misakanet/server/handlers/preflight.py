"""Preflight check handler for MisakaNet MCP server."""
from __future__ import annotations


def handle_preflight(args: dict) -> dict:
    """Check risk level before executing high-risk operations."""
    from scripts.mcp_preflight import preflight_check

    intent = args.get("intent", "")
    context = args.get("context", "")
    if not intent:
        return {"error": "intent is required", "voice": "failure-warning"}
    result = preflight_check(intent, context)
    return result
