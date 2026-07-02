---
domain: "git"
title: "Git credential helper fails with token in URL on Windows"
verification: "metadata-normalized"
---
---{"title": "Git credential helper fails with token in URL on Windows", "domain": "git", "tags": ["git", "credentials", "token", "windows", "clone"]}---

## Problem

Running `git clone https://user:token@github.com/repo.git` fails with connection timeout or SSL errors on Windows, even though the token is valid and the URL is correct.

## Root Cause

Embedding tokens in git clone URLs can trigger Windows credential manager conflicts, SSL renegotiation timeout issues, or proxy interference. Git's credential helper may try to validate the embedded credentials before the actual HTTPS connection, causing unexpected failures.

## Fix

Use `git config --global credential.helper manager-core` and set the token via environment: `set GIT_ASKPASS=echo` then `set GITHUB_TOKEN=your_token`. Alternatively, use `gh auth login` or store credentials via `git credential approve`. For scripts, use the GitHub API instead of git clone with embedded tokens.

## Verification

Run `git ls-remote https://github.com/owner/repo.git` with proper credential helper configured. Should return HEAD refs without timeout.
