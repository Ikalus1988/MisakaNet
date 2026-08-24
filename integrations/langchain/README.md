# MisakaNet LangChain Integration

Search MisakaNet failure memory from LangChain agents and chains.

## Installation

```bash
pip install langchain
# No additional dependencies needed - uses stdlib only
```

## Quick Start

```python
from integrations.langchain.misakanet_tool import MisakaNetSearchTool

# Create the tool
tool = MisakaNetSearchTool()

# Use directly
result = tool.run("TypeErrCannot read property of undefined")
print(result)
```

## With LangChain Agent

```python
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from integrations.langchain.misakanet_tool import MisakaNetSearchTool

# Initialize tool and LLM
tool = MisakaNetSearchTool()
llm = ChatOpenAI(model="gpt-4")

# Create agent with MisakaNet tool
agent = create_react_agent(llm, [tool], prompt)
executor = AgentExecutor(agent=agent, tools=[tool])

# Agent will automatically search MisakaNet when encountering errors
result = executor.invoke({"input": "Fix this Docker build error: permission denied"})
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `MISAKANET_SEARCH_URL` | Search API endpoint | `https://misakanet.dev/api/search` |
| `MISAKANET_MCP_URL` | MCP protocol endpoint | `https://misakanet.dev/mcp` |
| `MISAKANET_API_KEY` | API key for authenticated requests | None |

### Programmatic Configuration

```python
tool = MisakaNetSearchTool(
    endpoint="http://localhost:8000/api/search",
    use_mcp=True,  # Use MCP protocol instead of REST
    api_key="your-api-key",
)
```

## MCP Protocol Support

For MCP-compatible environments:

```python
tool = MisakaNetSearchTool(use_mcp=True)
result = tool.run("Docker permission denied")
```

## API Reference

### `MisakaNetSearchTool`

LangChain `BaseTool` subclass for MisakaNet search.

**Parameters:**
- `query` (str): Error description or failure pattern
- `max_results` (int): Max results to return (1-10, default: 3)

**Returns:** Formatted string with matching lessons and solutions.

### `get_misakanet_tool(**kwargs)`

Convenience function to create a configured tool instance.

## Related Issues

- Implements #1178
