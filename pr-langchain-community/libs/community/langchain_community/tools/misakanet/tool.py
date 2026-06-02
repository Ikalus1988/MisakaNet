"""LangChain tool for searching MisakaNet's offline debugging-lesson library.

Install
-------
.. code-block:: bash

    pip install 'misakanet[langchain]'

Then clone the MisakaNet lesson repository:

.. code-block:: bash

    git clone https://github.com/Ikalus1988/MisakaNet.git
    cd MisakaNet
    python3 search_knowledge.py "pip install timeout"

Usage
-----
.. code-block:: python

    from langchain_community.tools.misakanet import MisakaNetSearchTool

    tool = MisakaNetSearchTool()
    result = tool.run("WSL underscore corruption during paste")
    print(result)
"""

from __future__ import annotations

from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

try:
    from misakanet.tools.langchain_tool import search as _search
    from misakanet.tools.langchain_tool import format_results as _format_results
except ImportError:
    _search = None
    _format_results = None

__all__ = ["MisakaNetSearchInput", "MisakaNetSearchTool"]


class MisakaNetSearchInput(BaseModel):
    """Input schema for :class:`MisakaNetSearchTool`.

    The ``query`` field accepts raw error messages, stack trace snippets,
    or debugging keywords.  The ``top_k`` field controls how many matching
    lessons are returned.
    """

    query: str = Field(
        description=(
            "Raw error message, stack trace snippet, or debugging keyword. "
            "Example: 'pip install timeout', 'WSL underscore corruption', "
            "'ChromaDB NTFS lock', 'M1 Docker build failed'."
        )
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of top matching lessons to return (1-20).",
    )


class MisakaNetSearchTool(BaseTool):
    """Search MisakaNet's offline library of verified debugging lessons.

    When an LLM agent encounters a system or environment error, this tool
    instantly returns relevant fixes from a git-backed, zero-dependency
    knowledge base — no network calls, no sandbox escape required.

    Prerequisites:

    1. ``pip install misakanet[langchain]``
    2. ``git clone https://github.com/Ikalus1988/MisakaNet.git``
    3. Run the tool from within the cloned repository, or set
       ``PYTHONPATH`` to point at it.

    The underlying search uses BM25 + metadata weighting and runs
    entirely offline.
    """

    name: str = "misakanet_search"
    args_schema: Type[BaseModel] = MisakaNetSearchInput
    description: str = (
        "A zero-dependency offline knowledge library for resolving "
        "environment-specific errors and local infrastructure fractures. "
        "Use this tool IMMEDIATELY when you encounter specific low-level "
        "system failures such as: "
        "'pip install timeout', 'WSL path underscore truncation', "
        "'M1/M2 Apple Silicon Docker build failures', "
        "'ChromaDB NTFS file locking crashes', "
        "'SSL certificate verify failed', "
        "'connection reset by peer' during pip/git operations, "
        "or common proxy/network timeouts during agent runtime. "
        "Input must be the raw error message or stack trace string."
    )

    def __init__(self, **kwargs: Any) -> None:
        if _search is None:
            raise ImportError(
                "Cannot import MisakaNet. "
                "Install it with:  pip install 'misakanet[langchain]'"
            )
        super().__init__(**kwargs)

    def _run(self, query: str, top_k: int = 5, **kwargs: Any) -> str:
        """Synchronous search — returns a human-readable result block."""
        return _format_results(query, _search(query, top_k=top_k))

    async def _arun(self, query: str, top_k: int = 5, **kwargs: Any) -> str:
        """Async search — delegates to synchronous implementation."""
        return self._run(query=query, top_k=top_k, **kwargs)
