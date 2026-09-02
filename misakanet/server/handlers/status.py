"""Usage status and registration handlers for MisakaNet MCP server."""
from __future__ import annotations


def handle_usage_status(args: dict) -> dict:
    """Show current usage status and remaining quota."""
    try:
        from scripts.usage_meter import get_status

        user = args.get("user", "anon:mcp-default")
        status = get_status(user)
        return {
            "user": status["user"],
            "free_reads_used": status["free_reads_used"],
            "free_reads_limit": status["free_reads_limit"],
            "free_reads_remaining": status["free_reads_remaining"],
            "credits": status["credits"],
            "is_registered": status["is_registered"],
            "next": (
                "Use misakanet_submit_intake"
                " or misakanet_contribute_lesson"
                " to request more credits."
            ),
        }
    except Exception as e:
        return {
            "error": str(e),
            "user": "unknown",
            "free_reads_remaining": -1,
        }


def handle_register(args: dict) -> dict:
    """Register an agent and return a node_id + token."""
    import secrets
    from datetime import datetime, timezone

    agent_type = args.get("agent_type", "unknown")

    # Generate deterministic node_id from agent_type + random suffix
    suffix = secrets.token_hex(3).upper()
    node_id = f"Misaka{int(suffix, 16) % 100000:05d}"

    # Generate token
    token = f"mcp_{secrets.token_urlsafe(24)}"

    registered_at = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    # Persist registration to usage_meter
    try:
        from scripts.usage_meter import _save_record

        _save_record({
            "user": f"token:{token}",
            "action": "register",
            "node_id": node_id,
            "agent_type": agent_type,
            "ts": registered_at,
        })
    except Exception:
        pass  # Non-fatal: registration still returns token

    return {
        "node_id": node_id,
        "token": token,
        "registered_at": registered_at,
        "agent_type": agent_type,
    }
