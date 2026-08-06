# Remote MCP Journey Report — 2026-08-05

## 测试环境
- 客户端: Cursor / Claude Desktop / curl
- 系统: Linux (Ubuntu 24.04 LTS)
- 时间: 2026-08-05 14:30

## 步骤与结果

### 1. 发现端点
- 入口: GitHub README & Glama Listing (glama.json)
- 结果: ✅
- 卡点: 无。端点 URL https://misakanet.org/mcp 在 glama.json 和 README 中明确标出。

### 2. 理解认证
- 结果: ✅
- 卡点: 公开只读端点无需 Bearer Token 即可完成 initialize 和 tools/call 查询。建议在 README 或 MCP 接入文档中明确标注 public read 不需要 Authorization header。

### 3. 配置客户端
- 配置方式: URL config (streamable-http) / curl JSON-RPC
- 结果: ✅
- 卡点: 无。Cursor/Claude Desktop 中使用 Streamable HTTP 协议直接填入 https://misakanet.org/mcp 即可识别。

### 4. initialize
- 请求: {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "curl-client", "version": "1.0.0"}}}
- 响应: {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "io.github.Ikalus1988/misakanet", "version": "2.15.0"}}}
- 结果: ✅

### 5. tools/list
- 结果: ✅
- 工具数量: 2 (misakanet_search, misakanet_get_lesson)

### 6. tools/call (search)
- 查询: {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "misakanet_search", "arguments": {"query": "pip install timeout"}}}
- 结果: ✅
- 返回结果数: 3

## 卡点汇总

| 严重性 | 描述 | 建议修复 |
|--------|------|---------|
| 体验差 | 认证说明不够直观，用户不确定是否必须传入 Bearer token | 在 docs/mcp-quickstart 中补充说明 public remote endpoint 默认支持 unauthenticated read |
| 建议 | Glama 说明页缺少针对 Cursor 的 one-click copy JSON 配置示例 | 在 README 和 Glama 页面中增加 mcpServers JSON 粘贴块 |

## 总体评价

整体 Remote MCP 用户旅程非常顺畅，从发现 Endpoint 到完成 tools/call 仅需数秒，协议响应符合 MCP 2024-11-05 规范。