# MisakaNet LlamaIndex Integration

Search MisakaNet failure memory from LlamaIndex agents and query engines.

## Installation

```bash
pip install llama-index-core
```

## Quick Start

```python
from integrations.llamaindex.misakanet_tool import misakanet_search

# Direct function call
result = misakanet_search("TypeErrCannot read property of undefined")
print(result)
```

## With LlamaIndex Agent

```python
from llama_index.core.agent import ReActAgent
from llama_index.llms.openai import OpenAI
from integrations.llamaindex.misakanet_tool import get_misakanet_tool

# Create tool and LLM
tool = get_misakanet_tool()
llm = OpenAI(model="gpt-4")

# Create agent with MisakaNet tool
agent = ReActAgent.from_tools([tool], llm=llm, verbose=True)

# Agent will search MisakaNet when encountering errors
response = agent.chat("Fix this error: CUDA out of memory")
print(response)
```

## Module-Level Tool Instance

```python
from integrations.llamaindex.misakanet_tool import misakanet_search_tool

if misakanet_search_tool:
    # Tool is ready to use
    result = misakanet_search_tool("npm ERESOLVE dependency conflict")
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `MISAKANET_SEARCH_URL` | Search API endpoint | `https://misakanet.dev/api/search` |
| `MISAKANET_API_KEY` | API key for authenticated requests | None |

### Programmatic Configuration

```python
from integrations.llamaindex.misakanet_tool import misakanet_search

result = misakanet_search(
    query="Docker permission denied",
    endpoint="http://localhost:8000/api/search",
    api_key="your-api-key",
    max_results=5,
)
```

## API Reference

### `misakanet_search(query, max_results=3, endpoint=None, api_key=None)`

Search MisakaNet for failure lessons matching the query.

**Parameters:**
- `query` (str): Error description or failure pattern
- `max_results` (int): Max results to return (1-10, default: 3)
- `endpoint` (str, optional): Custom search endpoint URL
- `api_key` (str, optional): API key for authenticated requests

**Returns:** Formatted string with matching lessons and solutions.

### `get_misakanet_tool()`

Create a LlamaIndex `FunctionTool` for MisakaNet search.

**Returns:** `FunctionTool` instance ready for use with LlamaIndex agents.

**Raises:** `ImportError` if llama_index is not installed.

## Related Issues

- Implements #1178
