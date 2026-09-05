---
title: "DSH Plugin Installation Troubleshooting — Common Failures and Fixes"
domain: tooling
tags:
  - dsh
  - plugin
  - installation
  - troubleshooting
  - npm
  - git
  - permissions
  - windows
status: draft
created: '2026-09-02'
language: en
source: issue-1421
evidence_level: E1
---

## Problem

Users installing the MisakaNet DSH plugin encounter a variety of failures across npm, git, and manual installation methods. This lesson consolidates the most common issues and their fixes into a single reference.

## Common Failures

### 1. npm Install — Registry Unreachable

**Symptom:** `dsh plugin add misakanet` hangs or times out.

**Cause:** Corporate firewall or proxy blocks `registry.npmjs.org`. Alternatively, npm cache is corrupted.

**Fix:**
```bash
# Check registry connectivity
curl -sS -o /dev/null -w "%{http_code}\n" https://registry.npmjs.org/

# Clear npm cache and retry
npm cache clean --force
dsh plugin add misakanet

# Or set proxy
npm config set proxy http://proxy:8080
npm config set https-proxy http://proxy:8080
```

### 2. Git Method — codeload.github.com Timeout

**Symptom:** `dsh plugin add github:Ikalus1988/MisakaNet` fails with `request timeout: cannot reach GitHub`.

**Cause:** `codeload.github.com` is blocked or slow in some networks (especially CN/GFW).

**Fix:** Use the npm channel instead (see `dsh-plugin-install-github-codeload-timeout.md`):
```bash
dsh plugin add misakanet   # from npm registry
```

### 3. Permission Denied on ~/.dsh/skills

**Symptom:** `EACCES: permission denied, mkdir '~/.dsh/skills'`

**Cause:** The `~/.dsh` directory was created by root or a different user.

**Fix:**
```bash
# Option A: Fix ownership
sudo chown -R $(whoami) ~/.dsh

# Option B: Use user-level install
dsh plugin add misakanet --user
```

### 4. Plugin Not Found After Install

**Symptom:** `dsh plugin list` shows no misakanet plugin after successful install.

**Cause:** Shell session not refreshed, or `~/.dsh/skills` not in PATH.

**Fix:**
```bash
# Restart terminal, then:
source ~/.bashrc   # or ~/.zshrc
dsh plugin list

# Or manually verify
ls -la ~/.dsh/skills/misakanet
```

### 5. Windows — python3 Not Found

**Symptom:** Plugin install or runtime fails with `python3: command not found`.

**Cause:** Windows ships `python` not `python3`.

**Fix:**
```bash
# Use python instead of python3
python --version

# Or set environment variable
set PYTHON=python
```

### 6. Version Conflict — dsh Too Old

**Symptom:** `Plugin requires dsh >= 1.0.0, found 0.x.x`

**Fix:**
```bash
npm update -g dsh
dsh plugin remove misakanet
dsh plugin add misakanet
```

### 7. Manual Install — Wrong Directory

**Symptom:** Skill not discovered after manual `cp -r`.

**Cause:** Copied to wrong path. Must be `~/.dsh/skills/misakanet/`, not `~/.dsh/skills/` directly.

**Fix:**
```bash
# Verify directory structure
ls ~/.dsh/skills/misakanet/skill.yml   # must exist
ls ~/.dsh/skills/misakanet/skill.md    # must exist
```

## Verification

After fixing any installation issue:
```bash
dsh plugin list                     # should show misakanet
dsh tool list | grep misakanet      # should show tools
dsh plugin --dump-config            # should show misakanet layer
```

## Related Lessons

- `dsh-plugin-install-github-codeload-timeout.md` — codeload-specific timeout deep dive
