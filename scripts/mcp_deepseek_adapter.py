#!/usr/bin/env python3
"""MisakaNet MCP Adapter for DeepSeekHarness.

Bridges MisakaNet's failure-memory tools to DeepSeekHarness's recovery contract.
This is a thin naming layer — all logic delegates to the existing MCP server.

Usage:
    # As MCP server (stdio transport)
    python3 scripts/mcp_deepseek_adapter.py

    # In DeepSeekHarness config:
    {
      "mcpServers": {
        "misakanet-recovery": {
          "command": "python3",
          "args": ["scripts/mcp_deepseek_adapter.py"]
        }
      }
    }

Tool mapping:
    misakanet.search          -> deepseek.recovery.search
    misakanet.get_lesson      -> deepseek.recovery.get_lesson
    misakanet.submit_usage    -> deepseek.recovery.submit_feedback
    misakanet.usage_status    -> deepseek.recovery.status
    (new)                     -> deepseek.recovery.doctor
    (new)                     -> deepseek.recovery.smoke
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADAPTER_VERSION = "1.0.1"

# ── Import existing MCP handlers ──────────────────────────────────
sys.path.insert(0, str(REPO_ROOT))
from scripts.mcp_server import (
    handle_search,
    handle_get_lesson,
    handle_submit_usage,
    handle_usage_status,
    get_server_version,
)

# ── DeepSeekHarness-compatible tool definitions ───────────────────

TOOLS = [
    {
        "name": "deepseek.recovery.search",
        "description": (
            "Search MisakaNet's failure-lesson index for recovery guidance. "
            "Use when an error, exception, or failure occurs and you need "
            "a documented fix from real engineering sessions. "
            "Input: query (required), domain (optional), top (optional). "
            "Output: ranked lesson summaries with path, title, score."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Error message, keyword, or topic to search for",
                },
                "domain": {
                    "type": "string",
                    "description": "Optional domain filter (devops, python, rag, mcp, etc.)",
                },
                "top": {
                    "type": "integer",
                    "description": "Max results to return (default 5)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "deepseek.recovery.get_lesson",
        "description": (
            "Fetch a specific failure-recovery lesson by ID or path. "
            "Use after deepseek.recovery.search returns a match. "
            "Input: id or path (one required). "
            "Output: lesson content in markdown, truncated to 5000 chars."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Lesson ID (filename without .md)",
                },
                "path": {
                    "type": "string",
                    "description": "Lesson path relative to repo root",
                },
            },
        },
    },
    {
        "name": "deepseek.recovery.submit_feedback",
        "description": (
            "Record that a lesson helped with a failure. "
            "Use after applying a fix from a lesson. "
            "Input: lesson_id (required), outcome (solved/partial/not-helpful). "
            "Output: confirmation with lesson_id and status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {
                    "type": "string",
                    "description": "ID of the lesson that helped",
                },
                "outcome": {
                    "type": "string",
                    "enum": ["solved", "partial", "not-helpful"],
                    "description": "Outcome of applying the lesson",
                },
                "tool": {
                    "type": "string",
                    "description": "Calling tool name (default: deepseek-harness)",
                },
            },
            "required": ["lesson_id", "outcome"],
        },
    },
    {
        "name": "deepseek.recovery.status",
        "description": (
            "Check MisakaNet recovery plugin status. "
            "Shows available lessons, search engine health, and usage quota. "
            "Input: none required. "
            "Output: status with lesson count, engine type, and quota."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "deepseek.recovery.doctor",
        "description": (
            "Health check for the MisakaNet recovery plugin. "
            "Verifies: data files exist, search engine is built, "
            "MCP server is reachable. "
            "Input: none required. "
            "Output: health status with checks and recommendations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "deepseek.recovery.smoke",
        "description": (
            "Minimal smoke test: runs a search and lesson fetch. "
            "Use to verify the plugin works end-to-end. "
            "Input: none required. "
            "Output: pass/fail with timing and result counts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

# ── Handler implementations ───────────────────────────────────────

def handle_deepseek_search(args: dict) -> dict:
    """Delegate to misakanet.search with DeepSeekHarness naming."""
    try:
        result = handle_search(args)
    except Exception as e:
        # SAG-Lite FTS may fail on SQLite keywords (e.g. "off", "and")
        # Fall back to empty result with error info
        result = {
            "results": [],
            "source": "error",
            "error": str(e),
            "hint": "Search engine error — try a different query or rebuild index",
        }
    # Remap voice field for harness compatibility
    if "voice" in result:
        result["harness_voice"] = result.pop("voice")
    return result

def handle_deepseek_get_lesson(args: dict) -> dict:
    """Delegate to misakanet.get_lesson."""
    # Map id/path to misakanet format
    misakanet_args = {}
    if "id" in args:
        misakanet_args["id"] = args["id"]
    if "path" in args:
        misakanet_args["path"] = args["path"]
    return handle_get_lesson(misakanet_args)

def handle_deepseek_submit_feedback(args: dict) -> dict:
    """Delegate to misakanet.submit_usage with harness naming."""
    misakanet_args = {
        "lesson_id": args.get("lesson_id", ""),
        "tool": args.get("tool", "deepseek-harness"),
        "outcome": args.get("outcome", "partial")  # Default to partial if not specified
    }
    return handle_submit_usage(misakanet_args)

def handle_deepseek_status(args: dict) -> dict:
    """Return plugin status information."""
    from scripts.misakanet_cli import cmd_doctor
    status = cmd_doctor()

    return {
        "plugin": "misakanet-recovery",
        "version": ADAPTER_VERSION,
        "overall": status["overall"],
        "lesson_count": next(
            (c["count"] for c in status["checks"] if c["name"] == "lessons.json"),
            0
        ),
        "search_engine": next(