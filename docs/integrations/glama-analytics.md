# Glama Analytics counting boundary

Date checked: 2026-08-02
MisakaNet version: v2.14.0
Glama listing: https://glama.ai/mcp/servers/Ikalus1988/MisakaNet
Related issue: #764

## Short conclusion

MisakaNet MCP server works locally; Glama listing exists; Glama Gateway/tool-call analytics has not discovered or routed MisakaNet tools yet.

This is **not** "MCP broken" or "0 usage". It is an analytics/gateway counting boundary: Glama currently shows 0 Glama-routed tool calls, while local stdio MCP calls are working and should not be described as "0 usage".

## External communication wording

For zsxh / external PRs / awesome-list listings, use this framing:

> MisakaNet is already registered as an MCP server and local MCP usage works. The current Glama issue is not MCP functionality. It is an analytics / gateway counting boundary: Glama currently shows 0 Glama-routed tool calls, while local stdio MCP calls are working and should not be described as "0 usage".

Do **not** say:
- "MisakaNet has 0 usage"
- "MCP integration needs to be fixed"
- "We need to register as an MCP server" (already registered)

## Focus areas (in order)

1. **Clarify Glama counting boundary** – document that Tool Calls = 0 is a measurement gap, not a failure
2. **Check Glama Gateway support** – confirm whether Glama can host/route MisakaNet tools (see Follow-up below)
3. **Improve first-call docs** – copy-paste config, recommended first query, expected output
4. Do **not** frame any of this as "MCP broken"

## Glama capability check

Current Glama docs indicate the platform does support both hosted MCP deployments and a Gateway endpoint for routed calls:

- Hosting: https://glama.ai/mcp/hosting
- Gateway: https://glama.ai/mcp/gateway

That means the remaining question is narrower than "can Glama do MCP?" The open question is whether MisakaNet currently has a deployed hosted endpoint / routed connection profile, or only a directory listing with analytics that still reports zero routed calls.

If a hosted endpoint exists, the next valid test is one `tools/call` through that endpoint and then a delayed analytics re-check.

## Evidence collected

### Glama listing API

Command:

```powershell
Invoke-RestMethod -Uri 'https://glama.ai/api/mcp/v1/servers/Ikalus1988/MisakaNet' | ConvertTo-Json -Depth 10
```

Observed key fields on 2026-08-02:

```json
{
  "id": "dr8pugtliz",
  "name": "MisakaNet",
  "namespace": "Ikalus1988",
  "repository": { "url": "https://github.com/Ikalus1988/MisakaNet" },
  "tools": [],
  "url": "https://glama.ai/mcp/servers/dr8pugtliz"
}
```

Interpretation: the Glama listing exists, but Glama does not currently expose discovered tool metadata for MisakaNet through this API response.

### Local MCP stdio smoke

Local stdio calls are working independently of Glama:

- `initialize` returned server name `misakanet`.
- `tools/list` returned `misakanet_search`, `misakanet_get_lesson`, `misakanet_submit_usage`, and `misakanet_usage_status`.
- `tools/call` for `misakanet_search` with query `database locked` returned SAG-Lite results.
- `tools/call` for `misakanet_usage_status` returned quota status for `anon:mcp-default`.

This proves the MCP server works locally, but it does not prove Glama Analytics increments for those local calls.

## Required wording

Use:

> MisakaNet is already registered as an MCP server and local MCP usage works. The current Glama issue is not MCP functionality — it is an analytics / gateway counting boundary.

Avoid:

> MisakaNet has 0 usage.
> MCP integration needs to be fixed.
> We need to register as an MCP server.

## Follow-up

1. Ask Glama or check Glama maintainer docs for whether a hosted/gateway endpoint can be enabled for this listing.
2. If a hosted/gateway endpoint appears, run one `tools/call` through that endpoint and re-check analytics after 10-30 minutes.
3. Keep first-call conversion work focused on copy-paste setup until a hosted Glama path is confirmed.
