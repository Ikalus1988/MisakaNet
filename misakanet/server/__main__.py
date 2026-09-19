"""`python -m misakanet.server` — the stdio MCP server, as an installed package module.

`scripts/mcp_server.py` is the same server, but as a *repo-checkout* script: it inserts `REPO_ROOT`
on `sys.path` first and re-exports the internals so tests can reach them. That path does not exist
after `pip install misakanet` — `scripts/` is not in the wheel — which is why `server.json`'s
`runtime.args = ["scripts/mcp_server.py"]` could never start a pip-installed server (2026-09-18
review, 意见 11/12). This module is the entry that *does* exist in the wheel, and it needs no path
surgery: `misakanet.server` is a package member.
"""
from __future__ import annotations

from misakanet.server import main

if __name__ == "__main__":
    raise SystemExit(main())
