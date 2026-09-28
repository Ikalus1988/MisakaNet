---
title: "Codex CLI: keyring 'User interaction is not allowed' diagnosis"
domain: development
tags: [codex, keyring, macos, keychain, oauth, cli]
status: published
evidence_level: "E0"
summary_plain: "Codex CLI 登录时报 'User interaction is not allowed'，是 macOS Keychain 的访问控制限制，不是凭据损坏——检查 ACL 和锁屏状态。"
trigger: "codex keyring User interaction is not allowed persist_failed cli_auth_credentials_store"
verify: "security find-generic-password -s 'Codex Auth' -a <user> 2>&1 | head -5 返回密码项信息而非错误"
provenance: verified
---

## Problem

Codex CLI on macOS with `cli_auth_credentials_store=keyring` fails to write OAuth
tokens with: `failed to write OAuth tokens to keyring: Platform secure storage
failure: User interaction is not allowed`. A fresh `codex login status` can still
read an existing ChatGPT session, and the Keychain reports unlocked.

## Root Cause

The macOS Keychain item's Access Control List (ACL) restricts which applications
can access it. The `User interaction is not allowed` error means the Keychain
拒绝了当前进程的写入请求，通常是因为：

1. **Screen is locked** — Keychain items with `kSecAttrAccessibleWhenUnlocked`
   are inaccessible when the screen is locked.
2. **ACL does not include the current process** — the item was created by a
   different binary or path, and the ACL only allows that specific app.
3. **Keychain is locked** — even if the UI shows it as unlocked, the CLI
   process may see a different state.

Read-only access (login status) works because reading may use a different
ACL entry or the item's access control allows read without interaction.

## Solution

### Step 1: Diagnose the ACL

```bash
# Check the Keychain item's ACL
security find-generic-password -s "Codex Auth" -a "<your-email>" 2>&1
# Look for "accc" (access control) entries — which app paths are allowed

# Check if Keychain is actually locked from CLI perspective
security show-keychain-info ~/Library/Keychains/login.keychain-db 2>&1
```

### Step 2: Fix the ACL

```bash
# Option A: Delete and recreate the item (next codex login will recreate it)
security delete-generic-password -s "Codex Auth" -a "<your-email>" 2>&1
codex login

# Option B: Add the current binary to the ACL
# This requires the Keychain Access GUI:
# 1. Open Keychain Access.app
# 2. Search for "Codex Auth"
# 3. Double-click → Access Control → click "+"
# 4. Navigate to /usr/local/bin/codex (or wherever it's installed)
# 5. Save
```

### Step 3: Verify

```bash
# Test write access
codex login 2>&1
# Expected: successful login without "User interaction" error

# Verify the item exists and is readable
security find-generic-password -s "Codex Auth" -a "<your-email>" -w 2>&1
# Expected: the token value (or at least no ACL error)
```

## Verification

```bash
security find-generic-password -s "Codex Auth" -g 2>&1 | head -5
# Expected: item attributes including "svce" = "Codex Auth"
# Not expected: "User interaction is not allowed" or "could not be found"
```
