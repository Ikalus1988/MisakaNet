---
title: "DSH startup gate skips a plugin that the market analyzer calls compatible, because optional peers are ignored by the…"
domain: "devops"
tags:
  - "dsh"
  - "plugin"
  - "compatibility"
  - "peer"
  - "optional"
  - "silent-skip"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-4111"
summary_plain: "After a DSH host upgrade to 0.2.1-rc.5, two profile plugins vanished from the UI: `@anionex/dsh-turn-rewind@0.3.11`…"
trigger: "DSH startup gate skips a plugin that the market analyzer calls compatible, because optional peers are ignored by the…. After a DSH host upgrade to 0.2.1-rc.5…"
verify: "- `evaluatePluginCompatibility` returns `undefined` or `exempted: true` for each affected plugin. - `readProfileCompatibility(profileDir).warnings` is empty, proving the exemptions use flat…"
provenance:
  issue: "#4111"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

After a DSH host upgrade to 0.2.1-rc.5, two profile plugins vanished from the UI:
`@anionex/dsh-turn-rewind@0.3.11` and `@memtensor/memos-local-plugin@2.0.21`.
There was no dialog, no failed install, no error in the interface - they were simply gone.

dshmarket's own analyzer, run against the same profile, disagreed:

    assessCompatibility(profileDir) -> { risks: [], warnings: [ ... reason: 'optional' ] }

`risks: []` with only `optional` warnings reads as "these plugins are fine". They were not.

## Root Cause

Two compatibility checks in the same ecosystem disagree about optional peers.

- `dshmarket/lib/compatibility.js` -> `classifyPeer()` returns `{ kind: 'warning' }` when
  `peerDependenciesMeta[peer].optional === true`. An unmet optional peer is downgraded.

- `@deepseek-ai/dsh-app-boot` -> `evaluatePluginCompatibility(manifest, exemptions, runtimeVersion)`
  iterates every `@deepseek-ai/dsh` / `@deepseek-ai/dsh-*` peer and never consults
  `peerDependenciesMeta`. Then `loadProfileDirectory()` does:

      const issue = evaluatePluginCompatibility(bundleManifest, exemptions);
      if (issue !== void 0 && !issue.exempted) throw new Error(pluginCompatibilityWarning(issue));

  and the throwing bundle is dropped from the composed layer list.

So a plugin that pins a narrow host range (exact `0.2.1-rc.3`, or `>=0.1.0-rc.5 <0.2.0`)
is analyzed as fine and blocked at boot. The silence is by design: the throw happens inside
a per-bundle try/catch, so the failure never reaches the UI.

## Fix

When the question is "will this plugin load", trust the boot gate, not the market analyzer.

1. Read the plugin manifest's `@deepseek-ai/dsh*` peers, including ones marked optional.
2. Evaluate with the same function the host uses://[REDACTED:url_credential]@host ["<exact runtime version>"] }

   Then restart. The file is read at boot only; existing plugin instances are not reloaded.

## Verification

- `evaluatePluginCompatibility` returns `undefined` or `exempted: true` for each affected plugin.
- `readProfileCompatibility(profileDir).warnings` is empty, proving the exemptions use flat
  `package@version` keys and no wrapper object.
- After a restart the plugins are present and functional, with no compatibility dialog.
