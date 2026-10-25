---
title: "DSH startup: '1 required plugin did not activate' because a hoisted old core library shadowed the tools service"
domain: "dsh"
tags:
  - "dsh"
  - "plugin"
  - "pnpm"
  - "hoisted-node-modules"
  - "peerdependencies"
  - "tools-service"
  - "startup-crash"
  - "profile-overrides"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "DSH 装完插件起不来，是某个插件把宿主核心库写进 dependencies，旧版被提升进 profile 遮蔽了宿主的 tools 服务。"
trigger: "DesktopHostFatalError: dsh: startup failed: 1 required plugin did not activate; agent-loop (required) missing tools"
verify: "The app starts with no '1 required plugin did not activate', the plugin panel lists every plugin, and <profile>/node_modules/@deepseek-ai does not exist."
source: "intake-3228"
provenance:
  issue: "#3228"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH startup: '1 required plugin did not activate' because a hoisted old core library shadowed the tools service

## Problem

Installing 11 plugins in one batch on the DeepSeek Harness (DSH) desktop client left the app crashing at
startup. The fatal line:

```text
DesktopHostFatalError: dsh: startup failed: 1 required plugin did not activate
```

and, right above it, the service wait list:

```text
Plugins waiting for services (7): agent-loop (required) -> missing tools
```

The GUI's "restart" / "disable third-party plugins" buttons had no effect, and disabling plugins one by one
did not localise the fault. The same batch also rewrote the profile's `cordis.patch.yml` — about 49 KB of
model-channel configuration — into a 217-byte empty template.

## Root Cause

One of the installed plugins declared the host core library `@deepseek-ai/dsh-tools` under `dependencies`
(exact version `0.1.2-rc.1`) instead of `peerDependencies`. Under pnpm with the hoisted `nodeLinker`, that
old version was hoisted to the profile's `node_modules` root, where it shadowed the host's own
`0.2.0-rc.2` copy inside `app.asar`. The plugin that provides the `tools` service then failed to load, so the
*required* `agent-loop` plugin could never activate — and the host refuses to start without it.

Two details make this hard to see from the UI:

- the trigger is **presence in the dependency tree**, not membership in `dsh.profile.bundles` — the package
  activates the failure even when it was never written into the bundle list;
- the fatal error names the *victim* (`agent-loop`, missing `tools`), not the plugin that carried the stale
  library, so plugin-by-plugin disabling chases the wrong list.

The crash trace also lives in `crash-*-host.log`; the "Plugins waiting for services" block there is what
identified `tools` as the missing service, before comparing profile `node_modules` against the host build
revealed the hoisted `@deepseek-ai/dsh-tools@0.1.2-rc.1`.

## Solution

1. Get the stale core library out of the resolution path immediately:

   ```bash
   mv <profile>/node_modules/@deepseek-ai <profile>/node_modules/@deepseek-ai.bak
   ```

   Move it, do not delete it — plugin code really does `require` the package. With the hoisted copy gone, the
   host falls back to its own copy in `app.asar` and startup recovers at once.

2. Pin the core libraries to the host build in the **profile's** `pnpm-workspace.yaml`:

   ```yaml
   overrides:
     "@deepseek-ai/dsh-tools": "<host version>"
     "@deepseek-ai/dsh-brand": "<host version>"
     "@deepseek-ai/dsh-util-values": "<host version>"
   ```

   pnpm 11 and later no longer read the `pnpm` field in `package.json`, so an override written there is
   ignored. The report gives the host's `dsh-tools` version (`0.2.0-rc.2`); the other two packages' host
   versions are not in the report — 报料者未给出，需复现确认.

3. Refuse the bad plugin before installing it. Static check: any plugin that lists a core library under
   `dependencies` is rejected — this is the condition that creates the shadow, and it is readable from the
   manifest without running anything.

4. Install one plugin per restart, confirming the UI comes up after each. Batching 11 installs turns one bad
   manifest into an application that will not boot, and leaves nothing to bisect.

5. Add a gate script that health-checks the profile before and after an install and returns a SAFE / blocking
   verdict, and forbids restarting on any verdict other than SAFE.

6. Back up the profile's patch configuration (`cordis.patch.yml`, the model-channel table) as part of the
   install workflow. The same batch that broke startup also replaced 49 KB of it with a 217-byte template,
   and that loss is silent — it does not crash anything.

## Verification

- Startup no longer prints `1 required plugin did not activate`;
- the plugin panel lists all plugins;
- the gate script prints `✅ 裁决: SAFE`;
- `cordis.patch.yml` is back to tens of KB, not a 217-byte template;
- from a shell, `<profile>/node_modules/@deepseek-ai` does not exist.

## Notes

- The report does not name which of the 11 plugins carried `@deepseek-ai/dsh-tools` in `dependencies`, nor
  the profile path — 报料者未给出，需复现确认.
- The GUI buttons are not a diagnostic here: with the host refusing to start, restart and disable-third-party
  actions never reach the failing load.
- The `pnpm-workspace.yaml` override is a containment measure for plugins that still declare the library
  wrongly; it does not repair their manifests. Rejecting the dependency (step 3) is what stops the pattern
  recurring.
