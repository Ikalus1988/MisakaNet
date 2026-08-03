# Glama Analytics — What "Tool Calls = 0" Means

> This page clarifies the difference between **local MCP functionality** and
> **Glama routing/analytics metrics**. It exists so visitors never mistake an
> analytics figure for a broken integration.

## MisakaNet is registered as an MCP server

MisakaNet publishes a stdio MCP server (`scripts/mcp_server.py`) that any
MCP-compatible client can load locally. The server is self-contained — it runs
from a `git clone`, no third-party service required.

- **Glama listing**: https://glama.ai/mcp/servers/Ikalus1988/MisakaNet
- **mcp-name** (registry identifier): `io.github.Ikalus1988/misakanet`
- **Server version** (smoke-tested): `2.12.0`
- **Local setup**: see [MCP Server setup](README.md#mcp-server)

✅ Local stdio MCP calls are **verified working** — see the
[smoke test report](../mcp-smoke-report.md). The server starts, responds to
`initialize`, and lists 4 tools, 5 resources, and 3 prompts over stdin/stdout.

## The "Tool Calls = 0" metric

The Glama score badge on the README tracks calls routed **through Glama's
proxy/listing gateway**. The displayed "Tool Calls" count only increments when
a client connects to MisakaNet *via a Glama-routed URL or proxy* — i.e. a user
who discovered MisakaNet through Glama and invoked the server through Glama's
managed endpoint.

`Tool Calls = 0` therefore means **0 Glama-routed tool calls**, not 0 local
MCP calls. It is a **traffic-source analytics metric**, not a
functionality indicator.

### What does NOT change this metric

- ✅ Connecting to MisakaNet via **local stdio** (the default setup in
  `claude.json` / Cursor / Claude Desktop) — these calls bypass Glama entirely.
- ✅ Connecting via the **MCP Registry** listing (`mcp-registry://...`).
- ✅ Running the server from a direct `git clone`.

None of these increment the Glama "Tool Calls" counter, because none are
routed through Glama's gateway.

## TL;DR

- **MisakaNet MCP is not broken.** Local MCP usage works (smoke-verified).
- **Glama `Tool Calls = 0`** = no calls routed *through Glama's gateway*.
  It does **not** mean users can't connect to the server.
- To see real local adoption, check the server's own usage reports or GitHub
  traffic — not the Glama routing count.

## Related reading

- [Local smoke test report](../mcp-smoke-report.md)
- [Glama MCP publishing guide](docs/glama-mcp-publish-guide.md)
- [MCP registry readiness lesson](../lessons/contrib/glama-mcp-server-deploy-lessons.md)
