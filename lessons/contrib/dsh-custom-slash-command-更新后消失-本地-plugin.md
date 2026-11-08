---
title: "DSH custom slash command disappears after update: local plugin was pruned because it was missing from profile…"
domain: "dsh"
tags:
  - "book-dsh-plugins"
  - "dsh"
  - "pnpm"
  - "node_modules"
  - "err_module_not_found"
  - "did-not-activate"
  - "cordis"
  - "profile-dependencies"
  - "custom-command"
  - "plugin-pruned"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4582"
summary_plain: "After a DSH (DeepSeek Harness) desktop update, a hand-written custom slash command stops working (e.g."
trigger: "DSH custom slash command disappears after update: local plugin was pruned because it was missing from profile…. After a DSH (DeepSeek Harness) desktop update…"
verify: "Static: `import('<index.js>')` returns name/inject/apply; package.json has the dependency, bundles count unchanged; YAML still parses with intact isolate groups. Runtime: after restart, the plugin…"
provenance:
  issue: "#4582"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

After a DSH (DeepSeek Harness) desktop update, a hand-written custom slash command stops working (e.g. /compact no longer appears in completion / does nothing). The GUI still opens and the host is healthy. The host crash log shows a non-fatal warning:

```
dsh: warning: 1 entry did not activate
local-compact-cmd (dsh-agent-compact-cmd): failed to import: Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'dsh-agent-compact-cmd' imported from <profile>/
```

A full search finds NO directory <profile>/node_modules/dsh-agent-compact-cmd anywhere (not even in backup/recycle folders), yet <profile><PATH> still has an enabled `- id: local-compact-cmd / name: 'dsh-agent-compact-cmd'` entry at the top-level `- insert:`. Commenting out those two lines makes the warning go away but the command still does not come back.

## Root Cause

Two distinct tables govern a DSH plugin, and only one was populated. `dsh.profile.bundles` (in <profile><PATH>) plus the cordis.patch.yml `- id/name` entry decide WHETHER the plugin is loaded. The `dependencies` object of <profile><PATH> decides WHETHER pnpm keeps the directory://[REDACTED:url_credential]@host (registered in dsh-base/cordis.patch.yml) does not step in to fill a custom realm in practice.

## Fix

1. Recreate <profile>/node_modules/<name>/ with package.json (`type: module`, `exports: {".":"./index.js","./package.json":"./package.json"}`) and index.js.
2. CRITICAL anti-recurrence step: add `"<name>": "file:node_modules/<name>"` to the `dependencies` object of <profile><PATH>. Adding it to `dsh.profile.bundles` is NOT required to keep the directory — dependencies is what pnpm's closure uses. Keep the existing bundle/entry for loading.
3. Restore the entry's `- id:` / `name:` lines in cordis.patch.yml (uncomment, 4-space / 6-space YAML indent), placing it at the top-level `- insert:`, NOT inside an isolate group.
4. Plugin contract that survived activation: declare only the minimum `inject` (e.g. `['commands']`) and lazily resolve other services with `ctx.get('svc') ?? ctx.svc` inside the handler; wrap `ctx.commands.register(...)` in try/catch that only writes a diag log and NEVER rethrows (a rethrow fails the whole entry); omitting `input` and `definitionId` is legal on 0.2.2-rc.1 register.
5. Restart the host (the agent cannot restart it; have the user do it).
Keep .bak backups of package.json and cordis.patch.yml so a rollback is one copy away.

## Verification

Static: `import('<index.js>')` returns name/inject/apply; package.json has the dependency, bundles count unchanged; YAML still parses with intact isolate groups. Runtime: after restart, the plugin diag log (<tmp><PATH> or DSH_PLUGIN_DIAG) shows three lines in order — `apply() called`, `/<cmd> registered`, and `→ OK n=... tok=... summarySeq=...`. Only the first two means registration was rejected (error text is in the log); none means the preset never mounted. Then invoke the command in the GUI and expect the summary line “Compacted N history items (~M tokens)” on screen. Verified end-to-end with n=403, tok=331401.
