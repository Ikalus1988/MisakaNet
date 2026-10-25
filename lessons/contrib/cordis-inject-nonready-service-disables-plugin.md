---
title: "A cordis plugin listing a service that never appears in inject() silently never runs"
domain: "dsh"
tags:
  - "cordis"
  - "dsh"
  - "plugin"
  - "inject"
  - "silent-failure"
  - "dependency-injection"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "cordis 插件 inject 里写进不存在的服务，apply 就永远不执行：界面全空，控制台也不报错。"
trigger: "cordis inject service never ready apply never runs plugin silently not loaded no console error"
verify: '改回 inject: ["betterSidebar"] 并刷新后两个入口同时恢复，面板标签与官方 dsh-context 插件的标签并排出现'
source: "intake-3263"
provenance:
  issue: "#3263"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A cordis plugin listing a service that never appears in inject() silently never runs

## Problem

A local DSH Web client plugin (`dsh-profile-dashboard`) loaded fine and showed its sidebar tab. Then
one word was added to its service list:

```js
inject: ["betterSidebar"]              // before: sidebar tab visible
inject: ["slots", "betterSidebar"]     // after:  everything disappears
```

After the change **both** of the plugin's entry points vanished at once — the official slot
(`conversation.view` view tab) and the `better-sidebar` tab. There was no error, no warning, and
nothing in the console outside DevTools: the plugin neither reported a failure nor appeared to load.

Three rounds went into the wrong hypotheses, all of which were excluded:

- the slot name was wrong (`conversation.view`),
- the registration arguments were wrong (`order`, `label`),
- the slot did not exist in this client version,
- and, at one point, that the host process needed a restart.

## Root Cause

`inject` in cordis is not a hint list — it is a **precondition**: `apply()` runs only after *every*
service named there is ready. A name that can never be resolved is not an error condition; it just
means the precondition is never satisfied, so `apply()` is never called.

Nothing is logged because nothing failed. The plugin is "loaded" and simply never starts, which from
the outside is indistinguishable from a wrong slot name or a broken registration — hence the three
rounds spent on registration arguments.

The same silent whole-plugin death has a second reported cause: a client bundle that `require`s a
module which is not declared in `package.json`'s `dsh.client.inject` throws during module load. On
the reporter's machine that missing module was `react-dom`, absent from the profile's `node_modules`
entirely — so the throw happens before any of the plugin's own code runs.

## Solution

### 1. List only services that are guaranteed to exist

Keep `inject` to services the host always provides. `slots` was not one of them on this client
version, and adding it disabled the plugin that had been working.

### 2. Probe optional services at runtime and retry

If you need a service that may arrive late (or may not exist), do not put it in `inject`. Ask the
context for it and retry until it is there (reporter's code, verbatim):

```js
function trySlots(n) {
  const slots = ctx.get ? ctx.get("slots") : null;
  if (slots && slots.inject) {
    ctx.effect(() => slots.inject("conversation.view", () => slots.register({
      name: "conversation.view", id: "x", order: 40, label: () => "标题"
    }, Comp)), "tag");
    return;
  }
  if (n < 20) setTimeout(() => trySlots(n + 1), 250);
}
trySlots(0);
```

This makes "service absent" a bounded, visible retry instead of an invisible precondition that
blocks the whole plugin.

### 3. Log on the first line of `apply()`

```js
apply(ctx, config) {
  console.log("[profile-dashboard] apply");   // did it even start?
  ...
}
```

One line splits the two cases that look identical from the UI: **plugin not loaded** (no log) versus
**loaded but registration rejected** (log present). Without it, every hypothesis has the same
symptom and you debug by guesswork.

## Verification

- Reverting to `inject: ["betterSidebar"]` and refreshing restored **both** entry points at once.
- The panel's top tab ("个人档案") appeared above the workspace, side by side with the official
  `dsh-context` plugin's tab — i.e. both the slot view and the sidebar tab were registered.
- Diagnostic criterion, worth memorizing: *widgets disappear with no console output at all* ⇒ check
  `inject` before checking slot names and registration arguments.

## Notes

- The report's `dsh.client.inject` mechanism for missing modules is reporter-reported; confirm the
  key name against your plugin's `package.json` before relying on it. The check itself is cheap:
  every top-level `require` in the bundle should resolve inside the profile's `node_modules`.
- Timeout/retry parameters in the snippet (20 attempts × 250 ms = 5 s) are the reporter's; adjust to
  your host's startup time. Silently giving up after the last attempt reproduces the original
  invisible failure, so log on exhaustion.
- Related shape, same plugin tree, different cause: a duplicate Loader entry id also crashes the
  plugin tree before your code runs —
  `lessons/contrib/dsh-plugin-l5-web-smoke-cordis-duplicate-entry.md`.
