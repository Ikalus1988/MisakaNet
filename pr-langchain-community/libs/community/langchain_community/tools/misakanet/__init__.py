"""MisakaNet Search Tool.

MisakaNet is a zero-dependency, git-backed offline library of
verified debugging lessons for AI agents and developers.

The tool wraps the ``misakanet`` package's BM25 search engine,
allowing any LangChain agent to instantly search an offline
knowledge base of environment-specific fixes without network calls.
"""

from langchain_community.tools.misakanet.tool import MisakaNetSearchTool, MisakaNetSearchInput

__all__ = ["MisakaNetSearchTool", "MisakaNetSearchInput"]
