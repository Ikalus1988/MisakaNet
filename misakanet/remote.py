"""Remote access to the MisakaNet endpoint — the path an *installed* package can use.

The in-package search engine (`misakanet/search/engine.py`) reads `lessons/` relative to a repo
checkout, so a wheel cannot search offline (there is no corpus in it). That is why the `misakanet` CLI
is remote-first: `pip install misakanet` + `misakanet "<error text>"` should work on a machine that has
never cloned anything (2026-09-18 review, 意见 1; #1821).

Zero dependencies on purpose, like the rest of the core: `urllib.request` from the standard library.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "https://misakanet.org/mcp"
PROTOCOL_VERSION = "2025-06-18"
# Anthropic's clients (and ours) send `Origin`; the endpoint only rejects a *wrong* value, but sending
# the documented one keeps this client identical to every example in the docs and to the installer.
ORIGIN = "https://misakanet.org"


class RemoteError(RuntimeError):
    """A remote call could not be completed. Carries the endpoint's own words when there were any."""


def endpoint() -> str:
    return (os.environ.get("MISAKANET_ENDPOINT") or DEFAULT_ENDPOINT).strip()


def call(tool: str, arguments: dict, *, token: str = "", timeout: float = 30.0,
         client_id: str = "", endpoint_url: str = "") -> dict:
    """One `tools/call`, returning the server's structured payload.

    `token` goes in the `Authorization` header only — never in the body (the endpoint deprecated
    `args.token`, and a token in a payload ends up in logs). `client_id`, when the user set one, is
    passed through as the stable key the endpoint documents (`AGENTS.md` §3.3): presenting it returns
    that node's token, so it is a **credential** (generate a random UUID, keep it private) — and
    without it the service has no way to keep one client's history together.
    """
    args = dict(arguments)
    if client_id:
        args.setdefault("client_id", client_id)
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Origin": ORIGIN,
        # Self-declared and optional: the endpoint records it as a hint, never as proof of identity.
        "User-Agent": f"misakanet-cli/{os.environ.get('MISAKANET_CLI_VERSION', 'dev')}",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(endpoint_url or endpoint(), data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:                       # 4xx/5xx with a body worth reading
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:300]
        except Exception:
            pass
        raise RemoteError(f"{endpoint()} answered HTTP {exc.code}{(' — ' + detail) if detail else ''}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RemoteError(f"{endpoint()} unreachable ({exc})") from exc

    if "error" in payload:
        raise RemoteError(str(payload["error"]))
    result = payload.get("result") or {}
    if isinstance(result.get("structuredContent"), (dict, list)):
        return result["structuredContent"]
    content = result.get("content")
    if isinstance(content, list) and content and isinstance(content[0], dict):
        text = content[0].get("text")
        if isinstance(text, str):
            try:
                return json.loads(text)
            except ValueError:
                return {"text": text}
    return result


def search(query: str, *, top: int = 5, token: str = "", client_id: str = "",
           endpoint_url: str = "") -> dict:
    """Search lessons by error text. Raises `RemoteError` — callers decide how to say so."""
    return call("misakanet_search", {"query": query, "top": top},
                token=token, client_id=client_id, endpoint_url=endpoint_url)
