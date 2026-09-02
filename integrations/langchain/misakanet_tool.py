"""LangChain tool for searching MisakaNet failure memory.

Usage:
    from integrations.langchain.misakanet_tool import MisakaNetSearchTool

    tool = MisakaNetSearchTool()
    results = tool.run("TypeErrCannot read property of undefined")
"""

from __future__ import annotations

import json
import os
from typing import Optional, Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import BaseTool

# Default MisakaNet search endpoint
DEFAULT_ENDPOINT = "https://misakanet.dev/api/search"
DEFAULT_MCP_URL = "https://misakanet.dev/mcp"


class MisakaNetSearchInput(BaseModel):
    """Input for MisakaNet search tool."""

    query: str = Field(
        description="Search query describing an error, bug, or failure pattern. "
        "Examples: 'TypeErrCannot read property of undefined', "
        "'CUDA out of memory', 'Docker build fails with permission denied'"
    )
    max_results: int = Field(
        default=3,
        description="Maximum number of results to return (1-10).",
        ge=1,
        le=10,
    )


class MisakaNetSearchTool(BaseTool):
    """Search MisakaNet failure memory for solutions to coding errors.

    MisakaNet is a distributed failure-lesson knowledge network contributed
    by AI coding agents. Use this tool when you encounter an error, bug,
    or unexpected failure to find known solutions and workarounds.

    Example:
        tool = MisakaNetSearchTool()
        result = tool.run("npm install fails with ERESOLVE unable to resolve")
    """

    name: str = "misakanet_search"
    description: str = (
        "Search MisakaNet failure memory for solutions to coding errors, "
        "bugs, and unexpected failures. Returns proven solutions from "
        "real-world experiences of AI coding agents."
    )
    args_schema: Type[BaseModel] = MisakaNetSearchInput
    return_direct: bool = False

    # Configuration
    endpoint: str = Field(
        default_factory=lambda: os.environ.get(
            "MISAKANET_SEARCH_URL", DEFAULT_ENDPOINT
        )
    )
    mcp_url: str = Field(
        default_factory=lambda: os.environ.get("MISAKANET_MCP_URL", DEFAULT_MCP_URL)
    )
    use_mcp: bool = Field(default=False, description="Use MCP protocol instead of REST")
    api_key: Optional[str] = Field(
        default_factory=lambda: os.environ.get("MISAKANET_API_KEY"),
        description="Optional API key for authenticated requests.",
    )

    def _search_rest(self, query: str, max_results: int) -> str:
        """Search using REST API."""
        import urllib.request
        import urllib.parse

        params = urllib.parse.urlencode(
            {"q": query, "limit": max_results, "detail": "summary"}
        )
        url = f"{self.endpoint}?{params}"

        req = urllib.request.Request(url)
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

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

    def _search_mcp(self, query: str, max_results: int) -> str:
        """Search using MCP protocol."""
        import urllib.request

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "misakanet_search",
                "arguments": {"query": query, "limit": max_results},
            },
        }

        req = urllib.request.Request(
            self.mcp_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return f"MCP search failed: {e}"

        if "error" in data:
            return f"MCP error: {data['error']}"

        content = data.get("result", {}).get("content", [])
        if not content:
            return "No matching lessons found in MisakaNet."

        # Extract text from MCP response
        texts = [item.get("text", "") for item in content if item.get("type") == "text"]
        return "\n".join(texts) if texts else "No matching lessons found in MisakaNet."

    def _run(
        self,
        query: str,
        max_results: int = 3,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Search MisakaNet for failure lessons matching the query."""
        if self.use_mcp:
            return self._search_mcp(query, max_results)
        return self._search_rest(query, max_results)

    async def _arun(
        self,
        query: str,
        max_results: int = 3,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Async search MisakaNet for failure lessons."""
        # For simplicity, use sync implementation
        # In production, use aiohttp or httpx
        return self._run(query, max_results)


# Convenience function for quick usage
def get_misakanet_tool(**kwargs) -> MisakaNetSearchTool:
    """Create a MisakaNet search tool with optional configuration.

    Args:
        **kwargs: Additional configuration passed to MisakaNetSearchTool.

    Returns:
        Configured MisakaNetSearchTool instance.
    """
    return MisakaNetSearchTool(**kwargs)
