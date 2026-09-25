"""Usage status and registration handlers for MisakaNet MCP server."""
from __future__ import annotations

import hashlib
import re

# Same identifier grammar as the deployed worker: 8-64 chars of A-Za-z0-9._:-.
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,64}$")

_INVALID_CLIENT_ID = {
    "error": "client_id must be 8-64 characters of A-Z a-z 0-9 . _ : -",
    "code": "invalid_client_id",
    "hint": (
        "Use a value you can regenerate, e.g. a UUID or a workspace/hostname id. "
        "Omit client_id to keep the old behaviour."
    ),
}


def _node_id_for_client(client_id: str) -> str:
    """Deterministic node id for a client-supplied identifier.

    The deployed worker keeps a client_id → node mapping in KV; this server has no
    KV, so it derives the id instead. The observable contract is the same: the same
    client_id always yields the same node_id.
    """
    digest = hashlib.sha256(f"misakanet:{client_id}".encode("utf-8")).hexdigest()
    return f"Misaka{int(digest[:8], 16) % 100000:05d}"


def _registered_tokens() -> dict[str, str]:
    """node_id → token for registrations recorded in the local usage meter.

    Wrapped in a function so tests can patch it without touching data/usage_credits.jsonl.
    """
    try:
        from scripts.usage_meter import _load_records
    except Exception:  # pragma: no cover - the meter is optional for registration
        return {}
    tokens: dict[str, str] = {}
    for record in _load_records():
        if record.get("action") == "register" and record.get("node_id") and record.get("token"):
            tokens[str(record["node_id"])] = str(record["token"])
    return tokens


def _save_registration(record: dict) -> None:
    """Persist a registration (best effort: registration must not fail on storage)."""
    try:
        from scripts.usage_meter import _save_record

        _save_record(record)
    except Exception:
        pass


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
    """Register an agent and return a node_id + token.

    Pass a stable `client_id` (a random UUID you keep private) and every call returns
    the same node and token, so reuse evidence and history accumulate in one place
    instead of restarting on every call. Omitting it keeps the old behaviour: a fresh
    node per call.

    `client_id` is a **key, not a label** (corrected 2026-09-24, #2083): when a token is
    already recorded for the derived node, this returns that stored token — so knowing
    someone's `client_id` is enough to be handed their token. Generate a random UUID and
    store it the way you store a token; do not derive it from a hostname, a workspace id,
    or anything else already public.
    """
    import secrets
    from datetime import datetime, timezone

    agent_type = args.get("agent_type", "unknown")
    client_id = args.get("client_id")
    client_id = client_id.strip() if isinstance(client_id, str) else ""
    if client_id and not CLIENT_ID_RE.match(client_id):
        return dict(_INVALID_CLIENT_ID)

    reused = False
    if client_id:
        node_id = _node_id_for_client(client_id)
        known_token = _registered_tokens().get(node_id)
        token = known_token or f"mcp_{secrets.token_urlsafe(24)}"
        reused = known_token is not None
    else:
        # Generate deterministic node_id from agent_type + random suffix
        suffix = secrets.token_hex(3).upper()
        node_id = f"Misaka{int(suffix, 16) % 100000:05d}"
        token = f"mcp_{secrets.token_urlsafe(24)}"

    registered_at = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    # Persist registration to usage_meter (also the client_id → token mapping this
    # server reads back on the next call with the same client_id).
    _save_registration({
        "user": f"token:{token}",
        "action": "register",
        "node_id": node_id,
        "agent_type": agent_type,
        "token": token,
        "client_id": client_id,
        "ts": registered_at,
    })

    result = {
        "node_id": node_id,
        "token": token,
        "registered_at": registered_at,
        "agent_type": agent_type,
    }
    if reused:
        result["reused"] = True
    return result
