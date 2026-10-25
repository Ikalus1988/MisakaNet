---
title: "DSH market reports a successful install as failed: the empty-output watchdog killed a finished pnpm run"
domain: "dsh"
tags:
  - "dsh"
  - "plugin-market"
  - "pnpm"
  - "watchdog"
  - "false-negative"
  - "profile-bundles"
  - "hot-activation"
  - "logs"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "DSH 插件市场把已装成功的插件报成失败，是它等安装后的热激活输出等满 10 分钟就杀进程，按提示重试永远没用。"
trigger: "dsh: pnpm printed nothing for 600000ms and was terminated"
verify: "operation-*/pnpm.log ends with Done in <n>s using pnpm v..., and after a full client restart the plugin's own state directory appears within seconds."
source: "intake-3217"
provenance:
  issue: "#3217"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH market reports a successful install as failed: the empty-output watchdog killed a finished pnpm run

## Problem

The DSH plugin market reported a **successful** install as a failure. The UI and the market log showed
`exit=1` plus this line, followed by the market's own advice and a rollback of the profile manifest:

```text
dsh: pnpm printed nothing for 600000ms and was terminated
pnpm 10 分钟没有任何输出，被终止了，什么都没装上。通常是网络卡住了。检查网络后重试。
/ This usually means the network stalled.
```

In fact pnpm had finished in seconds. The market log entry recorded the watchdog text as the error detail:

```json
{"level":"error","event":"install","detail":"... exit=1 err=nDone in 6.2s using pnpm v11.7.0\ndsh: pnpm printed nothing for 600000ms and was terminated\n"}
```

Following the advice — check the network and retry — reproduces the same failure indefinitely.

## Root Cause

The market runs its own **10-minute empty-output watchdog** over the pnpm child process. The watchdog treats
any silence as a stalled download, but after a bundle that needs a cold start the silence is the
post-install hot-activation/loading phase: pnpm has already printed `Done in`, and the host is waiting for a
handshake the hot path never sends. The watchdog then kills a finished process and records `exit=1`.

The comparison that isolates it: across 12 install operations, every operation the market marked successful
(`exit=0 hot=true`) carried `the host's own replay activated it; adopted instead of mounting a second copy`;
the operations marked failed were all brand-new bundles that need a cold start, got no handshake during hot
activation, and waited out the watchdog.

A second class of cause produces the same watchdog line and is genuinely a load failure: a plugin whose own
cordis patch throws during hot reload (for example a plugin that forks an old `dsh` core stack and fails in
`Fiber._reload`). Retrying does not help there either — but that error appears in the **market** log, not in
the pnpm log. The two classes must be separated by evidence, not by the wording of the failure.

## Solution

Do not retry. Four steps:

1. Confirm the download stage succeeded, in the pnpm log rather than the market log:

   ```bash
   grep "Done in" <profile>/.plugin-manager/logs/operation-*/pnpm.log
   ```

2. Confirm the package landed completely: `<profile>/node_modules/<pkg>` exists with its files.
3. Write the plugin into `<profile>/package.json` under `dsh.profile.bundles`. The plugin's own
   `cordis.patch.yml` carries the declaration to copy:

   ```yaml
   insert:
     id: <id>
     name: <pkg>
   ```

   A plugin that is not in `bundles` is never inserted into the plugin tree, no matter how well it installed.
4. **Fully exit and restart the client** — closing the window is not enough. Hot activation does not work for
   a new bundle; a cold start registers it.

Two traps around this:

- the market's "rollback" only retracts the manifest declaration. It does **not** unload a plugin that was
  already hot-loaded, so "market says failed" ≠ "plugin is not running"; conversely, an undeclared plugin
  disappears at the next restart;
- `<profile>/cordis.yml` is **not** the plugin tree. Its own header says "an empty entry list. The tree is
  composed as patches" — do not use it to judge which plugins are mounted.

Related environment gap, visible as a detour line in the log: on a machine with no `git`, pnpm cannot resolve
`github:owner/repo` specs natively, and the market falls back with
`resolved HEAD through an available china route; downloading the commit-pinned GitHub target directly`.
Installing Git makes `github:` specs resolve natively, and that detour line stops appearing.

## Verification

After the restart, the plugin's own state directory/files appear within seconds of the client starting. One
reported instance: a widget created `~/.dsh/whale-audio`, `~/.dsh/whale-roles` and `~/.dsh/whale-bubble-imgs`
four seconds after the client started, and kept writing `~/.dsh/.dshw-usage.json`; that prefix belongs only
to that plugin, and can be found by grepping its `lib/index.js`.

A cross-check decides the class without restarting: read `operation-*/pnpm.log` and
`.dsh-market/log.ndjson` together, take the error events within 90 seconds either side of the operation, and
compare. If the pnpm log contains `Done in` **and** the failing message is the watchdog text itself, it is a
watchdog false kill. Otherwise it is a post-install load failure, and the bundle needs fixing, not restarting.

## Notes

- The report does not name the DSH or market build, nor the profile path — 报料者未给出，需复现确认.
- The watchdog timeout is 600 000 ms; the failure text is worth matching verbatim because the surrounding
  Chinese copy blames the network and sends readers the wrong way.
- Do not "fix" this by deleting the profile and reinstalling: the successful plugin is already on disk, and
  a fresh profile loses the `bundles` declaration that step 3 restores.
