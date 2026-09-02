"""MisakaNet MCP Server package.

Usage:
    # As MCP server (stdio transport)
    python3 scripts/mcp_server.py

    # Import for testing
    from misakanet.server.protocol import handle_request
"""
from __future__ import annotations

from .protocol import handle_request, main
from .tools import TOOLS

__all__ = ["handle_request", "main", "TOOLS"]
