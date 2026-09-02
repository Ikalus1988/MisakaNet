---
title: Aider CLI --api-key parameter leaks API key to history files
domain: security
tags:
- aider
- security
- api-key
- leak
- history
status: published
created: '2026-08-22'
source: mcp-intake-1190
evidence_level: E2
---

<!-- provenance:
  contributor: "Ikalus1988"
  merged_at: "2026-08-22"
  evidence: "post-publication"
-->

<!-- 
## Problem

Aider CLI `--api-key` parameter leaks API key to `.aider.chat.history.md`, bash history, and `/proc/pid/cmdline`.

When a user runs a command like:
```bash
aider --api-key sk-ant-api03-XXXXXXXXXXXXXXXXXXXX
```

The API key is exposed in at least three places:
1. **Shell history files** (e.g., `~/.bash_history`, `~/.zsh_history`) — persisted across sessions and often synced or backed up.
2. **Aider's own chat history file** (`.aider.chat.history.md`) — written to the project directory and may be committed to version control.
3. **`/proc/<pid>/cmdline`** — readable by other processes on the same host while the process is running, which is a risk in shared or multi-tenant environments.

## Root Cause

This is a classic "secrets in arguments" vulnerability. On Linux and macOS, every process's full command line is visible via:
```bash
ps aux | grep aider
# or
cat /proc/$(pgrep aider)/cmdline | tr '\0' ' '
```

Unlike environment variables (which can be restricted), command-line arguments are world-readable by default on most Unix systems. Additionally, interactive shells record every command — including all arguments — to a history file. Aider compounds this by also logging session context (which may include the invocation command) to `.aider.chat.history.md`.

**Example of a leaked entry in `~/.bash_history`:**
```
aider --api-key sk-ant-api03-XXXXXXXXXXXXXXXXXXXX --model claude-3-5-sonnet
```

**Example of a leaked entry visible via `ps`:**
```
user   12345  0.5  1.2  aider --api-key sk-ant-api03-XXXXXXXXXXXXXXXXXXXX
```

## Solution

### Option 1: Use an environment variable (recommended)

Set the API key as an environment variable before invoking Aider. Aider automatically reads standard provider environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-XXXXXXXXXXXXXXXXXXXX"
aider --model claude-3-5-sonnet
```

To avoid the key appearing in shell history, either:
- Prefix the export with a space (in bash with `HISTCONTROL=ignorespace`):
  ```bash
   export ANTHROPIC_API_KEY="sk-ant-api03-XXXXXXXXXXXXXXXXXXXX"
  ```
- Or set it in your shell profile (`~/.bashrc`, `~/.zshrc`) so it is loaded automatically without being typed interactively.

### Option 2: Use a `.env` file

Create a `.env` file in your project root:
```
ANTHROPIC_API_KEY=sk-ant-api03-XXXXXXXXXXXXXXXXXXXX
```

Aider will automatically load `.env` files at startup. **Ensure this file is excluded from version control:**
```bash
echo ".env" >> .gitignore
```

### Option 3: Use a secrets manager

For team or CI/CD environments, inject the key via a secrets manager (e.g., HashiCorp Vault, AWS Secrets Manager, GitHub Actions secrets) rather than storing it in any file on disk.

## Verification

After switching to environment-variable-based authentication, verify that no key material is present in the exposed locations:

**1. Check shell history:**
```bash
grep -i "api.key\|api-key\|sk-ant\|sk-" ~/.bash_history ~/.zsh_history 2>/dev/null
```
**Expected Output:**
```
(no output — no matches found)
```

**2. Check Aider chat history file:**
```bash
grep -i "sk-ant\|api.key" .aider.chat.history.md 2>/dev/null
```
**Expected Output:**
```
(no output — no matches found)
```

**3. Confirm the environment variable is set correctly:**
```bash
aider --model claude-3-5-sonnet --message "Say hello"
```
**Expected Output:**
```
Successfully verified
```

**4. Confirm the key is NOT visible in the process list:**
```bash
ps aux | grep aider | grep -v grep
```
**Expected Output:**
```
user   12345  0.5  1.2  aider --model claude-3-5-sonnet --message "Say hello"
# No API key string present in the output
```

## Additional Recommendations

- **Rotate any key** that was previously passed via `--api-key` on the command line, as it should be considered compromised.
- **Audit `.aider.chat.history.md`** files in all project directories and remove or redact any key material before committing.
- **Add `.aider.chat.history.md` to `.gitignore`** to prevent accidental commits of session history:
  ```bash
  echo ".aider.chat.history.md" >> .gitignore
  ```