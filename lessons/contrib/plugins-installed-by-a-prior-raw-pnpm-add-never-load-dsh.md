---
title: "Plugins installed by a prior raw pnpm add never load — dsh plugin add skips the bundle registration"
domain: "devops"
tags:
  - "dsh"
  - "deepseek-harness"
  - "plugin"
  - "bundles"
  - "pnpm"
  - "loader"
  - "registration"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3686"
summary_plain: "A DSH plugin that was first installed with a raw `pnpm add` never loads afterwards."
trigger: "Plugins installed by a prior raw pnpm add never load — dsh plugin add skips the bundle registration. A DSH plugin that was first installed with a raw `pnpm…"
verify: "- `dsh.profile.bundles` in `~/.dsh/profiles/<profile>/package.json` includes the package name. - The runtime plugin list shows the plugin (not just its dependency entry). - No FAILED entries after…"
provenance:
  issue: "#3686"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A DSH plugin that was first installed with a raw `pnpm add` never loads afterwards. Running `dsh plugin --profile web add <pkg>` reports "Already up to date" (+0 packages); the package is present in `node_modules` and listed in `package.json` dependencies, but the plugin is absent from the runtime plugin list and neither its tools nor its settings appear.

Symptom is silent: no error, no FAILED row, the plugin simply does not mount.

## Root Cause

DSH keeps two separate records for a plugin: `dependencies` (installed files) and `dsh.profile.bundles` (what the loader mounts). A raw pnpm install writes only `dependencies`. `dsh plugin add` treats an already-present dependency as "already added" and therefore skips appending the package to `dsh.profile.bundles`, leaving the plugin installed but unloaded.

## Fix

Two independent records drive plugin loading:

1. `package.json` → `dependencies` (pnpm owns the files on disk).
2. `package.json` → `dsh.profile.bundles` (the loader owns what actually mounts).

A raw `pnpm add` only writes (1). `dsh plugin add` appends to (2) only when it performs the install itself; if the dependency already exists it reports "Already up to date" and skips the bundle registration.

Fix (either):
- Append the package name to `dsh.profile.bundles` in `~/.dsh/profiles/<profile>/package.json`; HMR/reload picks it up.
- Or remove the package from `dependencies` first, then re-run `dsh plugin --profile web add <pkg>` so the CLI does the full registration.

Practical guard: after any manual pnpm step, check both fields rather than trusting the install output.

## Verification

- `dsh.profile.bundles` in `~/.dsh/profiles/<profile>/package.json` includes the package name.
- The runtime plugin list shows the plugin (not just its dependency entry).
- No FAILED entries after reload.
