# OpenCode Integration Recipe

This document provides configuration details and verification records for integrating MisakaNet's remote MCP service with **OpenCode** (`opencode`).

## Overview & Scope

OpenCode is an open terminal-based and IDE agentic coding assistant supporting Model Context Protocol (MCP) integrations.

> **Status Grade Recommendation:** 🔵 **vendor-only** (or 🟡 **recipe** for the installer and config structure)  
> *Reasoning:* While the configuration structure (`~/.config/opencode/opencode.json` under key `mcp`) is automated and verified by the setup installer, upstream end-to-end multi-turn tool verification is documented in the smoke test report without modifying the global matrix.

---

## Configuration Recipe

### 1. Automated Setup (Recommended)

Since installer version 0.5.6, OpenCode configuration is natively supported:

```bash
npx @misaka-net/misakanet-setup@latest --only opencode
```

To verify the setup:
```bash
npx @misaka-net/misakanet-setup@latest --verify
```

### 2. Manual Configuration

- **Configuration File**: `~/.config/opencode/opencode.json` (or `$XDG_CONFIG_HOME/opencode/opencode.json`)
- **Container Key**: `mcp`
- **Official Documentation**: [OpenCode Configuration Documentation](https://opencode.ai/docs/config)

Add the `misakanet` server entry:

```json
{
  "mcp": {
    "misakanet": {
      "type": "remote",
      "url": "https://misakanet.org/mcp",
      "enabled": true
    }
  }
}
```

---

## Rules and Steering

- **Project Rules**: OpenCode reads `AGENTS.md` at the project root and `~/.config/opencode/AGENTS.md`.
- **Hooks**: OpenCode does not provide an automated pre-command shell hook mechanism (marked as 未验证 / unverified).

---

## Verification & Smoke Test

See the field verification report in [2026-09-21-opencode-mcp-smoke.md](../field-reports/2026-09-21-opencode-mcp-smoke.md).
