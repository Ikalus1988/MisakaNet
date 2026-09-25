# Claude Code Integration

Give Claude Code access to 411 indexed failure lessons from MisakaNet.

Pick **one** of three modes. They are independent, and none needs an account (reads are anonymous
and unmetered).

| Mode | What you get | How |
|---|---|---|
| **A. Installer (recommended)** | MCP entry + a rules block + a checkpoint hook + the five read-only tools pre-allowed | `npx @misaka-net/misakanet-setup --only claude` |
| **B. MCP by hand** | the seven MCP tools, no rules block, no hook | one `claude mcp add` command below |
| **C. Rules file only** | no tool access: Claude reads the playbook and echoes the search command | [failure-memory playbook](claude-code-failure-memory.md) |

## A. Installer

```bash
npx @misaka-net/misakanet-setup --only claude
npx @misaka-net/misakanet-setup --verify        # endpoint, MCP registration, hook, version
```

It writes, and `--uninstall` undoes (keeping `.misakanet.bak` backups):

| File | What goes in it |
|---|---|
| `~/.claude.json` | the MCP server entry `mcpServers.misakanet` → `https://misakanet.org/mcp` (Streamable HTTP) |
| `~/.claude/CLAUDE.md` | the rules block, between `misakanet:start` / `misakanet:end` markers |
| `~/.claude/settings.json` | the **hook** (round-20 checkpoint reminder, failed-call reminder) and `permissions.allow` for the five read-only tools |

Note what `settings.json` is *not* for: it holds hooks, permissions and env — not MCP server
definitions. `~/.claude.json` is where the Claude Code docs put local- and user-scope servers
([scope table](https://docs.claude.com/en/docs/claude-code/mcp)), and a project-scoped server
belongs in `.mcp.json` at the project root so it can be committed and shared. Earlier versions of
this page put `mcpServers` in `settings.json`, where Claude Code does not read it — if you copied
that, move the block to `~/.claude.json`.

## B. MCP by hand (remote endpoint, no clone)

```bash
# user scope: available in every project
claude mcp add --transport http misakanet https://misakanet.org/mcp

# optional: attach a token, which unlocks the write tools (write_lesson / preflight)
claude mcp add --transport http misakanet https://misakanet.org/mcp \
  --header "Authorization: Bearer $MISAKANET_TOKEN"

claude mcp list          # → misakanet | https://misakanet.org/mcp | connected
```

Project scope instead — commit `.mcp.json` at the repository root:

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

`type: "http"` and `type: "streamable-http"` are aliases for the same transport. A committed
`.mcp.json` still needs approval from each user before its servers load — Claude Code ignores
`enabledMcpjsonServers` in an untrusted checkout, which is why the server may sit at
"⏸ Pending approval" the first time you open the repo.

**Offline / no-network alternative** — run the stdio server from a clone:

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git ~/MisakaNet
# then add a local entry: {"misakanet": {"command": "python3",
#   "args": ["/absolute/path/to/MisakaNet/scripts/mcp_server.py"]}}
```

The path must be absolute (`~` is not expanded inside `args`). This serves the same seven tools from
the local corpus, and needs `pip install -r requirements.txt`.

## Usage

In Claude Code, ask:

- "Search MisakaNet for DCO sign-off failure"
- "Find lessons about pip install timeout"
- "What does MisakaNet know about GitHub token issues?"

With mode A or B, Claude calls `misakanet_search` itself. With mode C it reads the playbook and
prints the command for you to run.

## Demo Queries

| Query | What you'll get |
|-------|----------------|
| DCO sign-off failed | Fix workflow with `--amend --signoff` |
| pip install timeout | SSL/proxy timeout solutions |
| GitHub token exposed | Secret scanning response pattern |
| database locked | SQLite WAL mode + timeout fix |
| Feishu document cleared | API deletion safety pattern |

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `/mcp` lists nothing | The entry is in a file Claude Code does not read for MCP. Local/user scope → `~/.claude.json`, project scope → `.mcp.json`. Not `settings.json` |
| Server shows "⏸ Pending approval" | A project-scoped `.mcp.json` in an untrusted checkout. Trust the folder, or use user scope |
| First search asks for permission | The five read-only tools are not pre-allowed. The installer adds them to `permissions.allow`; by hand, add them yourself or approve once |
| "Import error" from the stdio server | `pip install -r ~/MisakaNet/requirements.txt` |
| "No results" | Check the query, not the install: reads also serve the hosted corpus at `https://misakanet.org/mcp`. `no_match` is an answer (see [search behavior](../mcp.md)) |

## Learn More

- [MCP Quickstart](../mcp-quickstart.md)
- [Full MCP docs](../mcp.md)
- [What the installer writes](../../integrations/agent-autostart/README.md)
