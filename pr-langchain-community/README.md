# PR: Add MisakaNetSearchTool to langchain-community

## Summary

Add a `MisakaNetSearchTool` — a LangChain `BaseTool` that wraps
[MisakaNet](https://github.com/Ikalus1988/MisakaNet), a zero-dependency,
git-backed offline library of verified debugging lessons for AI agents.

LLM agents can use this tool to instantly search an offline knowledge base
of environment-specific fixes (pip timeout, WSL path corruption, ChromaDB
NTFS crashes, etc.) without network calls or sandbox escape.

## Files to Create

### New: `libs/community/langchain_community/tools/misakanet/__init__.py`

```python
from langchain_community.tools.misakanet.tool import (
    MisakaNetSearchTool,
    MisakaNetSearchInput,
)
__all__ = ["MisakaNetSearchTool", "MisakaNetSearchInput"]
```

### New: `libs/community/langchain_community/tools/misakanet/tool.py`

Standalone `BaseTool` subclass (see file in this directory).  Thin wrapper
over the `misakanet` package's BM25 search engine.

## Files to Modify

### `libs/community/langchain_community/tools/__init__.py`

Add to exports:

```python
from langchain_community.tools.misakanet import (
    MisakaNetSearchTool as MisakaNetSearchTool,
    MisakaNetSearchInput as MisakaNetSearchInput,
)
```

## External Dependency

The tool imports from the `misakanet` package at runtime:

```bash
pip install 'misakanet[langchain]'
```

This dependency is optional — the tool raises a clear `ImportError` if
`misakanet` is not installed.

## Smoke Test

```python
from langchain_community.tools.misakanet import MisakaNetSearchTool

tool = MisakaNetSearchTool()
print(tool.run("pip install timeout on WSL"))
# → 5 matching lessons with scores, filepaths, and previews
```

## Review Notes

- **Scope**: The tool wraps only the search functionality (read-only).
  Lesson contribution remains a separate CLI workflow.
- **Security**: The underlying BM25 search is pure Python, no network,
  no shell execution, no dynamic imports.
- **Dependencies**: `misakanet` itself has zero runtime deps (stdlib only).
  `misakanet[langchain]` adds `langchain-core` and `pydantic`.
