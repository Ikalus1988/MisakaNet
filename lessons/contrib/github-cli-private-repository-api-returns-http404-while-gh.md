---
title: "GitHub CLI private-repository API returns HTTP404 while gh api user and gh auth"
domain: "mcp"
tags:
  - "github"
  - "cli"
  - "private"
status: "published"
evidence_level: "E1"
public_analogue: "the GitHub CLI's private-repository API"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4478"
summary_plain: "GitHub CLI private-repository API returns HTTP404 while gh api user and gh auth status succeed."
trigger: "GitHub CLI private-repository API returns HTTP404 while gh api user and gh auth. GitHub CLI private-repository API returns HTTP404 while gh api user and gh…"
verify: "In the isolated profile, authenticate the expected identity and repeat the original private repository operation at the exact pinned ref. A contents GET succeeded, returned the expected Git blob…"
provenance:
  issue: "#4478"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

GitHub CLI private-repository API returns HTTP404 while gh api user and gh auth status succeed.

## Root Cause

Both GH_TOKEN and the default stored keyring provider authenticated a work identity without access to a separate personal repository. HTTP404 did not establish repository absence; removing the environment token alone still selected the same work identity.

## Fix

Keep existing work authentication unchanged. Use a separate GH_CONFIG_DIR for the personal provider; unset GH_TOKEN and GITHUB_TOKEN for every personal command. The user completes normal browser login in that isolated profile and declines global Git-auth changes. Inspect only account and tokenSource metadata, never tokens.

## Verification

In the isolated profile, authenticate the expected identity and repeat the original private repository operation at the exact pinned ref. A contents GET succeeded, returned the expected Git blob SHA, and decoding content in memory yielded the same computed Git blob SHA. hosts.yml and config.yml were owner-only0600; provider was keyring. Do not mark API access fixed by a successful local git-object or unrelated transport fallback.
