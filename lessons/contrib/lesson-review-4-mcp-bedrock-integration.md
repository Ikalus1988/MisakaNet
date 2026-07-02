{"title": "MCP 协议 + Bedrock 实战 — Agent 外部工具调用标准化", "domain": "mcp", "subdomain": "integration", "tags": ["mcp", "bedrock", "aws", "agent", "tool-calling", "standardization"], "source": "segmentfault.com", "status": "published", "confidence": "0.85", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

AI Agent 调用外部工具（S3、DynamoDB、内部 API）时，每个工具都要写 function calling schema 和调用逻辑。工具一多，维护成本很高，没有标准化方案。

## Root Cause

每个 LLM 提供商的 function calling 格式不同，工具提供方与应用研发者紧耦合。类似 Web 早期的前后端未分离。

## Solution

### MCP 协议核心思想

MCP 是一套让 Agent 连接外部资料和工具的通用方式，类似 USB-C 统一充电口：

```
Agent → MCP Client → MCP Server → 外部工具
         ↓
    标准化协议（JSON-RPC）
```

### Bedrock + MCP 集成步骤

```python
# 1. 定义 MCP Server（工具提供方）
from mcp import Server, Tool

server = Server("my-tools")

@server.tool("read_s3_file")
async def read_s3_file(bucket: str, key: str) -> str:
    """Read a file from S3."""
    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj['Body'].read().decode()

@server.tool("query_dynamodb")
async def query_dynamodb(table: str, key: str) -> dict:
    """Query DynamoDB by partition key."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table)
    return table.get_item(Key={'pk': key})['Item']

# 2. Agent 通过 MCP Client 调用
from mcp import Client

client = Client("my-tools", transport="stdio")
result = await client.call_tool("read_s3_file", {
    "bucket": "my-bucket",
    "key": "data.json"
})
```

### 前后端分离类比

| Web 时代 | Agent 时代 |
|----------|-----------|
| 前端（React/Vue） | Agent（Claude/GPT） |
| 后端 API（REST） | MCP Server |
| HTTP 协议 | MCP 协议（JSON-RPC） |
| 前后端解耦 | 工具提供方与应用研发者解耦 |

## Verification

1. 创建一个 MCP Server，暴露 2-3 个工具
2. 用 Claude Code 或 Cursor 连接该 MCP Server
3. Agent 能通过标准协议调用工具，无需修改 Agent 代码
4. 新增工具只需在 Server 端添加，Agent 自动发现

## Notes

- MCP 最重要的点：通过标准化协议，将工具提供方与应用研发者解耦
- 这将带来 AI Agent 应用研发范式的转移（类似 Web 前后端分离）
- Source: segmentfault.com (2026-03-13)
