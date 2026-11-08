---
title: "DSH custom agent presets show '加载失败' after upgrade: a stale composition subpath reports 'never started' and is…"
domain: "dsh"
tags:
  - "dsh"
  - "agent-preset"
  - "composition"
  - "broken"
  - "never-started"
  - "auditrows"
  - "exports"
  - "subpath"
  - "cordis.patch.yml"
  - "profile-patch"
status: "published"
evidence_level: "E1"
public_analogue: "an IDE's extension list and its plugin diagnostics log"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4581"
summary_plain: "After a DSH profile plugin upgrade (dsh-ops 0.4.4 -> 0.5.0) on host @deepseek-ai/dsh 0.2.2-rc.1, four custom agent…"
trigger: "DSH custom agent presets show '加载失败' after upgrade: a stale composition subpath reports 'never started' and is…. After a DSH profile plugin upgrade (dsh-ops…"
verify: "Script self-check: PARSE_ERRORS=0; DryRun on the real file is zero-write (SHA unchanged, 0 new backups); a COPY run of -Apply -> -Rollback restores the exact original SHA with EXIT=0. Applied state…"
provenance:
  issue: "#4581"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

After a DSH profile plugin upgrade (dsh-ops 0.4.4 -> 0.5.0) on host @deepseek-ai/dsh 0.2.2-rc.1, four custom agent presets disappeared from the GUI preset picker and showed a red "加载失败" (Failed to load) badge in the management section, while the four built-in presets (standard/ptc/minimal/cordis) still worked. Hovering the red badge / reading the card reason showed the raw broken text: `tool-subagent-list-agents (@deepseek-ai/dsh-tool-subagent-control/list-agents): never started`. `plugin_manager list_plugins` showed all four `include:preset-*` cordis entries `en=True phase=active` — registration had succeeded, but the presets were not offered.

## Root Cause

Two independent layers, easy to conflate. (1) Registration://[REDACTED:url_credential]@host has `presetOptions(presets) { return presets.filter(p => p.broken === void 0).map(...) }` — the picker lists healthy presets only, while the management section renders the full roster with a brokenBadge "加载失败" and shows row.broken verbatim in the tooltip/card reason. auditRows() (registry lib/types/mount.js) classifies rows://[REDACTED:url_credential]@host On the 0.2.2-rc.1 host that package's package.json exports are [".", "./src/*", "./package.json", "./locale/*.json"] — there is NO "./list-agents" subpath export; its lib/index.js registerListAgents() already folds the list_agents tool into the MAIN package row. A full-host scan for the exact stale subpath string returned 0 hits, and the official dsh-web-app/presets/standard.patch.yml delegation group has only tool-subagent-control + tool-subagent with no list-agents row. So the generated custom preset bundle carried a stale subpath reference -> fiber undefined -> `never started` -> broken -> filtered. All four custom presets broke together because the stale row lived in their SHARED delegation group; the first preset had no compaction group yet still broke, pinning the fault to the shared rows.

## Fix

1. Get the exact broken text without touching credentials://[REDACTED:url_credential]@host `exports`, grep the exact subpath across the host, and diff against the official presets/*.patch.yml. Also strictly re-check EVERY `name://[REDACTED:url_credential]@host — list_agents is still registered by the main row, matching the official preset. Deliver as a reversible PowerShell 7 script: default DryRun zero-write, -Apply/-Rollback/-Verify, SHA lock of the current file, BOM/CRLF guards, shape asserts (main row = 4 presets, `- insert:` = 1, no CR), no-clobber byte-level backups before Apply/Rollback, read/write via [IO.File]::ReadAllBytes/WriteAllBytes with UTF8-no-BOM to preserve LF. 5. Run the script in a SEPARATE terminal, never inside the live DSH session — editing the active profile patch hot-reloads and swaps the tool surface. The patch is a generated artifact (install.mjs of the preset bundle); a reinstall can overwrite it, so re-run the script then. 6. RESTART DSH after -Apply: composition is audited once at boot, a hot edit does not re-audit. Editing top-level `- insert:` rows (e.g. a local-compact-cmd line) does NOT help — the audit only walks config.plugins, never the top-level insert group.

## Verification

Script self-check: PARSE_ERRORS=0; DryRun on the real file is zero-write (SHA unchanged, 0 new backups); a COPY run of -Apply -> -Rollback restores the exact original SHA with EXIT=0. Applied state: the stale specifier appears 0 times active and 4 times commented; the main package row is untouched; a `*.bak-*` backup exists. End-to-end: after -Apply + DSH restart (new instance / changed GUI port), the four "加载失败" badges disappear and all four custom presets reappear in the picker — confirmed by the user on 2026-11-08.
