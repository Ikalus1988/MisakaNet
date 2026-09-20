# Cursor Integration – Remote MCP First Approach

> **TL;DR** – You don’t need to clone the whole repository or install the Python SDK.  
> Just point Cursor at a remote **MCP** endpoint and it will work.  
> The classic *stdio / local* mode is still supported as an offline fallback.

## 1. What is MCP?

MCP (MisakaNet Control Plane) is a tiny HTTP‑JSON service that implements the
Cursor tool‑listing and search APIs.  
Starting with **Cursor 0.45** the client can read a file called `~/.cursor/mcp.json`
(or a project‑local `.cursor/mcp.json`) and automatically talk to the remote
endpoint.

### Remote‑first configuration shape

Create a file called **`.cursor/mcp.json`** (either in your home directory or
inside the project you are working on). The file must contain a JSON object
with the following keys:

| Key      | Type   | Description |
|----------|--------|-------------|
| `url`    | string | Base URL of the MCP server (e.g. `https://mcp.example.com/api/v1`). |
| `headers`| object | Optional HTTP headers. Most often you will need an `Authorization` header with a Bearer token. |

#### Example – Minimal remote config

