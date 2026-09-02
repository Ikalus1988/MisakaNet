#!/usr/bin/env python3
"""MisakaNet MCP Server — thin CLI wrapper.

All logic lives in misakanet/server/. This file provides:
  1. CLI entry point (python3 scripts/mcp_server.py)
  2. Backward-compatible re-exports for tests and adapters

Usage:
    # As MCP server (stdio transport)
    python3 scripts/mcp_server.py

    # In Claude Code settings.json:
    {
      "mcpServers": {
        "misakanet": {
          "command": "python3",
          "args": ["scripts/mcp_server.py"]
        }
      }
    }
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on sys.path for scripts.* imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Re-export everything for backward compatibility
from misakanet.server import TOOLS, handle_request, main  # noqa: E402
from misakanet.server._config import (  # noqa: E402
    _init_search,
    get_server_version,
)
from misakanet.server.handlers import (  # noqa: E402
    handle_get_lesson,
    handle_memory_context,
    handle_preflight,
    handle_register,
    handle_search as _handle_search,
    handle_submit_intake,
    handle_submit_usage,
    handle_usage_status,
    handle_write_lesson,
)
from misakanet.server.handlers.search import (  # noqa: E402
    _apply_detail_level,
    _compact_result,
    _extract_problem_fix,
    _fallback_search,
    _freshness,
    _summary_result,
)
from misakanet.server.prompts import (  # noqa: E402
    PROMPTS,
    handle_prompts_get,
)
from misakanet.server.resources import (  # noqa: E402
    RESOURCES,
    handle_resources_list,
    handle_resources_read,
)
from misakanet.server.tools import _filtered_tools  # noqa: E402

# Expose search state for tests that monkeypatch
HAS_SAG, SAG_DB, HAS_BM25, sag_search = _init_search()


def handle_search(args: dict) -> dict:
    """Search through the package handler using compatibility search state."""
    return _handle_search(args, (HAS_SAG, SAG_DB, HAS_BM25, sag_search))

__all__ = [
    "TOOLS",
    "PROMPTS",
    "RESOURCES",
    "handle_request",
    "main",
    "get_server_version",
    "handle_search",
    "handle_get_lesson",
    "handle_submit_usage",
    "handle_submit_intake",
    "handle_write_lesson",
    "handle_preflight",
    "handle_usage_status",
    "handle_register",
    "handle_memory_context",
    "handle_resources_list",
    "handle_resources_read",
    "handle_prompts_get",
    "_filtered_tools",
    "_fallback_search",
    "_extract_problem_fix",
    "_compact_result",
    "_summary_result",
    "_freshness",
    "_apply_detail_level",
    "HAS_SAG",
    "SAG_DB",
    "HAS_BM25",
    "sag_search",
]

if __name__ == "__main__":
    main()
