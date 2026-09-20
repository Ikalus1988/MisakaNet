# GitHub Copilot 集成配方

> **状态：部分验证（Partial）**
>
> GitHub Copilot 是「一个名字、三种互不兼容的配置形状」。本文件按 surface 分节给出可直接粘贴的最小配置，并标注键名与路径的官方来源。
>
> ⚠️ **核心陷阱**：VS Code Copilot Chat 用的是 **`servers`** 键，而 Copilot CLI 与 github.com coding agent 用的是 **`mcpServers`** 键。把 `mcpServers` 抄进 VS Code 的 `mcp.json` 会**静默失效**——没有报错，server 就是不出现。

## 三种配置形状总览

| Surface | 键 | 位置 | 来源 |
|---|---|---|---|
| VS Code Copilot Chat | **`servers`**（不是 `mcpServers`） | `.vscode/mcp.json`（项目）/ 用户 profile 的 `mcp.json` | [VS Code MCP 文档](https://code.visualstudio.com/docs/copilot/chat/mcp-servers) |
| Copilot CLI | `mcpServers` | `~/.copilot/mcp-config.json`（用户）/ `.mcp.json` / `.github/mcp.json`（项目） | [Copilot CLI MCP 文档](https://docs.github.com/en/copilot/github-copilot-in-the-cli/using-model-context-protocol-in-copilot-cli) |
| github.com coding agent | `mcpServers` | 仓 Settings → Coding agent → MCP servers（无文件） | [Coding agent MCP 文档](https://docs.github.com/en/copilot/customizing-copilot/adding-mcp-servers-for-copilot-coding-agent) |

---

## 1. VS Code Copilot Chat

**键名：`servers`**（注意：不是 `mcpServers`）

### 项目级配置

文件：`.vscode/mcp.json`

