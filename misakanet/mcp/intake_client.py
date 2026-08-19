"""
misakanet.mcp.intake_client
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Lightweight Python client for the MisakaNet MCP remote intake endpoint.

Usage (search first, then submit if nothing matches)::

    from misakanet.mcp.intake_client import IntakeClient

    client = IntakeClient()

    # Step 1 — search existing lessons
    results = client.search("pip install SSL certificate error")
    if not results:
        # Step 2 — submit intake (no GitHub account required)
        response = client.submit_intake(
            kind="missing_lesson",
            problem="pip install fails with SSL: CERTIFICATE_VERIFY_FAILED on macOS",
            error="ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]",
            what_tried="pip install --trusted-host pypi.org ...",
            source="my-agent/1.0",
        )
        print(response)  # {"submitted": True, "intake_id": "issue-1234", ...}

The worker endpoint requires no authentication from the caller.
All sensitive data must be stripped before submitting.
"""

from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Literal, Optional

__all__ = [
    "IntakeClient",
    "IntakePayload",
    "validate_intake_payload",
    "build_jsonrpc_call",
]

MCP_ENDPOINT = "https://misakanet.org/mcp"
MCP_PROTOCOL_VERSION = "2025-06-18"

IntakeKind = Literal["missing_lesson", "stale_lesson", "domain_gap"]
VALID_KINDS: tuple[str, ...] = ("missing_lesson", "stale_lesson", "domain_gap")

MAX_FIELD_LEN = 1000
MAX_SOURCE_LEN = 80


# ── Payload dataclass (stdlib, no attrs/pydantic needed) ──────────────────


class IntakePayload:
    """Validated intake payload ready for submission."""

    __slots__ = (
        "kind", "problem", "error", "what_tried", "fix", "verification", "source"
    )

    def __init__(
        self,
        kind: IntakeKind,
        problem: str,
        *,
        error: str = "",
        what_tried: str = "",
        fix: str = "",
        verification: str = "",
        source: str = "python-intake-client",
    ) -> None:
        errors = validate_intake_payload(
            kind=kind,
            problem=problem,
            error=error,
            what_tried=what_tried,
            fix=fix,
            verification=verification,
            source=source,
        )
        if errors:
            raise ValueError(f"Invalid intake payload: {'; '.join(errors)}")
        self.kind = kind
        self.problem = _truncate(problem, MAX_FIELD_LEN)
        self.error = _truncate(error, MAX_FIELD_LEN)
        self.what_tried = _truncate(what_tried, MAX_FIELD_LEN)
        self.fix = _truncate(fix, MAX_FIELD_LEN)
        self.verification = _truncate(verification, MAX_FIELD_LEN)
        self.source = _truncate(source, MAX_SOURCE_LEN)

    def to_dict(self) -> Dict[str, str]:
        d: Dict[str, str] = {"kind": self.kind, "problem": self.problem}
        if self.error:
            d["error"] = self.error
        if self.what_tried:
            d["what_tried"] = self.what_tried
        if self.fix:
            d["fix"] = self.fix
        if self.verification:
            d["verification"] = self.verification
        if self.source:
            d["source"] = self.source
        return d


# ── Validation ────────────────────────────────────────────────────────────


def validate_intake_payload(
    kind: str,
    problem: str,
    error: str = "",
    what_tried: str = "",
    fix: str = "",
    verification: str = "",
    source: str = "",
) -> List[str]:
    """Validate an intake payload before submission.

    Returns a list of error strings. An empty list means the payload is valid.

    This mirrors the validation logic in ``workers/mcp-intake/index.js``.
    """
    errs: List[str] = []

    # kind
    if kind not in VALID_KINDS:
        errs.append(
            f"Invalid kind '{kind}'. Must be one of: {', '.join(VALID_KINDS)}"
        )

    # problem — required, min 10 chars
    if not problem or not isinstance(problem, str):
        errs.append("'problem' is required.")
    elif len(problem.strip()) < 10:
        errs.append("'problem' must be at least 10 characters.")
    elif len(problem) > MAX_FIELD_LEN:
        errs.append(f"'problem' must not exceed {MAX_FIELD_LEN} characters.")

    # Optional text fields — length checks only
    for fname, val in [
        ("error", error),
        ("what_tried", what_tried),
        ("fix", fix),
        ("verification", verification),
    ]:
        if val and len(val) > MAX_FIELD_LEN:
            errs.append(f"'{fname}' must not exceed {MAX_FIELD_LEN} characters.")

    # source — length only
    if source and len(source) > MAX_SOURCE_LEN:
        errs.append(f"'source' must not exceed {MAX_SOURCE_LEN} characters.")

    return errs


# ── JSON-RPC helpers ──────────────────────────────────────────────────────


def build_jsonrpc_call(method: str, params: Dict[str, Any], req_id: int = 1) -> bytes:
    """Build a JSON-RPC 2.0 POST body for an MCP tool call.

    >>> body = build_jsonrpc_call("tools/list", {})
    >>> import json; data = json.loads(body)
    >>> data["jsonrpc"]
    '2.0'
    >>> data["method"]
    'tools/list'
    """
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params,
    }
    return json.dumps(payload).encode("utf-8")


def _truncate(val: str, max_len: int) -> str:
    if not val:
        return ""
    return val[:max_len]


# ── HTTP client ───────────────────────────────────────────────────────────


class IntakeClient:
    """Simple HTTP client for the MisakaNet MCP remote endpoint.

    No external dependencies — uses urllib from the Python standard library.

    Args:
        endpoint: MCP endpoint URL (default: ``https://misakanet.org/mcp``)
        user_agent: User-Agent header sent with every request
        timeout: HTTP timeout in seconds
    """

    def __init__(
        self,
        endpoint: str = MCP_ENDPOINT,
        user_agent: str = "MisakaNet-Python-Client/1.0",
        timeout: int = 15,
    ) -> None:
        self.endpoint = endpoint
        self.user_agent = user_agent
        self.timeout = timeout

    def _post(self, body: bytes) -> Dict[str, Any]:
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Origin": "https://claude.ai",
                "User-Agent": self.user_agent,
                "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
        return json.loads(raw)

    def search(self, query: str, top: int = 5) -> List[Dict[str, Any]]:
        """Search MisakaNet lessons.

        Returns a list of lesson dicts, or an empty list if none found.
        """
        body = build_jsonrpc_call(
            "tools/call",
            {
                "name": "misakanet_search",
                "arguments": {"query": query, "top": top},
            },
        )
        resp = self._post(body)
        result = resp.get("result", {})
        content = result.get("content", [])
        text = content[0].get("text", "") if content else ""
        # Parse lesson list from text (lightweight, no regex needed for agent use)
        lines = [l for l in text.splitlines() if l.startswith("- [")]
        return [{"raw": l} for l in lines]

    def submit_intake(
        self,
        kind: IntakeKind,
        problem: str,
        *,
        error: str = "",
        what_tried: str = "",
        fix: str = "",
        verification: str = "",
        source: str = "python-intake-client",
    ) -> Dict[str, Any]:
        """Submit an intake report for a missing or stale lesson.

        Validates the payload locally before sending.

        Returns the parsed JSON-RPC result dict on success, raises on error.

        >>> # Dry-run payload validation without network I/O:
        >>> errors = validate_intake_payload("missing_lesson", "short")
        >>> "at least 10" in errors[0]
        True
        """
        payload = IntakePayload(
            kind=kind,
            problem=problem,
            error=error,
            what_tried=what_tried,
            fix=fix,
            verification=verification,
            source=source,
        )
        body = build_jsonrpc_call(
            "tools/call",
            {
                "name": "misakanet_submit_intake",
                "arguments": payload.to_dict(),
            },
        )
        resp = self._post(body)
        if "error" in resp:
            raise RuntimeError(
                f"MCP error {resp['error'].get('code')}: {resp['error'].get('message')}"
            )
        result = resp.get("result", {})
        return {
            "submitted": result.get("submitted", False),
            "intake_id": result.get("intake_id"),
            "status": result.get("status"),
            "issue_url": result.get("issue_url"),
        }
