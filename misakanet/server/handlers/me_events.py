"""`misakanet_me_events` on the local stdio server — a proxy, and why it has to be one.

Why this file exists (2026-09-30, owner decision D4=A; intake #2000 / #2486)
--------------------------------------------------------------------------
The local stdio server had no `misakanet_me_events` while the hosted endpoint did, so the skill's
own reuse-evidence step — the one flow that asks an agent to verify its contribution was reused —
answered `Unknown tool: misakanet_me_events` on a local install. Neither tool set contained the
other.

The evidence the tool returns (helpful votes, regression-benchmark citations, cross-node
confirmation) is aggregated by the worker against its KV store and
`data/regression_queries.json`, so a checkout *cannot* compute it locally: it is a read of the
caller's reuse evidence **from the hosted service**. This handler is that read, using the same MCP
JSON-RPC client the repo's CLI already uses (`misakanet/remote.py`) rather than a second,
hand-rolled POST.

Degradation is explicit, not silent and not a crash (2026-09-30)
----------------------------------------------------------------
With no network the handler returns `{error, code: "hosted_endpoint_unavailable", hint}` instead of
raising. Raising would become a JSON-RPC internal error (`protocol.main`) — diagnosable, but
returning `{events: []}` would be worse: it reads as "no reuse evidence", which is a *different and
false* claim from "the evidence could not be read".
"""
from __future__ import annotations

from misakanet import remote

# The hosted read is a couple of KV lookups plus one JSON fetch; 30s is the CLI default for a full
# search. Keep the proxy short so a black-holed connection fails this call, not the session.
_TIMEOUT_SECONDS = 15.0

_TOOL = "misakanet_me_events"


def handle_me_events(args: dict) -> dict:
    """Proxy `misakanet_me_events` to the hosted endpoint.

    Argument validation mirrors the worker's definition (`minProperties: 1`): at least one of
    `lesson_id` / `lesson_path`, the latter accepted because the endpoint derives the id from the
    path the same way. An empty reference is refused before spending a network round-trip — and the
    hosted server would answer the same error anyway.
    """
    lesson_id = str(args.get("lesson_id") or "").strip()
    lesson_path = str(args.get("lesson_path") or "").strip()
    if not lesson_id and not lesson_path:
        return {
            "error": "lesson_id or lesson_path is required",
            "code": "missing_lesson_reference",
            "hint": (
                "Pass lesson_id (the filename stem, e.g. 'dco-auto-fix-workflow') or lesson_path "
                "(e.g. 'lessons/core/dco-auto-fix-workflow.md')."
            ),
        }

    payload: dict[str, str] = {}
    if lesson_id:
        payload["lesson_id"] = lesson_id
    if lesson_path:
        payload["lesson_path"] = lesson_path

    try:
        return remote.call(_TOOL, payload, timeout=_TIMEOUT_SECONDS)
    except remote.RemoteError as exc:
        # Honest offline answer. There is deliberately no local fallback: this evidence is
        # aggregated server-side, so "could not read it" must not look like "there is none".
        return {
            "error": str(exc),
            "code": "hosted_endpoint_unavailable",
            "tool": _TOOL,
            "hint": (
                f"{_TOOL} reads reuse evidence from the hosted endpoint ({remote.endpoint()}); a "
                "local stdio install has no local copy of it. Retry when the network is available."
            ),
        }
