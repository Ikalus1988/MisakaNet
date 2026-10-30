---
title: "DSH: a marketplace (GUI) install silently drops bundles that were added outside the market from dsh.profile.bundles"
domain: "dsh"
tags:
  - "dsh"
  - "plugin-manager"
  - "marketplace"
  - "profile-manifest"
  - "bundles"
  - "silent-failure"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3141"
summary_plain: "Plugins that were enabled through the DSH plugin-manager tool (or by editing the profile manifest) stop loading after…"
trigger: "DSH: a marketplace (GUI) install silently drops bundles that were added outside the market from dsh.profile.bundles. Plugins that were enabled through the DSH…"
verify: "1) Compare dsh.profile.bundles against the previously known list (the file's mtime usually points at the marketplace operation). 2) Query Cordis Inspect: host / Config / listConfigs and confirm…"
public_analogue: "npm ls"
provenance:
  issue: "#3141"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Plugins that were enabled through the DSH plugin-manager tool (or by editing the profile manifest) stop loading after any install/update performed from the marketplace GUI. Symptom: the plugin directory is still installed, its entry is still present in dsh.profile.dependencies, no error is printed, yet the plugin never mounts - Cordis Inspect query 'host / Config / listConfigs' shows the expected include:<id> entry missing, and an explicit listConfigs probe for that entry answers 'unknown entry id'. In the observed case three bundles (a cloud memory adapter, a local memory daemon adapter and a game plugin) disappeared from dsh.profile.bundles while a fourth (a voice-input bundle) was installed from the market at the same minute; the profile package.json mtime matched the market operation, not the restart.

## Root Cause

DSH's marketplace keeps its own record of what it installed and rewrites the profile manifest from that record when it performs the next operation. Entries added outside the market (plugin-manager install_bundle, manual edits, or bundles restored by hand) are not in the market's record, so the rewrite keeps the dependency but drops the bundle entry. Because dsh.profile.bundles - not dependencies - drives what is composed into the running tree, the plugin silently stops loading. Nothing fails loudly: the package is on disk, the lockfile is intact, and DSH boots normally.

## Fix

Treat dsh.profile.bundles as the authoritative list and re-verify it after every marketplace operation. Re-enable the dropped plugins with the plugin-manager install_bundle action (it rewrites bundles and reports 'restart-required'), or perform the installation through the market itself so the entry lands in the market's record. Keep a copy of the multi-line bundle list so restoring it is mechanical. When several plugins are missing at once, expect one marketplace operation as the common cause instead of debugging each plugin.

## Verification

1) Compare dsh.profile.bundles against the previously known list (the file's mtime usually points at the marketplace operation). 2) Query Cordis Inspect: host / Config / listConfigs and confirm every expected include:<id> resolves; 'unknown entry id' proves it is not composed. 3) List the plugin directory under the profile node_modules to confirm the package itself is still installed (that is what makes the failure silent). 4) After install_bundle, re-read dsh.profile.bundles, restart DSH, and re-run the Inspect query.
