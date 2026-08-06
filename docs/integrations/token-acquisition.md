# Token Acquisition Guide

> **Status:** Tokens are currently provisioned manually via Cloudflare.
> This guide explains how to get one and the roadmap for self-service.

## Quick Answer: How to get a token

**Option A — Contact the maintainer (current method):**

1. Open an issue: [Request Access Token](https://github.com/Ikalus1988/MisakaNet/issues/new?title=Token+Request&body=Please+provide+a+Bearer+token+for+the+MisakaNet+MCP+endpoint.%0A%0AUse+case%3A+...)
2. Or reach out via [Discord](https://discord.gg/misakanet) (if available)
3. The maintainer will provision a token via the Cloudflare dashboard and share it privately

**Option B — Use Glama (token-free, coming soon):**

Glama's hosted MCP endpoint will provide token-free access once [#817](https://github.com/Ikalus1988/MisakaNet/issues/817) is resolved.
Track that issue for updates.

**Option C — Public read-only token (planned):**

A future version will support anonymous read-only access for `misakanet_search` and `misakanet_get_lesson`
without requiring a token. Subscribe to [#855](https://github.com/Ikalus1988/MisakaNet/issues/855) for progress.

## Why tokens are required

The MCP endpoint validates `Authorization: Bearer <token>` on every request to:
- Prevent abuse and rate-limit by user
- Track usage for the community leaderboard
- Enable future credit/usage tiers

## After you have a token

Once you have your token, configure your MCP client:

```json
{
  "mcpServers": {
    "misakanet": {
      "url": "https://misakanet.org/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

See the [Remote MCP setup guide](mcp-remote.md) for client-specific instructions.

## Roadmap

| Milestone | Status | Issue |
|-----------|--------|-------|
| Self-service `/api/token` endpoint with email | Planned | [#855](https://github.com/Ikalus1988/MisakaNet/issues/855) |
| Token-free via Glama proxy | In progress | [#817](https://github.com/Ikalus1988/MisakaNet/issues/817) |
| Public read-only (no auth) | Proposed | [#855](https://github.com/Ikalus1988/MisakaNet/issues/855) |