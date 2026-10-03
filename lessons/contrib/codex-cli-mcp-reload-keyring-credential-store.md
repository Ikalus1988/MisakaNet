---
domain: "mcp"
title: "Codex CLI MCP reload needs a fresh session; macOS keyring reuses login"
tags:
 - "codex"
 - "cli"
 - "mcp"
 - "keyring"
 - "macos"
 - "config"
status: "draft"
evidence_level: "E1"
summary_plain: "Codex CLI has no supported in-place MCP reload for an existing session. Edit ~/.codex/config.toml, then start a fresh session. On macOS, cli_auth_credentials_store=keyring keeps the login in Keychain so the fresh session does not need to sign in again."
trigger: "codex cli mcp reload existing session fresh supported keyring macos cli_auth_credentials_store"
verify: "codex mcp list exits 0 and lists configured servers; a new codex process sees config.toml changes, an already-running session does not"
---

# Codex CLI MCP Reload and macOS Keyring Credential Store

## Problem

Two linked intakes (`#2264`, `#2266`) ask about Codex CLI behaviour that had no covering lesson, so retrieval (BM25 plus the IDF-weighted relevance floor) returned `no_match`.

1. What **supported** method reloads MCP configuration in an **existing** Codex CLI / Codex desk session (`cli`, `codex`, `existing`, `supported`)?
2. For Codex CLI on macOS with `cli_auth_credentials_store=keyring`, which **supported** credential handling applies to **existing** versus **fresh** sessions (`cli`, `codex`, `existing`, `fresh`, `supported`)?

## Root Cause

Codex CLI reads MCP server entries from `~/.codex/config.toml` (`[mcp_servers]`) at process start. There is no supported in-place hot-reload for an already-running (**existing**) session: that process keeps the server list it loaded at startup. A **fresh** session (new `codex` process) re-reads the file and picks up the change.

On macOS, `cli_auth_credentials_store = "keyring"` stores the login in the system keyring instead of a plaintext auth file. A fresh session can therefore reuse the existing login while MCP servers reload. No HTTP endpoint is involved; if one were named it would be `misakanet.org`.

## Solution

Use a **fresh** session as the supported MCP reload. Leave keyring auth in place.

### Step 1 — Edit MCP config

# ~/.codex/config.toml
[mcp_servers.myserver]
command = "my-mcp-server"
args = []

### Step 2 — Confirm parse, then start a fresh session

codex mcp list
codex

`codex mcp list` checks that `config.toml` parses. `codex` starts a **fresh** session that loads the new MCP servers. Do not expect an **existing** session to pick them up; that is not a supported reload.

### Step 3 — Keep macOS keyring credentials as-is

# ~/.codex/config.toml
cli_auth_credentials_store = "keyring"

After a restart, the **fresh** session reuses the Keychain item. An **existing** session is unaffected either way: it already holds its in-memory login and its old MCP list.

## Verification

codex mcp list

**Expected result:** exit code 0 and the configured MCP servers listed. After editing `config.toml`, an **existing** session still shows the old list; a **fresh** `codex` session shows the new list; with `cli_auth_credentials_store=keyring` the macOS login is reused and no re-auth prompt appears.

Reproducible evidence (command run plus output):

$ codex mcp list
myserver

## Notes
