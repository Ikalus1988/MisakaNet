---
domain: "contrib"
title: "DeepSeek TUI — Feishu MCP Server Setup & Permission Boundaries"
verification: "metadata-normalized"
{"title": "DeepSeek TUI — Feishu MCP Server Setup & Permission Boundaries", "domain": "feishu", "source": "deepseek-tui", "status": "published", "tags": ["feishu", "mcp", "deepseek", "docx-api", "permissions"], "created": "2026-05-19", "updated": "2026-05-19", "domain_expert": "deepseek-tui", "verified_date": "2026-05-19"}
---

## 背景

需要在 DeepSeek TUI 中在线操作飞书云文档（docx），通过 MCP 协议暴露飞书 API。

## 关键发现

### 1. MCP Server 架构

```
飞书 MCP Server (Python FastMCP)
  ├─ stdio 协议 ↔ DeepSeek TUI (deepseek mcp add)
  ├─ docx API: 创建/读取/编辑云文档
  ├─ IM API: 发送消息、列出群聊、查询群名
  └─ WebSocket: 后台接收群消息（需事件订阅）
```

### 2. 凭证安全管理

飞书 App ID / App Secret 不应硬编码在 server.py 中，应通过 DeepSeek TUI 的 mcp.json env 字段注入：

```json
{
  "servers": {
    "feishu": {
      "command": ".venv/bin/python3",
      "args": ["server.py"],
      "env": {
        "FEISHU_APP_ID": "cli_xxxxx",
        "FEISHU_APP_SECRET": "xxxxxxxx"
      }
    }
  }
}
```

MCP Server 启动时读取环境变量，缺失则 fail-fast 退出。

### 3. 飞书 API 权限边界（重要）

飞书自建应用的权限按 scope 隔离，并非有 token 就能调：

| API 类别 | 可用 | 所需权限 |
|----------|------|----------|
| docx 云文档 | ✅ 创建/读取/编辑 | docx:document（默认自带） |
| IM 消息发送 | ✅ 发送到群/用户 | im:message（默认自带） |
| IM 群列表 | ✅ 列出群信息 | im:chat（默认自带） |
| 消息接收（WS） | ❌ 需事件订阅 | im.message.receive_v1 事件 |
| 消息历史查询 | ❌ 需额外权限 | im:message.group_msg |
| 云盘/文件 | ❌ 未开通 | drive:drive |
| Wiki 知识库 | ❌ 未开通 | wiki:wiki |
| 文档评论 | ❌ 未开通 | docs:document.comment:read |
| 联系人 | ❌ 未开通 | contact:contact.base:readonly |

**关键**: 即使 docx 创建 API 可用（code=0），读取其他用户创建的文档也可能返回 1770032 forBidden——需要文档所有者将机器人添加为协作者。

### 4. 飞书 Block API 特性

- PATCH 更新 block 内容可用（update_text_elements）
- DELETE block 接口返回 404（飞书 docx API 可能不支持直接删除）
- 替代方案：PATCH 将内容清空
- 批量追加 children 每批建议 ≤40 blocks
- 文档 revision_id 递增，需关注

### 5. DeepSeek TUI MCP 集成

```bash
deepseek mcp add feishu --command .venv/bin/python3 --arg server.py
deepseek mcp list        # 查看注册的 MCP 服务
```

MCP 配置保存在 `~/.deepseek/mcp.json`。

## 部署步骤

```bash
# DeepSeek TUI — Feishu MCP Server Setup & Permission Boundaries
mkdir -p .feishu-mcp-server && cd .feishu-mcp-server
uv init --name feishu-mcp-server
uv add mcp requests websocket-client

# 2. 编写 server.py (FastMCP + 飞书 API)

# 3. 注册到 DeepSeek TUI
deepseek mcp add feishu \
  --command .venv/bin/python3 \
  --arg server.py

# 4. 验证
deepseek mcp list
# 输出: feishu [enabled] ...
```

## 验证方式

```python
# 测试 MCP 工具列表
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        # → 应包含 create_document / get_document_content / send_message 等
```

## 已知限制

## Verification

1. Complete the MCP server setup and verify `FEISHU_*` env vars are picked up
2. Test `search_knowledge.py "feishu"` — confirm lessons are retrieved through the MCP bridge
3. Attempt to create a Feishu doc via the MCP server — confirm write permissions work
4. Try sheet and wiki operations — confirm they return an explicit "not supported" error

- 不支持 sheet（电子表格）和 wiki（知识库）
- 文档评论需要额外权限（docs:document.comment:read）
- 消息接收需要事件订阅配置 + 发布应用版本
