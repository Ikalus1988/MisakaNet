from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.mcp_preflight import evaluate_intent, RISK_PROFILES
from scripts.mcp_server import handle_request


def test_evaluate_intent_rag_build():
    result = evaluate_intent("build RAG index from 218 PDFs", "WSL, GPU 8GB VRAM")
    assert result["risk"] in ["high", "critical"]
    assert len(result["guards"]) > 0
    assert any("sample" in g.lower() for g in result["guards"])
    assert "probe" in result["recommendation"]


def test_evaluate_intent_wsl_gpu():
    result = evaluate_intent("run local inference on cuda with torch", "WSL2")
    assert result["risk"] in ["high", "critical"]
    assert any("wsl" in g.lower() or "vram" in g.lower() for g in result["guards"])


def test_evaluate_intent_bulk_import():
    result = evaluate_intent("unzip and bulk import 100+ files to database")
    assert result["risk"] in ["medium", "high", "critical"]
    assert any("chunk" in g.lower() or "manifest" in g.lower() or "count" in g.lower() for g in result["guards"])


def test_evaluate_intent_safe_action():
    result = evaluate_intent("read file readme.md and show summary")
    assert result["risk"] == "low"
    assert len(result["guards"]) == 0


def test_mcp_server_tools_list_contains_preflight():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    resp = handle_request(req)
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "misakanet_preflight" in tool_names


def test_mcp_server_tools_call_preflight():
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "misakanet_preflight",
            "arguments": {
                "intent": "build RAG index from 218 PDFs",
                "context": "WSL, GPU 8GB VRAM",
            },
        },
    }
    resp = handle_request(req)
    assert resp["id"] == 2
    content = resp["result"]["content"][0]["text"]
    data = json.loads(content)
    assert data["risk"] in ["high", "critical"]
    assert "guards" in data
    assert len(data["guards"]) > 0
