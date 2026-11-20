"""Remote access to the MisakaNet endpoint — the path an *installed* package can use.

The in-package search engine (`misakanet/search/engine.py`) reads `lessons/` relative to a repo
checkout, so a wheel cannot search offline (there is no corpus in it). That is why the `misakanet` CLI
is remote-first: `pip install misakanet` + `misakanet "<error text>"` should work on a machine that has
never cloned anything (2026-09-18 review, 意见 1; #1821).

No third-party packages on purpose, like the rest of the core: `urllib.request` from the standard library.
"""
from __future__ import annotations

import http.client
import json
import os
import urllib.error
import urllib.request

from .mcp_reply import McpReplyUnreadable, McpRpcError, parse_mcp_reply

DEFAULT_ENDPOINT = "https://misakanet.org/mcp"
PROTOCOL_VERSION = "2025-06-18"
# Anthropic's clients (and ours) send `Origin`; the endpoint only rejects a *wrong* value, but sending
# the documented one keeps this client identical to every example in the docs and to the installer.
ORIGIN = "https://misakanet.org"


class RemoteError(RuntimeError):
    """A remote call could not be completed. Carries the endpoint's own words when there were any."""


class TruncatedReply(RemoteError):
    """A reply started arriving and then stopped early — the delivery was cut, not the body malformed.

    Why this is its own error (#5245). Production served a 200 that announced 13315 bytes and delivered
    605, and the client had no word for it: the short bytes reached `parse_mcp_reply`, which could only
    say "could not decode reply", so six intakes were triaged as *parse* failures when nothing had been
    mis-parsed. Measured afterwards (`scripts/probe_mcp_body.py`, 60 samples, zero short bodies), the
    endpoint is not the author — the bytes were cut between it and the caller.

    That distinction is the whole point, because the two have opposite handling: a malformed body means
    the endpoint is wrong and the next identical request reproduces it, while a cut delivery means the
    bytes that *were* sent never arrived and a retry usually succeeds. Carries `announced`/`received`
    so a caller (or a bug report) can state the discrepancy instead of guessing at it.
    """

    def __init__(self, *, endpoint: str, announced: int | None, received: int,
                 status: int | None = None, reason: str = "") -> None:
        self.endpoint = endpoint
        self.announced = announced
        self.received = received
        self.status = status
        self.reason = reason
        measured = (f"{received} of {announced} announced bytes" if announced is not None
                    else f"{received} bytes, with no announced length")
        super().__init__(
            f"{endpoint} answered HTTP {status if status is not None else 200} and delivered {measured}"
            f" — the reply was cut in transit, not malformed"
            + (f" ({reason})" if reason else "")
            + ". Retrying the same request is safe."
        )


def endpoint() -> str:
    return (os.environ.get("MISAKANET_ENDPOINT") or DEFAULT_ENDPOINT).strip()


def _announced_length(response) -> int | None:
    """The body size this response promised, or `None` when it promised none (chunked framing).

    Reached through `getattr`/`get` on purpose: an opener that is not `urllib`'s — a test double, a
    proxying handler — may have no `.headers`, and "made no promise" is the right reading of that. The
    header check is a second witness anyway; the transport's own short-read error is the first.
    """
    headers = getattr(response, "headers", None)
    value = headers.get("Content-Length") if headers is not None else None
    text = str(value).strip() if value is not None else ""
    return int(text) if text.isdigit() else None


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
    url = endpoint_url or endpoint()
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            announced = _announced_length(response)
            try:
                raw = response.read()
            except (http.client.IncompleteRead, OSError) as exc:
                # The answer had already started — status line and headers arrived, then the body
                # stopped. That is not "unreachable" (the endpoint answered) and not a parse failure
                # (there is nothing to parse), and calling it either one is how #5245 was mis-triaged.
                # `IncompleteRead` is named because it is what `urllib` raises when a declared length
                # or a chunked stream is unmet; a mid-body reset arrives as `OSError` instead.
                partial = getattr(exc, "partial", b"")
                expected = getattr(exc, "expected", None)
                raise TruncatedReply(
                    endpoint=url, status=status, received=len(partial),
                    announced=announced if announced is not None else (
                        len(partial) + expected if isinstance(expected, int) else None),
                    reason=f"{type(exc).__name__}: {exc}",
                ) from exc
    except urllib.error.HTTPError as exc:                       # 4xx/5xx with a body worth reading
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:300]
        except Exception:
            pass
        raise RemoteError(f"{endpoint()} answered HTTP {exc.code}{(' — ' + detail) if detail else ''}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RemoteError(f"{endpoint()} unreachable ({exc})") from exc

    # `Content-Length` is the response's own promise about its body, so one byte short of it is a cut
    # delivery even when the transport raised nothing — a proxy that closes cleanly after N bytes, or
    # an opener that hands back what it managed to read. Checked before decoding, because short bytes
    # reach the decoder as "could not decode reply" and that answer blames the wrong party (#5245).
    if announced is not None and len(raw) < announced:
        raise TruncatedReply(endpoint=url, status=status, announced=announced, received=len(raw))

    # One decoder for both frames (#3548). `Accept` here is JSON-only, but a caller may override it
    # and get SSE; decoding is not something each call site should re-derive.
    try:
        return parse_mcp_reply(raw, status=status, endpoint=endpoint_url or endpoint())
    except (McpReplyUnreadable, McpRpcError) as exc:
        raise RemoteError(str(exc)) from exc


def search(query: str, *, top: int = 5, token: str = "", client_id: str = "",
           endpoint_url: str = "") -> dict:
    """Search lessons by error text. Raises `RemoteError` — callers decide how to say so."""
    return call("misakanet_search", {"query": query, "top": top},
                token=token, client_id=client_id, endpoint_url=endpoint_url)
