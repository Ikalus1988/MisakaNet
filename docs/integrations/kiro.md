# Kiro Integration Recipe

This document provides configuration details and verification records for integrating MisakaNet's remote MCP service with **Kiro** (`kiro`).

## Overview & Scope

Kiro is an agentic coding assistant supporting Model Context Protocol (MCP) integrations with project steering capabilities.

> **Status Grade Recommendation:** 🔵 **vendor-only** (or 🟡 **recipe** for installer and config structure)  
> *Reasoning:* Automated setup is natively supported by MisakaNet Setup (`packages/misakanet-setup`) writing to `~/.kiro/settings/mcp.json`. The matrix file `docs/integrations/status.md` remains unedited to preserve single-writer ownership.

---

## Configuration Recipe

### 1. Automated Setup (Recommended)

Since installer version 0.5.6, Kiro configuration is natively supported:

```bash
npx @misaka-net/misakanet-setup@latest --only kiro
```

To verify the setup:
```bash
npx @misaka-net/misakanet-setup@latest --verify
```

### 2. Manual Configuration

- **Configuration File**: `~/.kiro/settings/mcp.json`
- **Container Key**: `mcpServers`
- **Server Key**: `misakanet`
- **Connection Model**: Remote SSE / HTTP Stream (`url`)

Add the `misakanet` server entry:

```json
{
  "mcpServers": {
    "misakanet": {
      "url": "https://misakanet.org/mcp",
      "headers": {
        "Authorization": "Bearer <YOUR_MISAKANET_TOKEN>"
      },
      "autoApprove": [
        "misakanet_search"
      ]
    }
  }
}
```

> **Note on Client Keys:** Unlike some clients that use `serverUrl` or `command`, Kiro expects a bare `url` key. A mismatched key fails silently in Kiro without registering the server.

---

## Rules and Steering

- **Project Rules / Steering**: Kiro reads `.kiro/steering/*.md` at the project workspace level.
- **Rule Guidance**: To prompt Kiro to query MisakaNet before taking destructive actions or debugging unfamiliar errors, add a steering rule into `.kiro/steering/misakanet.md`:
  ```markdown
  When encountering compile errors, obscure runtime exceptions, or unfamiliar tool failures, search MisakaNet knowledge first via `misakanet_search`.
  ```
- **Hooks**: Kiro does not expose shell lifecycle hooks (marked as 未验证 / unverified).

---

## Verification & Smoke Test

See the field verification report in [2026-09-21-kiro-mcp-smoke.md](../field-reports/2026-09-21-kiro-mcp-smoke.md).
