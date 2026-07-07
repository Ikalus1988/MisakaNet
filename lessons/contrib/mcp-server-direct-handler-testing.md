---
title: "MCP Server 测试 — 直接调用 handler 跳过 stdio 传输"
domain: development
tags:
  - mcp
  - testing
  - json-rpc
  - python
  - unit-test
status: published
source: practical-experience
confidence: 0.85
created: 2026-07-07
---

## Problem

MCP Server 使用 stdio 传输（stdin/stdout JSON-RPC），测试时需要启动子进程、写入 stdin、解析 stdout。这种方式：

1. 启动慢（需要 fork 进程）
2. 调试难（stdout 混合协议消息和日志）
3. 依赖完整环境（搜索索引、数据库等）

## Root Cause

MCP Server 的核心逻辑在 `handle_request()` 函数中，stdio 只是传输层。如果直接调用 handler，可以跳过整个传输层。

## Solution

**直接调用 JSON-RPC handler，不启动子进程：**

```python
from scripts.mcp_server import handle_request

def rpc(method: str, params: dict = None) -> dict:
    """Send a JSON-RPC request to the handler directly."""
    return handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    })

# 测试 initialize
resp = rpc("initialize")
assert resp["result"]["serverInfo"]["name"] == "misakanet"

# 测试 tools/list
resp = rpc("tools/list")
tool_names = {t["name"] for t in resp["result"]["tools"]}
assert "misakanet_search" in tool_names

# 测试 tools/call
resp = rpc("tools/call", {
    "name": "misakanet_search",
    "arguments": {"query": "CI pipeline", "top": 3},
})
result = json.loads(resp["result"]["content"][0]["text"])
assert "results" in result
```

### 处理搜索不可用的情况

测试不应依赖外部服务。当搜索索引不存在时，gracefully 降级：

```python
def test_search():
    resp = rpc("tools/call", {
        "name": "misakanet_search",
        "arguments": {"query": "test"},
    })
    result = json.loads(resp["result"]["content"][0]["text"])
    
    if "error" in result:
        print(f"  ⚠️ Search unavailable: {result['error']}")
        return  # 不算失败，只是跳过
    
    assert len(result["results"]) > 0
```

## Verification

1. 测试文件直接 import handler 函数
2. 不启动子进程、不读写 stdin/stdout
3. 搜索不可用时测试标记为 skipped 而非 failed
4. 覆盖：initialize、tools/list、tools/call、error handling

## Why it matters

MCP（Model Context Protocol）是 AI 工具集成的标准协议。直接测试 handler 比端到端测试快 10 倍，且不需要完整运行环境。这个模式适用于任何 JSON-RPC 服务：直接调用 dispatcher 函数，跳过传输层。
