---
domain: "dsh"
title: "Registering a DSH plugin in profile bundles before pnpm ran its blocked build crashes startup"
tags:
  - "dsh"
  - "pnpm"
  - "plugin"
  - "ignored-builds"
  - "allowbuilds"
  - "profile-bundles"
  - "startup-crash"
  - "rollback"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3527"
summary_plain: "DSH 桌面版把插件先写进加载列表、却没让 pnpm 跑完被拦下的构建脚本，重启后程序起不来并回滚到只剩基础插件。"
trigger: "ERR_PNPM_IGNORED_BUILDS Ignored build scripts: agent-browser@0.34.0 / dsh plugin add then DSH crashes on startup"
verify: "dsh plugin --profile desktop install prints no ERR_PNPM_IGNORED_BUILDS line, node_modules contains the plugin and its deps, and DSH restarts to the session list."
provenance:
  issue: "#3527"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Registering a DSH plugin in profile bundles before pnpm ran its blocked build crashes startup

## Problem

On the DeepSeek Harness (DSH) desktop build, a third-party plugin was installed from a GitHub source:

```bash
dsh plugin --profile desktop add github:<owner>/<repo>
```

pnpm refused to run the plugin dependency's build script and printed:

```
[ERR_PNPM_IGNORED_BUILDS] Ignored build scripts: agent-browser@0.34.0
dsh: git-hosted plugins build on install via their prepare script, which pnpm blocks until allowed — add the exact key pnpm printed above under allowBuilds in .../pnpm-workspace.yaml, then re-run
```

Despite the error, the plugin had already been written into the profile's `package.json`
dependencies. So the reporter added the plugin name to `dsh.profile.bundles`, added the
`allowBuilds` entry to `pnpm-workspace.yaml`, and **restarted DSH without re-running the install**.

The restart did not come back up: DSH errored continuously and never opened. It then rolled the
profile back on its own:

- `dsh.profile.bundles` was emptied back to the base entries only (`@deepseek-ai/dsh-base`,
  `dsh-web-app`);
- the plugin's dependency directories disappeared from `node_modules` along with the uninstall;
- every other installed plugin (a whale widget, a plugin marketplace, a memory system) came back as
  **not loaded**.

So one blocked build script cost the whole profile, not just the one plugin.

## Root Cause

**`allowBuilds` authorizes a build; it does not run one.** The error was read as a warning that a
hand-edited allowlist could patch around, but pnpm only executes the blocked `prepare` script on the
*next* install. After the edit, nothing had produced the plugin's build output — and the bundle entry
was added anyway.

That is the ordering defect: **three steps that must happen in one order, done in another.**

| step | what it produces | done here |
|---|---|---|
| allow the build (`allowBuilds` in `pnpm-workspace.yaml`) | permission only | yes |
| re-run the install so pnpm actually builds | the plugin's build artifacts on disk | **no** |
| register the plugin in `dsh.profile.bundles` | an entry the loader will resolve at startup | yes — too early |

The loader resolves every entry in `dsh.profile.bundles` during startup. An entry whose package has
no build artifacts fails to load, and the failure happens before the app window and session list
exist — which is why the symptom is "DSH will not open at all" rather than "this plugin is broken".

**Why the blast radius is the whole profile:** rollback treats `bundles` as the authority. Resetting it
to the base list is how the app gets back to a bootable state, and a subsequent install prunes the
dependency tree no longer referenced by `dependencies`. Unrelated plugins lose their load state as a
side effect of the reset — they were never part of the fault, only part of the recovery.

**Not established by the report:** the startup exception text was not included, so the exact throw
site is unconfirmed here. The reporter also did not confirm whether DSH's rollback ran before or
after the first failed window creation.

## Solution

### Step 1: allow the build, then actually run it

Add the key exactly as pnpm printed it (name and version), in the profile's workspace file:

```yaml
# <profile>/pnpm-workspace.yaml
allowBuilds:
  agent-browser@0.34.0: true
```

Then re-run the install — this is the step that was skipped:

```bash
dsh plugin --profile desktop install
```

Repeat until pnpm stops printing `ERR_PNPM_IGNORED_BUILDS`.

### Step 2: confirm the dependency tree is on disk

```bash
ls node_modules/agent-browser          # the plugin package itself
ls node_modules/agent-browser/node_modules 2>/dev/null || true
```

If the plugin directory or its dependencies are missing, the build did not complete — do not continue.

### Step 3: only now register the plugin

Add the plugin name to `dsh.profile.bundles` in the profile's `package.json`. This is the last step,
by construction: the loader must never be pointed at a package that has not been built.

### Step 4: restart DSH

```bash
dsh --profile desktop
```

### Recovering from the crash-rollback state

The profile is in a half-reverted state, so rebuild it from the last known-good list rather than
editing forward:

1. restore `dsh.profile.bundles` from a backup (base entries plus the plugins that were working);
2. remove the new plugin from `dependencies`;
3. restore `pnpm-lock.yaml`;
4. reinstall and restart:

```bash
dsh plugin --profile desktop install --no-frozen-lockfile
```

`--no-frozen-lockfile` is required because the lockfile and manifest no longer agree after the manual
edits; without it pnpm aborts instead of reconciling them.

### For `file:` plugins

Do not install a plugin from a temporary directory. The profile is rebuilt and pruned on recovery,
and the OS clears `TEMP` on its own schedule, which turns a `file:` dependency into a dangling path.
Keep it in a fixed location, e.g. `%USERPROFILE%\tools\<plugin>` on Windows.

## Verification

The reporter's four checks, in order of increasing confidence:

1. `dsh plugin --profile desktop install` no longer prints `ERR_PNPM_IGNORED_BUILDS`.
2. `node_modules` contains the target plugin **and** its dependency directories.
3. Restarting DSH opens the program normally, with the session list intact.
4. `dsh plugin` lists the plugin as loaded.

Check 1 alone is not enough — it only proves the permission was accepted. Check 2 is the one that
distinguishes "the build ran" from "the build was allowed", and check 3 is the one that fails when a
bundle entry was registered ahead of its build.

## Notes

- Evidence level E1: one operator's account of the install order and the resulting rollback; not
  reproduced in this repository, and the startup stack trace was not provided.
- The `allowBuilds` key must be the exact string pnpm prints (`name@version`). A bare package name, or
  a version that no longer matches the lockfile, leaves the build blocked with no new error.
- Rollback is destructive to **unrelated** plugins. Keep a copy of the profile's `package.json` (at
  least `dsh.profile.bundles`) before adding anything to it, so recovery restores a list instead of
  reconstructing one.
- If a plugin is a git-hosted source, its `prepare` script is the build; there is no separate
  "already built" path to fall back on when pnpm skips it.
- Related symptom, different cause: a duplicate Loader entry id also crashes the plugin tree at
  startup (`dsh-plugin-l5-web-smoke-cordis-duplicate-entry`). Check whether the failing entry is a
  duplicate id before blaming a missing build.
