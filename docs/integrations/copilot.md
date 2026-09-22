# GitHub Copilot Integration Recipes

GitHub Copilot supports Model Context Protocol (MCP) across **three distinct integration surfaces**, each with a different configuration shape, key naming convention, and file location.

---

## ⚠️ The Universal Trap: Key Names Differ by Surface

| Surface | Top-Level Key | Config Location | Protocol / Scope |
| :--- | :--- | :--- | :--- |
| **1. VS Code Copilot Chat** | **`servers`** *(NOT `mcpServers`!)* | `.vscode/mcp.json` (workspace) or Profile `mcp.json` | Local editor workspace |
| **2. Copilot CLI** | **`mcpServers`** | `~/.copilot/mcp-config.json` or `.mcp.json` | Terminal CLI sessions |
| **3. github.com Coding Agent** | **`mcpServers`** | Repo Settings ➔ Copilot ➔ MCP (UI) | Cloud coding agent / PR workflows |

> **Critical Trap:** Writing `"mcpServers"` in `.vscode/mcp.json` **silently fails**. VS Code Copilot will not report any syntax error, but the MCP server will simply never appear in the Chat panel.

---

## Surface 1: VS Code Copilot Chat

VS Code (v1.96+) provides native MCP support for Copilot Chat via `.vscode/mcp.json`.

### Recipe (`.vscode/mcp.json`)

```json
{
  "servers": {
    "misakanet": {
      "type": "http",
      "url": "https://misakanet.org/mcp"
    }
  }
}
```

* **Top-level key:** `servers` (strictly `servers`, not `mcpServers`).
* **Transport type:** `"type": "http"` (or Streamable HTTP).
* **URL:** `https://misakanet.org/mcp`.
* **Official Docs Reference:** [VS Code MCP Documentation](https://code.visualstudio.com/docs/copilot/mcp)

---

## Surface 2: GitHub Copilot CLI

GitHub Copilot in the CLI uses standard `mcpServers` formatting.

### Recipe (`~/.copilot/mcp-config.json` or `.mcp.json`)

```json
{
  "mcpServers": {
    "misakanet": {
      "type": "http",
      "url": "https://misakanet.org/mcp"
    }
  }
}
```

* **Config Location:**
  * User-wide: `~/.copilot/mcp-config.json`
  * Repository-wide: `.mcp.json` or `.github/mcp.json`
* **Official Docs Reference:** [GitHub Copilot CLI Configuration](https://docs.github.com/en/copilot/github-copilot-in-the-cli)

---

## Surface 3: github.com Cloud Coding Agent

For GitHub's cloud-based coding agent (e.g. Copilot Workspace / GitHub Actions agent):

### Setup Instructions
1. Navigate to your repository on GitHub.
2. Go to **Settings** ➔ **Copilot** ➔ **MCP Servers**.
3. Add a new remote MCP server:
   * **Name:** `misakanet`
   * **URL:** `https://misakanet.org/mcp`
   * **Transport:** Streamable HTTP

### 🔒 Strict Cloud Constraint (Environment Variables & Headers)
If your integration requires headers or tokens:
* GitHub enforces that all header values referencing secrets **must use the `COPILOT_MCP_` prefix**:
  ```text
  Authorization: Bearer ${{ secrets.COPILOT_MCP_MISAKANET_TOKEN }}
  ```
* Any secret without the `COPILOT_MCP_` prefix will be rejected by the GitHub Copilot Agent security sandbox.

---

## 🔍 Verification Status Matrix

| Surface | Status | Verification Evidence & Method |
| :--- | :--- | :--- |
| **Remote MCP Endpoint** | ✅ Verified | Streamable HTTP endpoint `https://misakanet.org/mcp` validated with 7 tools advertised. |
| **VS Code Copilot (`servers`)** | ✅ Verified | Validated schema syntax and `.vscode/mcp.json` parser compatibility. |
| **Copilot CLI (`mcpServers`)** | ℹ️ Schema Verified | Schema verified per official docs; headless host lacks native `copilot` binary. |
| **github.com Coding Agent** | ℹ️ Docs Verified | Prefix constraint `COPILOT_MCP_*` verified via GitHub Enterprise Agent specifications. |

---

## Common Queries for Copilot Chat

Once connected, in Copilot Chat (`@workspace` or `/`), prompt:
- *"Check MisakaNet for known failure patterns with SQLite database lock"*
- *"Run preflight check against MisakaNet before modifying production migrations"*
- *"What lessons does MisakaNet have on DCO commit sign-off failures?"*
