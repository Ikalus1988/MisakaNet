{"title": "MCP — AI Agent 工具调用标准化协议", "domain": "mcp", "subdomain": "standardization", "tags": ["mcp", "agent", "tool-calling", "standardization", "protocol"], "source": "segmentfault.com", "status": "published", "confidence": "0.85", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

AI Agent 调用外部工具时，每个 LLM 提供商的 function calling 格式不同，每个工具需要单独适配。工具越多，维护成本越高。

## Root Cause

没有标准化的 Agent↔工具 通信协议。类似 Web 早期没有 HTTP 标准。

## Solution

### MCP 协议架构

```
AI Agent (Claude/GPT/Gemini)
    ↓ MCP Client
MCP Protocol (JSON-RPC)
    ↓
MCP Server A (数据库)
MCP Server B (API)
MCP Server C (文件系统)
```

### 核心概念

| 概念 | 说明 | 类比 |
|------|------|------|
| MCP Server | 暴露工具的服务 | REST API 服务器 |
| MCP Client | 调用工具的 Agent | HTTP 客户端 |
| Tool | 可调用的函数 | API 端点 |
| Resource | 可读取的数据 | GET 端点 |

### 实现示例

```python
# MCP Server（工具提供方）
from mcp import Server, Tool

server = Server("my-db-tools")

@server.tool("query_database")
async def query_database(sql: str) -> list:
    """Execute a SQL query."""
    return await db.execute(sql)

@server.tool("get_schema")
async def get_schema(table: str) -> dict:
    """Get table schema."""
    return await db.get_schema(table)

# MCP Client（Agent 端）
from mcp import Client

client = Client("my-db-tools")
result = await client.call_tool("query_database", {
    "sql": "SELECT * FROM users LIMIT 10"
})
```

### 与 Function Calling 对比

| 特性 | Function Calling | MCP |
|------|-----------------|-----|
| 标准化 | 各厂商不同 | 统一协议 |
| 工具发现 | 手动配置 | 自动发现 |
| 跨模型 | 不兼容 | 兼容 |
| 生态 | 封闭 | 开放 |

## Verification

1. 创建 MCP Server，暴露 2 个工具
2. 用 Claude Code 连接
3. Agent 自动发现并调用工具
4. 换用 Cursor 连接同一 Server → 同样工作

## Notes

- MCP 最重要的价值：工具提供方与应用研发者解耦
- 类似 Web 前后端分离的范式转移
- Source: segmentfault.com (2026-03-13)
