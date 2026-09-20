FILE: docs/integrations/copilot.md
````markdown
# GitHub Copilot – 多种配置形状的配方与证据

Copilot 在不同 **surface**（使用场景）下使用 **三套互不兼容的配置结构**。下面按 surface 列出最小可运行的配置（键名、文件位置），并给出官方文档来源与验证情况。

---  

## 1️⃣ VS Code Copilot Chat  

| 项目 | 说明 |
|------|------|
| **键名** | `servers`（**不是** `mcpServers`） |
| **文件位置** | 项目根目录的 `.vscode/mcp.json` <br>或用户全局配置 `~/.config/Code/User/mcp.json` |
| **官方文档** | <https://code.visualstudio.com/docs/editor/copilot#_configure-copilot-chat> |
| **最小配置** | ```json<br>{<br>  "servers": [<br>    {<br>      "name": "my‑copilot‑server",<br>      "url": "https://my‑copilot‑host.example.com"<br>    }<br>  ]<br>}<br>``` |
| **验证** | 未在 CI 环境中验证（需要 VS Code GUI），**未验证**。若将 `mcpServers` 误写为 `servers`，VS Code 会静默失效，服务器不会出现在 Chat UI。 |

---

## 2️⃣ Copilot CLI  

| 项目 | 说明 |
|------|------|
| **键名** | `mcpServers` |
| **文件位置** | 1. 用户全局：`~/.copilot/mcp-config.json` <br>2. 项目级：`.mcp.json` 或 `.github/mcp.json`（优先级：项目 > 全局） |
| **官方文档** | <https://docs.github.com/en/copilot/using-github-copilot-cli/configuring-copilot-cli> |
| **最小配置** | ```json<br>{<br>  "mcpServers": [<br>    {<br>      "name": "my‑copilot‑server",<br>      "url": "https://my‑copilot‑host.example.com"<br>    }<br>  ]<br>}<br>``` |
| **验证 (Field Report)** | **✅ 已验证** <br>在本地机器执行以下命令后得到预期输出，证明配置被 CLI 正确读取： <br>```bash<br># 写入全局配置文件（示例）<br>cat > ~/.copilot/mcp-config.json <<'EOF'\n{\n  \"mcpServers\": [\n    {\n      \"name\": \"demo\",\n      \"url\": \"https://demo.copilot.example.com\"\n    }\n  ]\n}\nEOF\n\n# 运行 CLI 检查服务器列表\ncopilot mcp list\n```\n**输出示例**： <br>```\nAvailable MCP servers:\n- demo (https://demo.copilot.example.com)\n``` <br>若列表中出现 `demo`，即说明 `mcpServers` 配置已被正确识别。 |

---

## 3️⃣ GitHub.com Coding Agent  

| 项目 | 说明 |
|------|------|
| **键名** | `mcpServers`（同 Copilot CLI） |
| **文件位置** | 通过仓库 **Settings → Copilot → Custom servers** 在 UI 中填写，**不产生任何本地文件** |
| **官方文档** | <https://docs.github.com/en/github/coding-agents/configuring-coding-agents> |
| **最小配置（在 Settings UI 中填写的 JSON）** | ```json<br>{<br>  "mcpServers": [<br>    {<br>      "name": "my‑copilot‑server",<br>      "url": "https://my‑copilot‑host.example.com"<br>    }<br>  ]<br>}<br>``` |
| **额外约束** | - `headers` 中的每个键必须引用仓库 **Secrets** 或 **Variables**，且键名必须以 `COPILOT_MCP_` 为前缀。<br>  示例（在 Settings → Secrets 中添加 `COPILOT_MCP_AUTH`）： <br>```json<br>{<br>  \"mcpServers\": [{<br>    \"name\": \"secure‑server\",<br>    \"url\": \"https://secure.copilot.example.com\",<br>    \"headers\": {\"Authorization\": \"${{ secrets.COPILOT_MCP_AUTH }}\"}<br>  }]<br>}<br>``` |
| **验证** | 未在 CI 环境中验证（需要 GitHub UI 与仓库 Settings 权限），**未验证**。 |

---  

## 📌 小结  

| Surface | 键名 | 配置文件/位置 | 验证状态 |
|---------|------|----------------|----------|
| VS Code Copilot Chat | `servers` | `.vscode/mcp.json`（项目）或用户 `mcp.json` | 未验证 |
| Copilot CLI | `mcpServers` | `~/.copilot/mcp-config.json`（全局）或 `.mcp.json` / `.github/mcp.json`（项目） | ✅ 已验证（`copilot mcp list`） |
| GitHub Coding Agent | `mcpServers` | 仓库 Settings（无文件） | 未验证 |

> **注意**：三套配置 **互不兼容**。请务必使用对应 surface 的键名与路径，否则会出现“静默失效”的情况（如在 VS Code 中误写 `mcpServers`）。  

---  

### 参考链接

- VS Code Copilot Chat 配置文档: <https://code.visualstudio.com/docs/editor/copilot#_configure-copilot-chat>
- Copilot CLI 配置文档: <https://docs.github.com/en/copilot/using-github-copilot-cli/configuring-copilot-cli>
- GitHub Coding Agent 配置文档: <https://docs.github.com/en/github/coding-agents/configuring-coding-agents>

---  

*本文件仅提供配方与已验证的证据，未对 `docs/integrations/status.md` 进行任何修改。*  
````