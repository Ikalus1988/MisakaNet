"""LlamaIndex tool for searching MisakaNet failure memory.

Usage:
    from integrations.llamaindex.misakanet_tool import misakanet_search_tool

    # Use directly as a FunctionTool
    result = misakanet_search_tool("TypeErrCannot read property of undefined")
"""

from __future__ import annotations

import json
import os
from typing import Optional

# Default MisakaNet search endpoint
DEFAULT_ENDPOINT = "https://misakanet.dev/api/search"
DEFAULT_MCP_URL = "https://misakanet.dev/mcp"


def misakanet_search(
    query: str,
    max_results: int = 3,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Search MisakaNet failure memory for solutions to coding errors.

    MisakaNet is a distributed failure-lesson knowledge network contributed
    by AI coding agents. Use this function when you encounter an error, bug,
    or unexpected failure to find known solutions and workarounds.

    Args:
        query: Search query describing an error, bug, or failure pattern.
            Examples: "TypeErrCannot read property of undefined",
            "CUDA out of memory", "Docker build fails with permission denied"
        max_results: Maximum number of results to return (1-10). Default: 3.
        endpoint: Custom search endpoint URL. Defaults to MISAKANET_SEARCH_URL
            env var or https://misakanet.dev/api/search.
        api_key: Optional API key for authenticated requests. Defaults to
            MISAKANET_API_KEY env var.

    Returns:
        Formatted string with matching failure lessons and their solutions.

    Example:
        >>> result = misakanet_search("npm install ERESOLVE unable to resolve")
        >>> print(result)
        Found 2 relevant lessons:
        1. [dependency] npm ERESOLVE dependency conflict resolution...
    """
    import urllib.request
    import urllib.parse

    search_endpoint = endpoint or os.environ.get(
        "MISAKANET_SEARCH_URL", DEFAULT_ENDPOINT
    )
    key = api_key or os.environ.get("MISAKANET_API_KEY")

    # Clamp max_results to valid range
    max_results = max(1, min(10, max_results))

    params = urllib.parse.urlencode(
        {"q": query, "limit": max_results, "detail": "summary"}
    )
    url = f"{search_endpoint}?{params}"

    req = urllib.request.Request(url)
    if key:
        req.add_header("Authorization", f"Bearer {key}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return f"Search failed: {e}"

    if not data.get("results"):
        return "No matching lessons found in MisakaNet."

    lines = [f"Found {len(data['results'])} relevant lessons:\n"]
    for i, result in enumerate(data["results"], 1):
        score = result.get("score", 0)
        title = result.get("title", "Untitled")
        lesson_type = result.get("type", "unknown")
        lines.append(f"{i}. [{lesson_type}] {title} (relevance: {score:.2f})")

        # Include summary or problem if available
        if result.get("summary"):
            lines.append(f"   {result['summary']}")
        elif result.get("problem"):
            lines.append(f"   Problem: {result['problem']}")
        lines.append("")

    return "\n".join(lines)


def get_misakanet_tool():
    """Create a LlamaIndex FunctionTool for MisakaNet search.

    Returns:
        FunctionTool instance ready for use with LlamaIndex agents.

    Example:
        from llama_index.core.agent import ReActAgent
        from integrations.llamaindex.misakanet_tool import get_misakanet_tool

        tool = get_misakanet_tool()
        agent = ReActAgent.from_tools([tool], llm=llm)
        response = agent.chat("Fix this error: TypeErrCannot read property 'map' of undefined")
    """
    try:
        from llama_index.core.tools import FunctionTool
    except ImportError:
        raise ImportError(
            "llama_index is required for LlamaIndex integration. "
            "Install it with: pip install llama-index-core"
        )

    return FunctionTool.from_defaults(
        fn=misakanet_search,
        name="misakanet_search",
        description=(
            "Search MisakaNet failure memory for solutions to coding errors, "
            "bugs, and unexpected failures. Returns proven solutions from "
            "real-world experiences of AI coding agents. Use this tool when "
            "you encounter any error or unexpected behavior."
        ),
    )


# Module-level tool instance for convenience
try:
    misakanet_search_tool = get_misakanet_tool()
except ImportError:
    # llama_index not installed; tool will be created on first call
    misakanet_search_tool = None
