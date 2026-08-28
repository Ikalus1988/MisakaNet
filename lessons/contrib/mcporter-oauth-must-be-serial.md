---
title: "mcporter OAuth Authorization Must Be Serial: Concurrent Auth Causes client_id/state Corruption"
domain: "devops"
tags: ["mcporter", "oauth", "mcp", "cloudflare", "concurrency", "vault"]
status: "published"
source: "intake-issue-1306"
created: "2026-08-27"
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# mcporter OAuth Authorization Must Be Serial

## Problem

Running multiple mcporter auth commands in parallel (e.g., cloudflare-bindings/builds/observability three background jobs authorizing simultaneously) causes browser authorization page to report "invalid_request Invalid client_id". Multiple authorization URLs share the same state parameter (should be random each time) and the same invalid client_id, causing all authorizations to fail.

## Root Cause

mcporter's OAuth state is stored in shared single files: vault (`~/.mcporter/credentials.json`) and token cache directory (`state.txt` / `code_verifier.txt` / `tokens.json`). Multiple auth processes concurrently read/write the same files, overwriting each other:
- PKCE state gets overwritten by the last writer (URL state identical)
- Dynamically registered client_id gets串写 as invalid value
- Additionally, in sandbox/permission environments, vault writing to `~/.mcporter` may fail with EACCES, requiring HOME redirection

## Solution

1. **OAuth authorization must be serial**: Run one mcporter auth at a time, complete (browser authorization + callback + token save) before starting the next
2. **If corrupted**: Delete vault entries for affected servers (credentials.json entries), clean token cache directory, then `--reset` to re-authorize
3. **Give each server independent tokenCacheDir**: `config add --token-cache-dir <dir>` to reduce shared file conflicts
4. **Sandbox environments**: Use wrapper script to redirect HOME to writable directory

## Verification

```bash
# Run serial authorization (one at a time)
mcporter auth cloudflare-bindings
# Wait for completion: "Authorization complete. 23 tools available."
mcporter auth cloudflare-builds
# Wait for completion: "Authorization complete. 6 tools available."
mcporter auth cloudflare-observability
# Wait for completion: "Authorization complete. 8 tools available."

# Verify all servers authorized
mcporter list

# Check no Invalid client_id errors
mcporter auth cloudflare-bindings 2>&1 | grep -i "invalid\|error" || echo "No errors"
```

**Expected Output:**
```
cloudflare-bindings: 23 tools
cloudflare-builds: 6 tools
cloudflare-observability: 8 tools
No errors
```
