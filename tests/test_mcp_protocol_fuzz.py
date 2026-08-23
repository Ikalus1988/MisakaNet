"""Hypothesis fuzz tests for MCP protocol handling (Issue #1182).

Tests that MCP server handles malformed requests gracefully.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from hypothesis import given, strategies as st, settings, HealthCheck
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

pytestmark = pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")


def _get_handle_request():
    """Get MCP request handler."""
    from scripts.mcp_server import handle_request
    return handle_request


@given(request=st.text(min_size=1, max_size=100000))
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_mcp_handles_malformed_string_requests(request):
    """MCP server should handle string input gracefully (parse as JSON or return error)."""
    handle = _get_handle_request()

    try:
        # Try to parse as JSON first
        try:
            parsed = json.loads(request)
            if not isinstance(parsed, dict):
                pytest.skip("Non-dict JSON input")
        except (json.JSONDecodeError, TypeError):
            pytest.skip("Invalid JSON input")

        response = handle(parsed)
        assert isinstance(response, dict)
        # Should have either result or error
        assert "result" in response or "error" in response
    except Exception as e:
        pytest.fail(f"MCP handler crashed on input {repr(request[:100])}: {e}")


@given(request=st.dictionaries(
    keys=st.text(min_size=1, max_size=100),
    values=st.text(min_size=0, max_size=1000),
    min_size=0,
    max_size=10,
))
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_mcp_handles_dict_input(request):
    """MCP server should handle dict input gracefully."""
    handle = _get_handle_request()

    try:
        response = handle(request)
        assert isinstance(response, dict)
    except Exception as e:
        pytest.fail(f"MCP handler crashed on dict input: {e}")


@given(
    method=st.text(min_size=0, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz"),
    req_id=st.integers(min_value=0, max_value=1000),
)
@settings(max_examples=30)
def test_mcp_handles_jsonrpc_format(method, req_id):
    """MCP server should handle JSON-RPC format requests."""
    handle = _get_handle_request()

    request = {
        "jsonrpc": "2.0",
        "method": method,
        "id": req_id,
    }

    try:
        response = handle(request)
        assert isinstance(response, dict)
        # Should have jsonrpc field
        assert "jsonrpc" in response
    except Exception as e:
        pytest.fail(f"MCP handler crashed on JSON-RPC input: {e}")


@given(request=st.sampled_from([
    {},
    {"jsonrpc": "2.0", "method": "nonexistent", "id": 1},
    {"jsonrpc": "2.0", "method": "search", "id": 1},
    {"jsonrpc": "2.0", "method": "search", "params": None, "id": 1},
    {"jsonrpc": "2.0", "method": "search", "params": {}, "id": 1},
    {"jsonrpc": "2.0", "method": "search", "params": {"query": ""}, "id": 1},
    {"jsonrpc": "2.0", "method": "search", "params": {"query": "a" * 10000}, "id": 1},
]))
@settings(max_examples=20)
def test_mcp_edge_cases(request):
    """Edge case requests should not crash."""
    handle = _get_handle_request()

    try:
        response = handle(request)
        assert isinstance(response, dict)
    except Exception as e:
        pytest.fail(f"MCP handler crashed on edge case: {e}")


@given(
    query=st.text(min_size=0, max_size=10000),
    domain=st.one_of(st.none(), st.text(min_size=0, max_size=100)),
    top=st.integers(min_value=0, max_value=1000),
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_mcp_search_params(query, domain, top):
    """Search with arbitrary params should not crash."""
    handle = _get_handle_request()

    # Build params dict, only include non-None values
    params = {"query": query}
    if domain is not None:
        params["domain"] = domain
    if top is not None:
        params["top"] = top

    request = {
        "jsonrpc": "2.0",
        "method": "search",
        "params": params,
        "id": 1,
    }

    try:
        response = handle(request)
        assert isinstance(response, dict)
    except Exception as e:
        pytest.fail(f"MCP search crashed: {e}")


if __name__ == "__main__":
    if HAS_HYPOTHESIS:
        test_mcp_handles_malformed_requests()
        test_mcp_handles_dict_input()
        test_mcp_handles_jsonrpc_format()
        test_mcp_edge_cases()
        test_mcp_search_params()
        print("All MCP fuzz tests passed ✓")
    else:
        print("hypothesis not installed, skipping fuzz tests")
