---
title: "Editing a plugin source file has no effect because pnpm file: dependencies are copies in node_modules"
domain: "nodejs"
tags:
  - "pnpm"
  - "nodejs"
  - "plugin"
  - "node_modules"
  - "dsh"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3786"
summary_plain: "A local plugin is installed into a profile as a file: dependency."
trigger: "Editing a plugin source file has no effect because pnpm file: dependencies are copies in node_modules. A local plugin is installed into a profile as a file…"
verify: "The new code string is present in node_modules/<package>/ and the behaviour changes after restart."
provenance:
  issue: "#3786"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A local plugin is installed into a profile as a file: dependency. Editing the plugin source in the workspace and restarting the host changes nothing.

## Root Cause

pnpm materialises file: dependencies into node_modules as copies (not symlinks in this setup), and the host loads the plugin from node_modules. The edited workspace file is never read.

## Fix

After editing, copy the changed files into the profile node_modules/<package>/ directory as well, then restart the host. Verify by grepping for a unique string from the new code inside node_modules before restarting.

## Verification

The new code string is present in node_modules/<package>/ and the behaviour changes after restart.
