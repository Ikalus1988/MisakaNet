"""`python -m misakanet.mcp_server` — the same stdio server under the name the MCP registry expects.

Two module paths for one server is one too many, and this one exists only so a client or a listing
that was written against the old name keeps working: the canonical entry is `misakanet.server`
(`python -m misakanet.server`). Both are thin wrappers over `misakanet.server.main`, so there is no
behaviour to drift.
"""
from __future__ import annotations

from misakanet.server import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
